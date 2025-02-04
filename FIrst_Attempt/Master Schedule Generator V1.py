import pulp
import random
from itertools import product

# Initialize the problem
problem = pulp.LpProblem("Class_Scheduling_Problem", pulp.LpMaximize)

# Define periods, classes, sections, teachers, and students
periods = [1, 2, 3, 4, 5, 6]
classes = ['Math103', 'Eng101']
sections = {
    'Math103': [1, 2, 3],
    'Eng101': [1, 2]
}
teachers = ['Teacher1', 'Teacher2', 'Teacher3']
students = ['Student1', 'Student2', 'Student3']

# Student preferences
student_class_preferences = {
    'Student1': ['Math103', 'Eng101'],
    'Student2': ['Math103'],
    'Student3': ['Eng101']
}

# Teacher qualifications
qualified_teacher = {
    'Math103': ['Teacher1', 'Teacher2'],
    'Eng101': ['Teacher3']
}

# Decision variables
# Create a list of valid keys for x and y using list comprehensions
x_keys = [
    (p, cls, sec, t)
    for p in periods
    for cls in classes
    for sec in sections[cls]
    for t in teachers
    if t in qualified_teacher[cls]  # Only include qualified teachers
]

x = pulp.LpVariable.dicts("x", x_keys, cat=pulp.LpBinary)

y_keys = [
    (p, cls, sec, st)
    for p in periods
    for cls in classes
    for sec in sections[cls]
    for st in students
    if cls in student_class_preferences.get(st, [])  # Only include preferred classes
]

y = pulp.LpVariable.dicts("y", y_keys, cat=pulp.LpBinary)

# Objective function: Maximize overall student satisfaction
problem += pulp.lpSum(y.values()), "Total_Student_Satisfaction"

# Constraints

# Each student is assigned to one section of each preferred class
for st in students:
    for cls in student_class_preferences.get(st, []):
        problem += (
            pulp.lpSum(
                y[p, cls, sec, st]
                for p, cls2, sec, st2 in y_keys
                if st2 == st and cls2 == cls
            ) == 1,
            f"Student_{st}_Assigned_Once_To_{cls}"
        )

# Each teacher teaches at most one section per period
for p in periods:
    for t in teachers:
        problem += (
            pulp.lpSum(
                x[p2, cls, sec, t2]
                for p2, cls, sec, t2 in x_keys
                if p2 == p and t2 == t
            ) <= 1,
            f"Teacher_{t}_One_Class_Period_{p}"
        )

# Each student attends at most one class per period
for p in periods:
    for st in students:
        problem += (
            pulp.lpSum(
                y[p2, cls, sec, st2]
                for p2, cls, sec, st2 in y_keys
                if p2 == p and st2 == st
            ) <= 1,
            f"Student_{st}_One_Class_Period_{p}"
        )

# Teacher assignment validity: A teacher can only be assigned if students are enrolled
for key in x_keys:
    p, cls, sec, t = key
    # Sum over all students assigned to this class, section, and period
    students_in_section = pulp.lpSum(
        y.get((p, cls, sec, st), 0) for st in students
    )
    problem += (
        x[key] <= students_in_section,
        f"Teacher_Assignment_Validity_{p}_{cls}_{sec}_{t}"
    )

# Ensure that a section is taught by exactly one teacher during a period
for p in periods:
    for cls in classes:
        for sec in sections[cls]:
            problem += (
                pulp.lpSum(
                    x.get((p, cls, sec, t), 0) for t in teachers if (p, cls, sec, t) in x_keys
                ) <= 1,
                f"Section_{cls}_{sec}_One_Teacher_Period_{p}"
            )

# Solve the problem
problem.solve()

# Output the results
print("Objective Value (Total Satisfaction):", pulp.value(problem.objective))

# Teacher assignments
print("\nTeacher Assignments:")
for key, var in x.items():
    if pulp.value(var) == 1:
        p, cls, sec, t = key
        print(f"Period {p}: {t} teaches section {sec} of {cls}")

# Student assignments
print("\nStudent Assignments:")
for key, var in y.items():
    if pulp.value(var) == 1:
        p, cls, sec, st = key
        print(f"Period {p}: {st} is in section {sec} of {cls}")
