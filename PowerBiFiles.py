import pandas as pd
import os

def safe_read_csv(filepath, required=True):
    """Safely read a CSV file, return empty DataFrame if file doesn't exist and not required"""
    try:
        return pd.read_csv(filepath)
    except pd.errors.EmptyDataError:
        # Return empty DataFrame with expected columns for empty files
        if filepath.endswith('Students_Unmet_Requests.csv'):
            return pd.DataFrame(columns=['Student ID', 'Course ID'])
        return pd.DataFrame()
    except FileNotFoundError:
        if required:
            raise FileNotFoundError(f"Required file {filepath} not found!")
        print(f"Warning: Optional file {filepath} not found, using empty DataFrame")
        return pd.DataFrame()

def prepare_powerbi_data():
    # First create the initial PowerBI datasets
    print("Step 1: Creating initial datasets...")
    create_initial_datasets()
    
    # Then format them for PowerBI
    print("\nStep 2: Formatting for PowerBI...")
    format_for_powerbi()

def create_initial_datasets():
    # Create initial output directory
    powerbi_dir = 'PowerBi'
    os.makedirs(powerbi_dir, exist_ok=True)
    
    # Load input CSVs
    sections_info = safe_read_csv('input/Sections_Information.csv')
    student_info = safe_read_csv('input/Student_Info.csv')
    student_preference = safe_read_csv('input/Student_Preference_Info.csv')
    teacher_info = safe_read_csv('input/Teacher_Info.csv')
    teacher_unavailability = safe_read_csv('input/Teacher_unavailability.csv', required=False)
    
    # Load output CSVs
    master_schedule = safe_read_csv('output/Master_Schedule.csv')
    student_assignments = safe_read_csv('output/Student_Assignments.csv')
    teacher_assignments = safe_read_csv('output/Teacher_Assignments.csv')
    unmet_requests = safe_read_csv('output/Students_Unmet_Requests.csv', required=False)

    # Create dimension tables
    periods = pd.DataFrame({
        'Period': sorted(master_schedule['Period'].unique()),
        'Day_Type': [p[0] for p in sorted(master_schedule['Period'].unique())],
        'Period_Number': [int(p[1]) for p in sorted(master_schedule['Period'].unique())]
    })
    periods.to_csv(f'{powerbi_dir}/DimPeriod.csv', index=False)

    teacher_info.to_csv(f'{powerbi_dir}/DimTeacher.csv', index=False)
    student_info.to_csv(f'{powerbi_dir}/DimStudent.csv', index=False)
    sections_info.to_csv(f'{powerbi_dir}/DimSection.csv', index=False)

    # Create fact tables
    fact_schedule = master_schedule.merge(
        sections_info[['Section ID', 'Course ID', 'Teacher Assigned', 'Department']],
        on='Section ID',
        how='left'
    )
    fact_schedule.to_csv(f'{powerbi_dir}/FactSchedule.csv', index=False)

    fact_enrollment = student_assignments.merge(
        master_schedule[['Section ID', 'Period']],
        on='Section ID',
        how='left'
    )
    fact_enrollment.to_csv(f'{powerbi_dir}/FactStudentEnrollment.csv', index=False)

    # Create utilization facts
    section_counts = student_assignments.groupby('Section ID').size().reset_index(name='Enrollment_Count')
    fact_utilization = sections_info[['Section ID', 'Course ID', '# of Seats Available', 'Department']].merge(
        section_counts,
        on='Section ID',
        how='left'
    )
    fact_utilization['Enrollment_Count'] = fact_utilization['Enrollment_Count'].fillna(0)
    fact_utilization['Utilization_Rate'] = fact_utilization['Enrollment_Count'] / fact_utilization['# of Seats Available']
    fact_utilization.to_csv(f'{powerbi_dir}/FactSectionUtilization.csv', index=False)

    teacher_assignments.to_csv(f'{powerbi_dir}/FactTeacherAssignment.csv', index=False)

    # Create bridge tables
    if not student_preference.empty:
        student_preferences_expanded = student_preference.assign(
            Preferred_Sections=student_preference['Preferred Sections'].str.split(';')
        ).explode('Preferred_Sections')
        bridge_preferences = student_preferences_expanded[['Student ID', 'Preferred_Sections']]
        bridge_preferences.columns = ['Student ID', 'Course ID']
        bridge_preferences.to_csv(f'{powerbi_dir}/BridgeStudentPreference.csv', index=False)

def format_for_powerbi():
    # Create PowerBI-ready directory structure
    base_dir = 'PowerBI_Ready'
    dim_dir = os.path.join(base_dir, 'Dimensions')
    fact_dir = os.path.join(base_dir, 'Facts')
    
    os.makedirs(dim_dir, exist_ok=True)
    os.makedirs(fact_dir, exist_ok=True)

    # Process Dimension Tables
    print("Processing dimension tables...")
    
    # DimPeriod with enhanced fields
    periods = safe_read_csv('PowerBi/DimPeriod.csv')
    periods['PeriodName'] = 'Period ' + periods['Period']
    periods['SortOrder'] = periods.apply(
        lambda x: (1 if x['Day_Type'] == 'R' else 2) * 10 + x['Period_Number'], 
        axis=1
    )
    periods.to_csv(f'{dim_dir}/DimPeriod.csv', index=False)

    # DimTeacher with friendly names
    teachers = safe_read_csv('PowerBi/DimTeacher.csv')
    teachers['TeacherName'] = teachers['Teacher ID']
    teachers.to_csv(f'{dim_dir}/DimTeacher.csv', index=False)

    # DimStudent with SPED boolean
    students = safe_read_csv('PowerBi/DimStudent.csv')
    students['IsSPED'] = students['SPED'].astype(bool)
    students.to_csv(f'{dim_dir}/DimStudent.csv', index=False)

    # DimSection with renamed capacity
    sections = safe_read_csv('PowerBi/DimSection.csv')
    sections.rename(columns={'# of Seats Available': 'Capacity'}, inplace=True)
    sections.to_csv(f'{dim_dir}/DimSection.csv', index=False)

    # Process Fact Tables
    print("Processing fact tables...")
    
    # FactSchedule with sort order
    schedule = safe_read_csv('PowerBi/FactSchedule.csv')
    schedule = schedule.merge(
        periods[['Period', 'SortOrder']], 
        on='Period', 
        how='left'
    )
    schedule.to_csv(f'{fact_dir}/FactSchedule.csv', index=False)

    # FactStudentEnrollment with SPED info
    enrollments = safe_read_csv('PowerBi/FactStudentEnrollment.csv')
    enrollments = enrollments.merge(
        students[['Student ID', 'IsSPED']], 
        on='Student ID', 
        how='left'
    )
    enrollments.to_csv(f'{fact_dir}/FactStudentEnrollment.csv', index=False)

    # FactSectionUtilization with percentage metrics
    utilization = safe_read_csv('PowerBi/FactSectionUtilization.csv')
    utilization['UtilizationPercent'] = utilization['Utilization_Rate'] * 100
    utilization['RemainingSeats'] = utilization['# of Seats Available'] - utilization['Enrollment_Count']
    utilization.to_csv(f'{fact_dir}/FactSectionUtilization.csv', index=False)

    # Create loading instructions
    instructions = """
PowerBI Quick Load Instructions:

1. Open PowerBI
2. Get Data -> Folder
3. Navigate to PowerBI_Ready folder
4. Select Transform Data
5. Load dimensions first:
   - Filter to Dimensions folder
   - Combine Files
   - Load
6. Load facts second:
   - Filter to Facts folder
   - Combine Files
   - Load

Key Relationships to Create:
- FactSchedule -> DimPeriod (Period)
- FactSchedule -> DimSection (Section ID)
- FactSchedule -> DimTeacher (Teacher ID)
- FactStudentEnrollment -> DimStudent (Student ID)
- FactStudentEnrollment -> DimSection (Section ID)
- FactSectionUtilization -> DimSection (Section ID)
    """
    
    with open(f'{base_dir}/LOAD_INSTRUCTIONS.txt', 'w') as f:
        f.write(instructions)

    print("\nFiles have been processed and organized into:")
    print(f"- {dim_dir} (Dimension tables)")
    print(f"- {fact_dir} (Fact tables)")
    print("\nCheck LOAD_INSTRUCTIONS.txt for PowerBI loading steps.")

if __name__ == "__main__":
    prepare_powerbi_data()