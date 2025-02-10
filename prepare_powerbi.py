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

    def process_conflicts_and_recommendations(self):
        """Process conflicts and recommendations from linear programming output"""
        try:
            # Read conflicts file
            conflicts = self.safe_read_csv('output/conflicts.csv', required=False)
            if not conflicts.empty:
                # Ensure we have the expected columns
                expected_columns = ['Student ID', 'Course ID 1', 'Course ID 2', 'Conflict Type', 'Description']
                if not all(col in conflicts.columns for col in expected_columns):
                    print("Warning: Conflicts file missing expected columns")
                    print(f"Expected: {expected_columns}")
                    print(f"Found: {conflicts.columns.tolist()}")
                    return pd.DataFrame(), pd.DataFrame()
                    
                conflicts = conflicts.rename(columns={
                    'Student ID': 'StudentID',
                    'Course ID 1': 'CourseID1',
                    'Course ID 2': 'CourseID2',
                    'Conflict Type': 'ConflictType',
                    'Description': 'ConflictDescription'
                })
                conflicts['DetectedDateTime'] = datetime.now()
                
                # Add severity level based on conflict type
                conflicts['Severity'] = conflicts['ConflictType'].map({
                    'HARD': 'High',
                    'SOFT': 'Medium',
                    'WARNING': 'Low'
                }).fillna('Medium')

            # Read recommendations file
            recommendations = self.safe_read_csv('output/recommendations.csv', required=False)
            if not recommendations.empty:
                recommendations = recommendations.rename(columns={
                    'Section ID': 'SectionID',
                    'Student ID': 'StudentID',
                    'Recommendation Type': 'RecommendationType',
                    'Description': 'RecommendationDescription',
                    'Priority': 'RecommendationPriority'
                })
                # Add timestamp for when the recommendation was generated
                recommendations['GeneratedDateTime'] = datetime.now()

            return conflicts, recommendations
        except Exception as e:
            print(f"Error processing conflicts and recommendations: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()

    def create_excel_dataset(self):
        """Create a consolidated Excel file containing all dimension and fact tables."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_path = os.path.join(self.data_dir, f'MasterSchedule_{timestamp}.xlsx')
        
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # Load input files with careful header handling
                sections_info = self.safe_read_csv('input/Sections_Information.csv')
                student_info = self.safe_read_csv('input/Student_Info.csv')
                teacher_info = self.safe_read_csv('input/Teacher_Info.csv')
                master_schedule = self.safe_read_csv('output/Master_Schedule.csv')
                student_assignments = self.safe_read_csv('output/Student_Assignments.csv')
                teacher_assignments = self.safe_read_csv('output/Teacher_Assignments.csv')

                # Standardize column names based on actual input columns
                sections_info = sections_info.rename(columns={
                    'Section ID': 'SectionID',
                    'Course ID': 'CourseID',
                    'Teacher Assigned': 'TeacherID',  # This matches the actual column name
                    '# of Seats Available': 'SeatsAvailable',
                    'Department': 'SectionDepartment'  # Add this if present
                })

                student_info = student_info.rename(columns={
                    'Student ID': 'StudentID',
                    'SPED': 'SPED'  # Keep as is
                })

                teacher_info = teacher_info.rename(columns={
                    'Teacher ID': 'TeacherID',
                    'Department': 'TeacherDepartment'
                })

                master_schedule = master_schedule.rename(columns={
                    'Section ID': 'SectionID',
                    'Period': 'Period'
                })

                student_assignments = student_assignments.rename(columns={
                    'Student ID': 'StudentID',
                    'Section ID': 'SectionID'
                })

                # Ensure teacher assignments has correct column names
                teacher_assignments = teacher_assignments.rename(columns={
                    'Teacher ID': 'TeacherID',
                    'Section ID': 'SectionID',
                    'Period': 'Period'
                })

                # Create DimPeriod from master schedule
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

                # Save dimension tables
                periods.to_excel(writer, sheet_name='DimPeriod', index=False)
                teacher_info.to_excel(writer, sheet_name='DimTeacher', index=False)
                student_info.to_excel(writer, sheet_name='DimStudent', index=False)
                sections_info.to_excel(writer, sheet_name='DimSection', index=False)

                # Create fact tables with proper relationships
                # First merge sections with teacher department info
                sections_with_dept = pd.merge(
                    sections_info,
                    teacher_info[['TeacherID', 'TeacherDepartment']],
                    on='TeacherID',
                    how='left'
                )

                # Create schedule fact table
                schedule_fact = pd.merge(
                    master_schedule,
                    sections_with_dept,
                    on='SectionID',
                    how='left'
                )
                schedule_fact.to_excel(writer, sheet_name='FactSchedule', index=False)

                # Create student enrollment fact table
                enrollment_fact = pd.merge(
                    student_assignments,
                    sections_with_dept,
                    on='SectionID',
                    how='left'
                )
                enrollment_fact = pd.merge(
                    enrollment_fact,
                    master_schedule[['SectionID', 'Period']],
                    on='SectionID',
                    how='left'
                )
                enrollment_fact.to_excel(writer, sheet_name='FactStudentEnrollment', index=False)

                # Create section utilization fact table
                section_counts = student_assignments.groupby('SectionID').size().reset_index(name='EnrollmentCount')
                utilization_fact = pd.merge(
                    sections_with_dept,
                    section_counts,
                    on='SectionID',
                    how='left'
                )
                utilization_fact['EnrollmentCount'] = utilization_fact['EnrollmentCount'].fillna(0)
                utilization_fact['UtilizationRate'] = utilization_fact['EnrollmentCount'] / utilization_fact['SeatsAvailable']
                utilization_fact['UtilizationPercentage'] = (utilization_fact['UtilizationRate'] * 100).round(2)
                utilization_fact.to_excel(writer, sheet_name='FactSectionUtilization', index=False)

                # Process conflicts and recommendations if available
                conflicts, recommendations = self.process_conflicts_and_recommendations()
                if not conflicts.empty:
                    conflicts.to_excel(writer, sheet_name='FactConflicts', index=False)
                if not recommendations.empty:
                    recommendations.to_excel(writer, sheet_name='FactRecommendations', index=False)

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