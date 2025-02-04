import pandas as pd
import numpy as np
import random

def generate_school_data(num_students, student_teacher_ratio=16):
    # Calculate the number of teachers
    num_teachers = max(1, num_students // student_teacher_ratio)
    
    # Days and Periods
    days = ['Red', 'Gold']
    periods = [1, 2, 3, 4]
    total_periods = [{'Day': day, 'Period': period} for day in days for period in periods]
    
    # Generate Periods.csv
    periods_df = pd.DataFrame(total_periods)
    periods_df.to_csv('Periods.csv', index=False)
    
    # Departments and Courses
    departments = ['Science', 'PE/Health', 'World Language', 'Medical', 'Social Science', 'Math', 'English']
    courses_per_department = {
        'Science': ['Biology', 'Chemistry', 'Physics'],
        'PE/Health': ['PE 9', 'Health'],
        'World Language': ['Spanish 1', 'Spanish 2', 'French 1', 'French 2'],
        'Medical': ['Medical Career', 'Heroes Teach'],
        'Social Science': ['Student Government', 'History'],
        'Math': ['Algebra I', 'Geometry', 'Algebra II', 'Calculus'],
        'English': ['English 9', 'English 10', 'English 11', 'English 12']
    }
    
    # Courses.csv
    courses_data = []
    course_id = 1
    for dept, courses in courses_per_department.items():
        for course in courses:
            sections = max(1, num_students // (30 * len(courses_per_department)))
            is_lab_class = True if dept == 'Science' and course in ['Biology', 'Chemistry'] else False
            sped_limit = 12 if 'Co-Taught' in course else np.nan
            co_taught = True if 'Co-Taught' in course else False
            courses_data.append({
                'CourseID': course,
                'Department': dept,
                'Sections': sections,
                'IsLabClass': is_lab_class,
                'SPEDLimit': sped_limit,
                'CoTaught': co_taught
            })
            course_id += 1
    
    courses_df = pd.DataFrame(courses_data)
    courses_df.to_csv('Courses.csv', index=False)
    
    # Teachers.csv
    teacher_ids = [f'T{i+1}' for i in range(num_teachers)]
    genders = ['Male', 'Female']
    teacher_data = []
    for i, teacher_id in enumerate(teacher_ids):
        dept = random.choice(departments)
        qualified_courses = courses_per_department[dept]
        free_periods = ''
        if random.random() < 0.2:  # 20% chance to have free periods
            day = random.choice(days)
            period = random.choice(periods)
            free_periods = f'{day}-{period}'
        special_status = True if random.random() < 0.1 else False  # 10% chance to be special teacher
        gender = random.choice(genders)
        teacher_data.append({
            'TeacherID': teacher_id,
            'QualifiedCourses': '|'.join(qualified_courses),
            'FreePeriods': free_periods,
            'SpecialStatus': special_status,
            'Gender': gender,
            'Department': dept
        })
    
    teachers_df = pd.DataFrame(teacher_data)
    teachers_df.to_csv('Teachers.csv', index=False)
    
    # Students.csv
    student_ids = [f'S{i+1}' for i in range(num_students)]
    free_period_preferences = ['AM', 'PM', '']
    grades = [9, 10, 11, 12]
    student_data = []
    for student_id in student_ids:
        sped_status = True if random.random() < 0.1 else False  # 10% chance to be SPED
        free_pref = np.random.choice(free_period_preferences, p=[0.25, 0.75, 0.0])
        grade_level = random.choice(grades)
        student_data.append({
            'StudentID': student_id,
            'SPEDStatus': sped_status,
            'FreePeriodPreference': free_pref,
            'GradeLevel': grade_level
        })
    
    students_df = pd.DataFrame(student_data)
    students_df.to_csv('Students.csv', index=False)
    
    # StudentCourseSelections.csv
    selections = []
    for student in student_ids:
        num_courses = 8 if random.random() < 0.5 else 6  # 50% chance of 8 courses
        selected_courses = random.sample(courses_df['CourseID'].tolist(), num_courses)
        for course in selected_courses:
            selections.append({
                'StudentID': student,
                'CourseID': course
            })
    
    student_courses_df = pd.DataFrame(selections)
    student_courses_df.to_csv('StudentCourseSelections.csv', index=False)
    
    print(f"Generated data for {num_students} students and {num_teachers} teachers.")
    print("CSV files have been created.")

# Generate data for a 50-student school
print("Generating data for a 50-student school:")
generate_school_data(50)


