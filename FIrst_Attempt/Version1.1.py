import pulp
import pandas as pd
from itertools import product
import time

start_time = time.time()

# Load data from CSV files
periods_df = pd.read_csv('Periods.csv')
courses_df = pd.read_csv('Courses.csv')
teachers_df = pd.read_csv('Teachers.csv')
students_df = pd.read_csv('Students.csv')
student_courses_df = pd.read_csv('StudentCourseSelections.csv')

# Preprocess data
# Days and periods
days = periods_df['Day'].unique().tolist()
periods = sorted(periods_df['Period'].unique().tolist())
total_periods = list(periods_df.itertuples(index=False, name=None))

# Courses and sections
courses = courses_df['CourseID'].tolist()
sections = {row.CourseID: list(range(1, int(row.Sections) + 1)) for row in courses_df.itertuples()}
is_lab_class = {row.CourseID: row.IsLabClass for row in courses_df.itertuples()}
sped_limits = {row.CourseID: row.SPEDLimit for row in courses_df.itertuples() if not pd.isna(row.SPEDLimit)}

# Teachers and qualifications
teachers = teachers_df['TeacherID'].tolist()
teacher_qualifications = {}
teacher_free_periods = {}
special_teachers = []
for row in teachers_df.itertuples():
    qualified_courses = row.QualifiedCourses.split('|') if pd.notna(row.QualifiedCourses) else []
    teacher_qualifications[row.TeacherID] = qualified_courses
    if pd.notna(row.FreePeriods) and row.FreePeriods != '':
        free_periods = [tuple(fp.split('-')) for fp in row.FreePeriods.split('|')]
        teacher_free_periods[row.TeacherID] = [(day, int(period)) for day, period in free_periods]
    else:
        teacher_free_periods[row.TeacherID] = []
    if row.SpecialStatus:
        special_teachers.append(row.TeacherID)

# Students and their attributes
students = students_df['StudentID'].tolist()
student_sped_status = students_df.set_index('StudentID')['SPEDStatus'].to_dict()
student_free_prefs = students_df.set_index('StudentID')['FreePeriodPreference'].to_dict()

# Student course selections
student_courses = student_courses_df.groupby('StudentID')['CourseID'].apply(set).to_dict()

# Preprocess to reduce variables
# Create sets of possible assignments to reduce the number of variables
# Only create variables for feasible assignments

# Map course to students who selected it
course_students = {}
for course in courses:
    course_students[course] = set()
for student, courses_selected in student_courses.items():
    for course in courses_selected:
        course_students[course].add(student)

# Map course to qualified teachers
course_teachers = {}
for course in courses:
    course_teachers[course] = set()
    for teacher in teachers:
        if course in teacher_qualifications.get(teacher, []):
            course_teachers[course].add(teacher)

# Possible teacher assignments
x_keys = [
    (day, period, course, section, teacher)
    for (day, period) in total_periods
    for course in courses
    for section in sections[course]
    for teacher in course_teachers[course]
    if (day, period) not in teacher_free_periods.get(teacher, [])
]
x_key_set = set(x_keys)

x = pulp.LpVariable.dicts("x", x_keys, cat=pulp.LpBinary)

# Possible student assignments
y_keys = [
    (day, period, course, section, student)
    for (day, period) in total_periods
    for course in courses
    for section in sections[course]
    for student in course_students[course]
    if not (
        (student_free_prefs.get(student) == 'AM' and period == periods[0]) or
        (student_free_prefs.get(student) == 'PM' and period == periods[-1])
    )
]

y = pulp.LpVariable.dicts("y", y_keys, cat=pulp.LpBinary)

# Initialize the problem
problem = pulp.LpProblem("Chico_High_School_Scheduling", pulp.LpMaximize)

# Objective Function: Maximize total student satisfaction
problem += pulp.lpSum(y.values()), "Total_Student_Satisfaction"

# Constraints

# Student Assignment Constraints
for student in students:
    # Each student must be assigned to one section of each of their chosen courses
    for course in student_courses.get(student, []):
        # Collect possible assignments for this student and course
        possible_assignments = [
            y[day, period, course, section, student]
            for (day, period, course2, section, student2) in y_keys
            if student2 == student and course2 == course
        ]
        if possible_assignments:
            problem += (
                pulp.lpSum(possible_assignments) == 1,
                f"Student_{student}_Assigned_Once_To_{course}"
            )
    # Students cannot take more than one class in the same period
    for day, period in total_periods:
        possible_assignments = [
            y[day, period, course, section, student]
            for (d, p, course, section, s) in y_keys
            if s == student and d == day and p == period
        ]
        if possible_assignments:
            problem += (
                pulp.lpSum(possible_assignments) <= 1,
                f"Student_{student}_One_Class_Per_Period_{day}_{period}"
            )

# Teacher Assignment Constraints
for teacher in teachers:
    # A teacher can only teach one section per period
    for day, period in total_periods:
        possible_assignments = [
            x[day, period, course, section, teacher]
            for (d, p, course, section, t) in x_keys
            if t == teacher and d == day and p == period
        ]
        if possible_assignments:
            problem += (
                pulp.lpSum(possible_assignments) <= 1,
                f"Teacher_{teacher}_One_Class_Per_Period_{day}_{period}"
            )
    # Special teachers who only teach two periods back-to-back
    if teacher in special_teachers:
        for day in days:
            # Ensure the teacher teaches exactly two periods
            possible_assignments = [
                x[day, period, course, section, teacher]
                for period in periods
                for course in courses
                for section in sections[course]
                if (day, period, course, section, teacher) in x_key_set
            ]
            if possible_assignments:
                problem += (
                    pulp.lpSum(possible_assignments) == 2,
                    f"Special_Teacher_{teacher}_Two_Periods_{day}"
                )

                # Create binary variables indicating whether the teacher teaches in each period
                t_p = {}
                for period in periods:
                    var_name = f"t_{teacher}_{day}_{period}"
                    t_p[period] = pulp.LpVariable(var_name, cat=pulp.LpBinary)
                    # Set t_p[period] to 1 if teacher teaches in that period
                    possible_period_assignments = [
                        x[day, period, course, section, teacher]
                        for course in courses
                        for section in sections[course]
                        if (day, period, course, section, teacher) in x_key_set
                    ]
                    if possible_period_assignments:
                        problem += (
                            t_p[period] == pulp.lpSum(possible_period_assignments),
                            f"Teacher_{teacher}_Teaching_Period_{day}_{period}"
                        )
                    else:
                        problem += t_p[period] == 0
                # Ensure the two periods are consecutive
                for idx, period in enumerate(periods):
                    if idx == 0:
                        next_period = periods[idx + 1]
                        problem += (
                            t_p[period] <= t_p[next_period],
                            f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                        )
                    elif idx == len(periods) - 1:
                        prev_period = periods[idx - 1]
                        problem += (
                            t_p[period] <= t_p[prev_period],
                            f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                        )
                    else:
                        prev_period = periods[idx - 1]
                        next_period = periods[idx + 1]
                        problem += (
                            t_p[period] <= t_p[prev_period] + t_p[next_period],
                            f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                        )

# Student Assignment Consistency
# Students can only be assigned to classes that are taught
for (day, period, course, section, student) in y_keys:
    teacher_assignments = [
        x[day, period, course, section, teacher]
        for teacher in teachers
        if (day, period, course, section, teacher) in x_key_set
    ]
    if teacher_assignments:
        problem += (
            y[day, period, course, section, student] <= pulp.lpSum(teacher_assignments),
            f"Student_{student}_Assigned_Only_If_Class_Taught_{day}_{period}_{course}_{section}"
        )
    else:
        # No teacher assigned; student cannot be assigned
        problem += y[day, period, course, section, student] == 0

# Class Size Constraints
max_class_size = 30
min_class_size = 10
class_sections = set((day, period, course, section) for (day, period, course, section, student) in y_keys)
for (day, period, course, section) in class_sections:
    num_students = pulp.lpSum(
        y[day, period, course, section, student]
        for student in students
        if (day, period, course, section, student) in y_keys
    )
    problem += num_students <= max_class_size
    problem += num_students >= min_class_size

# Optional: Reduce the number of constraints by grouping similar ones

# Solve the problem
solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=600)  # Set a time limit of 10 minutes
problem.solve(solver)

end_time = time.time()
print(f"Solver Status: {pulp.LpStatus[problem.status]}")
print(f"Total Time Taken: {end_time - start_time:.2f} seconds")
print("Objective Value (Total Satisfaction):", pulp.value(problem.objective))

# Output master schedule in a digestible format
# Create DataFrames for teacher assignments and student schedules

# Teacher assignments
teacher_schedule = []
for (day, period, course, section, teacher) in x_keys:
    if x[day, period, course, section, teacher].varValue == 1:
        teacher_schedule.append({
            'Day': day,
            'Period': period,
            'Course': course,
            'Section': section,
            'Teacher': teacher
        })

# Special Department Constraints

# Constraint: 'Student Government' must be scheduled during Red period 2 and Gold period 3
if 'Student Government' in courses:
    # Ensure 'Student Government' is only scheduled during the specified periods
    for day, period in total_periods:
        if not ((day == 'Red' and period == 2) or (day == 'Gold' and period == 3)):
            # For all other periods, set assignment variables to 0
            for section in sections['Student Government']:
                for teacher in course_teachers['Student Government']:
                    if (day, period, 'Student Government', section, teacher) in x_key_set:
                        problem += (
                            x[day, period, 'Student Government', section, teacher] == 0,
                            f"StudentGovernment_Not_Scheduled_{day}_{period}_{section}_{teacher}"
                        )
    # Ensure that 'Student Government' is scheduled during the specified periods
    for (day, period) in [('Red', 2), ('Gold', 3)]:
        for section in sections['Student Government']:
            teacher_assignments = [
                x[day, period, 'Student Government', section, teacher]
                for teacher in course_teachers['Student Government']
                if (day, period, 'Student Government', section, teacher) in x_key_set
            ]
            problem += (
                pulp.lpSum(teacher_assignments) == 1,
                f"StudentGovernment_Scheduled_{day}_{period}_{section}"
            )

teacher_schedule_df = pd.DataFrame(teacher_schedule)
print("\nTeacher Schedule:")
print(teacher_schedule_df)

# Student schedules
student_schedule = []
for (day, period, course, section, student) in y_keys:
    if y[day, period, course, section, student].varValue == 1:
        student_schedule.append({
            'StudentID': student,
            'Day': day,
            'Period': period,
            'Course': course,
            'Section': section
        })
student_schedule_df = pd.DataFrame(student_schedule)
print("\nSample Student Schedules:")
# Display schedules for first 5 students
for student in students[:5]:
    sched = student_schedule_df[student_schedule_df['StudentID'] == student]
    print(f"\nSchedule for Student {student}:")
    print(sched.sort_values(['Day', 'Period']))
