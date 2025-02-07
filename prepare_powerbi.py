"""
PowerBI Dashboard Data Preparation Module

This module handles the automation of data preparation for the Master Schedule PowerBI dashboard.
It processes various input CSV files and creates a structured Excel dataset with fact and dimension tables.
"""

import pandas as pd
import os
import shutil
from datetime import datetime

class ScheduleDashboardAutomation:
    """
    Handles the automation of data preparation for the Master Schedule PowerBI dashboard.
    
    This class manages the creation and organization of data files, including:
    - Reading and processing input CSV files
    - Creating dimension and fact tables
    - Generating a consolidated Excel dataset
    - Managing file archival
    """
    
    def __init__(self):
        self.base_dir = 'ScheduleDashboard'
        self.data_dir = os.path.join(self.base_dir, 'Data')
        self.archive_dir = os.path.join(self.base_dir, 'Archive')
        
        # Create directory structure
        for directory in [self.base_dir, self.data_dir, self.archive_dir]:
            os.makedirs(directory, exist_ok=True)

    def inspect_csv_headers(self, filepath):
        """Debug helper to check CSV structure"""
        try:
            # Try reading first few lines directly
            with open(filepath, 'r') as f:
                print(f"\nFirst few lines of {filepath}:")
                for i, line in enumerate(f):
                    if i < 3:  # Print first 3 lines
                        print(line.strip())
                    else:
                        break
        except Exception as e:
            print(f"Error reading {filepath}: {str(e)}")

    def safe_read_csv(self, filepath, required=True):
        """Safely read a CSV file with explicit header handling"""
        try:
            # First try reading with default parameters
            df = pd.read_csv(filepath, encoding='utf-8')
            
            # If we got a malformed DataFrame, try without header
            if len(df.columns) < len(df.iloc[0]):
                df = pd.read_csv(filepath, encoding='utf-8', header=None)
                # Use first row as column names
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
            
            return df
        except Exception as e:
            if required:
                raise Exception(f"Error reading {filepath}: {str(e)}")
            return pd.DataFrame()

    def create_excel_dataset(self):
        """Create a consolidated Excel file containing all dimension and fact tables."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_path = os.path.join(self.data_dir, f'MasterSchedule_{timestamp}.xlsx')
        
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # Load all input files
                sections_info = self.safe_read_csv('input/Sections_Information.csv')
                student_info = self.safe_read_csv('input/Student_Info.csv')
                student_preferences = self.safe_read_csv('input/Student_Preference_Info.csv')
                teacher_info = self.safe_read_csv('input/Teacher_Info.csv')
                master_schedule = self.safe_read_csv('output/Master_Schedule.csv')
                student_assignments = self.safe_read_csv('output/Student_Assignments.csv')

                # Process student preferences to extract grade levels
                def extract_grade(courses):
                    grade_indicators = {
                        'English 10-P': 10,
                        'American Lit-P': 11,
                        'Eng 12/ERWC-P': 12
                    }
                    courses_list = courses.split(';')
                    for course in courses_list:
                        for indicator, grade in grade_indicators.items():
                            if indicator in course:
                                return grade
                    return None

                student_preferences['GradeLevel'] = student_preferences['Preferred Sections'].apply(extract_grade)
                
                # Merge grade level information into student info
                student_info = student_info.merge(
                    student_preferences[['Student ID', 'GradeLevel']],
                    left_on='Student ID',
                    right_on='Student ID',
                    how='left'
                )

                # Standardize column names based on actual CSV structure
                sections_info = sections_info.rename(columns={
                    'Section ID': 'SectionID',
                    'Course ID': 'CourseID',
                    'Teacher Assigned': 'TeacherID',
                    '# of Seats Available': 'SeatsAvailable'
                })

                student_info = student_info.rename(columns={
                    'Student ID': 'StudentID',
                    'SPED': 'SPED'  # Keep original SPED column
                })

                teacher_info = teacher_info.rename(columns={
                    'Teacher ID': 'TeacherID',
                    'Department': 'Department'
                })

                master_schedule = master_schedule.rename(columns={
                    'Section ID': 'SectionID'
                })

                student_assignments = student_assignments.rename(columns={
                    'Student ID': 'StudentID',
                    'Section ID': 'SectionID'
                })

                # Create fact tables with correct column references
                schedule = master_schedule.merge(
                    sections_info[['SectionID', 'CourseID', 'TeacherID', 'Department']],
                    on='SectionID',
                    how='left'
                )

                # Enhanced section utilization calculation
                section_counts = student_assignments.groupby('SectionID').size().reset_index(name='Enrollment_Count')
                utilization = sections_info.merge(
                    section_counts,
                    on='SectionID',
                    how='left'
                ).merge(
                    master_schedule[['SectionID', 'Period']],
                    on='SectionID',
                    how='left'
                )

                # Rest of utilization calculations
                utilization['Enrollment_Count'] = utilization['Enrollment_Count'].fillna(0)
                utilization['SeatsAvailable'] = pd.to_numeric(utilization['SeatsAvailable'], errors='coerce')
                utilization['Utilization_Rate'] = utilization.apply(
                    lambda x: min(x['Enrollment_Count'] / x['SeatsAvailable'], 1.0) 
                    if x['SeatsAvailable'] > 0 else 0, axis=1
                )
                utilization['Empty_Seats'] = utilization.apply(
                    lambda x: max(x['SeatsAvailable'] - x['Enrollment_Count'], 0), axis=1
                )
                utilization['Overbooked_Seats'] = utilization.apply(
                    lambda x: max(x['Enrollment_Count'] - x['SeatsAvailable'], 0), axis=1
                )
                utilization.to_excel(writer, sheet_name='FactSectionUtilization', index=False)

                # Modified student load summary to include SPED status
                student_load = student_assignments.merge(
                    student_info[['StudentID', 'SPED', 'GradeLevel']],
                    on='StudentID',
                    how='left'
                ).merge(
                    sections_info[['SectionID', 'Department', 'CourseID']],
                    on='SectionID',
                    how='left'
                )

                student_load_summary = student_load.groupby(
                    ['StudentID', 'SPED', 'GradeLevel']
                ).agg({
                    'SectionID': 'count',
                    'Department': lambda x: len(set(x))
                }).reset_index()
                student_load_summary.columns = ['StudentID', 'SPED', 'GradeLevel', 'Total_Courses', 'Unique_Departments']

                # Add preference analysis
                student_preferences['Preferred_Count'] = student_preferences['Preferred Sections'].str.count(';') + 1
                preferences_summary = student_preferences.merge(
                    student_load_summary[['StudentID', 'Total_Courses']],
                    left_on='Student ID',
                    right_on='StudentID',
                    how='left'
                )
                preferences_summary['Preference_Fulfillment'] = (
                    preferences_summary['Total_Courses'] / preferences_summary['Preferred_Count']
                ).round(3)
                
                # Save all sheets
                periods = pd.DataFrame({
                    'Period': sorted(master_schedule['Period'].unique()),
                    'Day_Type': [p[0] for p in sorted(master_schedule['Period'].unique())],
                    'Period_Number': [int(p[1]) for p in sorted(master_schedule['Period'].unique())]
                })
                periods['PeriodName'] = 'Period ' + periods['Period']
                periods['SortOrder'] = periods.apply(
                    lambda x: (1 if x['Day_Type'] == 'R' else 2) * 10 + x['Period_Number'], 
                    axis=1
                )

                # Save all sheets and ensure they're visible
                periods.to_excel(writer, sheet_name='DimPeriod', index=False, header=True)
                teacher_info.to_excel(writer, sheet_name='DimTeacher', index=False, header=True)
                student_info.to_excel(writer, sheet_name='DimStudent', index=False, header=True)
                sections_info.to_excel(writer, sheet_name='DimSection', index=False, header=True)

                # Create and save fact tables
                schedule.to_excel(writer, sheet_name='FactSchedule', index=False)

                # Update student enrollments
                enrollments = student_assignments.merge(
                    master_schedule[['SectionID', 'Period']],
                    on='SectionID',
                    how='left'
                )
                enrollments.to_excel(writer, sheet_name='FactStudentEnrollment', index=False)

                # Create DimDepartment for better department analytics
                departments = pd.DataFrame({
                    'Department': sorted(sections_info['Department'].unique()),
                    'DepartmentName': sorted(sections_info['Department'].unique())
                })
                departments.to_excel(writer, sheet_name='DimDepartment', index=False)

                # Create department summary
                dept_summary = utilization.groupby('Department').agg({
                    'SectionID': 'count',
                    'SeatsAvailable': 'sum',
                    'Enrollment_Count': 'sum',
                    'Empty_Seats': 'sum',
                    'Overbooked_Seats': 'sum'
                }).reset_index()
                dept_summary['Avg_Utilization'] = (dept_summary['Enrollment_Count'] / 
                                                 dept_summary['SeatsAvailable']).round(3)
                dept_summary.to_excel(writer, sheet_name='FactDepartmentSummary', index=False)

                # Create student course load summary
                student_load_summary.to_excel(writer, sheet_name='FactStudentLoad', index=False)

                # Create time slot summary
                time_summary = master_schedule.merge(
                    utilization[['SectionID', 'Enrollment_Count', 'SeatsAvailable']],
                    on='SectionID',
                    how='left'
                ).groupby('Period').agg({
                    'SectionID': 'count',
                    'Enrollment_Count': 'sum',
                    'SeatsAvailable': 'sum'
                }).reset_index()
                time_summary['Utilization_Rate'] = (time_summary['Enrollment_Count'] / 
                                                  time_summary['SeatsAvailable']).round(3)
                time_summary.to_excel(writer, sheet_name='FactTimeSlotSummary', index=False)

                preferences_summary.to_excel(writer, sheet_name='FactPreferenceFulfillment', index=False)

                # Make sure the workbook has the first sheet visible and active
                writer.book.active = 0

            # Archive old files if they exist
            for file in os.listdir(self.data_dir):
                if file.startswith('MasterSchedule_') and file.endswith('.xlsx') and file != os.path.basename(excel_path):
                    shutil.move(
                        os.path.join(self.data_dir, file),
                        os.path.join(self.archive_dir, file)
                    )

            print(f"\nCreated new dataset: {excel_path}")
            return excel_path

        except Exception as e:
            print(f"Error creating dataset: {str(e)}")
            raise

    def update_dashboard(self):
        """
        Main workflow for updating the dashboard data.
        
        This method orchestrates the entire update process:
        - Creates new dataset
        - Archives old files
        - Provides usage instructions
        
        Raises:
            Exception: If any step in the process fails
        """
        try:
            print("Starting dashboard update process...")
            excel_path = self.create_excel_dataset()
            print("\nDashboard data has been updated successfully!")
            print("\nTo use with PowerBI:")
            print("1. Create a PowerBI Template (.pbit) pointing to the Data folder")
            print("2. Each time you open the template, it will use the latest dataset")
            print(f"\nLatest dataset: {excel_path}")
            
        except Exception as e:
            print(f"Error updating dashboard: {str(e)}")
            raise

if __name__ == "__main__":
    automation = ScheduleDashboardAutomation()
    automation.update_dashboard()