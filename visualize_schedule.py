import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Define the ordered periods
ordered_periods = ['R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4']

# Read data files
df_teachers = pd.read_csv('output/Teacher_Assignments.csv')
df_students = pd.read_csv('output/Student_Assignments.csv')
df_master = pd.read_csv('output/Master_Schedule.csv')
sections_info = pd.read_csv('input/Sections_Information.csv')

# Merge course information
df_teachers = df_teachers.merge(sections_info[['Section ID', 'Course ID']], on='Section ID', how='left')
df_students = df_students.merge(sections_info[['Section ID', 'Course ID']], on='Section ID', how='left')

# Sort periods categorically
df_teachers['Period'] = pd.Categorical(df_teachers['Period'], categories=ordered_periods, ordered=True)
df_teachers = df_teachers.sort_values(['Period', 'Teacher ID'])

def create_master_table():
    """Creates the master schedule view"""
    student_counts = df_students.groupby('Section ID').size().reindex(df_teachers['Section ID']).fillna(0)
    return go.Table(
        header=dict(
            values=['Period', 'Teacher ID', 'Course ID', 'Section ID', 'Student Count'],
            fill_color='#1C3F99',
            font=dict(color='white'),
            align='left',
            line_color='#476FD6'
        ),
        cells=dict(
            values=[
                df_teachers['Period'],
                df_teachers['Teacher ID'],
                df_teachers['Course ID'].fillna('Unknown'),
                df_teachers['Section ID'],
                student_counts
            ],
            fill_color='#FBFCFE',
            font=dict(color='#15213F'),
            align='left',
            line_color='#EDF1F8'
        )
    )

def create_teacher_table(teacher_id=None):
    """Creates a teacher-specific schedule view"""
    df = df_teachers if teacher_id is None else df_teachers[df_teachers['Teacher ID'] == teacher_id]
    return go.Table(
        header=dict(
            values=['Teacher ID', 'Period', 'Course ID', 'Section ID'],
            fill_color='#1C3F99',
            font=dict(color='white'),
            align='left',
            line_color='#476FD6'
        ),
        cells=dict(
            values=[
                df['Teacher ID'],
                df['Period'],
                df['Course ID'],
                df['Section ID']
            ],
            fill_color='#FBFCFE',
            font=dict(color='#15213F'),
            align='left',
            line_color='#EDF1F8'
        )
    )

def create_student_table(student_id=None):
    """Creates a student-specific schedule view"""
    df = df_students if student_id is None else df_students[df_students['Student ID'] == student_id]
    section_info = df_teachers.set_index('Section ID')
    periods = df['Section ID'].map(section_info['Period']).fillna('Unknown')
    teacher_ids = df['Section ID'].map(section_info['Teacher ID']).fillna('Unknown')
    
    return go.Table(
        header=dict(
            values=['Student ID', 'Period', 'Course ID', 'Teacher ID'],
            fill_color='#1C3F99',
            font=dict(color='white'),
            align='left',
            line_color='#476FD6'
        ),
        cells=dict(
            values=[
                df['Student ID'],
                periods,
                df['Course ID'].fillna('Unknown'),
                teacher_ids
            ],
            fill_color='#FBFCFE',
            font=dict(color='#15213F'),
            align='left',
            line_color='#EDF1F8'
        )
    )

# Create the main figure with subplots
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=("Master Schedule", "Teacher View", "Student View", "Course Statistics"),
    specs=[[{"type": "table"}, {"type": "table"}],
           [{"type": "table"}, {"type": "bar"}]]
)

# Add the initial views
fig.add_trace(create_master_table(), row=1, col=1)
fig.add_trace(create_teacher_table(), row=1, col=2)
fig.add_trace(create_student_table(), row=2, col=1)

# Add course statistics with updated styling
course_stats = df_students.groupby('Course ID').size()
fig.add_trace(
    go.Bar(
        x=course_stats.index, 
        y=course_stats.values, 
        name="Enrollments",
        marker_color='#1C3F99',
        hovertemplate="Course: %{x}<br>Students: %{y}<extra></extra>"
    ),
    row=2, col=2
)

# Create dropdown menus
def create_view_buttons():
    return [
        dict(label="All Views",
             method="update",
             args=[{"visible": [True] * 4}]),
        dict(label="Master Schedule Only",
             method="update",
             args=[{"visible": [True, False, False, False]}]),
        dict(label="Teacher View Only",
             method="update",
             args=[{"visible": [False, True, False, False]}]),
        dict(label="Student View Only",
             method="update",
             args=[{"visible": [False, False, True, False]}]),
        dict(label="Statistics Only",
             method="update",
             args=[{"visible": [False, False, False, True]}])
    ]

# Update layout with new theme
fig.update_layout(
    title=dict(
        text="Interactive Master Schedule Dashboard",
        font=dict(color='#1C3F99', size=24),
        x=0.5,
        y=0.95
    ),
    showlegend=True,
    height=1000,
    width=1200,
    paper_bgcolor='#EDF1F8',
    plot_bgcolor='#FBFCFE',
    font=dict(color='#15213F'),
    updatemenus=[
        # View selection dropdown
        dict(
            buttons=create_view_buttons(),
            direction="down",
            showactive=True,
            x=0.1,
            xanchor="left",
            y=1.15,
            yanchor="top",
            bgcolor='#FBFCFE',
            font=dict(color='#15213F')
        ),
        # Period filter dropdown
        dict(
            buttons=[dict(label="All Periods",
                         method="update",
                         args=[{"visible": [True] * 4}])] +
                    [dict(label=p,
                          method="update",
                          args=[{"visible": [True] * 4}])
                     for p in ordered_periods],
            direction="down",
            showactive=True,
            x=0.3,
            xanchor="left",
            y=1.15,
            yanchor="top",
            bgcolor='#FBFCFE',
            font=dict(color='#15213F')
        )
    ]
)

# Update subplot titles
fig.update_annotations(font_size=16, font_color='#1C3F99')

# Add dropdown for teacher/student selection
fig.add_trace(
    go.Scatter(
        x=[0],
        y=[0],
        mode='markers',
        marker=dict(size=0),
        showlegend=False,
        hoverinfo='none',
        visible=False
    )
)

# Show the figure
fig.show()
