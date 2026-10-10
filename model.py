import os
import json
import joblib
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    'attendance',
    'prev_sem_percentage',
    'internal_marks',
    'assignment_marks',
    'practical_marks',
    'study_hours',
    'backlogs'
]

MODEL_FILE = os.path.join(os.path.dirname(__file__), "best_model.pkl")
METRICS_FILE = os.path.join(os.path.dirname(__file__), "model_metrics.json")

_cached_model = None
_cached_metrics = None

def get_model():
    """Loads the trained model pipeline from disk, retraining if needed."""
    global _cached_model
    if _cached_model is None:
        if not os.path.exists(MODEL_FILE):
            from train_model import train_and_evaluate_all_models
            train_and_evaluate_all_models()
        _cached_model = joblib.load(MODEL_FILE)
    return _cached_model

def get_metrics():
    """Loads model evaluation metrics and algorithm comparisons."""
    global _cached_metrics
    if _cached_metrics is None or not os.path.exists(METRICS_FILE):
        if not os.path.exists(METRICS_FILE):
            from train_model import train_and_evaluate_all_models
            train_and_evaluate_all_models()
        with open(METRICS_FILE, 'r') as f:
            _cached_metrics = json.load(f)
    return _cached_metrics

def evaluate_academic_factors(inputs):
    """
    Evaluates individual entered academic factors against educational benchmarks
    to assist teachers when a student is at risk of failing.
    """
    benchmarks = {
        'attendance': {'benchmark': 75.0, 'unit': '%', 'good_when': 'higher', 'desc': 'Attendance Rate'},
        'prev_sem_percentage': {'benchmark': 60.0, 'unit': '%', 'good_when': 'higher', 'desc': 'Previous Semester'},
        'internal_marks': {'benchmark': 50.0, 'unit': '/100', 'good_when': 'higher', 'desc': 'Internal Assessment'},
        'assignment_marks': {'benchmark': 60.0, 'unit': '/100', 'good_when': 'higher', 'desc': 'Assignment Score'},
        'practical_marks': {'benchmark': 60.0, 'unit': '/100', 'good_when': 'higher', 'desc': 'Practical Score'},
        'study_hours': {'benchmark': 3.0, 'unit': 'hrs/day', 'good_when': 'higher', 'desc': 'Daily Study Hours'},
        'backlogs': {'benchmark': 0, 'unit': 'subjects', 'good_when': 'lower', 'desc': 'Previous Backlogs'}
    }

    factor_details = []
    for feat in FEATURE_COLUMNS:
        val = float(inputs.get(feat, 0))
        meta = benchmarks[feat]
        if meta['good_when'] == 'higher':
            status = 'Good' if val >= meta['benchmark'] else ('Average' if val >= meta['benchmark'] * 0.7 else 'Needs Improvement')
            badge = 'success' if status == 'Good' else ('warning' if status == 'Average' else 'danger')
        else:
            status = 'Clear' if val == 0 else ('Manageable' if val == 1 else 'Critical')
            badge = 'success' if status == 'Clear' else ('warning' if status == 'Manageable' else 'danger')

        factor_details.append({
            'key': feat,
            'label': meta['desc'],
            'value': val,
            'unit': meta['unit'],
            'benchmark': meta['benchmark'],
            'status': status,
            'badge': badge
        })

    return factor_details

def predict_student(student_inputs):
    """
    Predicts PASS or FAIL for a student using the trained classification pipeline.
    
    Parameters:
      student_inputs (dict): Dictionary with keys:
        attendance, prev_sem_percentage, internal_marks,
        assignment_marks, practical_marks, study_hours, backlogs
    
    Returns:
      dict containing prediction, probabilities, confidence, and factors.
    """
    model = get_model()
    metrics = get_metrics()

    # Build DataFrame in the EXACT feature order as training
    row = {}
    for col in FEATURE_COLUMNS:
        if col not in student_inputs or student_inputs[col] is None or student_inputs[col] == '':
            raise ValueError(f"Missing required academic feature: {col}")
        try:
            row[col] = float(student_inputs[col])
        except (ValueError, TypeError):
            raise ValueError(f"Feature '{col}' must be a valid number, got: {student_inputs[col]}")

    input_df = pd.DataFrame([row], columns=FEATURE_COLUMNS)

    # Prediction and probabilities
    pred_code = int(model.predict(input_df)[0])
    prediction_label = "PASS" if pred_code == 1 else "FAIL"

    pass_prob = 0.5
    fail_prob = 0.5
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(input_df)[0]
        # Classes: 0 (FAIL), 1 (PASS)
        if len(probs) >= 2:
            fail_prob = float(probs[0])
            pass_prob = float(probs[1])
        else:
            pass_prob = float(probs[0])
            fail_prob = 1.0 - pass_prob

    confidence = round((pass_prob if pred_code == 1 else fail_prob) * 100, 2)
    factors = evaluate_academic_factors(row)

    return {
        'prediction': prediction_label,
        'result_code': pred_code,
        'confidence': confidence,
        'pass_probability': round(pass_prob, 4),
        'fail_probability': round(fail_prob, 4),
        'algorithm': metrics.get('best_algorithm', 'Classification Model'),
        'factors': factors,
        'feature_importances': metrics.get('feature_importances', {}),
        'raw_inputs': row
    }

# Backward compatibility with original model.py signature
def predict_result(study, att, ut_avg, ese):
    """
    Legacy helper to ensure backward compatibility.
    Maps legacy inputs (study, att, ut_avg, ese) to the updated 7 features.
    """
    data = {
        'attendance': float(att),
        'prev_sem_percentage': float(ese),
        'internal_marks': float(ut_avg) * 5.0,  # Scaled to 100
        'assignment_marks': float(ut_avg) * 4.5,
        'practical_marks': float(ese),
        'study_hours': float(study),
        'backlogs': 0
    }
    result = predict_student(data)
    return result['result_code']