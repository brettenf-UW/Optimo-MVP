import pandas as pd
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpBinary, LpStatus

# Load Data from CSV Files
# Students CSV: 'students.csv' with columns ['StudentID', 'GradeLevel', 'CourseRequests', 'FreePeriodPreference', 'SPED']
students_df = pd.read_csv('students.csv')

# Teachers CSV: 'teachers.csv' with columns ['TeacherID', 'Name', 'QualifiedCourses', 'AvailablePeriods', 'FreePeriods', 'SpecialConstraints']
teachers_df = pd.read_csv('teachers.csv')

# Courses CSV: 'courses.csv' with columns ['CourseID', 'CourseName', 'GradeLevels', 'Capacity', 'Department', 'SPED']
courses_df = pd.read_csv('courses.csv')

# Rooms CSV (Optional): 'rooms.csv' with columns ['RoomID', 'Capacity', 'LabBased']
# rooms_df = pd.read_csv('rooms.csv')

# Simulation Data Generation for Testing
# For the purpose of this example, let's generate simulation data programmatically
# Generate data for 1000 students, student-teacher ratio of 16:1
num_students = 1000
num_teachers = num_students // 16

# Generate Students Data
students_df = pd.DataFrame({
    'StudentID': range(1, num_students + 1),
    'GradeLevel': [9 + (i % 4) for i in range(num_students)],
    'CourseRequests': [['Course' + str(j) for j in range(1, 9)] for _ in range(num_students)],
    'FreePeriodPreference': ['AM' if i % 4 == 0 else 'PM' for i in range(num_students)],
    'SPED': [False for _ in range(num_students)]
})

# Generate Teachers Data
teachers_df = pd.DataFrame({
    'TeacherID': range(1, num_teachers + 1),
    'Name': ['Teacher' + str(i) for i in range(1, num_teachers + 1)],
    'QualifiedCourses': [['Course' + str(j) for j in range(1, 9)] for _ in range(num_teachers)],
    'AvailablePeriods': [['Red1', 'Red2', 'Red3', 'Red4', 'Gold1', 'Gold2', 'Gold3', 'Gold4'] for _ in range(num_teachers)],
    'FreePeriods': [[] for _ in range(num_teachers)],
    'SpecialConstraints': [None for _ in range(num_teachers)]
})

# Generate Courses Data
courses_df = pd.DataFrame({
    'CourseID': ['Course' + str(i) for i in range(1, 9)],
    'CourseName': ['Course' + str(i) for i in range(1, 9)],
    'GradeLevels': [[9, 10, 11, 12] for _ in range(8)],
    'Capacity': [30 for _ in range(8)],
    'Department': ['Department' + str(i % 5) for i in range(1, 9)],
    'SPED': [False for _ in range(8)]
})

# Define Sets
students = students_df['StudentID'].tolist()
teachers = teachers_df['TeacherID'].tolist()
courses = courses_df['CourseID'].tolist()
periods = ['Red1', 'Red2', 'Red3', 'Red4', 'Gold1', 'Gold2', 'Gold3', 'Gold4']
days = ['Red', 'Gold']

# Decision Variables
# x[s, c, p]: 1 if student s is assigned to course c in period p, 0 otherwise
x = LpVariable.dicts('x', ((s, c, p) for s in students for c in courses for p in periods), cat=LpBinary)

# y[t, c, p]: 1 if teacher t teaches course c in period p, 0 otherwise
y = LpVariable.dicts('y', ((t, c, p) for t in teachers for c in courses for p in periods), cat=LpBinary)

# Initialize the Problem
prob = LpProblem("Chico_High_School_Scheduling", LpMinimize)

# Objective Function
# Since we are only interested in feasibility, we can set the objective to minimize the number of unmet requests
# Let's define a variable for unmet requests
unmet_requests = LpVariable.dicts('unmet', (s for s in students), cat=LpBinary)
prob += lpSum(unmet_requests[s] for s in students)

# Constraints

# 1. Each student must be assigned to one section of each of their requested courses
for s in students:
    requested_courses = students_df.loc[students_df['StudentID'] == s, 'CourseRequests'].values[0]
    for c in requested_courses:
        prob += lpSum(x[s, c, p] for p in periods) == 1, f"Student_{s}_Course_{c}_Assignment"
    # Unmet request if not all courses are assigned
    prob += unmet_requests[s] >= 1 - lpSum(x[s, c, p] for c in requested_courses for p in periods) / len(requested_courses)

# 2. Students cannot be assigned to multiple courses in the same period
for s in students:
    for p in periods:
        prob += lpSum(x[s, c, p] for c in courses) <= 1, f"Student_{s}_Period_{p}_OneCourse"

# 3. Teachers cannot teach multiple courses in the same period
for t in teachers:
    for p in periods:
        prob += lpSum(y[t, c, p] for c in courses) <= 1, f"Teacher_{t}_Period_{p}_OneCourse"

# 4. Teachers can only teach courses they are qualified for
for t in teachers:
    qualified_courses = teachers_df.loc[teachers_df['TeacherID'] == t, 'QualifiedCourses'].values[0]
    for c in courses:
        if c not in qualified_courses:
            for p in periods:
                prob += y[t, c, p] == 0, f"Teacher_{t}_NotQualified_{c}_{p}"

# 5. Teachers have designated free periods
for t in teachers:
    free_periods = teachers_df.loc[teachers_df['TeacherID'] == t, 'FreePeriods'].values[0]
    for p in free_periods:
        for c in courses:
            prob += y[t, c, p] == 0, f"Teacher_{t}_FreePeriod_{p}"

# 6. Special Department Constraints
# Example: "Student Government" must be scheduled during Red2 and Gold3
for c in ['Student Government']:
    for p in periods:
        if p not in ['Red2', 'Gold3']:
            for t in teachers:
                prob += y[t, c, p] == 0, f"StudentGov_NotIn_{p}"
    # Ensure that it is scheduled in those periods
    prob += lpSum(y[t, c, 'Red2'] for t in teachers) >= 1, f"StudentGov_Red2_Scheduled"
    prob += lpSum(y[t, c, 'Gold3'] for t in teachers) >= 1, f"StudentGov_Gold3_Scheduled"

# 7. PE Coverage: Ensure male and female teachers are assigned to each PE period
# Assuming we have gender information in teachers_df
# For simplicity, let's assume we have male_teachers and female_teachers lists
male_teachers = teachers_df[teachers_df['Name'].str.contains('Male')]['TeacherID'].tolist()
female_teachers = teachers_df[teachers_df['Name'].str.contains('Female')]['TeacherID'].tolist()
for p in periods:
    prob += lpSum(y[t, 'PE', p] for t in male_teachers) >= 1, f"PE_Male_Coverage_{p}"
    prob += lpSum(y[t, 'PE', p] for t in female_teachers) >= 1, f"PE_Female_Coverage_{p}"

# 8. Science Teachers need prep time between different lab-based classes
lab_courses = ['Biology', 'Chemistry']
for t in teachers:
    for i in range(len(periods) - 1):
        p1 = periods[i]
        p2 = periods[i + 1]
        for c1 in lab_courses:
            for c2 in lab_courses:
                if c1 != c2:
                    prob += y[t, c1, p1] + y[t, c2, p2] <= 1, f"SciencePrep_{t}_{c1}_{p1}_{c2}_{p2}"

# 9. SPED Classes: Max 12 SPED students per co-taught class
sped_courses = courses_df[courses_df['SPED'] == True]['CourseID'].tolist()
for c in sped_courses:
    for p in periods:
        prob += lpSum(x[s, c, p] for s in students_df[students_df['SPED'] == True]['StudentID']) <= 12, f"SPED_Max_{c}_{p}"

# 10. Class Capacities
for c in courses:
    capacity = courses_df.loc[courses_df['CourseID'] == c, 'Capacity'].values[0]
    for p in periods:
        prob += lpSum(x[s, c, p] for s in students) <= capacity, f"Capacity_{c}_{p}"

# 11. Avoid Conflicting Classes: Neither students nor teachers can have two classes in the same period
# Already handled in constraints 2 and 3

# 12. Red and Gold Day Consistency: Students have no more than 4 classes on Red or Gold days
for s in students:
    for day in days:
        day_periods = [p for p in periods if day in p]
        prob += lpSum(x[s, c, p] for c in courses for p in day_periods) <= 4, f"MaxClasses_{s}_{day}"

# Solve the Problem
prob.solve()

# Output the Master Schedule
master_schedule = []
for t in teachers:
    for c in courses:
        for p in periods:
            if y[t, c, p].varValue == 1:
                master_schedule.append({'TeacherID': t, 'CourseID': c, 'Period': p})

master_schedule_df = pd.DataFrame(master_schedule)
print("Master Schedule:")
print(master_schedule_df)

# Output Students Who Did Not Get Requested Classes
students_unmet_requests = []
for s in students:
    if unmet_requests[s].varValue == 1:
        students_unmet_requests.append({'StudentID': s, 'UnmetRequests': students_df.loc[students_df['StudentID'] == s, 'CourseRequests'].values[0]})

students_unmet_requests_df = pd.DataFrame(students_unmet_requests)
print("\nStudents Without All Requested Courses:")
print(students_unmet_requests_df)
