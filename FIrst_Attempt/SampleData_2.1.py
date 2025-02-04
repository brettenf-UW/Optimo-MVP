import pandas as pd
import numpy as np

# Generate sample data for students
students_data = {
    'student_id': [f'S{i:03d}' for i in range(1, 101)],
    'grade_level': np.random.choice([9, 10, 11, 12], 100),
    'gender': np.random.choice(['M', 'F'], 100),
    'free_period_preference': np.random.choice(['Free First Period', 'Free Fourth Period', 'None'], 100),
    'course_requests': [','.join(np.random.choice(['C001', 'C002', 'C003', 'C004', 'C005'], np.random.randint(1, 4))) for _ in range(100)],
    'sped_status': np.random.choice(['Yes', 'No'], 100)
}
students_df = pd.DataFrame(students_data)

# Generate sample data for teachers
teachers_data = {
    'teacher_id': [f'T{i:02d}' for i in range(1, 21)],
    'department': np.random.choice(['Math', 'Science', 'PE/Health', 'English'], 20),
    'gender': np.random.choice(['M', 'F'], 20),
    'assigned_sections': np.random.randint(1, 4, 20),
    'available_periods': [','.join(map(str, np.random.choice(range(1, 9), np.random.randint(4, 9), replace=False))) for _ in range(20)],
    'sped_teacher': np.random.choice(['Yes', 'No'], 20)
}
teachers_df = pd.DataFrame(teachers_data)

# Generate sample data for courses
courses_data = {
    'course_id': [f'C{i:03d}' for i in range(1, 6)],
    'department': np.random.choice(['Math', 'Science', 'PE/Health', 'English'], 5),
    'capacity': np.random.randint(20, 30, 5),
    'sections': np.random.randint(1, 3, 5),
    'co_taught': np.random.choice(['Yes', 'No'], 5),
    'grade_levels': [','.join(map(str, np.random.choice([9, 10, 11, 12], np.random.randint(1, 4), replace=False))) for _ in range(5)]
}
courses_df = pd.DataFrame(courses_data)

# Preprocess the data
students_cleaned = []
for index, row in students_df.iterrows():
    requested_courses = row['course_requests'].split(',')
    free_periods = [course for course in requested_courses if 'Free' in course]
    valid_courses = [course for course in requested_courses if course in courses_df['course_id'].tolist()]
    valid_courses = list(set(valid_courses))

    students_cleaned.append({
        'student_id': row['student_id'],
        'grade_level': row['grade_level'],
        'gender': row['gender'],
        'free_period_preference': row['free_period_preference'],
        'course_requests': ','.join(valid_courses),
        'free_periods': free_periods,
        'sped_status': row['sped_status']
    })

students_df_cleaned = pd.DataFrame(students_cleaned)

teachers_cleaned = []
for index, row in teachers_df.iterrows():
    available_periods = [int(p) for p in row['available_periods'].split(',')]
    qualified_courses = courses_df[courses_df['department'] == row['department']]['course_id'].tolist()

    teachers_cleaned.append({
        'teacher_id': row['teacher_id'],
        'department': row['department'],
        'gender': row['gender'],
        'assigned_sections': row['assigned_sections'],
        'available_periods': available_periods,
        'qualified_courses': qualified_courses,
        'sped_teacher': row['sped_teacher']
    })

teachers_df_cleaned = pd.DataFrame(teachers_cleaned)

# Save the generated data to CSV files
students_df_cleaned.to_csv('students.csv', index=False)
teachers_df_cleaned.to_csv('teachers.csv', index=False)
courses_df.to_csv('courses.csv', index=False)

print("Sample data generated and saved to CSV files.")