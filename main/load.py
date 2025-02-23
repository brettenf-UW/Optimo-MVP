import pandas as pd
from pathlib import Path
import os
import datetime

class ScheduleDataLoader:
    MAX_LOG_ENTRIES = 100  # Limit logs for large datasets

    def __init__(self):
        """Initialize file paths and debug logging."""
        self.project_root = Path(__file__).parent.parent
        self.input_dir = self.project_root / 'input'
        self.debug_dir = self.project_root / 'debug'
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped debug files
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.summary_file = self.debug_dir / f"debug_summary_{timestamp}.log"
        self.base_data_file = self.debug_dir / f"base_data_{timestamp}.log"
        self.relationship_file = self.debug_dir / f"relationship_data_{timestamp}.log"
        self.validation_file = self.debug_dir / f"validation_{timestamp}.log"

        self.data = {}
        if not self.input_dir.exists():
            self.log_summary("[ERROR] Input directory not found.")
            raise FileNotFoundError(f"[ERROR] Input directory not found at {self.input_dir}")

        self.log_summary("[INIT] ✅ Data loader initialized successfully.")

    def log(self, file, message):
        """Write debug logs to the specified log file."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")

    def log_summary(self, message):
        """Write to the summary file and console."""
        self.log(self.summary_file, message)
        print(message)  # Also print to console

    def load_base_data(self):
        """Load primary data files."""
        try:
            self.log(self.base_data_file, "[LOAD] 📦 Loading base data files...")
            self.data['students'] = pd.read_csv(self.input_dir / 'Student_Info.csv')
            self.log(self.base_data_file, f"[LOAD] ✅ Students loaded: {len(self.data['students'])} records")

            self.data['teachers'] = pd.read_csv(self.input_dir / 'Teacher_Info.csv')
            self.log(self.base_data_file, f"[LOAD] ✅ Teachers loaded: {len(self.data['teachers'])} records")

            self.data['sections'] = pd.read_csv(self.input_dir / 'Sections_Information.csv')
            self.log(self.base_data_file, f"[LOAD] ✅ Sections loaded: {len(self.data['sections'])} records")

            self.data['periods'] = pd.read_csv(self.input_dir / 'Period.csv')
            self.log(self.base_data_file, f"[LOAD] ✅ Periods loaded: {len(self.data['periods'])} records")

        except FileNotFoundError as e:
            self.log_summary(f"[ERROR] Missing input file: {e.filename}")
            raise

    def load_relationship_data(self):
        """Load relationship data."""
        try:
            self.log(self.relationship_file, "[LOAD] 📦 Loading relationship data...")

            self.data['student_preferences'] = pd.read_csv(self.input_dir / 'Student_Preference_Info.csv')
            self.log(self.relationship_file, f"[LOAD] ✅ Student preferences: {len(self.data['student_preferences'])} records")

            try:
                self.data['teacher_unavailability'] = pd.read_csv(self.input_dir / 'Teacher_unavailability.csv')
                self.log(self.relationship_file, f"[LOAD] ✅ Teacher unavailability: {len(self.data['teacher_unavailability'])} records")
            except (pd.errors.EmptyDataError, FileNotFoundError):
                self.data['teacher_unavailability'] = pd.DataFrame(columns=['Teacher ID', 'Unavailable Periods'])
                self.log(self.relationship_file, "[WARNING] ⚠️ Teacher unavailability not found or empty.")

        except FileNotFoundError as e:
            self.log_summary(f"[ERROR] Missing relationship file: {e.filename}")
            raise

    def validate_relationships(self):
        """Validate relationships between data."""
        self.log(self.validation_file, "[VALIDATE] 🔎 Validating data relationships...")
        validation_issues = []

        sections = self.data['sections']
        teachers = self.data['teachers']
        prefs = self.data['student_preferences']

        # Validate teachers
        teachers_in_sections = sections['Teacher Assigned'].unique()
        known_teachers = teachers['Teacher ID'].unique()
        unknown_teachers = set(teachers_in_sections) - set(known_teachers)
        if unknown_teachers:
            issue = f"[VALIDATE] ⚠️ Unknown teachers: {unknown_teachers}"
            validation_issues.append(issue)
            self.log(self.validation_file, issue)

        # Validate student preferences
        all_courses = sections['Course ID'].unique()
        for idx, row in prefs.head(self.MAX_LOG_ENTRIES).iterrows():
            requested_courses = str(row['Preferred Sections']).split(';')
            unknown_courses = set(requested_courses) - set(all_courses)
            if unknown_courses:
                issue = f"[VALIDATE] ⚠️ Student {row['Student ID']} references unknown courses: {unknown_courses}"
                validation_issues.append(issue)
                self.log(self.validation_file, issue)

        if not validation_issues:
            self.log_summary("[VALIDATE] ✅ All relationships are valid.")
        else:
            self.log_summary("[VALIDATE] ❌ Validation issues found. See logs for details.")

    def load_all(self):
        """Load and validate all data."""
        try:
            self.log_summary("[LOAD ALL] 🚀 Starting data load...")
            self.load_base_data()
            self.load_relationship_data()
            self.validate_relationships()
            self.log_summary("[LOAD ALL] ✅ Data load complete.")
            return self.data
        except Exception as e:
            self.log_summary(f"[ERROR] ❌ An error occurred: {str(e)}")
            print(f"\n[ERROR] ❌ An error occurred: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        loader = ScheduleDataLoader()
        data = loader.load_all()
        print("\n[INFO] Data loaded successfully:")
        for key, df in data.items():
            print(f" - {key}: {len(df)} records")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
