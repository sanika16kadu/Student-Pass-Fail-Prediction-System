import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import messagebox, filedialog
import matplotlib.pyplot as plt
from model import predict_student, FEATURE_COLUMNS, get_metrics
from db_init import init_db

# Ensure database is initialized
init_db("users.db")

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Load latest dataset
try:
    data = pd.read_csv("student_data.csv")
except Exception:
    data = pd.DataFrame()

# ---------------- GUI ROOT ----------------
root = tk.Tk()
root.title("Student Pass & Fail Prediction System (AI/ML)")
root.geometry("520x560")
root.config(bg="#1e293b")

def clear():
    for widget in root.winfo_children():
        widget.destroy()

# ---------------- REGISTER ----------------
def register():
    clear()
    tk.Label(root, text="Teacher Registration", font=("Arial", 16, "bold"), fg="white", bg="#1e293b").pack(pady=15)

    tk.Label(root, text="Username:", fg="#94a3b8", bg="#1e293b").pack()
    user = tk.Entry(root, width=30)
    user.pack(pady=4)

    tk.Label(root, text="Password:", fg="#94a3b8", bg="#1e293b").pack()
    pwd = tk.Entry(root, show="*", width=30)
    pwd.pack(pady=4)

    def save():
        u = user.get().strip()
        p = pwd.get().strip()
        if not u or not p:
            messagebox.showerror("Error", "Username and password cannot be empty")
            return
        try:
            cursor.execute("INSERT INTO users (username, password, question, answer) VALUES (?, ?, ?, ?)",
                           (u, p, "Default Security Question", "answer"))
            conn.commit()
            messagebox.showinfo("Success", "Registered successfully!")
            login()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")

    tk.Button(root, text="Register", command=save, bg="#22c55e", fg="white", width=20, font=("Arial", 10, "bold")).pack(pady=12)
    tk.Button(root, text="Back to Login", command=login, bg="#475569", fg="white", width=20).pack()

# ---------------- LOGIN ----------------
def login():
    clear()
    tk.Label(root, text="AI Student Prediction System", font=("Arial", 16, "bold"), fg="white", bg="#1e293b").pack(pady=15)
    tk.Label(root, text="Teacher Login", font=("Arial", 12), fg="#38bdf8", bg="#1e293b").pack(pady=5)

    tk.Label(root, text="Username:", fg="#94a3b8", bg="#1e293b").pack()
    user = tk.Entry(root, width=30)
    user.pack(pady=4)

    tk.Label(root, text="Password:", fg="#94a3b8", bg="#1e293b").pack()
    pwd = tk.Entry(root, show="*", width=30)
    pwd.pack(pady=4)

    def check():
        u = user.get().strip()
        p = pwd.get().strip()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        if cursor.fetchone():
            dashboard(u)
        else:
            messagebox.showerror("Error", "Invalid username or password")

    tk.Button(root, text="Login", command=check, bg="#3b82f6", fg="white", width=20, font=("Arial", 10, "bold")).pack(pady=12)
    tk.Button(root, text="Register New Teacher", command=register, bg="#475569", fg="white", width=20).pack()

# ---------------- DASHBOARD ----------------
def dashboard(username="Teacher"):
    clear()
    metrics = get_metrics()
    algo = metrics.get('best_algorithm', 'Random Forest')

    tk.Label(root, text="Academic Dashboard", font=("Arial", 16, "bold"), fg="white", bg="#1e293b").pack(pady=10)
    tk.Label(root, text=f"Logged in: {username}", fg="#38bdf8", bg="#1e293b", font=("Arial", 10)).pack()
    tk.Label(root, text=f"Active ML Model: {algo}", fg="#a3e635", bg="#1e293b", font=("Arial", 10, "bold")).pack(pady=4)

    # Student count from DB
    cursor.execute("SELECT COUNT(*) FROM students")
    total_db = cursor.fetchone()[0]

    tk.Label(root, text=f"Total Students in DB: {total_db}", fg="white", bg="#1e293b", font=("Arial", 12)).pack(pady=8)

    tk.Button(root, text="🎯 Predict Student (AI Model)", command=lambda: predict_screen(username),
              bg="#22c55e", fg="white", width=25, font=("Arial", 10, "bold")).pack(pady=6)

    tk.Button(root, text="📊 Show Pass/Fail Distribution", command=show_chart,
              bg="#f59e0b", fg="white", width=25, font=("Arial", 10, "bold")).pack(pady=6)

    tk.Button(root, text="📁 Load New Dataset CSV", command=lambda: upload_file(username),
              bg="#06b6d4", fg="white", width=25, font=("Arial", 10, "bold")).pack(pady=6)

    tk.Button(root, text="🚪 Logout", command=login, bg="#ef4444", fg="white", width=25).pack(pady=15)

# ---------------- CHART ----------------
def show_chart():
    try:
        cursor.execute("SELECT result FROM students")
        results = [r[0] for r in cursor.fetchall() if r[0]]
        pass_count = sum(1 for r in results if 'PASS' in str(r).upper())
        fail_count = sum(1 for r in results if 'FAIL' in str(r).upper())

        if pass_count == 0 and fail_count == 0 and not data.empty and 'result' in data.columns:
            pass_count = int((data['result'] == 1).sum())
            fail_count = int((data['result'] == 0).sum())

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(['Pass', 'Fail'], [pass_count, fail_count], color=['#10b981', '#ef4444'])
        ax.set_title("Student Pass vs Fail Distribution")
        ax.set_ylabel("Number of Students")
        plt.tight_layout()
        plt.show()
    except Exception as e:
        messagebox.showerror("Chart Error", str(e))

# ---------------- UPLOAD CSV ----------------
def upload_file(username):
    global data
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if file_path:
        try:
            data = pd.read_csv(file_path)
            messagebox.showinfo("Success", f"Loaded {len(data)} student records from CSV!")
            dashboard(username)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")

# ---------------- PREDICTION SCREEN ----------------
def predict_screen(username):
    clear()
    tk.Label(root, text="Academic Pass/Fail Predictor", font=("Arial", 15, "bold"), fg="white", bg="#1e293b").pack(pady=10)

    entries = {}
    fields = [
        ("attendance", "Attendance % (0-100):", "80.0"),
        ("prev_sem_percentage", "Previous Sem % (0-100):", "72.0"),
        ("internal_marks", "Internal Marks (0-100):", "65.0"),
        ("assignment_marks", "Assignment Marks (0-100):", "70.0"),
        ("practical_marks", "Practical Marks (0-100):", "75.0"),
        ("study_hours", "Daily Study Hours (0-16):", "4.0"),
        ("backlogs", "Previous Backlogs Count:", "0")
    ]

    form_frame = tk.Frame(root, bg="#1e293b")
    form_frame.pack(pady=5)

    for i, (key, label, default) in enumerate(fields):
        tk.Label(form_frame, text=label, fg="#cbd5e1", bg="#1e293b", anchor="w", width=26).grid(row=i, column=0, pady=2, sticky="w")
        ent = tk.Entry(form_frame, width=14)
        ent.insert(0, default)
        ent.grid(row=i, column=1, pady=2)
        entries[key] = ent

    result_lbl = tk.Label(root, text="", fg="white", bg="#1e293b", font=("Arial", 13, "bold"))
    result_lbl.pack(pady=8)

    prob_lbl = tk.Label(root, text="", fg="#94a3b8", bg="#1e293b", font=("Arial", 10))
    prob_lbl.pack(pady=2)

    def do_predict():
        try:
            payload = {
                'attendance': float(entries['attendance'].get()),
                'prev_sem_percentage': float(entries['prev_sem_percentage'].get()),
                'internal_marks': float(entries['internal_marks'].get()),
                'assignment_marks': float(entries['assignment_marks'].get()),
                'practical_marks': float(entries['practical_marks'].get()),
                'study_hours': float(entries['study_hours'].get()),
                'backlogs': int(entries['backlogs'].get())
            }

            res = predict_student(payload)
            if res['prediction'] == "PASS":
                result_lbl.config(text="Prediction: PASS ✔", fg="#22c55e")
            else:
                result_lbl.config(text="Prediction: FAIL ✖", fg="#ef4444")

            prob_lbl.config(
                text=f"Confidence: {res['confidence']}% | Pass: {res['pass_probability']*100:.1f}% | Fail: {res['fail_probability']*100:.1f}%\nModel: {res['algorithm']}"
            )
        except Exception as e:
            messagebox.showerror("Validation Error", str(e))

    btn_frame = tk.Frame(root, bg="#1e293b")
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="⚡ Run ML Prediction", command=do_predict,
              bg="#22c55e", fg="white", font=("Arial", 10, "bold"), width=20).grid(row=0, column=0, padx=5)

    tk.Button(btn_frame, text="Back to Dashboard", command=lambda: dashboard(username),
              bg="#64748b", fg="white", width=16).grid(row=0, column=1, padx=5)

if __name__ == "__main__":
    login()
    root.mainloop()