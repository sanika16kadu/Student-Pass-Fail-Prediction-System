import json
import sqlite3
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "http://127.0.0.1:5000"

def run_all_tests():
    print("==================================================")
    print("   RUNNING END-TO-END VERIFICATION TEST SUITE     ")
    print("==================================================")

    # 1. TEST MODEL INFO API
    print("\n[TEST 1] Verifying /api/model-info endpoint...")
    with urllib.request.urlopen(f"{BASE_URL}/api/model-info") as res:
        assert res.status == 200
        data = json.loads(res.read().decode())
        print(f"  -> Best Algorithm: {data['best_algorithm']}")
        print(f"  -> Model Accuracy: {data['best_metrics']['accuracy'] * 100:.2f}%")
        print(f"  -> Model Precision: {data['best_metrics']['precision'] * 100:.2f}%")
        print(f"  -> Model Recall: {data['best_metrics']['recall'] * 100:.2f}%")
        print(f"  -> Model F1-Score: {data['best_metrics']['f1_score']:.4f}")
        print("  [PASS] /api/model-info working properly.")

    # 2. TEST STATS API
    print("\n[TEST 2] Verifying /api/stats endpoint...")
    with urllib.request.urlopen(f"{BASE_URL}/api/stats") as res:
        assert res.status == 200
        data = json.loads(res.read().decode())
        print(f"  -> Total Students: {data['total_students']}, Pass: {data['pass_count']}, Fail: {data['fail_count']}")
        print("  [PASS] /api/stats working properly.")

    # 3. TEST VALID STUDENT PREDICTION (PASS)
    print("\n[TEST 3] Testing prediction for strong student (PASS expected)...")
    pass_payload = {
        'attendance': 92.5,
        'prev_sem_percentage': 84.0,
        'internal_marks': 82.0,
        'assignment_marks': 85.0,
        'practical_marks': 88.0,
        'study_hours': 5.0,
        'backlogs': 0
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/predict",
        data=json.dumps(pass_payload).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode())
        assert data['prediction'] == "PASS"
        assert data['result_code'] == 1
        assert data['confidence'] > 50.0
        print(f"  -> Outcome: {data['prediction']} (Confidence: {data['confidence']}%, Pass Prob: {data['pass_probability']})")
        print("  [PASS] Strong student accurately predicted as PASS.")

    # 4. TEST VALID STUDENT PREDICTION (FAIL)
    print("\n[TEST 4] Testing prediction for at-risk student (FAIL expected)...")
    fail_payload = {
        'attendance': 44.0,
        'prev_sem_percentage': 38.0,
        'internal_marks': 25.0,
        'assignment_marks': 30.0,
        'practical_marks': 35.0,
        'study_hours': 1.0,
        'backlogs': 4
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/predict",
        data=json.dumps(fail_payload).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode())
        assert data['prediction'] == "FAIL"
        assert data['result_code'] == 0
        assert data['confidence'] > 50.0
        print(f"  -> Outcome: {data['prediction']} (Confidence: {data['confidence']}%, Fail Prob: {data['fail_probability']})")
        print(f"  -> Factors flagged: {len(data['factors'])} factors evaluated.")
        print("  [PASS] At-risk student accurately predicted as FAIL with diagnostic factors.")

    # 5. TEST INVALID & MISSING INPUTS
    print("\n[TEST 5] Testing error handling for invalid/missing inputs...")
    # Missing fields
    try:
        bad_req = urllib.request.Request(
            f"{BASE_URL}/api/predict",
            data=json.dumps({'attendance': 85.0}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(bad_req)
        assert False, "Should have returned 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print("  -> Missing features correctly caught with HTTP 400.")

    # Out of range
    try:
        bad_req2 = urllib.request.Request(
            f"{BASE_URL}/api/predict",
            data=json.dumps({
                'attendance': 120.0,
                'prev_sem_percentage': 80.0,
                'internal_marks': 70.0,
                'assignment_marks': 70.0,
                'practical_marks': 70.0,
                'study_hours': 3.0,
                'backlogs': 0
            }).encode(),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(bad_req2)
        assert False, "Should have returned 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print("  -> Out-of-range attendance (120%) correctly caught with HTTP 400.")
    print("  [PASS] Input validation working completely.")

    # 6. TEST WEB PAGES RENDERING
    print("\n[TEST 6] Testing Web Page Routes...")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    # GET /
    res = opener.open(f"{BASE_URL}/")
    assert res.status == 200
    print("  -> GET / (Login page) loaded.")

    # GET /predict
    res = opener.open(f"{BASE_URL}/predict")
    assert res.status == 200
    print("  -> GET /predict (Student Prediction Page) loaded.")

    # GET /analysis
    res = opener.open(f"{BASE_URL}/analysis")
    assert res.status == 200
    print("  -> GET /analysis (ML Analysis Page) loaded.")

    # POST / (Login)
    login_data = urllib.parse.urlencode({'username': 'Gayatri', 'password': 'Gayatri1155'}).encode()
    res = opener.open(f"{BASE_URL}/", data=login_data)
    dashboard_html = res.read().decode()
    assert "Student Pass" in dashboard_html
    print("  -> Authenticated Dashboard loaded.")

    # POST /add_student
    add_data = urllib.parse.urlencode({
        'name': 'Suite Verification Student',
        'attendance': '89.5',
        'prev_sem': '79.0',
        'internal_marks': '74.0',
        'assignment': '80.0',
        'practical': '85.0',
        'study': '4.0',
        'backlogs': '0'
    }).encode()
    res = opener.open(f"{BASE_URL}/add_student", data=add_data)
    assert res.status == 200
    print("  -> Student successfully added to dashboard.")

    # Verify student exists in DB and test PDF
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM students WHERE name='Suite Verification Student' AND teacher='Gayatri'")
    row = cur.fetchone()
    assert row is not None
    sid = row[0]
    print(f"  -> Student created with ID: {sid}")

    # GET /pdf/<id>
    pdf_res = opener.open(f"{BASE_URL}/pdf/{sid}")
    assert pdf_res.status == 200
    assert pdf_res.headers.get('Content-Type') == 'application/pdf'
    pdf_bytes = pdf_res.read()
    assert len(pdf_bytes) > 500
    print(f"  -> Generated PDF Report ({len(pdf_bytes)} bytes) successfully downloaded.")

    # Cleanup test student
    del_res = opener.open(f"{BASE_URL}/delete/{sid}")
    assert del_res.status == 200
    print("  -> Test student deleted cleanly.")

    print("\n==================================================")
    print("    ALL TESTS PASSED WITH 100% SUCCESS!          ")
    print("==================================================")

if __name__ == "__main__":
    run_all_tests()
