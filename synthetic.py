import pandas as pd
import random
import numpy as np
import math

def generate_synthetic_data(output_path):
    # Modify constants for better feasibility
    STUDENTS_PER_GRADE = 60  # Keep same number of students
    SECTION_SIZES = {
        'default': 25,  # Increase from 20 to allow flexibility
        'lab': 30,      # Increase from 24
        'PE': 35,       # Increase from 30
        'special': 15   # Reduce from 20 to make special courses more exclusive
    }
    MIN_SECTIONS_PER_COURSE = 2  # Ensure at least 2 sections per course

    SPED_RATIO = 0.15  # 15% SPED students to test distribution
    SPECIAL_COURSE_RATIO = 0.3  # Only 30% of students get special courses

    # Course patterns by grade
    COURSE_PATTERNS = {
        9: [
            ['English 9', 'Math 1', 'Biology', 'World History', 'PE', 'Medical Career'],
            ['English 9', 'Math 1', 'Biology', 'World History', 'PE', 'Heroes Teach'],
            ['English 9', 'Math 1', 'Biology', 'World History', 'PE', 'Study Hall']  # Non-special alternative
        ],
        10: [
            ['English 10', 'Math 2', 'Chemistry', 'US History', 'PE', 'Medical Career'],
            ['English 10', 'Math 2', 'Chemistry', 'US History', 'PE', 'Heroes Teach'],
            ['English 10', 'Math 2', 'Chemistry', 'US History', 'PE', 'Study Hall']  # Non-special alternative
        ],
        11: [
            ['English 11', 'Math 3', 'Physics', 'Government', 'Sports Med', 'Medical Career'],
            ['English 11', 'Math 3', 'Physics', 'Government', 'Sports Med', 'Heroes Teach'],
            ['English 11', 'Math 3', 'Physics', 'Government', 'Sports Med', 'Study Hall']  # Non-special alternative
        ],
        12: [
            ['English 12', 'Math 4', 'AP Biology', 'Economics', 'Sports Med', 'Medical Career'],
            ['English 12', 'Math 4', 'AP Biology', 'Economics', 'Sports Med', 'Heroes Teach'],
            ['English 12', 'Math 4', 'AP Biology', 'Economics', 'Sports Med', 'Study Hall']  # Non-special alternative
        ]
    }

    # Calculate unique courses first
    unique_courses = set()
    for patterns in COURSE_PATTERNS.values():
        for pattern in patterns:
            unique_courses.update(pattern)

    # Generate student data
    students = []
    student_preferences = []
    student_id = 1
    
    for grade in COURSE_PATTERNS:
        for _ in range(STUDENTS_PER_GRADE):
            student_id_str = f"ST{student_id:03d}"
            is_sped = random.random() < SPED_RATIO
            
            # Determine if student gets a special course
            gets_special = random.random() < SPECIAL_COURSE_RATIO
            
            students.append({
                'Student ID': student_id_str,
                'SPED': "Yes" if is_sped else "No"
            })
            
            # Select course pattern based on special course availability
            if gets_special:
                pattern = random.choice(COURSE_PATTERNS[grade][:2])  # Only special patterns
            else:
                pattern = COURSE_PATTERNS[grade][2]  # Non-special pattern
                
            student_preferences.append({
                'Student ID': student_id_str,
                'Preferred Sections': ';'.join(pattern)
            })
            
            student_id += 1

    # Generate teacher data
    num_students = len(students)
    num_teachers = math.ceil(num_students / 20)  # 20:1 ratio
    
    # Update departments list to include Study Hall
    departments = {
        'English': ['English 9', 'English 10', 'English 11', 'English 12'],
        'Math': ['Math 1', 'Math 2', 'Math 3', 'Math 4'],
        'Science': ['Biology', 'Chemistry', 'Physics', 'AP Biology'],
        'Social Studies': ['World History', 'US History', 'Government', 'Economics'],
        'PE': ['PE', 'Sports Med'],
        'Special': ['Medical Career', 'Heroes Teach'],
        'General': ['Study Hall']  
    }

    # Helper functions
    def get_section_size(course):
        if 'Biology' in course or 'Chemistry' in course or 'Physics' in course:
            return SECTION_SIZES['lab']
        elif 'PE' in course:
            return SECTION_SIZES['PE']
        elif course in ['Medical Career', 'Heroes Teach', 'Sports Med']:
            return SECTION_SIZES['special']
        return SECTION_SIZES['default']

    def get_department(course):
        if course == 'Study Hall':
            return 'General'
        for dept, courses in departments.items():
            if any(course.startswith(c) for c in courses):
                return dept
        return 'General'

    # Calculate total sections needed per department first
    dept_sections = {dept: 0 for dept in departments}  # Now includes 'General'
    for course in unique_courses:
        total_requests = sum(1 for prefs in student_preferences 
                           if course in prefs['Preferred Sections'].split(';'))
        num_sections = max(2, math.ceil(total_requests / SECTION_SIZES['default']))
        
        # Find which department this course belongs to
        for dept, courses in departments.items():
            if any(c in course for c in courses):
                dept_sections[dept] += num_sections
                break

    # Calculate required teachers per department
    def calculate_required_teachers():
        dept_course_counts = {dept: 0 for dept in departments}  # Now includes 'General'
        for grade_patterns in COURSE_PATTERNS.values():
            for pattern in grade_patterns:
                for course in pattern:
                    dept = get_department(course)
                    dept_course_counts[dept] += STUDENTS_PER_GRADE / len(grade_patterns)

        required_teachers = {}
        for dept, count in dept_course_counts.items():
            if dept == 'Science':
                # Science teachers need more prep time due to labs
                required_teachers[dept] = math.ceil(count / (SECTION_SIZES['lab'] * 4))
            elif dept == 'General':
                required_teachers[dept] = 2  # Minimum teachers for Study Hall
            else:
                section_size = SECTION_SIZES['special'] if dept == 'Special' else SECTION_SIZES['default']
                required_teachers[dept] = math.ceil(count / (section_size * 4))
            # Ensure minimum of 2 teachers per department
            required_teachers[dept] = max(2, required_teachers[dept])
        
        return required_teachers

    # Modify teacher generation for special courses
    def generate_teachers():
        teachers = []
        teacher_id = 1
        required_teachers = calculate_required_teachers()

        # First, create dedicated teachers for special courses
        medical_teacher_id = f"T{teacher_id:03d}"
        heroes_teacher_id = f"T{teacher_id+1:03d}"
        
        teachers.extend([
            {
                'Teacher ID': medical_teacher_id,
                'Department': 'Special',
                'Dedicated Course': 'Medical Career',
                'Current Load': 0
            },
            {
                'Teacher ID': heroes_teacher_id,
                'Department': 'Special',
                'Dedicated Course': 'Heroes Teach',
                'Current Load': 0
            }
        ])
        teacher_id += 2

        # Generate remaining teachers based on calculated requirements
        for dept, num_required in required_teachers.items():
            if dept != 'Special':  # Special teachers already created
                for _ in range(num_required):
                    teachers.append({
                        'Teacher ID': f"T{teacher_id:03d}",
                        'Department': dept,
                        'Dedicated Course': None,
                        'Current Load': 0
                    })
                    teacher_id += 1

        return teachers, {
            'Medical Career': medical_teacher_id,
            'Heroes Teach': heroes_teacher_id
        }

    # Get teachers and special course mappings
    teachers, special_course_teachers = generate_teachers()
    
    # Initialize teacher loads
    teacher_loads = {t['Teacher ID']: 0 for t in teachers}

    # Add this function definition before section creation
    def assign_teacher_to_section(course, dept):
        """Assign a teacher to a section based on department and availability"""
        MAX_COURSES_PER_TEACHER = 4  # Maximum number of courses per teacher
        
        if course in special_course_teachers:
            teacher_id = special_course_teachers[course]
            teachers[next(i for i, t in enumerate(teachers) if t['Teacher ID'] == teacher_id)]['Current Load'] += 1
            return teacher_id
        
        # Get all teachers in the department
        dept_teachers = [t for t in teachers if t['Department'] == dept]
        
        # Sort by current load
        available_teachers = sorted(
            [t for t in dept_teachers if t['Current Load'] < MAX_COURSES_PER_TEACHER],
            key=lambda t: t['Current Load']
        )
        
        if not available_teachers:
            # Add a new teacher if needed
            new_teacher_id = f"T{len(teachers) + 1:03d}"
            new_teacher = {
                'Teacher ID': new_teacher_id,
                'Department': dept,
                'Dedicated Course': None,
                'Current Load': 1  # Start with load of 1
            }
            teachers.append(new_teacher)
            return new_teacher_id
        
        # Update chosen teacher's load
        chosen_teacher = available_teachers[0]
        chosen_teacher['Current Load'] += 1
        return chosen_teacher['Teacher ID']

    # Create sections with special course handling
    sections = []
    section_id = 1

    # Calculate course demands first
    course_demands = []
    for course in unique_courses:
        total_requests = sum(1 for prefs in student_preferences 
                           if course in prefs['Preferred Sections'].split(';'))
        course_demands.append((course, total_requests))
    
    # Sort by demand
    course_demands.sort(key=lambda x: x[1], reverse=True)

    # Handle special courses first
    special_courses = ['Medical Career', 'Heroes Teach']
    for course in special_courses:
        requests = sum(1 for prefs in student_preferences 
                      if course in prefs['Preferred Sections'].split(';'))
        num_sections = max(2, math.ceil(requests / SECTION_SIZES['special']))
        
        teacher_id = special_course_teachers[course]
        for _ in range(num_sections):
            sections.append({
                'Section ID': f"S{section_id:03d}",
                'Course ID': course,
                'Teacher Assigned': teacher_id,
                '# of Seats Available': SECTION_SIZES['special'],
                'Department': 'Special'
            })
            section_id += 1
            teacher_loads[teacher_id] += 1

    # Modify section creation for better capacity distribution
    def create_course_sections(course, requests):
        """Create sections for a course with appropriate capacity"""
        section_size = get_section_size(course)
        
        # Calculate minimum sections needed for capacity
        min_sections_needed = math.ceil(requests / section_size)
        
        # Always create at least 2 sections, and ensure enough capacity
        num_sections = max(MIN_SECTIONS_PER_COURSE, min_sections_needed)
        
        # Add extra section if close to capacity
        if (requests / (num_sections * section_size)) > 0.85:
            num_sections += 1
            
        return num_sections, section_size

    # Then handle regular courses
    regular_courses = [c for c in course_demands if c[0] not in special_courses]
    for course, total_requests in regular_courses:
        num_sections, section_size = create_course_sections(course, total_requests)
        dept = get_department(course)
        
        for _ in range(num_sections):
            teacher_id = assign_teacher_to_section(course, dept)
            sections.append({
                'Section ID': f"S{section_id:03d}",
                'Course ID': course,
                'Teacher Assigned': teacher_id,
                '# of Seats Available': section_size,
                'Department': dept
            })
            section_id += 1

    # Generate teacher unavailability (to test constraints)
    periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']
    unavailability = []
    
    for teacher in teachers:
        if random.random() < 0.1:  # chance of unavailability
            unavail_periods = random.sample(periods, random.randint(1, 2))
            unavailability.append({
                'Teacher ID': teacher['Teacher ID'],
                'Unavailable Periods': ','.join(unavail_periods)
            })

    # Convert to DataFrames and save
    pd.DataFrame(students).to_csv(f"{output_path}/Student_Info.csv", index=False)
    pd.DataFrame(student_preferences).to_csv(f"{output_path}/Student_Preference_Info.csv", index=False)
    pd.DataFrame(teachers).to_csv(f"{output_path}/Teacher_Info.csv", index=False)
    pd.DataFrame(sections).to_csv(f"{output_path}/Sections_Information.csv", index=False)
    pd.DataFrame(unavailability).to_csv(f"{output_path}/Teacher_unavailability.csv", index=False)

if __name__ == "__main__":
    generate_synthetic_data("input")
