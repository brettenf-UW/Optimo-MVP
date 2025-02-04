import pandas as pd
import plotly.graph_objects as go
import os

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(current_dir, 'output')

# Read all CSV files with proper path
master_schedule = pd.read_csv(os.path.join(output_dir, 'Master_Schedule.csv'))
teacher_assignments = pd.read_csv(os.path.join(output_dir, 'Teacher_Assignments.csv'))
student_assignments = pd.read_csv(os.path.join(output_dir, 'Student_Assignments.csv'))

# Merge master schedule with teacher assignments
schedule_with_teachers = pd.merge(
    master_schedule,
    teacher_assignments[['Section ID', 'Teacher ID']],
    on='Section ID',
    how='left'
)

# Count students per section
students_per_section = student_assignments.groupby('Section ID').size().reset_index(name='Student Count')

# Create final schedule dataframe
final_schedule = pd.merge(
    schedule_with_teachers,
    students_per_section,
    on='Section ID',
    how='left'
)

# Create a pivot table for visualization
schedule_pivot = pd.pivot_table(
    final_schedule,
    index=['Section ID', 'Teacher ID', 'Student Count'],
    columns=['Period'],
    aggfunc=lambda x: 'X',
    fill_value=''
)

# Reset index for plotting
schedule_pivot = schedule_pivot.reset_index()

# Create the table visualization
fig = go.Figure(data=[go.Table(
    header=dict(
        values=['Section ID', 'Teacher ID', 'Student Count', 'R1', 'R2', 'R3', 'R4', 'G1', 'G2', 'G3', 'G4'],
        fill_color='paleturquoise',
        align='left'
    ),
    cells=dict(
        values=[schedule_pivot[col] for col in schedule_pivot.columns],
        fill_color='lavender',
        align='left'
    )
)])

# Update layout
fig.update_layout(
    title='Master Schedule',
    width=1000,
    height=400,
)

# Show the figure
fig.show()

# Save the figure as HTML in the correct directory
output_file = os.path.join(output_dir, "master_schedule_visualization.html")
fig.write_html(output_file)

print(f"Visualization has been created and saved as '{output_file}'")
