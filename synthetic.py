import pandas as pd
import random
import numpy as np
import math  # Add this import

def generate_synthetic_data(output_path):
    # Constants
    TARGET_UTILIZATION = 0.7  # Increased to get tighter fit
    STUDENTS_PER_GRADE = 25   # Keep same number of students
    SECTION_SIZES = {
        'default': 25,         # Smaller default size to create more sections
        'lab': 24,            # Science labs
        'PE': 35,             # Physical education 
        'art': 28,            # Art/Music classes
        'specialty': 25       # Medical Career, Heroes Teach, etc
    }
    MIN_SECTIONS_PER_COURSE = 1  # Ensure at least 2 sections per course
    SPED_RATIO = 0.03         # 12% of students are SPED
    MAX_SECTIONS_PER_TEACHER = 5  # Maximum sections per teacher

    def calc_required_sections(student_count, course_type='default'):
        """Calculate required sections based on demand and capacity"""
        base_size = SECTION_SIZES[course_type]
        # Calculate sections needed based on actual student count
        return math.ceil(student_count / base_size)

    # Update section capacity calculation
    def calc_section_capacity(course_id, expected_enrollment):
        """Calculate section capacity and number of sections needed"""
        # Determine course type
        if 'Science' in course_id:
            course_type = 'lab'
        elif course_id in ['PE']:
            course_type = 'PE'
        elif course_id in ['Art', 'Music']:
            course_type = 'art'
        elif course_id in ['Medical Career', 'Heroes Teach', 'Sports Med']:
            course_type = 'specialty'
        else:
            course_type = 'default'
            
        base_size = SECTION_SIZES[course_type]
        num_sections = calc_required_sections(expected_enrollment, course_type)
        
        return base_size, num_sections

    NUM_STUDENTS = {
        9: STUDENTS_PER_GRADE,   # Freshmen
        10: STUDENTS_PER_GRADE,  # Sophomores
        11: STUDENTS_PER_GRADE,  # Juniors
        12: STUDENTS_PER_GRADE   # Seniors
    }

    # Course patterns by grade with required sections
    COURSE_PATTERNS = {
        9: [
            ['English 9', 'Algebra 1', 'Biology', 'World History', 'Spanish 1', 'PE', 'Art'],
            ['English 9', 'Algebra 1', 'Biology', 'World History', 'Spanish 1', 'PE', 'Music']
        ],
        10: [
            ['English 10', 'Geometry', 'Chemistry', 'World History', 'Spanish 2', 'PE', 'Art'],
            ['English 10', 'Geometry', 'Chemistry', 'World History', 'Spanish 2', 'PE', 'Music']
        ],
        11: [
            ['English 11', 'Algebra 2', 'Physics', 'US History', 'Medical Career', 'Heroes Teach', 'Art'],
            ['English 11', 'Algebra 2', 'Physics', 'US History', 'Medical Career', 'Heroes Teach', 'Music']
        ],
        12: [
            ['English 12', 'Pre-Calculus', 'Government', 'Medical Career', 'Heroes Teach', 'Sports Med', 'Art'],
            ['English 12', 'Pre-Calculus', 'Government', 'Medical Career', 'Heroes Teach', 'Sports Med', 'Music']
        ]
    }

    # Calculate required sections for each course
    course_demands = {}
    for grade, patterns in COURSE_PATTERNS.items():
        student_count = NUM_STUDENTS[grade]
        pattern_count = len(patterns)
        
        # Count total students per course accounting for all patterns
        for pattern in patterns:
            for course in pattern:
                if course not in course_demands:
                    course_demands[course] = 0
                # Each student in this grade takes this course if it's in their pattern
                course_demands[course] += student_count * (pattern.count(course) / pattern_count)

    # Calculate required sections
    required_sections = {}
    for course, demand in course_demands.items():
        if 'Science' in course:
            course_type = 'lab'
        elif course in ['PE']:
            course_type = 'PE'
        elif course in ['Art', 'Music']:
            course_type = 'art'
        elif course in ['Medical Career', 'Heroes Teach', 'Sports Med']:
            course_type = 'specialty'
        else:
            course_type = 'default'
            
        required_sections[course] = calc_required_sections(demand, course_type)

    # Generate student data
    students = []
    student_preferences = []
    
    for grade in NUM_STUDENTS:
        for i in range(NUM_STUDENTS[grade]):
            student_id = f"ST{len(students) + 1:03d}"
            is_sped = random.random() < SPED_RATIO
            students.append({
                'Student ID': student_id,
                'Grade Level': grade,
                'SPED': 1 if is_sped else 0
            })
            
            # Generate course preferences
            courses = random.choice(COURSE_PATTERNS[grade])
            student_preferences.append({
                'Student ID': student_id,
                'Preferred Sections': ';'.join(courses)
            })

    # Calculate minimum required teachers based on total sections
    total_sections = sum(required_sections.values())
    min_teachers_needed = -(-total_sections // MAX_SECTIONS_PER_TEACHER)  # Ceiling division
    num_teachers = max(min_teachers_needed, len(set(course_demands.keys())))  # At least one per unique course

    # Create initial teacher frame with just IDs
    teachers = [{'Teacher ID': f'T{i:03d}'} for i in range(1, num_teachers + 1)]
    teachers_df = pd.DataFrame(teachers)

    # Generate sections ensuring each course has required sections
    sections = []
    section_id = 1
    teacher_loads = {t['Teacher ID']: [] for t in teachers}  # Track courses per teacher
    
    # Calculate expected enrollment per course
    course_enrollments = {}
    for course in course_demands.keys():
        total_demand = sum(
            NUM_STUDENTS[grade] / len(COURSE_PATTERNS[grade])
            for grade in NUM_STUDENTS
            if any(course in pattern for pattern in COURSE_PATTERNS[grade])
        )
        course_enrollments[course] = total_demand

    # First pass: Create required sections with appropriate capacity
    for course in course_demands.keys():
        expected_enrollment = course_enrollments[course]
        if 'Science' in course:
            course_type = 'lab'
        elif course in ['PE']:
            course_type = 'PE'
        elif course in ['Art', 'Music']:
            course_type = 'art'
        elif course in ['Medical Career', 'Heroes Teach', 'Sports Med']:
            course_type = 'specialty'
        else:
            course_type = 'default'
            
        base_size = SECTION_SIZES[course_type]
        num_sections = required_sections[course]  # Use pre-calculated required sections
        
        # Calculate optimal section size
        section_capacity = math.ceil(expected_enrollment / num_sections)
        
        # Create exactly the required number of sections
        for i in range(num_sections):
            available_teachers = [t['Teacher ID'] for t in teachers 
                                if len(teacher_loads[t['Teacher ID']]) < MAX_SECTIONS_PER_TEACHER]
            
            if not available_teachers:
                new_teacher_id = f'T{len(teachers) + 1:03d}'
                teachers.append({'Teacher ID': new_teacher_id})
                teacher_loads[new_teacher_id] = []
                available_teachers = [new_teacher_id]
            
            teacher = min(available_teachers, key=lambda t: len(teacher_loads[t]))
            teacher_loads[teacher].append(course)
            
            # For last section, adjust capacity to match remaining enrollment if needed
            if i == num_sections - 1:
                total_capacity_so_far = (num_sections - 1) * section_capacity
                remaining_needed = expected_enrollment - total_capacity_so_far
                if remaining_needed > 0:
                    section_capacity = math.ceil(remaining_needed)
            
            sections.append({
                'Section ID': f'S{section_id:03d}',
                'Course ID': course,
                'Teacher Assigned': teacher,
                '# of Seats Available': section_capacity
            })
            section_id += 1

    # Print utilization statistics
    print("\nSection Utilization Analysis:")
    for course in course_demands.keys():
        course_sections = [s for s in sections if s['Course ID'] == course]
        total_capacity = sum(s['# of Seats Available'] for s in course_sections)
        expected_enrollment = course_enrollments[course]
        utilization = expected_enrollment / total_capacity
        print(f"{course}: {utilization:.1%} utilization "
              f"(Capacity: {total_capacity}, Expected: {int(expected_enrollment)})")

    # Print verification of coverage
    print("\nCourse Coverage Verification:")
    for course in course_demands.keys():
        actual_sections = len([s for s in sections if s['Course ID'] == course])
        required = required_sections[course]
        print(f"{course}: {actual_sections}/{required} sections assigned")
        if actual_sections < required:
            raise ValueError(f"Failed to assign enough sections for {course}")

    # Convert to DataFrames
    students_df = pd.DataFrame(students)
    preferences_df = pd.DataFrame(student_preferences)
    sections_df = pd.DataFrame(sections)

    # Generate teacher unavailability (more realistic)
    unavailability = []
    periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']
    
    for teacher in teachers_df['Teacher ID']:
        if random.random() < 0.05:  # Changed back to 20% chance of unavailability
            num_unavailable = random.randint(1, 2)
            unavailable_periods = random.sample(periods, num_unavailable)
            unavailability.append({
                'Teacher ID': teacher,
                'Unavailable Periods': ','.join(unavailable_periods)
            })
    
    # Create DataFrame with explicit columns, even if empty
    unavailability_df = pd.DataFrame(
        unavailability if unavailability else [{'Teacher ID': '', 'Unavailable Periods': ''}],
        columns=['Teacher ID', 'Unavailable Periods']
    )
    
    # Remove empty row if it was added to create columns
    if len(unavailability) == 0:
        unavailability_df = unavailability_df.iloc[0:0]

    # Verify expected columns are present
    expected_columns = {
        'students_df': ['Student ID', 'Grade Level', 'SPED'],
        'preferences_df': ['Student ID', 'Preferred Sections'],
        'teachers_df': ['Teacher ID'],
        'sections_df': ['Section ID', 'Course ID', 'Teacher Assigned', '# of Seats Available'],
        'unavailability_df': ['Teacher ID', 'Unavailable Periods']
    }

    # Verify and save each DataFrame with proper columns
    def verify_and_save_df(df, name, path, required_cols):
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in {name}: {missing_cols}")
        print(f"\nVerifying {name}:")
        print(f"Columns present: {list(df.columns)}")
        print(f"Number of records: {len(df)}")
        df.to_csv(path, index=False)

    # Save files with verification
    verify_and_save_df(students_df, 'Student_Info.csv', 
                      f"{output_path}/Student_Info.csv",
                      expected_columns['students_df'])
    
    verify_and_save_df(preferences_df, 'Student_Preference_Info.csv',
                      f"{output_path}/Student_Preference_Info.csv", 
                      expected_columns['preferences_df'])
    
    verify_and_save_df(teachers_df, 'Teacher_Info.csv',
                      f"{output_path}/Teacher_Info.csv",
                      expected_columns['teachers_df'])
    
    verify_and_save_df(sections_df, 'Sections_Information.csv',
                      f"{output_path}/Sections_Information.csv",
                      expected_columns['sections_df'])
    
    verify_and_save_df(unavailability_df, 'Teacher_unavailability.csv',
                      f"{output_path}/Teacher_unavailability.csv",
                      expected_columns['unavailability_df'])

    # Print summary statistics for verification
    print("\nData Generation Summary:")
    print(f"Total Students: {len(students_df)}")
    print(f"Total Teachers: {len(teachers_df)}")
    print(f"Total Sections: {len(sections_df)}")
    print(f"Teachers with Unavailability: {len(unavailability_df)}")
    
    # Verify referential integrity
    teacher_ids = set(teachers_df['Teacher ID'])
    section_teachers = set(sections_df['Teacher Assigned'])
    unavail_teachers = set(unavailability_df['Teacher ID'])
    
    if not section_teachers.issubset(teacher_ids):
        raise ValueError("Found sections assigned to non-existent teachers")
    if not unavail_teachers.issubset(teacher_ids):
        raise ValueError("Found unavailability for non-existent teachers")

    # Print statistics
    print("\nGenerated Data Statistics:")
    print(f"Total Students: {len(students_df)}")
    print(f"SPED Students: {len(students_df[students_df['SPED'] == 1])}")
    print(f"Total Teachers: {len(teachers_df)}")
    print(f"Total Sections: {len(sections_df)}")
    print("\nSections per course:")
    for course in required_sections:
        print(f"{course}: {required_sections[course]} sections")
    print("\nTeacher loads:", teacher_loads)

if __name__ == "__main__":
    output_path = "input"
    generate_synthetic_data(output_path)
