import numpy as np
import pandas as pd
import os

def generate_student_dataset(output_path="student_data.csv", n_samples=1200, seed=42):
    """
    Generates a realistic student academic dataset for Pass/Fail classification.
    Features:
      1. attendance: Attendance percentage (35.0% - 100.0%)
      2. prev_sem_percentage: Previous semester percentage (35.0% - 98.0%)
      3. internal_marks: Internal assessment marks (15.0 - 98.0 out of 100)
      4. assignment_marks: Assignment marks (20.0 - 100.0 out of 100)
      5. practical_marks: Practical/Lab marks (25.0 - 100.0 out of 100)
      6. study_hours: Daily study hours (0.5 - 10.0 hours/day)
      7. backlogs: Number of previous backlogs/arrears (0 - 5)
    Target:
      result: 1 (PASS) or 0 (FAIL)
    """
    np.random.seed(seed)

    attendance = np.clip(np.random.normal(72.5, 13.5, n_samples), 35.0, 100.0).round(1)
    prev_sem = np.clip(np.random.normal(68.0, 12.8, n_samples), 35.0, 98.0).round(1)
    internal = np.clip(np.random.normal(64.5, 14.5, n_samples), 15.0, 98.0).round(1)
    assignment = np.clip(np.random.normal(70.0, 13.8, n_samples), 20.0, 100.0).round(1)
    practical = np.clip(np.random.normal(72.0, 13.0, n_samples), 25.0, 100.0).round(1)
    study_hours = np.clip(np.random.normal(3.8, 1.8, n_samples), 0.5, 10.0).round(1)
    backlogs = np.random.choice([0, 1, 2, 3, 4, 5], size=n_samples, p=[0.55, 0.22, 0.12, 0.06, 0.03, 0.02])

    # Realistic composite academic index based on educational factors
    academic_index = (
        0.22 * (attendance / 100.0) +
        0.22 * (prev_sem / 100.0) +
        0.20 * (internal / 100.0) +
        0.10 * (assignment / 100.0) +
        0.10 * (practical / 100.0) +
        0.12 * (study_hours / 6.0) -
        0.16 * (backlogs / 2.0)
    )

    # Add realistic variation/noise
    noise = np.random.normal(0, 0.08, n_samples)
    sigmoid_input = (academic_index + noise - 0.52) * 12.0
    pass_prob = 1.0 / (1.0 + np.exp(-sigmoid_input))
    result = (pass_prob >= 0.5).astype(int)

    df = pd.DataFrame({
        'attendance': attendance,
        'prev_sem_percentage': prev_sem,
        'internal_marks': internal,
        'assignment_marks': assignment,
        'practical_marks': practical,
        'study_hours': study_hours,
        'backlogs': backlogs,
        'result': result
    })

    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} samples saved to {output_path}")
    print(f"Pass count: {(result == 1).sum()} ({(result == 1).mean() * 100:.1f}%)")
    print(f"Fail count: {(result == 0).sum()} ({(result == 0).mean() * 100:.1f}%)")
    return df

if __name__ == "__main__":
    generate_student_dataset()