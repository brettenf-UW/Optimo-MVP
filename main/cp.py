# File: cp.py
from ortools.sat.python import cp_model
import pandas as pd
import sys
from load import ScheduleDataLoader
import datetime
from pathlib import Path
import os

# Constants for logging
MAX_LOG_ENTRIES = 100

def setup_debug_log():
    """
    Initialize debug logging with exactly 2 files:
      1) process.log - Main process flow and results
      2) debug.log  - Detailed debugging information
    """
    project_root = Path(__file__).parent.parent
    debug_dir = project_root / 'debug'
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Delete ALL existing logs
    for log_file in debug_dir.glob('*.log'):
        try:
            os.remove(log_file)
        except OSError:
            pass

    # Create just 2 log files
    log_files = {
        'process': debug_dir / "process.log",
        'debug': debug_dir / "debug.log"
    }

    # Initialize each log file
    for name, path in log_files.items():
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"=== {name.upper()} LOG ===\n")

    return log_files


def log(file_path, message):
    """Write logs with timestamps."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)


def solve_schedule():
    """Solve the scheduling problem using only 2 debug logs."""
    debug_files = setup_debug_log()

    # ---------------------------
    # 1) Load Data
    # ---------------------------
    log(debug_files['process'], "\n[STEP 1] 📦 Loading data...")
    loader = ScheduleDataLoader()
    data = loader.load_all()

    sections_df = data['sections']
    teachers_df = data['teachers']
    periods_df = data['periods']
    students_df = data['students']
    prefs_df = data['student_preferences']

    log(debug_files['process'], f"[STEP 1] ✅ Loaded data: {len(sections_df)} sections,"
                                f" {len(teachers_df)} teachers,"
                                f" {len(periods_df)} periods,"
                                f" {len(students_df)} students")

    # ---------------------------
    # 2) Teacher Availability
    # ---------------------------
    log(debug_files['process'], "\n[STEP 2] 🗓 Building teacher availability map...")
    teacher_unavail = {}
    unavdf = data.get('teacher_unavailability', pd.DataFrame())
    for _, row in unavdf.iterrows():
        t_id = row['Teacher ID']
        unavailable = set(s.strip() for s in str(row.get('Unavailable Periods', '')).split(',') if s.strip())
        teacher_unavail[t_id] = unavailable
    log(debug_files['process'], f"[STEP 2] ✅ Teacher availability map built for {len(teacher_unavail)} teachers.")

    # ---------------------------
    # 3) Section-to-Period Domains
    # ---------------------------
    log(debug_files['process'], "\n[STEP 3] 🧩 Building section-to-period domains...")
    section_period_domain = {}
    domain_count = 0
    for _, row in sections_df.iterrows():
        sec_id = row['Section ID']
        t_id = row['Teacher Assigned']
        unavailable = teacher_unavail.get(t_id, set())
        valid_periods = set(periods_df['period_name']) - unavailable
        section_period_domain[sec_id] = valid_periods

        # Log up to MAX_LOG_ENTRIES
        if domain_count < MAX_LOG_ENTRIES:
            log(debug_files['debug'], f"🧩 Domain: Section {sec_id} (Teacher {t_id}) => {valid_periods}")
            domain_count += 1

    log(debug_files['process'], f"[STEP 3] ✅ Section-to-period domains built. Logged first {domain_count} entries.")

    # ---------------------------
    # 4) Build CP Model
    # ---------------------------
    log(debug_files['process'], "\n[STEP 4] 🧠 Building CP-SAT model...")
    model = cp_model.CpModel()

    # Create section-period variables
    log(debug_files['process'], "[STEP 4] 🧩 Creating section-period variables...")
    section_period_vars = {}
    var_count = 0
    for sec_id, valid_p in section_period_domain.items():
        for p in valid_p:
            var_name = f"sec_{sec_id}_p_{p}"
            section_period_vars[(sec_id, p)] = model.NewBoolVar(var_name)

            if var_count < MAX_LOG_ENTRIES:
                log(debug_files['debug'], f"🧷 Var: {var_name}")
                var_count += 1

    log(debug_files['process'], f"[STEP 4] ✅ Created all section-period vars. Logged first {var_count} entries.")

    # ---------------------------
    # 5) Constraints
    # ---------------------------
    log(debug_files['process'], "\n[STEP 5] 📏 Adding constraints...")
    constr_count = 0
    for sec_id, valid_p in section_period_domain.items():
        if valid_p:
            c = model.Add(sum(section_period_vars[(sec_id, p)] for p in valid_p) == 1)
            if constr_count < MAX_LOG_ENTRIES:
                log(debug_files['debug'],
                    f"📏 Constraint: {sec_id} in exactly 1 period. (ID: {c.Index()})"
                )
                constr_count += 1
        else:
            log(debug_files['debug'],
                f"[WARNING] ❌ Section {sec_id} has no valid periods => infeasible if mandatory.")

    log(debug_files['process'], f"[STEP 5] ✅ Constraints added. Logged first {constr_count} entries.")

    # ---------------------------
    # 6) Solve
    # ---------------------------
    log(debug_files['process'], "\n[STEP 6] 🚀 Solving CP-SAT model...")
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True

    # Redirect solver logs to debug.log instead of separate file
    old_stdout = sys.stdout
    sys.stdout = open(debug_files['debug'], 'a', encoding='utf-8')
    status = solver.Solve(model)
    sys.stdout.close()
    sys.stdout = old_stdout  # restore original stdout

    # ---------------------------
    # 7) Results
    # ---------------------------
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        log(debug_files['process'], "\n✅ Feasible solution found!")
        for sec_id, valid_p in section_period_domain.items():
            for p in valid_p:
                if solver.Value(section_period_vars[(sec_id, p)]) == 1:
                    log(debug_files['process'], f"[RESULT] 📚 Section {sec_id} → Period {p}")
    elif status == cp_model.INFEASIBLE:
        log(debug_files['process'], "\n[ERROR] ❌ No feasible solution found (infeasible).")
    else:
        log(debug_files['process'], "\n[ERROR] ❌ No solution found within the search limit.")


if __name__ == "__main__":
    solve_schedule()
