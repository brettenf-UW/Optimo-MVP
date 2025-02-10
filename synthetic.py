import pandas as pd
import random
import numpy as np
import math

def generate_synthetic_data(output_path):
    # Constants
    STUDENTS_PER_GRADE = 400  # total students for ~16 teachers (20:1 ratio)
    SECTION_SIZES = {
        'default': 20,
        'lab': 24,
        'PE': 30,
        'special': 20  # Medical Career, Heroes Teach, Sports Med
    }
    SPED_RATIO = 0.15  # 15% SPED students to test distribution

    # Course patterns by grade
    COURSE_PATTERNS = {
        9: [
            ['English 9', 'Math 1', 'Biology', 'World History', 'PE', 'Medical Career'],
            ['English 9', 'Math 1', 'Biology', 'World History', 'PE', 'Heroes Teach']
        ],
        10: [
            ['English 10', 'Math 2', 'Chemistry', 'US History', 'PE', 'Medical Career'],
            ['English 10', 'Math 2', 'Chemistry', 'US History', 'PE', 'Heroes Teach']
        ],
        11: [
            ['English 11', 'Math 3', 'Physics', 'Government', 'Sports Med', 'Medical Career'],
            ['English 11', 'Math 3', 'Physics', 'Government', 'Sports Med', 'Heroes Teach']
        ],
        12: [
            ['English 12', 'Math 4', 'AP Biology', 'Economics', 'Sports Med', 'Medical Career'],
            ['English 12', 'Math 4', 'AP Biology', 'Economics', 'Sports Med', 'Heroes Teach']
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
            
            students.append({
                'Student ID': student_id_str,
                'SPED': "Yes" if is_sped else "No"
            })
            
            # Assign course preferences
            pattern = random.choice(COURSE_PATTERNS[grade])
            student_preferences.append({
                'Student ID': student_id_str,
                'Preferred Sections': ';'.join(pattern)
            })
            
            student_id += 1

    # Generate teacher data
    num_students = len(students)
    num_teachers = math.ceil(num_students / 20)  # 20:1 ratio
    
    # Update departments list to match course needs with exact course names
    departments = {
        'English': ['English 9', 'English 10', 'English 11', 'English 12'],
        'Math': ['Math 1', 'Math 2', 'Math 3', 'Math 4'],
        'Science': ['Biology', 'Chemistry', 'Physics', 'AP Biology'],
        'Social Studies': ['World History', 'US History', 'Government', 'Economics'],
        'PE': ['PE', 'Sports Med'],
        'Special': ['Medical Career', 'Heroes Teach']
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
        for dept, courses in departments.items():
            if any(course.startswith(c) for c in courses):
                return dept
        return 'General'

    # Calculate total sections needed per department first
    dept_sections = {dept: 0 for dept in departments}
    for course in unique_courses:
        total_requests = sum(1 for prefs in student_preferences 
                           if course in prefs['Preferred Sections'].split(';'))
        num_sections = max(2, math.ceil(total_requests / SECTION_SIZES['default']))
        
        # Find which department this course belongs to
        for dept, courses in departments.items():
            if any(c in course for c in courses):
                dept_sections[dept] += num_sections
                break

    # Calculate minimum teachers needed per department
    teachers = []
    teacher_id = 1
    for dept, num_sections in dept_sections.items():
        # Each teacher can teach 5 sections, ensure at least 2 teachers per department
        num_teachers = max(2, math.ceil(num_sections / 5))
        for i in range(num_teachers):
            teachers.append({
                'Teacher ID': f"T{teacher_id:03d}",
                'Department': dept
            })
            teacher_id += 1

    # Update department assignment logic to be more flexible
    def get_department(course):
        for dept, courses in departments.items():
            if any(course.startswith(c) for c in courses):
                return dept
        return 'General'

    # Reset teacher loads
    teacher_loads = {t['Teacher ID']: 0 for t in teachers}

    # Create sections with more flexible teacher assignment
    sections = []
    section_id = 1

    # Sort courses by total requests to handle highest demand first
    course_demands = []
    for course in unique_courses:
        total_requests = sum(1 for prefs in student_preferences 
                           if course in prefs['Preferred Sections'].split(';'))
        course_demands.append((course, total_requests))
    
    course_demands.sort(key=lambda x: x[1], reverse=True)

    # Create sections with prioritized assignment
    for course, total_requests in course_demands:
        section_size = get_section_size(course)
        num_sections = max(2, math.ceil(total_requests / section_size))
        dept = get_department(course)
        
        # Get all teachers in this department sorted by current load
        dept_teachers = [t for t in teachers if t['Department'] == dept]
        if not dept_teachers:
            print(f"Warning: No teachers available for department {dept}")
            continue
            
        for _ in range(num_sections):
            # Sort teachers by current load to ensure even distribution
            available_teachers = sorted(
                [t for t in dept_teachers if teacher_loads[t['Teacher ID']] < 5],
                key=lambda t: teacher_loads[t['Teacher ID']]
            )
            
            if not available_teachers:
                # Add a new teacher if needed
                new_teacher_id = f"T{len(teachers) + 1:03d}"
                new_teacher = {'Teacher ID': new_teacher_id, 'Department': dept}
                teachers.append(new_teacher)
                teacher_loads[new_teacher_id] = 0
                available_teachers = [new_teacher]
            
            teacher = available_teachers[0]
            teacher_loads[teacher['Teacher ID']] += 1
            
            sections.append({
                'Section ID': f"S{section_id:03d}",
                'Course ID': course,
                'Teacher Assigned': teacher['Teacher ID'],
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
