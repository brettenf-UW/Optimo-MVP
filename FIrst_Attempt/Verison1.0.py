import pulp
import pandas as pd
from itertools import product

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
student_courses = student_courses_df.groupby('StudentID')['CourseID'].apply(list).to_dict()

# Decision variables for teacher assignments
x_keys = [
    (day, period, course, section, teacher)
    for (day, period) in total_periods
    for course in courses
    for section in sections[course]
    for teacher in teachers
    if course in teacher_qualifications.get(teacher, [])
]

x = pulp.LpVariable.dicts("x", x_keys, cat=pulp.LpBinary)

# Decision variables for student assignments
y_keys = [
    (day, period, course, section, student)
    for (day, period) in total_periods
    for course in courses
    for section in sections[course]
    for student in students
    if course in student_courses.get(student, [])
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
        problem += (
            pulp.lpSum(y[day, period, course, section, student]
                       for (day, period, course2, section, student2) in y_keys
                       if student2 == student and course2 == course) == 1,
            f"Student_{student}_Assigned_Once_To_{course}"
        )
    # Students cannot take more than one class in the same period
    for day, period in total_periods:
        problem += (
            pulp.lpSum(y[day, period, course, section, student]
                       for (d, p, course, section, s) in y_keys
                       if s == student and d == day and p == period) <= 1,
            f"Student_{student}_One_Class_Per_Period_{day}_{period}"
        )
    # Respect student preferences for free AM or PM periods
    free_pref = student_free_prefs.get(student)
    if free_pref == 'AM':
        for day in days:
            problem += (
                pulp.lpSum(y[day, periods[0], course, section, student]
                           for (d, p, course, section, s) in y_keys
                           if s == student and d == day and p == periods[0]) == 0,
                f"Student_{student}_Free_AM_Period_{day}"
            )
    elif free_pref == 'PM':
        for day in days:
            problem += (
                pulp.lpSum(y[day, periods[-1], course, section, student]
                           for (d, p, course, section, s) in y_keys
                           if s == student and d == day and p == periods[-1]) == 0,
                f"Student_{student}_Free_PM_Period_{day}"
            )

# Teacher Assignment Constraints
for teacher in teachers:
    # A teacher can only teach one section per period
    for day, period in total_periods:
        problem += (
            pulp.lpSum(x[day, period, course, section, teacher]
                       for (d, p, course, section, t) in x_keys
                       if t == teacher and d == day and p == period) <= 1,
            f"Teacher_{teacher}_One_Class_Per_Period_{day}_{period}"
        )
    # Respect teacher free periods
    for (day, period) in teacher_free_periods.get(teacher, []):
        problem += (
            pulp.lpSum(x[day, period, course, section, teacher]
                       for (d, p, course, section, t) in x_keys
                       if t == teacher and d == day and p == period) == 0,
            f"Teacher_{teacher}_Free_Period_{day}_{period}"
        )
    # Special teachers who only teach two periods back-to-back
    if teacher in special_teachers:
        for day in days:
            # Ensure the teacher teaches exactly two periods
            problem += (
                pulp.lpSum(x[day, period, course, section, teacher]
                           for period in periods
                           for course in courses
                           for section in sections[course]
                           if (day, period, course, section, teacher) in x_keys) == 2,
                f"Special_Teacher_{teacher}_Two_Periods_{day}"
            )

            # Create binary variables indicating whether the teacher teaches in each period
            t_p = {}
            for period in periods:
                t_p[period] = pulp.LpVariable(f"t_{teacher}_{day}_{period}", cat=pulp.LpBinary)
                problem += (
                    t_p[period] == pulp.lpSum(
                        x[day, period, course, section, teacher]
                        for course in courses
                        for section in sections[course]
                        if (day, period, course, section, teacher) in x_keys
                    ),
                    f"Teacher_{teacher}_Teaching_Period_{day}_{period}"
                )

            # Ensure the two periods are consecutive
            for period in periods:
                idx = periods.index(period)
                if idx == 0:
                    # First period
                    next_period = periods[idx + 1]
                    problem += (
                        t_p[period] <= t_p[next_period],
                        f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                    )
                elif idx == len(periods) - 1:
                    # Last period
                    prev_period = periods[idx - 1]
                    problem += (
                        t_p[period] <= t_p[prev_period],
                        f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                    )
                else:
                    # Middle periods
                    prev_period = periods[idx - 1]
                    next_period = periods[idx + 1]
                    problem += (
                        t_p[period] <= t_p[prev_period] + t_p[next_period],
                        f"Special_Teacher_{teacher}_Consecutive_{day}_{period}"
                    )

# Department Constraints
# Social Science: Student Government
for (day, period) in total_periods:
    if (day == 'Red' and period == 2) or (day == 'Gold' and period == 3):
        if 'StuGov' in courses and 'StuGov' in sections:
            problem += (
                pulp.lpSum(x[day, period, 'StuGov', section, teacher]
                           for teacher in teacher_qualifications
                           if 'StuGov' in teacher_qualifications[teacher]
                           for section in sections['StuGov']
                           if (day, period, 'StuGov', section, teacher) in x_keys) == 1,
                f"StudentGov_Scheduled_{day}_{period}"
            )
    else:
        if 'StuGov' in courses and 'StuGov' in sections:
            problem += (
                pulp.lpSum(x[day, period, 'StuGov', section, teacher]
                           for teacher in teacher_qualifications
                           if 'StuGov' in teacher_qualifications[teacher]
                           for section in sections['StuGov']
                           if (day, period, 'StuGov', section, teacher) in x_keys) == 0,
                f"StudentGov_Not_Scheduled_{day}_{period}"
            )

# World Language: Spanish scheduling
for day in days:
    if day == 'Red':
        spanish_course = 'Span1'
    else:
        spanish_course = 'Span2'
    if spanish_course in courses and spanish_course in sections:
        for period in periods:
            # Schedule the specified Spanish course
            problem += (
                pulp.lpSum(x[day, period, spanish_course, section, 'T7']
                           for section in sections[spanish_course]
                           if (day, period, spanish_course, section, 'T7') in x_keys) == 1,
                f"Spanish_{spanish_course}_Scheduled_{day}_{period}"
            )
        # Ensure the other Spanish course is not scheduled
        other_spanish = 'Span2' if spanish_course == 'Span1' else 'Span1'
        if other_spanish in courses and other_spanish in sections:
            for period in periods:
                problem += (
                    pulp.lpSum(x[day, period, other_spanish, section, 'T7']
                               for section in sections[other_spanish]
                               if (day, period, other_spanish, section, 'T7') in x_keys) == 0,
                    f"Spanish_{other_spanish}_Not_Scheduled_{day}_{period}"
                )

# Medical Department: Medical Career and Heroes Teach
medical_courses = {'Red': [('MedCar', 1), ('HerTeach', 2)], 'Gold': [('MedCar', 1), ('HerTeach', 2)]}
for day in days:
    for course_id, period in medical_courses[day]:
        if course_id in courses and course_id in sections:
            problem += (
                pulp.lpSum(x[day, period, course_id, section, 'T11']
                           for section in sections[course_id]
                           if (day, period, course_id, section, 'T11') in x_keys) == 1,
                f"MedicalCourse_{course_id}_Scheduled_{day}_{period}"
            )

# PE/Health: Male and Female teachers assigned for locker room coverage
for day, period in total_periods:
    if 'PE101' in courses and 'PE101' in sections:
        problem += (
            pulp.lpSum(x[day, period, 'PE101', section, 'T8']
                       for section in sections['PE101']
                       if (day, period, 'PE101', section, 'T8') in x_keys) >= 1,
            f"PE_Male_Teacher_{day}_{period}"
        )
        problem += (
            pulp.lpSum(x[day, period, 'PE101', section, 'T9']
                       for section in sections['PE101']
                       if (day, period, 'PE101', section, 'T9') in x_keys) >= 1,
            f"PE_Female_Teacher_{day}_{period}"
        )

# Science: Lab prep time between lab-based classes
lab_teachers = [teacher for teacher, qualified_courses in teacher_qualifications.items()
                if any(course in qualified_courses and is_lab_class.get(course, False) for course in courses)]
for teacher in lab_teachers:
    for day in days:
        for i in range(len(periods)-1):
            period1 = periods[i]
            period2 = periods[i+1]
            problem += (
                pulp.lpSum(x[day, period1, course, section, teacher]
                           for course in courses
                           if is_lab_class.get(course, False)
                           for section in sections[course]
                           if (day, period1, course, section, teacher) in x_keys) +
                pulp.lpSum(x[day, period2, course, section, teacher]
                           for course in courses
                           if is_lab_class.get(course, False)
                           for section in sections[course]
                           if (day, period2, course, section, teacher) in x_keys) <= 1,
                f"Lab_Prep_Time_{teacher}_{day}_{period1}_{period2}"
            )

# SPED Classes: Max 12 SPED students per co-taught class
sped_courses = [course for course in courses if course in sped_limits]
for course in sped_courses:
    for day, period in total_periods:
        for section in sections[course]:
            problem += (
                pulp.lpSum(y[day, period, course, section, student]
                           for student in students
                           if student_sped_status.get(student, False)
                           if (day, period, course, section, student) in y_keys) <= sped_limits[course],
                f"SPED_Limit_{course}_{day}_{period}_{section}"
            )

# Teacher Qualifications
for (day, period, course, section, teacher) in x_keys:
    if course not in teacher_qualifications.get(teacher, []):
        problem += x[day, period, course, section, teacher] == 0

# Student Assignment Consistency
for (day, period, course, section, student) in y_keys:
    problem += (
        y[day, period, course, section, student] <=
        pulp.lpSum(x[day, period, course, section, teacher]
                   for teacher in teachers
                   if (day, period, course, section, teacher) in x_keys),
        f"Student_{student}_Assigned_Only_If_Class_Taught_{day}_{period}_{course}_{section}"
    )

# Class Size Constraints
max_class_size = 30
min_class_size = 10
for (day, period, course, section) in set((day, period, course, section) for (day, period, course, section, student) in y_keys):
    num_students = pulp.lpSum(y[day, period, course, section, student]
                              for student in students
                              if (day, period, course, section, student) in y_keys)
    problem += num_students <= max_class_size
    problem += num_students >= min_class_size

# Solve the problem
problem.solve()

# Output the results
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
