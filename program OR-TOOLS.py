import pandas as pd
from ortools.sat.python import cp_model
import os
from collections import Counter
import time
import logging
from datetime import datetime
import sys
import psutil

# Create output directory if it doesn't exist
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# Set up logging to both file and console
log_filename = os.path.join(output_dir, f'scheduling_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Redirect stdout to the log file while keeping console output
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'a')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Redirect stdout to both console and file
sys.stdout = Logger(log_filename)

# Log basic system info
logger.info("=== Scheduling System Started ===")
logger.info(f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"Available Memory: {psutil.virtual_memory().available / (1024 * 1024 * 1024):.2f} GB")

# Load CSV files with robust empty file handling
student_info = pd.read_csv('input/Student_Info.csv')
student_preference_info = pd.read_csv('input/Student_Preference_Info.csv')
teacher_info = pd.read_csv('input/Teacher_Info.csv')
sections_info = pd.read_csv('input/Sections_Information.csv')

# More robust teacher unavailability loading
try:
    teacher_unavailability = pd.read_csv('input/Teacher_unavailability.csv')
    if (teacher_unavailability.empty):
        teacher_unavailability = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
except (pd.errors.EmptyDataError, FileNotFoundError):
    teacher_unavailability = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])

# Define periods
periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']

# Create course_to_sections mapping right after loading data
course_to_sections = {}
for _, row in sections_info.iterrows():
    if row['Course ID'] not in course_to_sections:
        course_to_sections[row['Course ID']] = []
    course_to_sections[row['Course ID']].append(row['Section ID'])

# Add validation and analysis functions right after imports
def validate_data():
    """Validate data and print detailed diagnostics"""
    logger.info("\n=== Data Validation ===")
    # Check student requests
    logger.info("\nAnalyzing student requests:")
    for student_id in student_info['Student ID']:
        requested_courses = student_preference_info[
            student_preference_info['Student ID'] == student_id
        ]['Preferred Sections'].values[0].split(';')
        logger.info(f"Student {student_id}: {len(requested_courses)} courses requested - {requested_courses}")
    
    # Check teacher assignments
    logger.info("\nAnalyzing teacher assignments:")
    teacher_course_count = {}
    for teacher_id in teacher_info['Teacher ID']:
        courses = sections_info[sections_info['Teacher Assigned'] == teacher_id]['Course ID'].unique()
        teacher_course_count[teacher_id] = len(courses)
        logger.info(f"Teacher {teacher_id}: {len(courses)} courses - {list(courses)}")

def validate_section_periods():
    """Validate period availability after valid_sections is created"""
    logger.info("\nAnalyzing period availability:")
    for section_id in sections_info['Section ID']:
        available_periods = [p for s, p in valid_sections if s == section_id]
        course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
        logger.info(f"Section {section_id} ({course_id}): {len(available_periods)} available periods - {available_periods}")

def analyze_period_requirements():
    """Analyze and validate period requirements"""
    logger.info("\n=== Period Requirements Analysis ===")
    # Track which periods are required by which courses
    period_usage = {p: [] for p in periods}
    
    # Medical Career needs R1 and G1
    for section_id in sections_info[sections_info['Course ID'] == 'Medical Career']['Section ID']:
        period_usage['R1'].append(f"Medical Career ({section_id})")
        period_usage['G1'].append(f"Medical Career ({section_id})")
    
    # Heroes Teach needs R2 and G2
    for section_id in sections_info[sections_info['Course ID'] == 'Heroes Teach']['Section ID']:
        period_usage['R2'].append(f"Heroes Teach ({section_id})")
        period_usage['G2'].append(f"Heroes Teach ({section_id})")
    
    # Log period requirements
    for period, courses in period_usage.items():
        if courses:
            logger.info(f"Period {period} required by: {', '.join(courses)}")
            
    # Check teacher assignments for these periods
    teachers_mc = sections_info[sections_info['Course ID'] == 'Medical Career']['Teacher Assigned'].unique()
    teachers_ht = sections_info[sections_info['Course ID'] == 'Heroes Teach']['Teacher Assigned'].unique()
    
    logger.info("\nTeacher Analysis:")
    logger.info(f"Medical Career teachers: {teachers_mc}")
    logger.info(f"Heroes Teach teachers: {teachers_ht}")
    
    # Check for teacher overlap
    overlap = set(teachers_mc) & set(teachers_ht)
    if overlap:
        logger.error(f"Teachers {overlap} are assigned to both Medical Career and Heroes Teach!")

def analyze_constraint_conflicts():
    """Analyze potential constraint conflicts before solving"""
    logger.info("\n=== Analyzing Potential Constraint Conflicts ===")
    # 1. Check teacher loads across special courses
    special_course_teachers = sections_info[
        sections_info['Course ID'].isin(['Medical Career', 'Heroes Teach'])
    ]['Teacher Assigned'].unique()
    
    for teacher in special_course_teachers:
        teacher_sections = sections_info[sections_info['Teacher Assigned'] == teacher]
        courses = teacher_sections['Course ID'].unique()
        if len(courses) > 1:
            logger.error(f"Teacher {teacher} is assigned to multiple courses: {courses}")
            logger.error("This may cause conflicts with special period requirements")
    
    # 2. Check section capacity vs student requests
    for course_id, sections in course_to_sections.items():
        total_capacity = sum(
            sections_info[sections_info['Section ID'] == section]['# of Seats Available'].values[0]
            for section in sections
        )
        requesting_students = len([
            student_id for student_id in student_info['Student ID']
            if course_id in student_preference_info[
                student_preference_info['Student ID'] == student_id
            ]['Preferred Sections'].values[0].split(';')
        ])
        if requesting_students > total_capacity:
            logger.error(f"Course {course_id}: {requesting_students} students requested but only {total_capacity} seats available")
    
    # 3. Check for science course conflicts
    science_courses = ['Chemistry', 'Biology', 'Physics', 'AP Biology']
    science_teachers = sections_info[
        sections_info['Course ID'].isin(science_courses)
    ]['Teacher Assigned'].unique()
    
    for teacher in science_teachers:
        assigned_science = sections_info[
            (sections_info['Teacher Assigned'] == teacher) & 
            (sections_info['Course ID'].isin(science_courses))
        ]['Course ID'].unique()
        if len(assigned_science) > 1:
            logger.warning(f"Teacher {teacher} assigned multiple science courses: {assigned_science}")
            logger.warning("Check if prep period constraints can be satisfied")

def analyze_section_capacity():
    """Analyze section capacity constraints"""
    for course_id, sections in course_to_sections.items():
        total_requests = len([
            student_id for student_id in student_info['Student ID']
            if course_id in student_preference_info[
                student_preference_info['Student ID'] == student_id
            ]['Preferred Sections'].values[0].split(';')
        ])
        
        total_capacity = sum(
            sections_info[sections_info['Section ID'] == section]['# of Seats Available'].iloc[0]
            for section in sections
        )
        
        logger.info(f"\nCourse: {course_id}")
        logger.info(f"Total student requests: {total_requests}")
        logger.info(f"Total capacity: {total_capacity}")
        
        if total_requests > total_capacity:
            logger.error(f"INFEASIBLE: {course_id} has more requests ({total_requests}) than capacity ({total_capacity})")
            logger.error("This makes the problem inherently infeasible")

def analyze_teacher_conflicts():
    """Analyze potential teacher scheduling conflicts"""
    teacher_courses = {}
    for _, row in sections_info.iterrows():
        teacher_id = row['Teacher Assigned']
        course_id = row['Course ID']
        if teacher_id not in teacher_courses:
            teacher_courses[teacher_id] = set()
        teacher_courses[teacher_id].add(course_id)
    
    for teacher_id, courses in teacher_courses.items():
        if 'Medical Career' in courses and 'Heroes Teach' in courses:
            logger.error(f"INFEASIBLE: Teacher {teacher_id} assigned to both Medical Career and Heroes Teach")
            logger.error("These courses have mutually exclusive period requirements")
            return False
    return True

def analyze_science_conflicts():
    """Analyze science course scheduling conflicts"""
    science_courses = ['Chemistry', 'Biology', 'Physics', 'AP Biology']
    science_teachers = {}
    
    for _, row in sections_info.iterrows():
        if row['Course ID'] in science_courses:
            teacher_id = row['Teacher Assigned']
            if teacher_id not in science_teachers:
                science_teachers[teacher_id] = []
            science_teachers[teacher_id].append(row['Course ID'])
    
    for teacher_id, courses in science_teachers.items():
        if len(courses) > 4:  # More courses than available prep periods
            logger.error(f"INFEASIBLE: Teacher {teacher_id} assigned too many science courses: {courses}")
            logger.error("Not enough prep periods available")
            return False
    return True

def check_feasibility():
    """Check basic feasibility conditions before solving"""
    issues = []
    
    # Check if each section has valid periods
    for section_id in sections_info['Section ID']:
        valid_period_count = sum(1 for s, p in valid_sections if s == section_id)
        if valid_period_count == 0:
            issues.append(f"ERROR: Section {section_id} has no valid periods available")
    
    # Check course capacity vs requests
    for course_id, sections in course_to_sections.items():
        total_requests = len([
            student_id for student_id in student_info['Student ID']
            if course_id in student_preference_info[
                student_preference_info['Student ID'] == student_id
            ]['Preferred Sections'].values[0].split(';')
        ])
        total_capacity = sum(
            sections_info[sections_info['Section ID'] == section]['# of Seats Available'].iloc[0]
            for section in sections
        )
        if total_requests > total_capacity:
            issues.append(f"ERROR: Course {course_id} has {total_requests} requests but only {total_capacity} seats")
    
    return issues

# After data loading but before any processing
logger.info("\n=== Initial Data Validation ===")
validate_data()

# Run early feasibility checks
logger.info("\n=== Analyzing Problem Feasibility ===")
analyze_period_requirements()
analyze_constraint_conflicts()
analyze_section_capacity()

if not analyze_teacher_conflicts():
    logger.error("Fatal teacher assignment conflicts detected")
    sys.exit(1)

if not analyze_science_conflicts():
    logger.error("Fatal science course conflicts detected")
    sys.exit(1)

# Now proceed with preprocessing
logger.info("\n=== Starting Preprocessing ===")
# Filter sections based on teacher availability and special course requirements
valid_sections = []
for section_id, teacher_id in zip(sections_info['Section ID'], sections_info['Teacher Assigned']):
    course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
    
    # Special handling for Medical Career - only R1 and G1 periods allowed
    if course_id == 'Medical Career':
        allowed_periods = ['R1', 'G1']
    # Special handling for Heroes Teach - only R2 and G2 periods allowed
    elif course_id == 'Heroes Teach':
        allowed_periods = ['R2', 'G2']
    else:
        allowed_periods = periods
    
    # Handle empty or missing teacher unavailability data
    if teacher_unavailability.empty or teacher_id not in teacher_unavailability['Teacher ID'].values:
        unavailable_periods = []
    else:
        unavailable_periods = teacher_unavailability[teacher_unavailability['Teacher ID'] == teacher_id]['Unavailable Periods'].values
        if len(unavailable_periods) > 0 and pd.notna(unavailable_periods[0]):
            unavailable_periods = unavailable_periods[0].split(',')
        else:
            unavailable_periods = []
            
    for period in allowed_periods:
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
model = cp_model.CpModel()

# Add these preprocessing functions after data loading
def preprocess_valid_assignments():
    """Preprocess valid student-section combinations"""
    valid_assignments = set()
    student_ids = student_info['Student ID'].values  # Get actual student IDs from data
    for student_id in student_ids:  # Use actual student IDs
        requested_courses = student_preference_info[
            student_preference_info['Student ID'] == student_id
        ]['Preferred Sections'].values[0].split(';')
        for course_id in requested_courses:
            if course_id in course_to_sections:
                for section_id in course_to_sections[course_id]:
                    valid_assignments.add((student_id, section_id))
    return valid_assignments

def preprocess_science_pairs():
    """Preprocess valid science section pairs"""
    science_pairs = []
    seen_pairs = set()
    science_sections = sections_info[sections_info['Course ID'].str.contains('Science')]
    
    for _, row1 in science_sections.iterrows():
        for _, row2 in science_sections.iterrows():
            if row1['Course ID'] != row2['Course ID'] and (row1['Section ID'], row2['Section ID']) not in seen_pairs:
                pair = tuple(sorted([row1['Section ID'], row2['Section ID']]))
                science_pairs.append(pair)
                seen_pairs.add(pair)
    return science_pairs

# Add these right before variable creation
valid_assignments = preprocess_valid_assignments()
science_pairs = preprocess_science_pairs()

# Replace variable creation section with optimized version
x = {}  # student-section assignments
z = {}  # section-period assignments
y = {}  # student-section-period assignments

# Only create necessary variables
for student_id, section_id in valid_assignments:
    x[(student_id, section_id)] = model.NewBoolVar(f"x_{student_id}_{section_id}")
    valid_periods = [p for s, p in valid_sections if s == section_id]
    for period in valid_periods:
        y[(student_id, section_id, period)] = model.NewBoolVar(f"y_{student_id}_{section_id}_{period}")

for section_id, period in valid_sections:
    z[(section_id, period)] = model.NewBoolVar(f"z_{section_id, period}")

# Create diagnostic variables
diagnostic_vars = {
    'section_overload': {},     # Track overcrowded sections
    'period_conflicts': {},     # Track scheduling conflicts
    'sped_overload': {},       # Track SPED distribution issues
    'science_prep_violation': {},  # Track science prep period violations
    'sports_med_violation': {}      # Track Sports Med constraints
}

# Initialize base objective (maximizing assignments)
objective = cp_model.LinearExpr.Sum([x[(student_id, section_id)] 
                 for student_id, section_id in valid_assignments])  # Only use valid combinations

# Add constraints with diagnostics

# Add linking constraints between x and new y variables
for student_id, section_id in valid_assignments:  # Only iterate over valid combinations
    valid_periods = [period for sec, period in valid_sections if sec == section_id]
    model.Add(cp_model.LinearExpr.Sum([y[(student_id, section_id, p)] for p in valid_periods]) == x[(student_id, section_id)])

# Ensure y is only active when the section is scheduled in that period
for student_id, section_id in valid_assignments:  # Only iterate over valid combinations
    valid_periods = [period for sec, period in valid_sections if sec == section_id]
    for p in valid_periods:
        model.Add(y[(student_id, section_id, p)] <= z[(section_id, p)])

# New period constraint: Each student can be assigned to at most one section per period,
# using the y variables that now associate assignments with specific scheduled periods.
for student_id in student_info['Student ID'].values:  # Use actual student IDs
    for period in periods:
        conflict = model.NewIntVar(0, 1, f"period_conflict_{student_id}_{period}")
        diagnostic_vars['period_conflicts'][(student_id, period)] = conflict
        # Sum over all sections that are available in this period.
        model.Add(cp_model.LinearExpr.Sum(
            [y[(student_id, section_id, period)]
            for section_id in requested_sections
            if (student_id, section_id) in valid_assignments and (section_id, period) in valid_sections]
        ) <= 1 + conflict)
        objective += -750 * conflict

# 2. Each section must be scheduled in exactly one period
for section_id in sections_info['Section ID']:
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, period)] 
                 for sec_id, period in valid_sections if sec_id == section_id]) == 1)

# 3. Link student assignment to section scheduling - Fix this section
for student_id, section_id in valid_assignments:  # Only iterate over valid combinations
    model.Add(x[(student_id, section_id)] <= cp_model.LinearExpr.Sum([z[(section_id, period)] 
            for sec_id, period in valid_sections if sec_id == section_id]))

# 5. One section per requested course constraint

for student_id in student_info['Student ID']:
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    for course_id in requested_courses:
        if course_id in course_to_sections:
            course_sections = course_to_sections[course_id]
            # Must get exactly one section of each requested course
            model.Add(cp_model.LinearExpr.Sum([x[(student_id, section_id)] 
                    for section_id in course_sections 
                    if (student_id, section_id) in valid_assignments]) == 1)

# Add debug output before solving to verify the problem setup
logger.info("\nDebug Information:")
logger.info(f"Total students: {len(student_info)}")
logger.info(f"Total courses: {len(course_to_sections)}")
for course_id, sections in course_to_sections.items():
    logger.info(f"Course {course_id}: {len(sections)} sections")
logger.info(f"Valid assignments: {len(valid_assignments)}")
logger.info(f"Valid sections: {len(valid_sections)}")

# Define special course sections before constraints
medical_career_sections = sections_info[sections_info['Course ID'] == 'Medical Career']['Section ID']
heroes_teach_sections = sections_info[sections_info['Course ID'] == 'Heroes Teach']['Section ID']

# Simplified special course constraints
# Medical Career constraints - must be in R1 or G1
for section_id in medical_career_sections:
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, p)] for p in ['R1', 'G1'] if (section_id, p) in valid_sections]) == 1)

# Heroes Teach constraints - must be in R2 or G2
for section_id in heroes_teach_sections:
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, p)] for p in ['R2', 'G2'] if (section_id, p) in valid_sections]) == 1)

# Teacher constraints - ensure no teacher has sections in conflicting periods
teachers_with_special_courses = set(
    sections_info[sections_info['Course ID'].isin(['Medical Career', 'Heroes Teach'])]['Teacher Assigned']
)

# Medical Career constraints:
medical_career_sections = sections_info[sections_info['Course ID'] == 'Medical Career']['Section ID']
if not medical_career_sections.empty:
    # Ensure at least one section in R1
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, 'R1')] for section_id in medical_career_sections if (section_id, 'R1') in z]) >= 1)
    # Ensure at least one section in G1
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, 'G1')] for section_id in medical_career_sections if (section_id, 'G1') in z]) >= 1)

# Heroes Teach constraints:
heroes_teach_sections = sections_info[sections_info['Course ID'] == 'Heroes Teach']['Section ID']
if not heroes_teach_sections.empty:
    # Ensure at least one section in R2
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, 'R2')] for section_id in heroes_teach_sections if (section_id, 'R2') in z]) >= 1)
    # Ensure at least one section in G2
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, 'G2')] for section_id in heroes_teach_sections if (section_id, 'G2') in z]) >= 1)

# Remove these courses from diagnostic variables since they're now hard constraints
diagnostic_vars = {
    'section_overload': {},     # Track overcrowded sections
    'period_conflicts': {},     # Track scheduling conflicts
    'sped_overload': {},       # Track SPED distribution issues
    'science_prep_violation': {},  # Track science prep period violations
    'sports_med_violation': {}      # Track Sports Med constraints
}

# 9. Sports Med constraints with diagnostics
sports_med_sections = sections_info[sections_info['Course ID'] == 'Sports Med']['Section ID']
for period in periods:
    overlap = model.NewIntVar(0, 1, f"sports_med_overlap_{period}")
    diagnostic_vars['sports_med_violation'][period] = overlap
    model.Add(cp_model.LinearExpr.Sum([z[(section_id, period)] 
                 for section_id in sports_med_sections 
                 if (section_id, period) in valid_sections]) <= 1 + overlap)
    objective += -600 * overlap

# 10. Science prep period constraints with diagnostics (modified for unique pairs)
# Optimization 1: Preprocess science sections to reduce pairs
science_sections = sections_info[sections_info['Course ID'].str.contains('Science')]
# Group science sections by course to only compare different courses
science_courses = {}
for _, row in science_sections.iterrows():
    if row['Course ID'] not in science_courses:
        science_courses[row['Course ID']] = []
    science_courses[row['Course ID']].append(row['Section ID'])

# Replace the old science prep constraints with this optimized version:
for course1, sections1 in science_courses.items():
    for course2, sections2 in science_courses.items():
        if course1 < course2:  # Only compare each pair once
            for section_id1 in sections1:
                for section_id2 in sections2:
                    for period1, period2 in zip(periods[:-1], periods[1:]):
                        if period1 in ['R2', 'G2'] and period2 in ['R3', 'G3']:
                            continue
                        if (section_id1, period1) in z and (section_id2, period2) in z:
                            violation = model.NewIntVar(0, 1, f"science_prep_{section_id1}_{section_id2}_{period1}_{period2}")
                            diagnostic_vars['science_prep_violation'][(section_id1, section_id2, period1, period2)] = violation
                            model.Add(z[(section_id1, period1)] + z[(section_id2, period2)] <= 1 + violation)
                            objective += -400 * violation

# Replace existing teacher scheduling conflict constraints with:
# Ensure teachers have exactly one section per period
for teacher in teacher_info['Teacher ID']:
    teacher_sections = list(sections_info[sections_info['Teacher Assigned'] == teacher]['Section ID'])
    for period in periods:
        model.Add(cp_model.LinearExpr.Sum(
            [z[(section_id, period)]
            for section_id in teacher_sections
            if (section_id, period) in z]
        ) <= 1)

# Identify SPED students
sped_students = student_info[student_info['SPED'] == 1]['Student ID']

# 11. SPED distribution constraints with diagnostics
for section_id in sections_info['Section ID']:
    sped_overload = model.NewIntVar(0, 1, f"sped_overload_{section_id}")
    diagnostic_vars['sped_overload'][section_id] = sped_overload
    model.Add(cp_model.LinearExpr.Sum([x[(student_id, section_id)] 
                 for student_id in sped_students 
                 if (student_id, section_id) in x]) <= 12 + sped_overload)
    objective += -250 * sped_overload

# Modify the balancing constraints to include capacity awareness
balance_weight = 1
for course_id, sections in course_to_sections.items():
    if len(sections) > 1:
        L_max = model.NewIntVar(0, 1000, f"L_max_{course_id}")
        L_min = model.NewIntVar(0, 1000, f"L_min_{course_id}")
        for sec in sections:
            load_sec = cp_model.LinearExpr.Sum([x[(student_id, sec)]
                           for student_id in student_info['Student ID']
                           if (student_id, sec) in valid_assignments])
            model.Add(L_max >= load_sec)
            model.Add(L_min <= load_sec)
        objective += -balance_weight * (L_max - L_min)

# Set the objective
model.Maximize(objective)

# Add progress reporting before solving
# Insert after setting up the problem but before prob.solve():
logger.info("Starting problem solution...")
logger.info("Setting up solver with 60 second time limit...")
def print_problem_stats(model):
    """Print statistics about the problem size"""
    # Get number of variables by counting our created decision variables
    num_vars = sum(
        len(var_dict) 
        for var_dict in [x, y, z] + 
        [diagnostic_vars[key] for key in diagnostic_vars]
    )
    
    # Calculate rough estimate of constraints from our explicit constraints
    num_constraints = (
        len(student_info) * len(periods) +  # Period conflicts
        len(sections_info) +                # One period per section
        len(valid_assignments) +            # Student-section assignments
        len(student_info) * len(course_to_sections) +  # Course requirements
        len(teacher_info) * len(periods) +  # Teacher scheduling
        len(sections_info) +                # SPED distribution
        len(course_to_sections) * 2         # Section balancing
    )
    
    logger.info(f"\nProblem Statistics:")
    logger.info(f"Number of variables: {num_vars}")
    logger.info(f"Estimated number of constraints: {num_constraints}")
    logger.info(f"Memory usage: {psutil.Process().memory_info().rss / (1024 * 1024):.2f} MB")

print_problem_stats(model)

# Add these diagnostic functions before the solve
# Remove or modify check_feasibility() to only check period availability
def check_feasibility():
    """Check basic feasibility conditions before solving"""
    issues = []
    
    # Only check period availability
    for section_id in sections_info['Section ID']:
        valid_period_count = sum(1 for s, p in valid_sections if s == section_id)
        if valid_period_count == 0:
            issues.append(f"Section {section_id} has no valid periods available")
    
    return issues

# Add feasibility check before solving
logger.info("Checking basic feasibility conditions...")
feasibility_issues = check_feasibility()
if feasibility_issues:
    logger.error("Feasibility issues detected:")
    for issue in feasibility_issues:
        logger.error(f"- {issue}")
    logger.info("Consider relaxing constraints or increasing capacities")
    sys.exit(1)

# Modify the solver setup
start_time = time.time()

# Create and configure OR-Tools solver
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 1800  # 5 minute time limit
solver.parameters.num_search_workers = 8  # Use multiple cores
solver.parameters.log_search_progress = True  # Enable logging

print("Solving...")
status = solver.Solve(model)

# Add solution report after solve
elapsed = time.time() - start_time
logger.info(f"\nSolution completed in {elapsed:.2f} seconds")
logger.info(f"Status: {solver.StatusName(status)}")

if status == cp_model.OPTIMAL:  # Optimal
    logger.info("Optimal solution found")
    logger.info(f"Objective value: {solver.ObjectiveValue()}")
elif status == cp_model.INFEASIBLE:  # Infeasible
    logger.error("Problem is infeasible - no solution exists with current constraints")
    logger.info("Try:")
    logger.info("1. Checking section capacities")
    logger.info("2. Verifying teacher availability")
    logger.info("3. Reviewing special course period restrictions")
    logger.info("4. Ensuring course prerequisites are correct")
    sys.exit(1)
elif status == cp_model.FEASIBLE:  # Not solved optimally
    logger.warning("Optimal solution not found within time limit")
    if solver.ObjectiveValue() is not None:
        logger.info(f"Best objective value found: {solver.ObjectiveValue()}")
        logger.info("Using best solution found")
    else:
        logger.error("No feasible solution found")
        sys.exit(1)
else:
    logger.error(f"Unexpected status: {solver.StatusName(status)}")
    sys.exit(1)

# Replace monitor_solution function with this version
def monitor_solution(solver, start_time):
    """Monitor solution progress"""
    elapsed = time.time() - start_time
    if solver.StatusName(status) == 'OPTIMAL':  # Optimal
        logger.info(f"\nOptimal solution found in {elapsed:.2f} seconds")
    elif solver.StatusName(status) == 'INFEASIBLE':  # Infeasible
        logger.error(f"\nProblem is infeasible (determined in {elapsed:.2f} seconds)")
    elif solver.StatusName(status) == 'FEASIBLE':  # Not solved optimally
        logger.info(f"\nSolution found in {elapsed:.2f} seconds (not proven optimal)")
        if solver.ObjectiveValue() is not None:
            logger.info(f"Current objective value: {solver.ObjectiveValue()}")
    else:
        logger.error(f"\nUnexpected status after {elapsed:.2f} seconds: {solver.StatusName(status)}")

# Add status check before continuing
if solver.StatusName(status) != 'OPTIMAL':  # Not optimal
    logger.warning("\nWarning: Optimal solution not found within time limit!")
    logger.info("Best solution found will be used")

# Modify the analyze_conflicts() function to report overloads but not treat them as errors
def analyze_conflicts():
    """Analyze and report all constraint violations and return formatted DataFrames"""
    conflicts = {
        'course_loads': [],  # Changed from overloaded_sections to course_loads
        'period_conflicts': [],
        'sped_issues': [],
        'science_prep_issues': [],
        'special_course_issues': []
    }
    
    print("\n=== Scheduling Analysis ===")
    print(f"\nSolver Status: {solver.StatusName(status)}")
    
    # Calculate and report section loads
    course_loads = {}
    for section_id in sections_info['Section ID']:
        capacity = sections_info[sections_info['Section ID'] == section_id]['# of Seats Available'].values[0]
        course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
        enrollment = sum(
            solver.Value(x[(student_id, section_id)])
            for student_id in student_info['Student ID'].values
            if (student_id, section_id) in valid_assignments
        )
        
        if course_id not in course_loads:
            course_loads[course_id] = {'total_enrollment': 0, 'total_capacity': 0, 'sections': []}
        
        course_loads[course_id]['sections'].append({
            'section': section_id,
            'capacity': capacity,
            'enrollment': enrollment,
            'utilization': enrollment / capacity if capacity > 0 else float('inf')
        })
        course_loads[course_id]['total_enrollment'] += enrollment
        course_loads[course_id]['total_capacity'] += capacity

    # Report course-level statistics
    print("\nCourse Level Statistics:")
    for course_id, data in course_loads.items():
        total_util = data['total_enrollment'] / data['total_capacity'] if data['total_capacity'] > 0 else float('inf')
        print(f"\n{course_id}:")
        print(f"  Total Enrollment: {data['total_enrollment']}")
        print(f"  Total Capacity: {data['total_capacity']}")
        print(f"  Overall Utilization: {total_util:.2%}")
        print("  Section Details:")
        for section in data['sections']:
            print(f"    {section['section']}: {section['enrollment']}/{section['capacity']} ({section['utilization']:.2%})")
            if section['utilization'] > 1:
                conflicts['course_loads'].append({
                    'section': section['section'],
                    'course': course_id,
                    'capacity': section['capacity'],
                    'enrollment': section['enrollment'],
                    'overload': int(section['enrollment'] - section['capacity'])
                })

    # Check special course constraints
    special_issues_found = False
    
    # Medical Career - Fixed tuple handling
    if 'medical_career_violation' in diagnostic_vars:
        r1_var, g1_var = diagnostic_vars['medical_career_violation']
        if solver.Value(r1_var) > 0 or solver.Value(g1_var) > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Medical Career',
                'issue': 'Not scheduled in required periods (R1/G1)',
                'violations': {'R1': solver.Value(r1_var), 'G1': solver.Value(g1_var)}
            })
    
    # Heroes Teach - Fixed tuple handling
    if 'heroes_teach_violation' in diagnostic_vars:
        r2_var, g2_var = diagnostic_vars['heroes_teach_violation']
        if solver.Value(r2_var) > 0 or solver.Value(g2_var) > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Heroes Teach',
                'issue': 'Not scheduled in required periods (R2/G2)',
                'violations': {'R2': solver.Value(r2_var), 'G2': solver.Value(g2_var)}
            })
    
    # Sports Med
    for period, var in diagnostic_vars['sports_med_violation'].items():
        if solver.Value(var) > 0:
            special_issues_found = True
            conflicts['special_course_issues'].append({
                'type': 'Sports Med',
                'period': period,
                'issue': f'Sections overlap in period {period}'
            })
    
    # Generate recommendations
    print("\n=== Recommendations ===")
    
    if conflicts['course_loads']:
        print("\nTo resolve section overloads:")
        for conflict in conflicts['course_loads']:
            print(f"- Increase capacity of {conflict['course']} section {conflict['section']} by {conflict['overload']} seats")
            print(f"  OR add new section to accommodate {conflict['overload']} students")
    
    if conflicts['special_course_issues']:
        print("\nTo resolve special course issues:")
        for conflict in conflicts['special_course_issues']:
            if conflict['type'] == 'Medical Career':
                print(f"- Ensure Medical Career sections are scheduled in both R1 and G1")
                print(f"  Current violations - R1: {conflict['violations']['R1']}, G1: {conflict['violations']['G1']}")
            elif conflict['type'] == 'Heroes Teach':
                print(f"- Ensure Heroes Teach sections are scheduled in both R2 and G2")
                print(f"  Current violations - R2: {conflict['violations']['R2']}, G2: {conflict['violations']['G2']}")
            elif conflict['type'] == 'Sports Med':
                print(f"- Resolve Sports Med sections overlap in period {conflict['period']}")
    
    # Teacher scheduling conflict analysis
    teacher_conflicts = []
    for teacher in teacher_info['Teacher ID']:
        teacher_sections = list(sections_info[sections_info['Teacher Assigned'] == teacher]['Section ID'])
        for period in periods:
            scheduled = sum(
                solver.Value(z[(section_id, period)]) if solver.Value(z[(section_id, period)]) is not None else 0
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
    if solver.Value(z[(section_id, period)]) == 1:
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
for student_id, section_id in valid_assignments:  # Use valid_assignments instead
    if solver.Value(x[(student_id, section_id)]) == 1:
        student_assignments.append({'Student ID': student_id, 'Section ID': section_id})

print("\nGrouped Student Assignments:")
assignments_by_student = {}
for student_id, section_id in valid_assignments:
    if solver.Value(x[(student_id, section_id)]) == 1:
        if student_id not in assignments_by_student:
            assignments_by_student[student_id] = []
        assignments_by_student[student_id].append(section_id)

for student_id, assigned_sections in assignments_by_student.items():
    print(f"Student {student_id} is assigned to sections: {assigned_sections}")

# Create student assignments CSV
student_assignments_df = pd.DataFrame(student_assignments)
student_assignments_df.to_csv(os.path.join(output_dir, 'Student_Assignments.csv'), index=False)

# Output teacher assignments
teacher_assignments = []
for section_id, period in valid_sections:
    if solver.Value(z[(section_id, period)]) == 1:
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
for student_id in student_info['Student ID'].values:  # Use .values to get actual IDs
    requested_courses = student_preference_info[
        student_preference_info['Student ID'] == student_id
    ]['Preferred Sections'].values[0].split(';')
    
    assigned_courses = set()
    for section_id in requested_sections:
        if (student_id, section_id) in valid_assignments and solver.Value(x[(student_id, section_id)]) == 1:
            course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
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

# Add this after loading data but before creating variables
def validate_data():
    """Validate data and print detailed diagnostics"""
    logger.info("\n=== Data Validation ===")
    
    # Check student requests
    logger.info("\nAnalyzing student requests:")
    for student_id in student_info['Student ID']:
        requested_courses = student_preference_info[
            student_preference_info['Student ID'] == student_id
        ]['Preferred Sections'].values[0].split(';')
        logger.info(f"Student {student_id}: {len(requested_courses)} courses requested - {requested_courses}")
    
    # Check teacher assignments
    logger.info("\nAnalyzing teacher assignments:")
    teacher_course_count = {}
    for teacher_id in teacher_info['Teacher ID']:
        courses = sections_info[sections_info['Teacher Assigned'] == teacher_id]['Course ID'].unique()
        teacher_course_count[teacher_id] = len(courses)
        logger.info(f"Teacher {teacher_id}: {len(courses)} courses - {list(courses)}")
    
    # Check period availability
    logger.info("\nAnalyzing period availability:")
    for section_id in sections_info['Section ID']:
        available_periods = [p for s, p in valid_sections if s == section_id]
        course_id = sections_info[sections_info['Section ID'] == section_id]['Course ID'].values[0]
        logger.info(f"Section {section_id} ({course_id}): {len(available_periods)} available periods - {available_periods}")

# Add this validation call before problem setup
validate_data()