import os
import io
import csv
import sqlite3
from flask import Flask, render_template, request, redirect, session, send_file, jsonify, g
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from db_init import init_db
from model import predict_student, predict_result, get_metrics, FEATURE_COLUMNS

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "student-prediction-secret-key-2026")

# Initialize database schema
init_db(DB_PATH)

def get_db():
    """Provides a thread-safe SQLite connection per request."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# CORS HEADERS
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# ----------------- AUTHENTICATION ROUTES -----------------

@app.route('/', methods=['GET', 'POST'])
def login():
    msg = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        user = cur.fetchone()
        if user:
            session['user'] = u
            return redirect('/dashboard')
        else:
            msg = "Invalid username or password. Please try again."
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        sec = request.form.get('section', 'A').strip()
        q = request.form.get('question', '').strip()
        a = request.form.get('answer', '').strip()

        if not u or not p or not q or not a:
            msg = "All fields are required."
            return render_template('register.html', msg=msg)

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password, section, question, answer) VALUES (?, ?, ?, ?, ?)",
                (u, p, sec, q, a)
            )
            db.commit()
            return redirect('/')
        except sqlite3.IntegrityError:
            msg = f"Username '{u}' is already taken. Please choose another."

    return render_template('register.html', msg=msg)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    msg = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT question FROM users WHERE username=?", (u,))
        row = cur.fetchone()
        if row:
            session['reset_user'] = u
            return render_template('verify_answer.html', question=row['question'])
        else:
            msg = f"User '{u}' not found."
    return render_template('forgot.html', msg=msg)

@app.route('/verify_answer', methods=['POST'])
def verify_answer():
    u = session.get('reset_user')
    if not u:
        return redirect('/forgot')
    
    ans = request.form.get('answer', '').strip()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT answer, question FROM users WHERE username=?", (u,))
    row = cur.fetchone()
    
    if row and row['answer'].strip().lower() == ans.lower():
        return render_template('reset.html')
    else:
        return render_template('verify_answer.html', question=row['question'] if row else '', msg="Incorrect security answer.")

@app.route('/reset', methods=['POST'])
def reset_password():
    u = session.get('reset_user')
    if not u:
        return redirect('/')
    
    new_pwd = request.form.get('password', '').strip()
    if len(new_pwd) < 4:
        return render_template('reset.html', msg="Password must be at least 4 characters.")

    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET password=? WHERE username=?", (new_pwd, u))
    db.commit()
    session.pop('reset_user', None)
    return render_template('login.html', msg="Password successfully reset! Please login.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ----------------- DASHBOARD & MANAGEMENT -----------------

def calculate_student_score(att, prev_sem, internal, assign, prac, study, backlogs):
    """Calculates overall composite ranking score (0 - 100)."""
    score = (
        (att / 100.0) * 15.0 +
        (prev_sem / 100.0) * 25.0 +
        (internal / 100.0) * 20.0 +
        (assign / 100.0) * 10.0 +
        (prac / 100.0) * 10.0 +
        min(10.0, (study / 5.0) * 10.0) -
        min(20.0, backlogs * 5.0)
    )
    return round(max(0.0, min(100.0, score)), 2)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    
    user = session['user']
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE teacher=? ORDER BY score DESC, id DESC", (user,))
    students = cur.fetchall()

    total_count = len(students)
    pass_count = sum(1 for s in students if 'PASS' in str(s['result']).upper())
    fail_count = sum(1 for s in students if 'FAIL' in str(s['result']).upper())
    
    pass_rate = round((pass_count / total_count * 100), 1) if total_count > 0 else 0.0
    fail_rate = round((fail_count / total_count * 100), 1) if total_count > 0 else 0.0

    stats = {
        'total_students': total_count,
        'predicted_pass_count': pass_count,
        'predicted_fail_count': fail_count,
        'pass_percentage': pass_rate,
        'fail_percentage': fail_rate
    }

    return render_template('dashboard.html', students=students, stats=stats)

@app.route('/add_student', methods=['POST'])
def add_student():
    if 'user' not in session:
        return redirect('/')

    name = request.form.get('name', '').strip()
    if not name:
        return redirect('/dashboard')

    att = float(request.form.get('attendance', 75.0))
    prev_sem = float(request.form.get('prev_sem', 68.0))
    internal = float(request.form.get('internal_marks', 65.0))
    assign = float(request.form.get('assignment', 65.0))
    prac = float(request.form.get('practical', 65.0))
    study = float(request.form.get('study', 3.5))
    backlogs = int(request.form.get('backlogs', 0))

    # Run ML prediction on addition
    pred_res = predict_student({
        'attendance': att,
        'prev_sem_percentage': prev_sem,
        'internal_marks': internal,
        'assignment_marks': assign,
        'practical_marks': prac,
        'study_hours': study,
        'backlogs': backlogs
    })

    result_label = f"{pred_res['prediction']}"
    prob = pred_res['confidence']
    score = calculate_student_score(att, prev_sem, internal, assign, prac, study, backlogs)

    db = get_db()
    cur = db.cursor()
    cur.execute("""
    INSERT INTO students (
        name, teacher, attendance, prev_sem, internal_marks, assignment, practical,
        study, backlogs, result, probability, score
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, session['user'], att, prev_sem, internal, assign, prac, study, backlogs, result_label, prob, score))
    db.commit()

    return redirect('/dashboard')

@app.route('/predict_student_row', methods=['POST'])
def predict_student_row():
    if 'user' not in session:
        return redirect('/')

    sid = int(request.form['id'])
    att = float(request.form.get('attendance', 75.0))
    prev_sem = float(request.form.get('prev_sem', 68.0))
    internal = float(request.form.get('internal_marks', 65.0))
    assign = float(request.form.get('assignment', 65.0))
    prac = float(request.form.get('practical', 65.0))
    study = float(request.form.get('study', 3.5))
    backlogs = int(request.form.get('backlogs', 0))

    pred_res = predict_student({
        'attendance': att,
        'prev_sem_percentage': prev_sem,
        'internal_marks': internal,
        'assignment_marks': assign,
        'practical_marks': prac,
        'study_hours': study,
        'backlogs': backlogs
    })

    result_label = f"{pred_res['prediction']}"
    prob = pred_res['confidence']
    score = calculate_student_score(att, prev_sem, internal, assign, prac, study, backlogs)

    db = get_db()
    cur = db.cursor()
    cur.execute("""
    UPDATE students SET
        attendance=?, prev_sem=?, internal_marks=?, assignment=?, practical=?,
        study=?, backlogs=?, result=?, probability=?, score=?
    WHERE id=? AND teacher=?
    """, (att, prev_sem, internal, assign, prac, study, backlogs, result_label, prob, score, sid, session['user']))
    db.commit()

    return redirect('/dashboard')

@app.route('/delete/<int:id>')
def delete_student(id):
    if 'user' not in session:
        return redirect('/')
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM students WHERE id=? AND teacher=?", (id, session['user']))
    db.commit()
    return redirect('/dashboard')

@app.route('/upload', methods=['POST'])
def upload_csv():
    if 'user' not in session:
        return redirect('/')

    file = request.files.get('file')
    if not file or not file.filename.endswith('.csv'):
        return redirect('/dashboard')

    stream = io.StringIO(file.stream.read().decode("UTF-8"), newline=None)
    csv_reader = csv.reader(stream)
    
    rows = list(csv_reader)
    if not rows:
        return redirect('/dashboard')

    db = get_db()
    cur = db.cursor()

    # Check if first row is header
    has_header = False
    header_lower = [h.strip().lower() for h in rows[0]]
    if any(k in header_lower for k in ['name', 'attendance', 'hours', 'marks', 'prev_sem']):
        has_header = True
        data_rows = rows[1:]
    else:
        data_rows = rows

    for r in data_rows:
        if not r or not r[0].strip():
            continue
        
        name = r[0].strip()
        # Defaults
        att, prev_sem, internal, assign, prac, study, backlogs = 75.0, 68.0, 65.0, 65.0, 65.0, 3.5, 0

        # If rich CSV provided with numbers
        try:
            if len(r) >= 8:
                att = float(r[1])
                prev_sem = float(r[2])
                internal = float(r[3])
                assign = float(r[4])
                prac = float(r[5])
                study = float(r[6])
                backlogs = int(r[7])
            elif len(r) >= 4:
                study = float(r[1])
                att = float(r[2])
                internal = float(r[3])
        except ValueError:
            pass

        pred_res = predict_student({
            'attendance': att,
            'prev_sem_percentage': prev_sem,
            'internal_marks': internal,
            'assignment_marks': assign,
            'practical_marks': prac,
            'study_hours': study,
            'backlogs': backlogs
        })
        result_label = pred_res['prediction']
        prob = pred_res['confidence']
        score = calculate_student_score(att, prev_sem, internal, assign, prac, study, backlogs)

        cur.execute("""
        INSERT INTO students (
            name, teacher, attendance, prev_sem, internal_marks, assignment, practical,
            study, backlogs, result, probability, score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, session['user'], att, prev_sem, internal, assign, prac, study, backlogs, result_label, prob, score))

    db.commit()
    return redirect('/dashboard')

# ----------------- DEDICATED PREDICTION PAGE -----------------

@app.route('/predict', methods=['GET', 'POST'])
def predict_page():
    metrics = get_metrics()
    algo_name = metrics.get('best_algorithm', 'Classification Model')
    result = None
    error = None
    inputs = None

    if request.method == 'POST':
        try:
            inputs = {
                'attendance': float(request.form.get('attendance', 0)),
                'prev_sem_percentage': float(request.form.get('prev_sem_percentage', 0)),
                'internal_marks': float(request.form.get('internal_marks', 0)),
                'assignment_marks': float(request.form.get('assignment_marks', 0)),
                'practical_marks': float(request.form.get('practical_marks', 0)),
                'study_hours': float(request.form.get('study_hours', 0)),
                'backlogs': int(request.form.get('backlogs', 0))
            }

            # Validation
            if not (0 <= inputs['attendance'] <= 100):
                raise ValueError("Attendance Percentage must be between 0 and 100%.")
            if not (0 <= inputs['prev_sem_percentage'] <= 100):
                raise ValueError("Previous Semester Percentage must be between 0 and 100%.")
            if not (0 <= inputs['internal_marks'] <= 100):
                raise ValueError("Internal Assessment Marks must be between 0 and 100.")
            if not (0 <= inputs['assignment_marks'] <= 100):
                raise ValueError("Assignment Marks must be between 0 and 100.")
            if not (0 <= inputs['practical_marks'] <= 100):
                raise ValueError("Practical Marks must be between 0 and 100.")
            if not (0 <= inputs['study_hours'] <= 24):
                raise ValueError("Daily Study Hours must be between 0 and 24 hours.")
            if inputs['backlogs'] < 0:
                raise ValueError("Previous Backlogs count cannot be negative.")

            result = predict_student(inputs)

        except (ValueError, TypeError) as e:
            error = str(e)

    return render_template(
        'predict.html',
        result=result,
        error=error,
        inputs=inputs,
        algorithm_name=algo_name
    )

# ----------------- ML ANALYSIS PAGE -----------------

@app.route('/analysis')
def analysis_page():
    metrics = get_metrics()
    return render_template('analysis.html', metrics=metrics)

# ----------------- PDF REPORT GENERATION -----------------

@app.route('/pdf/<int:id>')
def download_pdf(id):
    if 'user' not in session:
        return redirect('/')

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id=? AND teacher=?", (id, session['user']))
    s = cur.fetchone()
    if not s:
        return redirect('/dashboard')

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,  # Center
        spaceAfter=15
    )

    story = [
        Paragraph("Student Pass/Fail Academic Prediction Report", title_style),
        Paragraph(f"<b>Student Name:</b> {s['name']}", styles['Normal']),
        Paragraph(f"<b>Faculty / Teacher:</b> {s['teacher']}", styles['Normal']),
        Paragraph(f"<b>Prediction Result:</b> <b>{s['result']}</b>", styles['Normal']),
        Paragraph(f"<b>Prediction Confidence:</b> {s['probability']}%", styles['Normal']),
        Paragraph(f"<b>Composite Academic Score:</b> {s['score']:.2f} / 100", styles['Normal']),
        Spacer(1, 15),
        Paragraph("<b>Academic Factors Profile:</b>", styles['Heading3']),
        Spacer(1, 6)
    ]

    table_data = [
        ['Academic Factor', 'Recorded Metric', 'Benchmark'],
        ['Attendance Percentage', f"{s['attendance']}%", '>= 75.0%'],
        ['Previous Semester Percentage', f"{s['prev_sem']}%", '>= 60.0%'],
        ['Internal Assessment Marks', f"{s['internal_marks']} / 100", '>= 50.0'],
        ['Assignment Marks', f"{s['assignment']} / 100", '>= 60.0'],
        ['Practical Marks', f"{s['practical']} / 100", '>= 60.0'],
        ['Daily Study Hours', f"{s['study']} hrs/day", '>= 3.0 hrs'],
        ['Previous Backlogs', f"{s['backlogs']} subjects", '0 backlogs']
    ]

    t = Table(table_data, colWidths=[200, 150, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    story.append(t)

    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Advising & Remedial Recommendation:</b>", styles['Heading3']))
    if 'FAIL' in str(s['result']).upper():
        advice = ("The predictive model flags this student as being at academic risk. "
                  "It is recommended to schedule remedial tutoring sessions, monitor attendance weekly, "
                  "and provide targeted intervention on backlog clearance.")
    else:
        advice = ("The predictive model projects the student to pass successfully. "
                  "Continue encouraging consistent study routines and active engagement in coursework.")
    story.append(Paragraph(advice, styles['Normal']))

    doc.build(story)
    pdf_buffer.seek(0)
    filename = f"Report_{s['name'].replace(' ', '_')}_{s['id']}.pdf"
    return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

# ----------------- REST API ENDPOINTS -----------------

@app.route('/api/predict', methods=['POST', 'OPTIONS'])
def api_predict():
    """
    REST API endpoint for real-time Pass/Fail prediction.
    Accepts JSON with:
      attendance, prev_sem_percentage, internal_marks,
      assignment_marks, practical_marks, study_hours, backlogs
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            'status': 'error',
            'message': 'Invalid JSON body. Expected a JSON object with required academic features.'
        }), 400

    # Validation
    missing_fields = [f for f in FEATURE_COLUMNS if f not in data or data[f] is None or data[f] == '']
    if missing_fields:
        return jsonify({
            'status': 'error',
            'message': f"Missing required academic feature(s): {', '.join(missing_fields)}",
            'required_features': FEATURE_COLUMNS
        }), 400

    # Type and range validation
    clean_inputs = {}
    validation_errors = []
    
    range_checks = {
        'attendance': (0.0, 100.0, 'Attendance Percentage must be between 0 and 100%.'),
        'prev_sem_percentage': (0.0, 100.0, 'Previous Semester Percentage must be between 0 and 100%.'),
        'internal_marks': (0.0, 100.0, 'Internal Marks must be between 0 and 100.'),
        'assignment_marks': (0.0, 100.0, 'Assignment Marks must be between 0 and 100.'),
        'practical_marks': (0.0, 100.0, 'Practical Marks must be between 0 and 100.'),
        'study_hours': (0.0, 24.0, 'Daily Study Hours must be between 0 and 24 hours.'),
        'backlogs': (0, 20, 'Previous Backlogs must be between 0 and 20.')
    }

    for feat, (min_v, max_v, err_msg) in range_checks.items():
        try:
            val = float(data[feat]) if feat != 'backlogs' else int(data[feat])
            if val < min_v or val > max_v:
                validation_errors.append(err_msg)
            clean_inputs[feat] = val
        except (ValueError, TypeError):
            validation_errors.append(f"Feature '{feat}' must be a valid numeric value.")

    if validation_errors:
        return jsonify({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': validation_errors
        }), 400

    try:
        prediction_result = predict_student(clean_inputs)
        return jsonify({
            'status': 'success',
            'prediction': prediction_result['prediction'],
            'result_code': prediction_result['result_code'],
            'confidence': prediction_result['confidence'],
            'pass_probability': prediction_result['pass_probability'],
            'fail_probability': prediction_result['fail_probability'],
            'algorithm': prediction_result['algorithm'],
            'factors': prediction_result['factors'],
            'feature_importances': prediction_result['feature_importances']
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Prediction failed: {str(e)}"
        }), 500

@app.route('/api/model-info', methods=['GET'])
def api_model_info():
    """Returns metadata, accuracy, and comparison metrics for all trained models."""
    try:
        metrics = get_metrics()
        return jsonify({
            'status': 'success',
            'best_algorithm': metrics.get('best_algorithm'),
            'features': metrics.get('features'),
            'best_metrics': metrics.get('best_metrics'),
            'algorithm_comparison': metrics.get('comparison'),
            'feature_importances': metrics.get('feature_importances'),
            'dataset_summary': metrics.get('dataset_summary')
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Returns dashboard student count and pass/fail summary."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT result FROM students")
    records = cur.fetchall()

    total = len(records)
    pass_c = sum(1 for r in records if 'PASS' in str(r['result']).upper())
    fail_c = sum(1 for r in records if 'FAIL' in str(r['result']).upper())
    
    return jsonify({
        'status': 'success',
        'total_students': total,
        'pass_count': pass_c,
        'fail_count': fail_c,
        'pass_percentage': round((pass_c / total * 100), 1) if total > 0 else 0.0,
        'fail_percentage': round((fail_c / total * 100), 1) if total > 0 else 0.0
    }), 200

# ----------------- SERVER ENTRYPOINT -----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)