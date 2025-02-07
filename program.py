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

# Preprocess and reduce problem size
valid_student_section_pairs = set()
for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    for course_id in requested_courses:
        if course_id in course_to_sections:
            for section_id in course_to_sections[course_id]:
                valid_student_section_pairs.add((student_id, section_id))

# Add debug output
print("\nNumber of valid student-section pairs:", len(valid_student_section_pairs))
print("Sample of valid pairs (first 5):", list(valid_student_section_pairs)[:5])

# Create a mapping of valid periods for each section
valid_periods_by_section = {}
for section_id in sections_info['Section ID']:
    valid_periods_by_section[section_id] = [
        period for sec, period in valid_sections if sec == section_id
    ]

# Add problem size reduction function
def reduce_problem_size(student_info, sections_info, valid_student_section_pairs, max_students_per_batch=100):
    """Break problem into smaller batches"""
    all_students = list(student_info['Student ID'])
    batches = []
    
    for i in range(0, len(all_students), max_students_per_batch):
        batch_students = all_students[i:i + max_students_per_batch]
        batch_pairs = {(s, sec) for (s, sec) in valid_student_section_pairs if s in batch_students}
        batches.append(batch_pairs)
    
    return batches

# Add solver configuration function
def configure_solver(timeLimit=1200):
    """Configure solver with optimized parameters"""
    return PULP_CBC_CMD(
        msg=True,
        timeLimit=timeLimit,
        gapRel=0.1,  # 10% optimality gap for faster solutions
        options=[
            'presolve on',
            'strong branch',
            'cuts all',
            'heur feasibility',
            'heur roundingheur',
            'heur pivotandfix',
            'heur divefractional',
            'node strategy hybrid',
            'branching hybrid'
        ]
    )

# Modify the main solving loop
def solve_schedule(student_batch, valid_sections, valid_periods_by_section):
    """Solve scheduling problem for a batch of students"""
    prob = LpProblem(f"School_Scheduling_Batch", LpMaximize)
    
    # Create variables only for this batch
    x = {
        (student_id, section_id): LpVariable(f"x_{student_id}_{section_id}", 0, 1, cat='Binary')
        for (student_id, section_id) in student_batch
    }
    
    z = {
        (section_id, period): LpVariable(f"z_{section_id}_{period}", 0, 1, cat='Binary')
        for (section_id, period) in valid_sections
    }
    
    y = {}
    for (student_id, section_id) in student_batch:
        if section_id in valid_periods_by_section:
            for period in valid_periods_by_section[section_id]:
                y[(student_id, section_id, period)] = LpVariable(
                    f"y_{student_id}_{section_id}_{period}", 
                    0, 1, 
                    cat='Binary'
                )
    
    # Modified objective to include balanced section sizes
    assignment_obj = lpSum(x[(student_id, section_id)] * 1000 
                         for (student_id, section_id) in student_batch)
    
    # Add balance incentive by course
    balance_penalties = []
    for course_id, sections in course_to_sections.items():
        # Only consider sections that have students in this batch
        batch_sections = [s for s in sections if any((student_id, s) in student_batch for student_id in {s for s, _ in student_batch})]
        if len(batch_sections) > 1:
            for i in range(len(batch_sections)):
                for j in range(i + 1, len(batch_sections)):
                    sec1, sec2 = batch_sections[i], batch_sections[j]
                    # Calculate section loads
                    load1 = lpSum(x[(student_id, sec1)] for (student_id, s) in student_batch if s == sec1)
                    load2 = lpSum(x[(student_id, sec2)] for (student_id, s) in student_batch if s == sec2)
                    
                    # Create variables for absolute difference
                    diff_pos = LpVariable(f"diff_pos_{sec1}_{sec2}", 0, None)
                    diff_neg = LpVariable(f"diff_neg_{sec1}_{sec2}", 0, None)
                    
                    # Add constraints to model |load1 - load2|
                    prob += load1 - load2 == diff_pos - diff_neg
                    balance_penalties.append(diff_pos + diff_neg)
    
    balance_obj = -50 * lpSum(balance_penalties) if balance_penalties else 0
    prob += assignment_obj + balance_obj
    
    # Rest of constraints remain unchanged
    # 1. Each section must be scheduled in exactly one period
    for section_id in sections_info['Section ID']:
        prob += lpSum(z[(section_id, period)] 
                     for sec_id, period in valid_sections if sec_id == section_id) == 1
    
    # 2. MODIFIED: One section per requested course per student (REQUIRED not optional)
    student_courses = {}
    for student_id, section_id in student_batch:
        course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
        if student_id not in student_courses:
            student_courses[student_id] = {}
        if course_id not in student_courses[student_id]:
            student_courses[student_id][course_id] = []
        student_courses[student_id][course_id].append(section_id)
    
    # CHANGED: Must take exactly one section of each requested course
    for student_id, courses in student_courses.items():
        for course_id, sections in courses.items():
            prob += lpSum(x[(student_id, section_id)] 
                         for section_id in sections 
                         if (student_id, section_id) in x) == 1
    
    # 3. No period conflicts for students
    for student_id in {s for (s, _) in student_batch}:
        for period in periods:
            prob += lpSum(y[(student_id, section_id, period)]
                         for (s, section_id) in student_batch 
                         if s == student_id and (student_id, section_id, period) in y) <= 1
    
    # 4. Link x and y variables
    for (student_id, section_id) in student_batch:
        if section_id in valid_periods_by_section:
            prob += lpSum(y[(student_id, section_id, p)]
                         for p in valid_periods_by_section[section_id]
                         if (student_id, section_id, p) in y) == x[(student_id, section_id)]
    
    # 5. Link y and z variables
    for (student_id, section_id) in student_batch:
        if section_id in valid_periods_by_section:
            for period in valid_periods_by_section[section_id]:
                if (student_id, section_id, period) in y:
                    prob += y[(student_id, section_id, period)] <= z[(section_id, period)]
    
    return prob, x, y, z

# Modify main execution flow
student_batches = reduce_problem_size(student_info, sections_info, valid_student_section_pairs)
all_solutions = []

# Modify how we check solutions to handle None values
def get_value_safe(var):
    """Safely get variable value, returns 0 if None"""
    try:
        val = var.value()
        return 0 if val is None else val
    except:
        return 0

# Update solution storage
for batch_idx, student_batch in enumerate(student_batches):
    print(f"\nSolving batch {batch_idx + 1}/{len(student_batches)}")
    
    # Solve batch
    prob, x, y, z = solve_schedule(student_batch, valid_sections, valid_periods_by_section)
    solver = configure_solver()
    status = prob.solve(solver)
    
    # Store results
    if status == 1:  # Optimal solution found
        batch_solution = {
            'assignments': [(s, sec) for (s, sec) in student_batch if get_value_safe(x[(s, sec)]) > 0.5],
            'schedule': [(sec, p) for (sec, p) in valid_sections if get_value_safe(z[(sec, p)]) > 0.5]
        }
        all_solutions.append(batch_solution)
    else:
        print(f"Failed to solve batch {batch_idx + 1}")

# Merge solutions
final_schedule = []
final_assignments = []

for solution in all_solutions:
    final_schedule.extend(solution['schedule'])
    final_assignments.extend(solution['assignments'])

# Output results and create CSV files
# Create output directory
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# Output section scheduling - FIXED VERSION
print("\nSection Scheduling:")
section_scheduling = []
section_periods = {}

# Create a dictionary of section to period assignments from final schedule
for section_id, period in final_schedule:
    if section_id not in section_periods:  # Take first assignment if duplicates exist
        section_periods[section_id] = period
        section_scheduling.append({'Section ID': section_id, 'Period': period})
        print(f"Section {section_id} is scheduled in period {period}")

# Sort by section ID for cleaner output
section_scheduling.sort(key=lambda x: x['Section ID'])

# Output the master schedule
master_schedule_df = pd.DataFrame(section_scheduling)
master_schedule_df.to_csv(os.path.join(output_dir, 'Master_Schedule.csv'), index=False)
print("\nMaster Schedule:")
print(master_schedule_df)

# Update student assignments to use section_periods
print("\nStudent Assignments:")
student_assignments = []
assignments_by_student = {}

for student_id in student_info['Student ID']:
    assignments_by_student[student_id] = []
    assigned_sections = [(s, sec) for (s, sec) in final_assignments if s == student_id]
    
    for _, section_id in assigned_sections:
        course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
        period = section_periods.get(section_id, 'UNSCHEDULED')
        assignments_by_student[student_id].append((section_id, course_id, period))
        student_assignments.append({'Student ID': student_id, 'Section ID': section_id})

# Print detailed schedules
print("\nDetailed Student Schedules:")
for student_id, assignments in assignments_by_student.items():
    if assignments:
        print(f"\nStudent {student_id} is assigned to:")
        # Sort by period for cleaner output
        assignments.sort(key=lambda x: x[2])
        for section_id, course_id, period in assignments:
            print(f"  - {course_id} (Section {section_id}) in period {period}")
    else:
        print(f"\nStudent {student_id} has no assignments")

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

def analyze_conflicts(final_assignments, final_schedule):
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
    
    # Check missing courses
    for student_id in student_info['Student ID']:
        requested_courses = student_preference_info[
            student_preference_info['Student ID'] == student_id
        ]['Preferred Sections'].values[0].split(';')
        
        assigned_courses = set()
        for (s, section_id) in final_assignments:
            if s == student_id:
                course_id = sections_info[
                    sections_info['Section ID'] == section_id
                ]['Course ID'].values[0]
                assigned_courses.add(course_id)
        
        missing = set(requested_courses) - assigned_courses
        if missing:
            conflicts['missing_courses'].extend([
                {'student': student_id, 'course': course, 'missing_count': 1}
                for course in missing
            ])
    
    # Check section overloads
    section_counts = Counter(sec for _, sec in final_assignments)
    for section_id, count in section_counts.items():
        capacity = sections_info[
            sections_info['Section ID'] == section_id
        ]['# of Seats Available'].values[0]
        if count > capacity:
            course_id = sections_info[
                sections_info['Section ID'] == section_id
            ]['Course ID'].values[0]
            conflicts['overloaded_sections'].append({
                'section': section_id,
                'course': course_id,
                'overload': count - capacity
            })
    
    # Check period conflicts
    schedule_dict = {sec: period for sec, period in final_schedule}
    for student_id in student_info['Student ID']:
        student_sections = [sec for (s, sec) in final_assignments if s == student_id]
        for period in periods:
            sections_in_period = [
                sec for sec in student_sections
                if schedule_dict.get(sec) == period
            ]
            if len(sections_in_period) > 1:
                conflicts['period_conflicts'].append({
                    'student': student_id,
                    'period': period,
                    'sections': sections_in_period
                })
    
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
            print(f"- Increase capacity of {conflict['course']} section {conflict['section']} "
                  f"by {conflict['overload']} seats")
    
    if conflicts['period_conflicts']:
        print("\nTo resolve period conflicts:")
        for conflict in conflicts['period_conflicts']:
            print(f"- Student {conflict['student']} has multiple sections in period {conflict['period']}")
    
    return conflicts

# Run the conflict analysis with merged solutions
conflicts = analyze_conflicts(final_assignments, final_schedule)

# ...rest of existing code...