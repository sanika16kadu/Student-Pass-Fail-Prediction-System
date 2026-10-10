import sqlite3

def init_db(db_path="users.db"):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT,
        section TEXT DEFAULT 'A',
        question TEXT,
        answer TEXT
    )
    """)

    # Check existing user columns
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [c[1] for c in cursor.fetchall()]
    if 'section' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN section TEXT DEFAULT 'A'")

    # Create students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        teacher TEXT,
        attendance REAL DEFAULT 0,
        prev_sem REAL DEFAULT 0,
        internal_marks REAL DEFAULT 0,
        assignment REAL DEFAULT 0,
        practical REAL DEFAULT 0,
        study REAL DEFAULT 0,
        backlogs INTEGER DEFAULT 0,
        m1 REAL DEFAULT 0,
        m2 REAL DEFAULT 0,
        m3 REAL DEFAULT 0,
        result TEXT DEFAULT '',
        probability REAL DEFAULT 0,
        score REAL DEFAULT 0
    )
    """)

    # Check existing student columns
    cursor.execute("PRAGMA table_info(students)")
    student_cols = [c[1] for c in cursor.fetchall()]
    
    needed_columns = {
        'prev_sem': "REAL DEFAULT 65.0",
        'internal_marks': "REAL DEFAULT 60.0",
        'assignment': "REAL DEFAULT 65.0",
        'practical': "REAL DEFAULT 65.0",
        'backlogs': "INTEGER DEFAULT 0",
        'probability': "REAL DEFAULT 0.0"
    }

    for col_name, col_def in needed_columns.items():
        if col_name not in student_cols:
            cursor.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_def}")

    conn.commit()
    conn.close()
    print("Database initialized and verified.")

if __name__ == "__main__":
    init_db()
