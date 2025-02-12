import pandas as pd
import anthropic
import json
from pathlib import Path
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import io 

# Load environment variables from .env file
load_dotenv()

def validate_api_key(api_key: str) -> bool:
    """Validate Anthropic API key format"""
    print(f"Debug - Full API key: {api_key}")  # Temporary debug line
    print(f"Debug - Key length: {len(api_key)}")
    print(f"Debug - Key type: {type(api_key)}")
    
    if not api_key or isinstance(api_key, str) is False:
        print("API key is empty or not a string")
        return False
        
    # Remove any whitespace and newlines
    api_key = api_key.strip().replace('\n', '').replace('\r', '')
    
    if len(api_key) < 40:
        print(f"API key length ({len(api_key)}) is too short")
        return False
    
    print("API key validation passed")
    return True

class UtilizationOptimizer:
    def __init__(self, api_key: str):
        if not validate_api_key(api_key):
            raise ValueError(
                "Invalid Anthropic API key format. "
                "Key should start with 'sk-ant-' and be at least 40 characters long."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.base_path = Path(__file__).parent
        self.input_path = self.base_path / "input"
        self.output_path = self.base_path / "output"
        self.history_file = self.base_path / "utilization_history.json"
        self.target_utilization = 0.70
        
        self.load_history()
        self.constraints = {
            'max_teacher_sections': 6,
            'target_utilization': 0.70,
            'min_utilization': 0.30,  # Lower this to catch more problems
            'max_sped_per_section': 3,
            'min_section_size': 10,  # Add minimum section size
            'max_section_size': 40   # Add maximum section size
        }

    def load_history(self):
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = []

    def save_history(self):
        """Save optimization history to file"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def validate_schedule_constraints(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """Validate all schedule constraints and relationships"""
        violations = {
            'teacher_overload': [],
            'teacher_conflicts': [],
            'low_utilization': [],
            'sped_distribution': [],
            'unmet_preferences': []
        }
        
        # Skip validation if required data is missing
        teacher_assignments = data.get('current_teacher_assignments')
        if teacher_assignments is None:
            print("Note: Skipping teacher load validation - no assignments data available")
            return violations
            
        # Rest of validation logic only runs if we have assignment data
        if not teacher_assignments.empty:
            # Check teacher loads
            teacher_loads = {}
            for _, assignment in teacher_assignments.iterrows():
                teacher_id = assignment['Teacher ID']
                teacher_loads[teacher_id] = teacher_loads.get(teacher_id, 0) + 1
                if teacher_loads[teacher_id] > self.constraints['max_teacher_sections']:
                    violations['teacher_overload'].append(teacher_id)

            # Check schedule conflicts
            for _, unavail in data['teacher_unavailability'].iterrows():
                teacher_id = unavail['Teacher ID']
                unavail_periods = unavail['Unavailable Periods'].split(',')
                assignments = teacher_assignments[
                    teacher_assignments['Teacher ID'] == teacher_id
                ]
                for _, assignment in assignments.iterrows():
                    if assignment['Period'] in unavail_periods:
                        violations['teacher_conflicts'].append(
                            (teacher_id, assignment['Section ID'], assignment['Period'])
                        )

        # Calculate section utilization using student assignments if available
        student_assignments = data.get('current_student_assignments')
        if student_assignments is not None and not student_assignments.empty:
            for _, section in data['sections'].iterrows():
                section_id = section['Section ID']
                enrolled = len(student_assignments[
                    student_assignments['Section ID'] == section_id
                ])
                utilization = enrolled / section['# of Seats Available']
                if utilization < self.constraints['min_utilization']:
                    violations['low_utilization'].append((section_id, utilization))

        # Check SPED distribution if we have both student info and assignments
        if student_assignments is not None and not student_assignments.empty:
            sped_students = data['student_info'][
                data['student_info']['SPED'] == 'Yes'
            ]['Student ID'].tolist()
            
            for _, section in data['sections'].iterrows():
                section_id = section['Section ID']
                section_assignments = student_assignments[
                    student_assignments['Section ID'] == section_id
                ]
                sped_count = len(set(section_assignments['Student ID']) & set(sped_students))
                if sped_count > self.constraints['max_sped_per_section']:
                    violations['sped_distribution'].append((section_id, sped_count))

        return violations

    def initialize_assignments(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Initialize student assignments based on preferences"""
        assignments = []
        
        # Create initial assignments based on preferences
        for _, student in data['student_preferences'].iterrows():
            student_id = student['Student ID']
            for course in student['Preferred Sections'].split(';'):
                # Find all sections for this course
                course_sections = data['sections'][
                    data['sections']['Course ID'] == course
                ]
                if not course_sections.empty:
                    # Assign to least utilized section
                    chosen_section = course_sections.iloc[0]['Section ID']
                    assignments.append({
                        'Student ID': student_id,
                        'Section ID': chosen_section
                    })
        
        return pd.DataFrame(assignments)

    def analyze_utilization(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """Enhanced analysis considering all relationships"""
        sections = data['sections']
        student_preferences = data['student_preferences']
        student_info = data['student_info']
        teacher_info = data['teacher_info']
        
        # Ensure we have student assignments to analyze
        if 'current_student_assignments' not in data or data['current_student_assignments'].empty:
            print("No existing assignments found. Initializing based on preferences...")
            data['current_student_assignments'] = self.initialize_assignments(data)
        
        # Calculate course demand and actual enrollments
        course_demand = {}
        course_enrollments = {}
        
        # Calculate demand from preferences
        for _, student in student_preferences.iterrows():
            for course in student['Preferred Sections'].split(';'):
                course_demand[course] = course_demand.get(course, 0) + 1
        
        # Calculate actual enrollments
        for _, section in sections.iterrows():
            course = section['Course ID']
            enrolled = len(data['current_student_assignments'][
                data['current_student_assignments']['Section ID'] == section['Section ID']
            ])
            if course not in course_enrollments:
                course_enrollments[course] = []
            course_enrollments[course].append(enrolled)

        # Find optimization opportunities
        opportunities = {
            'remove_candidates': [],
            'merge_candidates': [],
            'split_candidates': []
        }

        for course, enrollments in course_enrollments.items():
            course_sections = sections[sections['Course ID'] == course]
            total_enrolled = sum(enrollments)
            total_capacity = course_sections['# of Seats Available'].sum()
            avg_enrollment = total_enrolled / len(enrollments)

            # Find sections to potentially remove
            if len(enrollments) > 1:
                for i in range(len(enrollments)):
                    enrollment = enrollments[i]
                    section = course_sections.iloc[i]
                    if enrollment < (0.3 * avg_enrollment):
                        opportunities['remove_candidates'].append({
                            'course': course,
                            'section': section['Section ID'],
                            'current_enrollment': enrollment,
                            'reason': f"Low enrollment ({enrollment}) compared to average ({avg_enrollment:.1f})"
                        })

            # Find merge candidates
            if len(enrollments) >= 2:
                sorted_sections = sorted(zip(course_sections['Section ID'], enrollments), 
                                      key=lambda x: x[1])
                if sorted_sections[0][1] + sorted_sections[1][1] <= course_sections.iloc[0]['# of Seats Available']:
                    current_util = (sorted_sections[0][1] + sorted_sections[1][1]) / course_sections.iloc[0]['# of Seats Available']
                    opportunities['merge_candidates'].append({
                        'course': course,
                        'section1': sorted_sections[0][0],
                        'section2': sorted_sections[1][0],
                        'combined_enrollment': sorted_sections[0][1] + sorted_sections[1][1],
                        'current_util': current_util
                    })

            # Add split candidates for highly utilized sections
            for i in range(len(enrollments)):
                enrollment = enrollments[i]
                try:
                    section = course_sections.iloc[i]
                    utilization = enrollment / section['# of Seats Available']
                    if utilization > 0.9:  # 90% or higher utilization
                        opportunities['split_candidates'].append({
                            'course': course,
                            'section': section['Section ID'],
                            'current_enrollment': enrollment,
                            'reason': f"High utilization ({utilization:.1%})"
                        })
                except Exception as e:
                    print(f"Warning: Error processing split candidate for course {course}, enrollment {enrollment}: {str(e)}")
                    continue

        return {
            'course_demand': course_demand,
            'course_enrollments': course_enrollments,
            'opportunities': opportunities,
            'total_students': len(student_preferences),
            'total_assignments': len(data.get('current_student_assignments', pd.DataFrame()))
        }

    def generate_optimization_prompt(self, analysis: Dict, data: Dict[str, pd.DataFrame]) -> str:
        """Create detailed optimization prompt with full context"""
        # Get current departments for reference
        departments = data['sections'].groupby('Course ID')['Department'].first().to_dict()
        
        # Calculate current teacher loads
        teacher_loads = {}
        for _, row in data.get('current_teacher_assignments', pd.DataFrame()).iterrows():
            teacher_id = row['Teacher ID']
            if teacher_id != 'Unassigned':
                teacher_loads[teacher_id] = teacher_loads.get(teacher_id, 0) + 1

        # Get teacher department info
        teacher_departments = {}
        for _, row in data['teacher_info'].iterrows():
            teacher_departments[row['Teacher ID']] = row['Department']
        
        prompt = f"""As a schedule optimization expert, analyze the data and provide an optimized Sections_Information.csv file.
Your task is to assign teachers to sections based on these rules:

SECTION SIZE CONSTRAINTS:
- Minimum section size: {self.constraints['min_section_size']} students
- Maximum section size: {self.constraints['max_section_size']} students
- Do not create sections that would be below minimum size
- Do not merge sections if combined size would exceed maximum

TEACHER CONSTRAINTS:
1. Each teacher can teach maximum 6 sections
2. Teachers must teach within their department
3. Current teacher loads must be considered:
"""
        # Add current teacher loads
        for teacher, load in teacher_loads.items():
            dept = teacher_departments.get(teacher, 'Unknown')
            prompt += f"\n{teacher} ({dept}): {load}/6 sections"

        prompt += "\n\nAVAILABLE TEACHERS BY DEPARTMENT:"
        # Group and add available teachers by department
        for dept, teachers in pd.DataFrame(teacher_departments.items(), 
                                         columns=['Teacher', 'Department']).groupby('Department'):
            available_teachers = [t for t in teachers['Teacher'] 
                                if teacher_loads.get(t, 0) < 6]
            prompt += f"\n{dept}: {', '.join(available_teachers)}"

        prompt += "\n\nCURRENT STATISTICS:"
        prompt += f"\nTotal Students: {analysis['total_students']}"
        prompt += f"\nTotal Current Assignments: {analysis['total_assignments']}"

        prompt += "\n\nDEPARTMENTS BY COURSE:"
        for course, dept in departments.items():
            prompt += f"\n{course}: {dept}"

        prompt += "\n\nCOURSE RELATIONSHIPS:"
        for course, demand in analysis['course_demand'].items():
            enrollments = analysis['course_enrollments'].get(course, [])
            prompt += f"\nCourse {course}:"
            prompt += f"\n  Demand: {demand} students"
            prompt += f"\n  Sections: {len(enrollments)}"
            if enrollments:
                prompt += f"\n  Current enrollments: {enrollments}"
                
        prompt += """

CRITICAL RULES FOR SPECIAL COURSES:

1. Medical Career:
   - MUST be scheduled ONLY in R1 or G1 periods
   - MUST have exactly one dedicated teacher who teaches NO other courses
   - Each section MUST have 15 seats maximum
   - Teacher CANNOT teach Heroes Teach
   - Generate at least 2 sections if any students request it

2. Heroes Teach:
   - MUST be scheduled ONLY in R2 or G2 periods
   - MUST have exactly one dedicated teacher who teaches NO other courses 
   - Each section MUST have 15 seats maximum
   - Teacher CANNOT teach Medical Career
   - Generate at least 2 sections if any students request it

3. Study Hall:
   - Regular sections for students not in Medical Career or Heroes Teach
   - Standard class size rules apply
   - Any teacher can teach Study Hall

4. Sports Med:
   - Maximum 1 section per period
   - Standard class size rules apply
   - Can be scheduled in any period

ABSOLUTE REQUIREMENTS:
1. Medical Career and Heroes Teach MUST have different dedicated teachers
2. Medical Career sections ONLY in R1 or G1
3. Heroes Teach sections ONLY in R2 or G2
4. The same teacher CANNOT teach both Medical Career and Heroes Teach
5. Keep special course sections small (15 students max)
6. Generate multiple sections for special courses to ensure feasibility

REQUIRED OUTPUT FORMAT:
You must include the exact header row followed by the data:
Section ID,Course ID,Teacher Assigned,# of Seats Available,Department

Example format:
Section ID,Course ID,Teacher Assigned,# of Seats Available,Department
S001,Medical Career,T001,15,Special
S002,Medical Career,T001,15,Special
S003,Heroes Teach,T002,15,Special
S004,Heroes Teach,T002,15,Special
...etc

Based on the data and constraints above, provide an optimized Sections_Information.csv content.
The first line MUST be the exact header row shown above.
Include only the CSV content in your response, no explanation or other text."""

        return prompt

    def consult_claude(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Get Claude's optimized schedule as a DataFrame"""
        analysis = self.analyze_utilization(data)
        prompt = self.generate_optimization_prompt(analysis, data)
        
        print("\nRequesting optimized schedule from Claude...")
        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        csv_content = response.content[0].text.strip()
        print("\nReceived CSV content:")
        print(csv_content[:200] + "...")  # Show first few lines
        
        try:
            # Split content into lines and verify header
            lines = csv_content.strip().split('\n')
            if len(lines) < 2:  # Need at least header and one data row
                print("Error: CSV content too short")
                return None
                
            expected_header = "Section ID,Course ID,Teacher Assigned,# of Seats Available,Department"
            if lines[0].strip() != expected_header:
                print("Error: Incorrect header format")
                print("Expected:", expected_header)
                print("Got:", lines[0])
                # Try to fix header
                csv_content = expected_header + '\n' + '\n'.join(lines)
            
            # Parse CSV content
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Validate required columns exist
            required_cols = ['Section ID', 'Course ID', 'Teacher Assigned', '# of Seats Available', 'Department']
            if not all(col in df.columns for col in required_cols):
                print("Error: Missing required columns")
                print("Expected:", required_cols)
                print("Got:", list(df.columns))
                return None
            
            # Ensure columns are in correct order
            df = df[required_cols]
            
            # Validate departments match original assignments
            original_depts = data['sections'].groupby('Course ID')['Department'].first()
            mismatched_depts = []
            for _, row in df.iterrows():
                if row['Course ID'] in original_depts:
                    if row['Department'] != original_depts[row['Course ID']]:
                        mismatched_depts.append(row['Course ID'])
            
            if mismatched_depts:
                print("Error: Department assignments changed for courses:", mismatched_depts)
                return None
                
            return df
            
        except Exception as e:
            print(f"Error parsing CSV content: {str(e)}")
            print("Raw CSV content:")
            print(csv_content)
            return None

    def process_multiple_actions(self, data: Dict[str, pd.DataFrame], details: Dict) -> Dict[str, pd.DataFrame]:
        """Process multiple optimization actions in the correct order"""
        modified_data = {k: df.copy() for k, df in data.items()}
        
        # Process actions in order: removes -> merges -> splits
        if 'removed_sections' in details['expected_impact']:
            for section_id in details['expected_impact']['removed_sections']:
                modified_data = self.modify_data(modified_data, {
                    "action": "remove",
                    "primary_section": section_id,
                    "details": {"source": "multiple_action"}
                })
        
        if 'merged_sections' in details['expected_impact']:
            for merge_info in details['expected_impact']['merged_sections']:
                for merge_pair, course in merge_info.items():
                    section1, section2 = merge_pair.split(' + ')
                    modified_data = self.modify_data(modified_data, {
                        "action": "merge",
                        "primary_section": section1.strip(),
                        "secondary_section": section2.strip(),
                        "details": {"course": course}
                    })
        
        if 'split_sections' in details['expected_impact']:
            for split_info in details['expected_impact']['split_sections']:
                for section_pair, course in split_info.items():
                    section = section_pair.split(' + ')[0]  # Take first section as base
                    modified_data = self.modify_data(modified_data, {
                        "action": "split",
                        "primary_section": section.strip(),
                        "details": {"course": course}
                    })
        
        return modified_data

    def modify_data(self, data: Dict[str, pd.DataFrame], decision: Dict) -> Dict[str, pd.DataFrame]:
        """Apply Claude's recommended changes to all relevant DataFrames"""
        modified_data = {k: df.copy() for k, df in data.items()}
        
        # Validate change won't create constraint violations
        if decision["action"] == "merge":
            # Check teacher capacity
            section1, section2 = decision["primary_section"], decision["secondary_section"]
            teacher1 = modified_data['sections'][
                modified_data['sections']['Section ID'] == section1
            ]['Teacher Assigned'].iloc[0]
            
            teacher_load = len(modified_data['teacher_assignments'][
                modified_data['teacher_assignments']['Teacher ID'] == teacher1
            ])
            
            if teacher_load >= self.constraints['max_teacher_sections']:
                print(f"Warning: Merge would exceed teacher {teacher1}'s capacity")
                return modified_data

            # Check combined size won't exceed maximum
            current_enrollment1 = len(modified_data['student_assignments'][
                modified_data['student_assignments']['Section ID'] == section1
            ])
            current_enrollment2 = len(modified_data['student_assignments'][
                modified_data['student_assignments']['Section ID'] == section2
            ])
            
            if current_enrollment1 + current_enrollment2 > self.constraints['max_section_size']:
                print(f"Warning: Merge would exceed maximum section size of {self.constraints['max_section_size']}")
                return modified_data

        if decision["action"] == "remove":
            # Remove section and redistribute students
            section_id = decision["primary_section"]
            modified_data['sections'] = modified_data['sections'][
                modified_data['sections']['Section ID'] != section_id
            ]
            modified_data['teacher_assignments'] = modified_data['teacher_assignments'][
                modified_data['teacher_assignments']['Section ID'] != section_id
            ]
            # Student redistribution would need additional logic
            
        elif decision["action"] == "merge":
            # Merge two sections
            section1 = decision["primary_section"]
            section2 = decision["secondary_section"]
            
            # Keep primary section and update capacity
            merged_capacity = (
                modified_data['sections'][
                    modified_data['sections']['Section ID'] == section1
                ]['# of Seats Available'].iloc[0] +
                modified_data['sections'][
                    modified_data['sections']['Section ID'] == section2
                ]['# of Seats Available'].iloc[0]
            )
            
            modified_data['sections'].loc[
                modified_data['sections']['Section ID'] == section1,
                '# of Seats Available'
            ] = merged_capacity
            
            # Remove secondary section
            modified_data['sections'] = modified_data['sections'][
                modified_data['sections']['Section ID'] != section2
            ]
            
            # Update student assignments
            modified_data['student_assignments'].loc[
                modified_data['student_assignments']['Section ID'] == section2,
                'Section ID'
            ] = section1
            
        elif decision["action"] == "split":
            # Split a section
            section_id = decision["primary_section"]
            original_section = modified_data['sections'][
                modified_data['sections']['Section ID'] == section_id
            ].iloc[0]
            
            # Create two new sections
            section_a = original_section.copy()
            section_b = original_section.copy()
            section_a["Section ID"] = f"{section_id}_A"
            section_b["Section ID"] = f"{section_id}_B"
            
            # Split capacity
            original_capacity = original_section['# of Seats Available']
            section_a['# of Seats Available'] = original_capacity // 2
            section_b['# of Seats Available'] = original_capacity // 2
            
            # Update sections
            modified_data['sections'] = modified_data['sections'][
                modified_data['sections']['Section ID'] != section_id
            ]
            modified_data['sections'] = pd.concat([
                modified_data['sections'],
                pd.DataFrame([section_a, section_b])
            ])
            
            # Split students
            students = modified_data['student_assignments'][
                modified_data['student_assignments']['Section ID'] == section_id
            ]
            half_point = len(students) // 2
            
            students.iloc[:half_point, students.columns.get_loc('Section ID')] = f"{section_id}_A"
            students.iloc[half_point:, students.columns.get_loc('Section ID')] = f"{section_id}_B"
            
            modified_data['student_assignments'] = modified_data['student_assignments'][
                modified_data['student_assignments']['Section ID'] != section_id
            ]
            modified_data['student_assignments'] = pd.concat([
                modified_data['student_assignments'],
                students
            ])

            # Check resulting sections won't be too small
            current_enrollment = len(modified_data['student_assignments'][
                modified_data['student_assignments']['Section ID'] == section_id
            ])
            
            if current_enrollment / 2 < self.constraints['min_section_size']:
                print(f"Warning: Split would create sections below minimum size of {self.constraints['min_section_size']}")
                return modified_data
        
        # Validate results
        violations = self.validate_schedule_constraints(modified_data)
        if any(violations.values()):
            print("\nWarning: Proposed changes would create constraint violations:")
            for category, issues in violations.items():
                if issues:
                    print(f"\n{category.replace('_', ' ').title()}:")
                    for issue in issues:
                        print(f"  {issue}")

        return modified_data

    def optimize(self):
        """Main optimization function"""
        print(f"Using input directory: {self.input_path}")
        print(f"Reading from output directory: {self.output_path}")

        if not self.input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_path}")
            
        input_files = {
            'sections': 'Sections_Information.csv',
            'student_info': 'Student_Info.csv',
            'student_preferences': 'Student_Preference_Info.csv',
            'teacher_info': 'Teacher_Info.csv',
            'teacher_unavailability': 'Teacher_unavailability.csv'
        }
        
        # Add this definition
        output_files = {
            'master_schedule': 'Master_Schedule.csv',
            'student_assignments': 'Student_Assignments.csv',
            'unmet_requests': 'Students_Unmet_Requests.csv',
            'teacher_assignments': 'Teacher_Assignments.csv'
        }

        # Load input data with special handling for teacher unavailability
        data = {}
        try:
            for key, filename in input_files.items():
                file_path = self.input_path / filename
                print(f"Loading input: {file_path}")
                
                if key == 'teacher_unavailability':
                    try:
                        df = pd.read_csv(file_path)
                        if df.empty:
                            raise pd.errors.EmptyDataError
                    except (FileNotFoundError, pd.errors.EmptyDataError):
                        print(f"Note: Creating empty teacher unavailability data")
                        # Create empty DataFrame with required columns
                        df = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                else:
                    df = pd.read_csv(file_path)
                    if df.empty:
                        raise Exception(f"Empty required file: {filename}")
                
                data[key] = df
                
        except Exception as e:
            if key != 'teacher_unavailability':  # Only raise for required files
                raise Exception(f"Error loading input file {filename}: {str(e)}")

        # Load output data if available, with proper error handling
        if self.output_path.exists():
            for key, filename in output_files.items():
                file_path = self.output_path / filename
                if file_path.exists():
                    print(f"Loading output: {file_path}")
                    try:
                        df = pd.read_csv(file_path)
                        if df.empty:
                            print(f"Warning: Empty file {filename}")
                            continue
                        data[f"current_{key}"] = df
                    except pd.errors.EmptyDataError:
                        print(f"Warning: Empty file {filename}")
                        continue
                    except Exception as e:
                        print(f"Warning: Could not load output file {filename}: {str(e)}")
                        continue
                else:
                    print(f"Note: Output file not found: {filename}")
            
        # Ensure output directory exists
        if not self.output_path.exists():
            print("Creating output directory...")
            self.output_path.mkdir(parents=True, exist_ok=True)

        # Get optimization recommendation as DataFrame
        optimized_sections = self.consult_claude(data)
        
        if optimized_sections is not None:
            # Save directly to input directory
            sections_file = self.input_path / 'Sections_Information.csv'
            optimized_sections.to_csv(sections_file, index=False)
            print(f"\nUpdated {sections_file}")
            
            # Save to history
            self.history.append({
                "timestamp": pd.Timestamp.now().isoformat(),
                "sections_before": len(data['sections']),
                "sections_after": len(optimized_sections),
                "status": "applied"
            })
            self.save_history()
            
            # Print summary
            print("\nOptimization Summary:")
            print(f"Sections before: {len(data['sections'])}")
            print(f"Sections after: {len(optimized_sections)}")
            print(f"Changes made: {len(data['sections']) - len(optimized_sections)}")
        else:
            print("\nNo optimization applied - invalid response from Claude")

def main():
    print("Starting API key retrieval...")
    
    # First try Windows environment variable using direct registry access
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
            api_key = winreg.QueryValueEx(key, 'ANTHROPIC_API_KEY')[0]
            print("Successfully read key from Windows registry")
    except Exception as e:
        print(f"Could not read from registry: {e}")
        api_key = None
    
    # If registry fails, try command prompt
    if not api_key:
        try:
            import subprocess
            result = subprocess.run(
                'cmd /c set ANTHROPIC_API_KEY', 
                capture_output=True, 
                text=True,
                shell=True
            )
            for line in result.stdout.splitlines():
                if line.startswith('ANTHROPIC_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    print("Successfully read key from cmd environment")
                    break
        except Exception as e:
            print(f"Could not read from cmd: {e}")
    
    if not api_key:
        raise ValueError(
            "Could not read ANTHROPIC_API_KEY from Windows environment.\n"
            "Please ensure you've set it correctly in System Properties > Environment Variables"
        )
    
    try:
        print(f"Found API key of length: {len(api_key)}")
        print(f"Key starts with: {api_key[:8]}...")
        optimizer = UtilizationOptimizer(api_key)
        optimizer.optimize()
    except ValueError as e:
        print(f"Error: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Open System Properties > Environment Variables")
        print("2. Under 'User variables for your-username'")
        print("3. Delete any existing ANTHROPIC_API_KEY variable")
        print("4. Click 'New' and add ANTHROPIC_API_KEY again")
        print("5. Paste your API key carefully (no extra spaces)")
        print("6. Click OK on all windows")
        print("7. Close and reopen your command prompt")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()