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

def create_powerbi_datasets():
    # Create output directory for PowerBI data
    powerbi_dir = 'PowerBi'
    os.makedirs(powerbi_dir, exist_ok=True)
    
    # Load all input CSVs (Dimension tables)
    sections_info = safe_read_csv('input/Sections_Information.csv')
    student_info = safe_read_csv('input/Student_Info.csv')
    student_preference = safe_read_csv('input/Student_Preference_Info.csv')
    teacher_info = safe_read_csv('input/Teacher_Info.csv')
    teacher_unavailability = safe_read_csv('input/Teacher_unavailability.csv', required=False)
    
    # Load output CSVs (Fact tables)
    master_schedule = safe_read_csv('output/Master_Schedule.csv')
    student_assignments = safe_read_csv('output/Student_Assignments.csv')
    teacher_assignments = safe_read_csv('output/Teacher_Assignments.csv')
    unmet_requests = safe_read_csv('output/Students_Unmet_Requests.csv', required=False)

    # 1. Create dimension tables
    
    # DimPeriod - Period dimension
    periods = pd.DataFrame({
        'Period': sorted(master_schedule['Period'].unique()),
        'Day_Type': [p[0] for p in sorted(master_schedule['Period'].unique())],
        'Period_Number': [int(p[1]) for p in sorted(master_schedule['Period'].unique())]
    })
    periods.to_csv(f'{powerbi_dir}/DimPeriod.csv', index=False)

    # DimTeacher - Teacher dimension (one row per teacher)
    dim_teacher = teacher_info.copy()
    dim_teacher.to_csv(f'{powerbi_dir}/DimTeacher.csv', index=False)

    # DimStudent - Student dimension (one row per student)
    dim_student = student_info.copy()
    dim_student.to_csv(f'{powerbi_dir}/DimStudent.csv', index=False)

    # DimSection - Section dimension (one row per section)
    dim_section = sections_info.copy()
    dim_section.to_csv(f'{powerbi_dir}/DimSection.csv', index=False)

    # 2. Create fact tables

    # FactSchedule - Master schedule fact table (one row per section-period combination)
    fact_schedule = master_schedule.merge(
        sections_info[['Section ID', 'Course ID', 'Teacher Assigned', 'Department']],
        on='Section ID',
        how='left'
    )
    fact_schedule.to_csv(f'{powerbi_dir}/FactSchedule.csv', index=False)

    # FactStudentEnrollment - Student enrollment fact table (one row per student-section combination)
    fact_enrollment = student_assignments.copy()
    fact_enrollment = fact_enrollment.merge(
        master_schedule[['Section ID', 'Period']],
        on='Section ID',
        how='left'
    )
    fact_enrollment.to_csv(f'{powerbi_dir}/FactStudentEnrollment.csv', index=False)

    # FactSectionUtilization - Section utilization metrics (one row per section)
    section_counts = student_assignments.groupby('Section ID').size().reset_index(name='Enrollment_Count')
    fact_utilization = sections_info[['Section ID', 'Course ID', '# of Seats Available', 'Department']].merge(
        section_counts,
        on='Section ID',
        how='left'
    )
    fact_utilization['Enrollment_Count'] = fact_utilization['Enrollment_Count'].fillna(0)
    fact_utilization['Utilization_Rate'] = fact_utilization['Enrollment_Count'] / fact_utilization['# of Seats Available']
    fact_utilization.to_csv(f'{powerbi_dir}/FactSectionUtilization.csv', index=False)

    # FactTeacherAssignment - Teacher assignment fact table (one row per teacher-period-section combination)
    fact_teacher_assignment = teacher_assignments.copy()
    fact_teacher_assignment.to_csv(f'{powerbi_dir}/FactTeacherAssignment.csv', index=False)

    # 3. Create bridge tables for many-to-many relationships

    # BridgeStudentPreference - Bridge table for student course preferences
    if not student_preference.empty:
        student_preferences_expanded = student_preference.assign(
            Preferred_Sections=student_preference['Preferred Sections'].str.split(';')
        ).explode('Preferred_Sections')
        bridge_preferences = student_preferences_expanded[['Student ID', 'Preferred_Sections']]
        bridge_preferences.columns = ['Student ID', 'Course ID']
        bridge_preferences.to_csv(f'{powerbi_dir}/BridgeStudentPreference.csv', index=False)

    print("\nPowerBI datasets have been created in the 'PowerBi' directory:")
    print("\nDimension Tables:")
    print("1. DimPeriod.csv - Period information")
    print("2. DimTeacher.csv - Teacher information")
    print("3. DimStudent.csv - Student information")
    print("4. DimSection.csv - Section information")
    
    print("\nFact Tables:")
    print("1. FactSchedule.csv - Master schedule")
    print("2. FactStudentEnrollment.csv - Student enrollments")
    print("3. FactSectionUtilization.csv - Section utilization metrics")
    print("4. FactTeacherAssignment.csv - Teacher assignments")
    
    print("\nBridge Tables:")
    print("1. BridgeStudentPreference.csv - Student-Course preferences")

    print("\nRecommended PowerBI relationships:")
    print("- Connect FactSchedule to DimPeriod using Period")
    print("- Connect FactSchedule to DimSection using Section ID")
    print("- Connect FactStudentEnrollment to DimStudent using Student ID")
    print("- Connect FactStudentEnrollment to DimSection using Section ID")
    print("- Connect FactTeacherAssignment to DimTeacher using Teacher ID")
    print("- Connect BridgeStudentPreference to DimStudent using Student ID")

if __name__ == "__main__":
    create_powerbi_datasets()