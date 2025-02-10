#check what constraints are unmet:

import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, LpStatus, PULP_CBC_CMD
import os
from collections import Counter

# Load CSV files
student_info = pd.read_csv('input/Student_Info.csv')
student_preference_info = pd.read_csv('input/Student_Preference_Info.csv')
teacher_info = pd.read_csv('input/Teacher_Info.csv')
teacher_unavailability = pd.read_csv('input/Teacher_unavailability.csv')
sections_info = pd.read_csv('input/Sections_Information.csv')

# Define periods
periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']

# Filter sections based on teacher availability and student requests
valid_sections = []
for section_id, teacher_id in zip(sections_info['Section ID'], sections_info['Teacher Assigned']):
    unavailable_periods = teacher_unavailability[teacher_unavailability['Teacher ID'] == teacher_id]['Unavailable Periods'].values
    if len(unavailable_periods) > 0 and pd.notna(unavailable_periods[0]):
        unavailable_periods = unavailable_periods[0].split(',')
    else:
        unavailable_periods = []
    for period in periods:
        if period not in unavailable_periods:
            valid_sections.append((section_id, period))

# Debugging: Print valid sections
print("Valid Sections:")
print(valid_sections)

# Create a mapping from courses to their sections
course_to_sections = {}
for _, row in sections_info.iterrows():
    if row['Course ID'] not in course_to_sections:
        course_to_sections[row['Course ID']] = []
    course_to_sections[row['Course ID']].append(row['Section ID'])

# Print mapping for debugging
print("\nCourse to Section Mapping:")
for course, sections in course_to_sections.items():
    print(f"{course}: {sections}")

# Filter sections based on student requests
requested_sections = set()
for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    # For each requested course, add all its sections to the set
    for course_id in requested_courses:
        if (course_id in course_to_sections):
            requested_sections.update(course_to_sections[course_id])

print("\nRequested Sections after mapping:")
print(requested_sections)

# Initialize the problem with diagnostics
prob = LpProblem("School_Scheduling_Diagnostic", LpMaximize)

# Create decision variables
x = {}  # student-section assignments
z = {}  # section-period assignments
# New variable: student-section-period assignments
y = {}

for student_id in student_info['Student ID']:
    for section_id in requested_sections:
        x[(student_id, section_id)] = LpVariable(f"x_{student_id}_{section_id}", 0, 1, cat='Binary')
        for sec, period in valid_sections:
            if sec == section_id:
                y[(student_id, section_id, period)] = LpVariable(f"y_{student_id}_{section_id}_{period}", 0, 1, cat='Binary')

for section_id, period in valid_sections:
    z[(section_id, period)] = LpVariable(f"z_{section_id}_{period}", 0, 1, cat='Binary')

# Create diagnostic variables
diagnostic_vars = {
    'missing_courses': {},      # Track students missing required courses
    'section_overload': {},     # Track overcrowded sections
    'period_conflicts': {},     # Track scheduling conflicts
    'sped_overload': {},       # Track SPED distribution issues
    'science_prep_violation': {},  # Track science prep period violations
    'medical_career_violation': {}, # Track Medical Career constraints
    'heroes_teach_violation': {},   # Track Heroes Teach constraints
    'sports_med_violation': {}      # Track Sports Med constraints
}

# Initialize base objective (maximizing assignments)
objective = lpSum(x[(student_id, section_id)] 
                 for student_id in student_info['Student ID'] 
                 for section_id in requested_sections)

# Add constraints with diagnostics

# Add linking constraints between x and new y variables
for student_id in student_info['Student ID']:
    for section_id in requested_sections:
        valid_periods = [period for sec, period in valid_sections if sec == section_id]
        prob += lpSum(y[(student_id, section_id, p)] for p in valid_periods) == x[(student_id, section_id)]

# Ensure y is only active when the section is scheduled in that period
for student_id in student_info['Student ID']:
    for section_id in requested_sections:
        valid_periods = [period for sec, period in valid_sections if sec == section_id]
        for p in valid_periods:
            prob += y[(student_id, section_id, p)] <= z[(section_id, p)]

# New period constraint: Each student can be assigned to at most one section per period,
# using the y variables that now associate assignments with specific scheduled periods.
for student_id in student_info['Student ID']:
    for period in periods:
        conflict = LpVariable(f"period_conflict_{student_id}_{period}", 0, None)
        diagnostic_vars['period_conflicts'][(student_id, period)] = conflict
        # Sum over all sections that are available in this period.
        prob += lpSum(
            y[(student_id, section_id, period)]
            for section_id in requested_sections
            if (section_id, period) in valid_sections
        ) <= 1 + conflict
        objective += -750 * conflict

# 2. Each section must be scheduled in exactly one period
for section_id in sections_info['Section ID']:
    prob += lpSum(z[(section_id, period)] 
                 for sec_id, period in valid_sections if sec_id == section_id) == 1

# 3. Link student assignment to section scheduling
for student_id in student_info['Student ID']:
    for section_id in requested_sections:
        prob += x[(student_id, section_id)] <= lpSum(z[(section_id, period)] 
                for sec_id, period in valid_sections if sec_id == section_id)

# 4. Section capacity constraints with diagnostics
for section_id in sections_info['Section ID']:
    overload = LpVariable(f"section_overload_{section_id}", 0, None)
    diagnostic_vars['section_overload'][section_id] = overload
    
    capacity = sections_info[sections_info['Section ID'] == section_id]['# of Seats Available'].values[0]
    prob += lpSum(x[(student_id, section_id)] 
                 for student_id in student_info['Student ID'] 
                 if (student_id, section_id) in x) <= capacity + overload
    objective += -100 * overload

# 5. One section per requested course constraint
for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    for course_id in requested_courses:
        course_sections = course_to_sections.get(course_id, [])
        # Student can take at most one section of each course
        prob += lpSum(x[(student_id, section_id)] 
                     for section_id in course_sections
                     if (student_id, section_id) in x) <= 1

# 6. Required courses constraint with diagnostics
for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    for course_id in requested_courses:
        slack = LpVariable(f"missing_courses_{student_id}_{course_id}", 0, 1)
        diagnostic_vars['missing_courses'][(student_id, course_id)] = slack
        
        if course_id in course_to_sections:
            course_sections = course_to_sections[course_id]
            # Must get exactly one section of each course
            prob += (lpSum(x[(student_id, section_id)] 
                    for section_id in course_sections 
                    if (student_id, section_id) in x) + slack == 1)
            
            objective += -1000 * slack  # High penalty for missing a required course

# 7. Replace Medical Career constraints:
medical_career_sections = sections_info[sections_info['Course ID'] == 'Medical Career']['Section ID']
if not medical_career_sections.empty:
    r1_violation = LpVariable("medical_r1_violation", 0, None)
    g1_violation = LpVariable("medical_g1_violation", 0, None)
    diagnostic_vars['medical_career_violation'] = (r1_violation, g1_violation)
    prob += lpSum(z[(section_id, 'R1')] for section_id in medical_career_sections if (section_id, 'R1') in z) + r1_violation >= 1
    prob += lpSum(z[(section_id, 'G1')] for section_id in medical_career_sections if (section_id, 'G1') in z) + g1_violation >= 1
    objective += -800 * (r1_violation + g1_violation)

# 8. Replace Heroes Teach constraints:
heroes_teach_sections = sections_info[sections_info['Course ID'] == 'Heroes Teach']['Section ID']
if not heroes_teach_sections.empty:
    r2_violation = LpVariable("heroes_r2_violation", 0, None)
    g2_violation = LpVariable("heroes_g2_violation", 0, None)
    diagnostic_vars['heroes_teach_violation'] = (r2_violation, g2_violation)
    prob += lpSum(z[(section_id, 'R2')] for section_id in heroes_teach_sections if (section_id, 'R2') in z) + r2_violation >= 1
    prob += lpSum(z[(section_id, 'G2')] for section_id in heroes_teach_sections if (section_id, 'G2') in z) + g2_violation >= 1
    objective += -800 * (r2_violation + g2_violation)

# 9. Sports Med constraints with diagnostics
sports_med_sections = sections_info[sections_info['Course ID'] == 'Sports Med']['Section ID']
for period in periods:
    overlap = LpVariable(f"sports_med_overlap_{period}", 0, None)
    diagnostic_vars['sports_med_violation'][period] = overlap
    prob += lpSum(z[(section_id, period)] 
                 for section_id in sports_med_sections 
                 if (section_id, period) in valid_sections) <= 1 + overlap
    objective += -600 * overlap

# 10. Science prep period constraints with diagnostics (modified for unique pairs)
science_sections = sections_info[sections_info['Course ID'].str.contains('Science')]
science_sections_ids = list(science_sections['Section ID'])
for i in range(len(science_sections_ids)):
    for j in range(i+1, len(science_sections_ids)):
        section_id1 = science_sections_ids[i]
        section_id2 = science_sections_ids[j]
        course_id1 = sections_info[sections_info['Section ID'] == section_id1]['Course ID'].values[0]
        course_id2 = sections_info[sections_info['Section ID'] == section_id2]['Course ID'].values[0]
        if course_id1 != course_id2:
            for period1, period2 in zip(periods[:-1], periods[1:]):
                if period1 in ['R2', 'G2'] and period2 in ['R3', 'G3']:
                    continue
                if (section_id1, period1) in z and (section_id2, period2) in z:
                    violation = LpVariable(f"science_prep_{section_id1}_{section_id2}_{period1}_{period2}", 0, None)
                    diagnostic_vars['science_prep_violation'][(section_id1, section_id2, period1, period2)] = violation
                    prob += z[(section_id1, period1)] + z[(section_id2, period2)] <= 1 + violation
                    objective += -400 * violation

# Replace existing teacher scheduling conflict constraints with:
# Ensure teachers have exactly one section per period
for teacher in teacher_info['Teacher ID']:
    teacher_sections = list(sections_info[sections_info['Teacher Assigned'] == teacher]['Section ID'])
    for period in periods:
        prob += lpSum(
            z[(section_id, period)]
            for section_id in teacher_sections
            if (section_id, period) in z
        ) <= 1

# Identify SPED students
sped_students = student_info[student_info['SPED'] == 1]['Student ID']

# 11. SPED distribution constraints with diagnostics
for section_id in sections_info['Section ID']:
    sped_overload = LpVariable(f"sped_overload_{section_id}", 0, None)
    diagnostic_vars['sped_overload'][section_id] = sped_overload
    prob += lpSum(x[(student_id, section_id)] 
                 for student_id in sped_students 
                 if (student_id, section_id) in x) <= 12 + sped_overload
    objective += -250 * sped_overload

# Original balancing constraints using all student assignments:
balance_weight = 50  # adjust this weight to tune balance encouragement

for course_id, sections in course_to_sections.items():
    if len(sections) > 1:
        L_max = LpVariable(f"L_max_{course_id}", 0)
        L_min = LpVariable(f"L_min_{course_id}", 0)
        for sec in sections:
            load_sec = lpSum(x[(student_id, sec)]
                             for student_id in student_info['Student ID']
                             if (student_id, sec) in x)
            prob += L_max >= load_sec
            prob += L_min <= load_sec
        objective += - balance_weight * (L_max - L_min)

# Set the objective
prob += objective

# Set up the solver with a time limit and message logging
solver = PULP_CBC_CMD(msg=True, timeLimit=60)

# Solve the problem using the solver options
prob.solve(solver)

def analyze_conflicts():
    """Analyze and report all constraint violations"""
    conflicts = {
        'missing_courses': [],
        'overloaded_sections': [],
        'period_conflicts': [],
        'sped_issues': [],
        'science_prep_issues': [],
        'special_course_issues': []
    }
    
    print("\n=== Scheduling Conflict Analysis ===")
    print(f"\nSolver Status: {LpStatus[prob.status]}")
    
    # Check missing courses - now checking per course
    missing_courses_found = False
    for (student_id, course_id), var in diagnostic_vars['missing_courses'].items():
        if var.varValue > 0:
            missing_courses_found = True
            conflicts['missing_courses'].append({
                'student': student_id,
                'course': course_id,
                'missing_count': 1
            })
    
    if missing_courses_found:
        print("\nStudents Missing Required Courses:")
        student_courses = {}
        for conflict in conflicts['missing_courses']:
            if conflict['student'] not in student_courses:
                student_courses[conflict['student']] = []
            student_courses[conflict['student']].append(conflict['course'])
            
        for student_id, missing_courses in student_courses.items():
            print(f"- Student {student_id} is missing {len(missing_courses)} courses:")
            for course in missing_courses:
                print(f"    - {course}")
    
    # Check section overloads
    overloads_found = False
    for section_id, var in diagnostic_vars['section_overload'].items():
        if var.varValue > 0:
            overloads_found = True
            course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
            conflicts['overloaded_sections'].append({
                'section': section_id,
                'course': course_id,
                'overload': int(var.varValue)
            })
    
    if overloads_found:
        print("\nOverloaded Sections:")
        for conflict in conflicts['overloaded_sections']:
            print(f"- Section {conflict['section']} ({conflict['course']}) is overloaded by {conflict['overload']} students")
    
    # Check special course constraints
    special_issues_found = False
    
    # Medical Career
    for section_id, (r1_var, g1_var) in diagnostic_vars['medical_career_violation'].items():
        if r1_var.varValue > 0 or g1_var.varValue > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Medical Career',
                'section': section_id,
                'issue': 'Not scheduled in required periods (R1/G1)'
            })
    
    # Heroes Teach
    for section_id, (r2_var, g2_var) in diagnostic_vars['heroes_teach_violation'].items():
        if r2_var.varValue > 0 or g2_var.varValue > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Heroes Teach',
                'section': section_id,
                'issue': 'Not scheduled in required periods (R2/G2)'
            })
    
    # Sports Med
    for period, var in diagnostic_vars['sports_med_violation'].items():
        if var.varValue > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Sports Med',
                'period': period,
                'issue': 'Sections overlap in same period'
            })
    
    if special_issues_found:
        print("\nSpecial Course Scheduling Issues:")
        for conflict in conflicts['special_course_issues']:
            print(f"- {conflict['type']}: {conflict['issue']}")
    
    # Generate recommendations
    print("\n=== Recommendations ===")
    
    if conflicts['missing_courses']:
        print("\nTo resolve missing courses:")
        course_counts = Counter([
            conflict['course']
            for conflict in conflicts['missing_courses']
        ])
        for course, count in course_counts.most_common():
            print(f"- Add capacity for {count} more students in {course}")
    
    if conflicts['overloaded_sections']:
        print("\nTo resolve section overloads:")
        for conflict in conflicts['overloaded_sections']:
            print(f"- Increase capacity of {conflict['course']} section {conflict['section']} by {conflict['overload']} seats")
            print(f"  OR add new section to accommodate {conflict['overload']} students")
    
    if conflicts['special_course_issues']:
        print("\nTo resolve special course issues:")
        for conflict in conflicts['special_course_issues']:
            if conflict['type'] == 'Medical Career':
                print(f"- Ensure Medical Career section {conflict['section']} is scheduled in both R1 and G1")
            elif conflict['type'] == 'Heroes Teach':
                print(f"- Ensure Heroes Teach section {conflict['section']} is scheduled in both R2 and G2")
            elif conflict['type'] == 'Sports Med':
                print(f"- Resolve Sports Med sections overlap in period {conflict['period']}")
    
    # Teacher scheduling conflict analysis
    teacher_conflicts = []
    for teacher in teacher_info['Teacher ID']:
        teacher_sections = list(sections_info[sections_info['Teacher Assigned'] == teacher]['Section ID'])
        for period in periods:
            scheduled = sum(
                z[(section_id, period)].varValue if z[(section_id, period)].varValue is not None else 0
                for section_id in teacher_sections if (section_id, period) in z
            )
            if scheduled > 1:
                teacher_conflicts.append({
                    'teacher': teacher,
                    'period': period,
                    'conflict_count': scheduled
                })
    
    if teacher_conflicts:
        print("\nTeacher Scheduling Conflicts:")
        for conflict in teacher_conflicts:
            print(f"- Teacher {conflict['teacher']} has {conflict['conflict_count']} sections scheduled in period {conflict['period']}")
    
    conflicts['teacher_conflicts'] = teacher_conflicts

    return conflicts

# Output results and create CSV files
# Create output directory
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# Output section scheduling
print("\nSection Scheduling:")
section_scheduling = []
for section_id, period in valid_sections:
    if z[(section_id, period)].varValue == 1:
        print(f"Section {section_id} is scheduled in period {period}")
        section_scheduling.append({'Section ID': section_id, 'Period': period})

# Output the master schedule
master_schedule_df = pd.DataFrame(section_scheduling)
master_schedule_df.to_csv(os.path.join(output_dir, 'Master_Schedule.csv'), index=False)
print("\nMaster Schedule:")
print(master_schedule_df)

# Output student assignments
print("\nStudent Assignments:")
student_assignments = []
for student_id in student_info['Student ID']:
    assigned_sections = []
    for section_id in requested_sections:
        if (student_id, section_id) in x and x[(student_id, section_id)].varValue == 1:
            assigned_sections.append(section_id)
            student_assignments.append({'Student ID': student_id, 'Section ID': section_id})
    if assigned_sections:
        print(f"Student {student_id} is assigned to sections: {assigned_sections}")
    else:
        print(f"Student {student_id} is not assigned to any section")

# Create student assignments CSV
student_assignments_df = pd.DataFrame(student_assignments)
student_assignments_df.to_csv(os.path.join(output_dir, 'Student_Assignments.csv'), index=False)

# Output teacher assignments
teacher_assignments = []
for section_id, period in valid_sections:
    if z[(section_id, period)].varValue == 1:
        teacher_id = sections_info[sections_info['Section ID'] == section_id]['Teacher Assigned'].values[0]
        teacher_assignments.append({
            'Teacher ID': teacher_id,
            'Section ID': section_id,
            'Period': period
        })

# Create teacher assignments CSV
teacher_assignments_df = pd.DataFrame(teacher_assignments)
teacher_assignments_df.to_csv(os.path.join(output_dir, 'Teacher_Assignments.csv'), index=False)

# Output unmet requests
students_unmet_requests = []
for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    assigned_courses = set()
    for section_id in requested_sections:
        if (student_id, section_id) in x and x[(student_id, section_id)].varValue == 1:
            course_id = sections_info[
                sections_info['Section ID'] == section_id
            ]['Course ID'].values[0]
            assigned_courses.add(course_id)
    
    unmet_courses = set(requested_courses) - assigned_courses
    if unmet_courses:
        students_unmet_requests.append({
            'Student ID': student_id,
            'Unmet Requests': ','.join(unmet_courses)
        })

# Create unmet requests CSV
students_unmet_requests_df = pd.DataFrame(students_unmet_requests)
students_unmet_requests_df.to_csv(os.path.join(output_dir, 'Students_Unmet_Requests.csv'), index=False)
print("\nStudents Without All Requested Courses:")
print(students_unmet_requests_df)

# Run the conflict analysis
analyze_conflicts()