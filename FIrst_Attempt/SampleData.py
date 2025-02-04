import pandas as pd
import numpy as np
import random

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

# 1. Generate Periods.csv
def generate_periods_csv():
    days = ['Red', 'Gold']
    periods = [1, 2, 3, 4]
    data = {'Day': [], 'Period': []}
    for day in days:
        for period in periods:
            data['Day'].append(day)
            data['Period'].append(period)
    periods_df = pd.DataFrame(data)
    periods_df.to_csv('Periods.csv', index=False)
    print("Periods.csv generated.")

# 2. Generate Courses.csv
def generate_courses_csv():
    departments = ['Math', 'English', 'Science', 'SocialScience']
    courses = []
    for dept in departments:
        for i in range(1, 3):  # 2 courses per department
            course_id = f"{dept[:3]}{i:02d}"
            course_name = f"{dept}Course{i}"
            sections = random.randint(1, 2)  # 1 to 2 sections per course
            is_lab_class = dept == 'Science' and random.choice([True, False])
            sped_limit = 12 if dept == 'SocialScience' and random.choice([True, False]) else np.nan
            courses.append({
                'CourseID': course_id,
                'CourseName': course_name,
                'Sections': sections,
                'IsLabClass': is_lab_class,
                'SPEDLimit': sped_limit
            })
    courses_df = pd.DataFrame(courses)
    courses_df.to_csv('Courses.csv', index=False)
    print("Courses.csv generated.")

# 3. Generate Teachers.csv
def generate_teachers_csv(courses_df):
    teachers = []
    teacher_id_counter = 1
    for index, row in courses_df.iterrows():
        num_teachers = row['Sections']
        for _ in range(num_teachers):
            teacher_id = f"T{teacher_id_counter}"
            teacher_name = f"Teacher_{teacher_id}"
            qualified_courses = row['CourseID']
            free_periods = ''
            special_status = False
            # Assign free periods or special status randomly
            if random.random() < 0.1:
                # 10% chance to have free periods
                day = random.choice(['Red', 'Gold'])
                period = random.randint(1, 4)
                free_periods = f"{day}-{period}"
            if random.random() < 0.05:
                # 5% chance to be a special teacher
                special_status = True
            teachers.append({
                'TeacherID': teacher_id,
                'TeacherName': teacher_name,
                'QualifiedCourses': qualified_courses,
                'FreePeriods': free_periods,
                'SpecialStatus': special_status
            })
            teacher_id_counter += 1
    teachers_df = pd.DataFrame(teachers)
    teachers_df.to_csv('Teachers.csv', index=False)
    print("Teachers.csv generated.")

# 4. Generate Students.csv
def generate_students_csv():
    num_students = 50  # Reduced number of students
    students = []
    for i in range(1, num_students + 1):
        student_id = f"S{i}"
        sped_status = random.choice([True, False, False, False])  # ~25% SPED students
        free_period_preference = random.choices(['AM', 'PM'], weights=[0.25, 0.75])[0]
        students.append({
            'StudentID': student_id,
            'SPEDStatus': sped_status,
            'FreePeriodPreference': free_period_preference
        })
    students_df = pd.DataFrame(students)
    students_df.to_csv('Students.csv', index=False)
    print("Students.csv generated.")

# 5. Generate StudentCourseSelections.csv
def generate_student_course_selections_csv(students_df, courses_df):
    selections = []
    grade_levels = ['Freshman', 'Sophomore', 'Junior', 'Senior']
    # Create a mapping from department to courses
    dept_course_map = {}
    for dept in courses_df['CourseName'].str.extract(r'(^[A-Za-z]+)', expand=False).unique():
        dept_courses = courses_df[courses_df['CourseName'].str.startswith(dept)]['CourseID'].tolist()
        dept_course_map[dept] = dept_courses

    mandatory_depts = ['Math', 'English', 'Science', 'SocialScience']
    for index, student in students_df.iterrows():
        student_id = student['StudentID']
        grade_level = random.choice(grade_levels)
        num_courses = 8 if grade_level in ['Freshman', 'Sophomore'] else 6
        selected_courses = set()
        # Mandatory courses
        for dept in mandatory_depts:
            dept_courses = dept_course_map.get(dept, [])
            if dept_courses:
                course = random.choice(dept_courses)
                selected_courses.add(course)
        # Electives (if any)
        elective_courses = [course for course_list in dept_course_map.values() for course in course_list]
        random.shuffle(elective_courses)
        for course in elective_courses:
            if len(selected_courses) >= num_courses:
                break
            selected_courses.add(course)
        # Add to selections
        for course_id in selected_courses:
            selections.append({
                'StudentID': student_id,
                'CourseID': course_id
            })
    selections_df = pd.DataFrame(selections)
    # Remove any duplicates just in case
    selections_df.drop_duplicates(subset=['StudentID', 'CourseID'], inplace=True)
    selections_df.to_csv('StudentCourseSelections.csv', index=False)
    print("StudentCourseSelections.csv generated.")

def main():
    # Generate CSV files
    generate_periods_csv()
    generate_courses_csv()
    courses_df = pd.read_csv('Courses.csv')
    generate_teachers_csv(courses_df)
    generate_students_csv()
    students_df = pd.read_csv('Students.csv')
    generate_student_course_selections_csv(students_df, courses_df)
    print("All CSV files have been generated.")

if __name__ == "__main__":
    main()
