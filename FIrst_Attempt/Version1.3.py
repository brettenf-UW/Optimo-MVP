import pandas as pd
import numpy as np
import pulp

# Preprocessing before initiating the linear program

# Load data from CSV files
students_df = pd.read_csv('students.csv')
teachers_df = pd.read_csv('teachers.csv')
courses_df = pd.read_csv('courses.csv')

# Preprocess the data

# 1. Separate out free periods and filter invalid course requests
students_cleaned = []
for index, row in students_df.iterrows():
    requested_courses = row['course_requests'].split(',')
    free_periods = [course for course in requested_courses if 'Free' in course]
    valid_courses = [course for course in requested_courses if course in courses_df['course_id'].tolist()]

    # Remove duplicates
    valid_courses = list(set(valid_courses))

    students_cleaned.append({
        'student_id': row['student_id'],
        'grade_level': row['grade_level'],
        'gender': row['gender'],
        'free_period_preference': row['free_period_preference'],
        'course_requests': ','.join(valid_courses),
        'free_periods': free_periods,  # Store free periods separately for special handling
        'sped_status': row['sped_status']
    })

students_df_cleaned = pd.DataFrame(students_cleaned)

# 2. Pre-check capacity constraints and potential oversubscription

# Ensure 'SS001' is in the courses list
courses = courses_df['course_id'].tolist()
if 'SS001' not in courses:
    courses.append('SS001')

# Pre-check capacity constraints and potential oversubscription

# Create course capacity dictionary considering the number of sections
course_capacity = (courses_df.set_index('course_id')['capacity'] * courses_df.set_index('course_id')['sections']).to_dict()

# Check if any courses are oversubscribed by counting course requests
course_demand = students_df_cleaned['course_requests'].str.split(',').explode().value_counts()

# Debugging: Print course_capacity and course_demand to verify
print("Course Capacity:", course_capacity)
print("Course Demand:", course_demand)

# Align the course demand index with the course capacity
course_capacity_series = pd.Series(course_capacity).reindex(course_demand.index).fillna(0)

# Debugging: Print course_capacity_series to verify
print("Course Capacity Series:", course_capacity_series)

# Compare the demand with capacity
oversubscribed_courses = course_demand[course_demand > course_capacity_series]

if not oversubscribed_courses.empty:
    print("Oversubscribed courses detected:", oversubscribed_courses)
    # Handle oversubscribed courses here by adjusting sections, splitting students, or other mechanisms

# 3. Ensure teachers are only assigned to valid courses and periods
teachers_cleaned = []
for index, row in teachers_df.iterrows():
    try:
        # Convert available_periods to a list of integers for efficiency
        available_periods = [int(p) for p in row['available_periods'].split(',') if p.isdigit()]
    except AttributeError:
        # Handle cases where available_periods is not a string
        available_periods = []

    # Ensure that teachers are only teaching courses they are qualified for
    qualified_courses = courses_df[courses_df['department'] == row['department']]['course_id'].tolist()

    teachers_cleaned.append({
        'teacher_id': row['teacher_id'],
        'department': row['department'],
        'gender': row['gender'],
        'assigned_sections': row['assigned_sections'],
        'available_periods': available_periods,  # Now a list of integers
        'qualified_courses': qualified_courses,
        'sped_teacher': row['sped_teacher']
    })
# Create the LP problem
prob = pulp.LpProblem("Chico_High_School_Master_Schedule", pulp.LpMaximize)

students = students_df_cleaned['student_id'].tolist()
teachers = teachers_df_cleaned['teacher_id'].tolist()
periods = list(range(1, 9))

student_requests = students_df_cleaned.set_index('student_id')['course_requests'].to_dict()
student_free_periods = students_df_cleaned.set_index('student_id')['free_periods'].to_dict()
student_grade = students_df_cleaned.set_index('student_id')['grade_level'].to_dict()
student_sped_status = students_df_cleaned.set_index('student_id')['sped_status'].to_dict()
teacher_dept = teachers_df_cleaned.set_index('teacher_id')['department'].to_dict()
teacher_available_periods = teachers_df_cleaned.set_index('teacher_id')['available_periods'].to_dict()
teacher_gender = teachers_df_cleaned.set_index('teacher_id')['gender'].to_dict()
teacher_sped = teachers_df_cleaned.set_index('teacher_id')['sped_teacher'].to_dict()
course_sections = courses_df.set_index('course_id')['sections'].to_dict()
course_capacity = courses_df.set_index('course_id')['capacity'].to_dict()
course_department = courses_df.set_index('course_id')['department'].to_dict()
course_co_taught = courses_df.set_index('course_id')['co_taught'].to_dict()
course_grade_levels = courses_df.set_index('course_id')['grade_levels'].to_dict()

dept_courses = courses_df.groupby('department')['course_id'].apply(list).to_dict()
teacher_qualified_courses = teachers_df_cleaned.set_index('teacher_id')['qualified_courses'].to_dict()

requested_courses = {}
for s in students:
    courses_requested = student_requests[s].split(',')
    requested_courses[s] = courses_requested

students_by_course = {}
for s in students:
    for c in requested_courses[s]:
        if c not in students_by_course:
            students_by_course[c] = set()
        students_by_course[c].add(s)

x_vars = pulp.LpVariable.dicts(
    "student_course_period",
    ((s, c, p) for s in students for c in requested_courses[s] for p in periods),
    cat='Binary'
)

y_vars = pulp.LpVariable.dicts(
    "teacher_course_period",
    ((t, c, p) for t in teachers for c in teacher_qualified_courses[t] for p in teacher_available_periods[t]),
    cat='Binary'
)

z_vars = pulp.LpVariable.dicts("course_period", ((c, p) for c in courses for p in periods), cat='Binary')

# Debugging: Print the keys of z_vars to verify
print("z_vars keys:", list(z_vars.keys()))

# Constraint: Schedule "Student Government" during Red period 2 and Gold period 3
prob += (z_vars['SS001', 2] == 1), "StudentGovernment_RedPeriod2"
prob += (z_vars['SS001', 7] == 1), "StudentGovernment_GoldPeriod3"

# Constraint: Schedule "Medical Career" during Red period 1 and Gold period 1
prob += z_vars['MD001', 1] == 1, "MedicalCareer_RedPeriod1"
prob += z_vars['MD001', 5] == 1, "MedicalCareer_GoldPeriod1"

# Constraint: Schedule "Heroes Teach" during Red period 2 and Gold period 2
prob += z_vars['MD002', 2] == 1, "HeroesTeach_RedPeriod2"
prob += z_vars['MD002', 6] == 1, "HeroesTeach_GoldPeriod2"
cat='Binary'

# Decision variables for course scheduling in periods
z_vars = pulp.LpVariable.dicts("course_period", ((c, p) for c in courses for p in periods), cat='Binary')

# Objective function: Maximize the total number of requested courses assigned to students
prob += pulp.lpSum(
    x_vars[s, c, p] for s in students for c in requested_courses[s] for p in periods
), "Maximize_Assigned_Courses"

# Constraint: Students can only be in one course per period
for s in students:
    for p in periods:
        prob += pulp.lpSum(
            x_vars[s, c, p] for c in requested_courses[s]
        ) <= 1, f"Student_{s}_Period_{p}_OneCourse"

# Constraint: Total scheduled periods for a course equals the number of sections
for c in courses:
    prob += pulp.lpSum(
        z_vars[c, p] for p in periods
    ) == course_sections[c], f"Course_{c}_SectionCount"

# Constraint: Students can only be assigned to courses scheduled in that period
for s in students:
    for c in requested_courses[s]:
        for p in periods:
            prob += x_vars[s, c, p] <= z_vars[c, p], f"Student_{s}_Course_{c}_Period_{p}_OnlyScheduledCourses"

# Constraint: Course capacity per period
for c in courses:
    for p in periods:
        if c in students_by_course:
            prob += pulp.lpSum(
                x_vars[s, c, p] for s in students_by_course[c]
            ) <= course_capacity[c], f"Course_{c}_Period_{p}_Capacity"
        else:
            # No students requested this course
            prob += 0 <= course_capacity[c], f"Course_{c}_Period_{p}_Capacity"

# Constraint: Teachers can only teach one course per period
for t in teachers:
    for p in teacher_available_periods[t]:
        prob += pulp.lpSum(
            y_vars[t, c, p] for c in teacher_qualified_courses[t]
        ) <= 1, f"Teacher_{t}_Period_{p}_OneCourse"

# Constraint: Each scheduled course must have at least one teacher assigned
for c in courses:
    for p in periods:
        prob += z_vars[c, p] <= pulp.lpSum(
            y_vars[t, c, p] for t in teachers if c in teacher_qualified_courses[t] and p in teacher_available_periods[t]
        ), f"Course_{c}_Period_{p}_TeacherAssigned"

# Constraint: Students cannot have more than 4 classes on a single day (Red Day)
for s in students:
    prob += pulp.lpSum(
        x_vars[s, c, p] for c in requested_courses[s] for p in [1, 2, 3, 4]
    ) <= 4, f"Student_{s}_RedDay_Max4Classes"

# Constraint: Students cannot have more than 4 classes on a single day (Gold Day)
for s in students:
    prob += pulp.lpSum(
        x_vars[s, c, p] for c in requested_courses[s] for p in [5, 6, 7, 8]
    ) <= 4, f"Student_{s}_GoldDay_Max4Classes"

# Constraint: Student free period preferences
for s in students:
    # Get the student's free periods from preprocessing
    free_periods = student_free_periods[s]
    if 'Free First Period' in free_periods:
        # Ensure no courses are assigned during first periods (1 and 5)
        for p in [1, 5]:
            prob += pulp.lpSum(
                x_vars[s, c, p] for c in requested_courses[s]
            ) == 0, f"Student_{s}_FreeFirstPeriod_{p}"
    if 'Free Fourth Period' in free_periods:
        # Ensure no courses are assigned during fourth periods (4 and 8)
        for p in [4, 8]:
            prob += pulp.lpSum(
                x_vars[s, c, p] for c in requested_courses[s]
            ) == 0, f"Student_{s}_FreeFourthPeriod_{p}"

# Constraint: Schedule "Student Government" during Red period 2 and Gold period 3
prob += (z_vars['SS001', 2] == 1), "StudentGovernment_RedPeriod2"
prob += (z_vars['SS001', 7] == 1), "StudentGovernment_GoldPeriod3"

# Constraint: Schedule "Medical Career" during Red period 1 and Gold period 1
prob += z_vars['MD001', 1] == 1, "MedicalCareer_RedPeriod1"
prob += z_vars['MD001', 5] == 1, "MedicalCareer_GoldPeriod1"

# Constraint: Schedule "Heroes Teach" during Red period 2 and Gold period 2
prob += z_vars['MD002', 2] == 1, "HeroesTeach_RedPeriod2"
prob += z_vars['MD002', 6] == 1, "HeroesTeach_GoldPeriod2"

# Constraint: Assign male and female PE teachers to each PE period
pe_courses = courses_df[courses_df['department'] == 'PE/Health']['course_id'].tolist()
pe_teachers = teachers_df_cleaned[teachers_df_cleaned['department'] == 'PE/Health']
male_pe_teachers = pe_teachers[pe_teachers['gender'] == 'M']['teacher_id'].tolist()
female_pe_teachers = pe_teachers[pe_teachers['gender'] == 'F']['teacher_id'].tolist()

for c in pe_courses:
    for p in periods:
        # Ensure a male PE teacher is assigned if the course is scheduled
        prob += pulp.lpSum(
            y_vars[t, c, p] for t in male_pe_teachers if p in teacher_available_periods[t]
        ) >= z_vars[c, p], f"PECourse_{c}_Period_{p}_MaleTeacher"
        # Ensure a female PE teacher is assigned if the course is scheduled
        prob += pulp.lpSum(
            y_vars[t, c, p] for t in female_pe_teachers if p in teacher_available_periods[t]
        ) >= z_vars[c, p], f"PECourse_{c}_Period_{p}_FemaleTeacher"

# Constraint: Limit SPED students in co-taught classes to 12
co_taught_courses = courses_df[courses_df['co_taught'] == 'Yes']['course_id'].tolist()
sped_students = [s for s in students if student_sped_status[s] == 'Yes']

for c in co_taught_courses:
    for p in periods:
        if c in students_by_course:
            prob += pulp.lpSum(
                x_vars[s, c, p] for s in sped_students if s in students_by_course[c]
            ) <= 12 * z_vars[c, p], f"CoTaughtCourse_{c}_Period_{p}_SPEDCapacity"
        else:
            # No students requested this course
            prob += 0 <= 12 * z_vars[c, p], f"CoTaughtCourse_{c}_Period_{p}_SPEDCapacity"

# Constraint: Science teachers need prep breaks between different lab courses
science_teachers = teachers_df_cleaned[teachers_df_cleaned['department'] == 'Science']['teacher_id'].tolist()

for t in science_teachers:
    for p in [1, 2, 3, 4, 5, 6, 7]:
        # Ensure not teaching different courses back-to-back on the same day
        # Only consider periods that are on the same day
        if (p <= 4 and p + 1 <= 4) or (p >= 5 and p + 1 <= 8 and p + 1 >= 5):
            for c1 in teacher_qualified_courses[t]:
                for c2 in teacher_qualified_courses[t]:
                    if c1 != c2:
                        # Use y_vars.get() to handle missing keys
                        prob += y_vars.get((t, c1, p), 0) + y_vars.get((t, c2, p + 1), 0) <= 1, \
                            f"ScienceTeacher_{t}_NoBackToBack_{p}_{p + 1}_{c1}_{c2}"

# Solve the LP problem
prob.solve()

print("Status:", pulp.LpStatus[prob.status])

# Check if the problem is feasible
if pulp.LpStatus[prob.status] == 'Optimal':
    # Extract student schedules
    student_schedule = []
    for s in students:
        for c in requested_courses[s]:
            for p in periods:
                if pulp.value(x_vars[s, c, p]) == 1:
                    student_schedule.append({'student_id': s, 'course_id': c, 'period': p})

    student_schedule_df = pd.DataFrame(student_schedule)

    # Extract teacher schedules
    teacher_schedule = []
    for t in teachers:
        for c in teacher_qualified_courses[t]:
            for p in teacher_available_periods[t]:
                if pulp.value(y_vars.get((t, c, p), 0)) == 1:
                    teacher_schedule.append({'teacher_id': t, 'course_id': c, 'period': p})

    teacher_schedule_df = pd.DataFrame(teacher_schedule)

    # Identify students who did not receive all requested courses
    students_unassigned_courses = []
    for s in students:
        requested = set(requested_courses[s])
        assigned = set(student_schedule_df[student_schedule_df['student_id'] == s]['course_id'].tolist())
        unassigned = requested - assigned
        if unassigned:
            students_unassigned_courses.append({'student_id': s, 'unassigned_courses': ','.join(unassigned)})

    students_unassigned_courses_df = pd.DataFrame(students_unassigned_courses)

    # Save the master schedule and unassigned students to CSV
    student_schedule_df.to_csv('student_schedule.csv', index=False)
    teacher_schedule_df.to_csv('teacher_schedule.csv', index=False)
    students_unassigned_courses_df.to_csv('students_unassigned_courses.csv', index=False)

    # Print the number of students without all requested courses
    print(f"Number of students without all requested courses: {len(students_unassigned_courses_df)}")
else:
    print("No feasible solution found. The problem may be infeasible due to oversubscription or conflicting constraints.")
