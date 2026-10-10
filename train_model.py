import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.calibration import CalibratedClassifierCV

FEATURE_COLUMNS = [
    'attendance',
    'prev_sem_percentage',
    'internal_marks',
    'assignment_marks',
    'practical_marks',
    'study_hours',
    'backlogs'
]
TARGET_COLUMN = 'result'

MODEL_FILE = os.path.join(os.path.dirname(__file__), "best_model.pkl")
METRICS_FILE = os.path.join(os.path.dirname(__file__), "model_metrics.json")
DATASET_FILE = os.path.join(os.path.dirname(__file__), "student_data.csv")

def train_and_evaluate_all_models(data_path=DATASET_FILE, random_state=42):
    """
    Trains and evaluates 5 classification models:
      1. Logistic Regression
      2. Decision Tree
      3. Random Forest
      4. KNN (K-Nearest Neighbors)
      5. SVM (Support Vector Machine)

    Selects the best performing model based on test F1-score and Accuracy.
    Saves the best model pipeline to best_model.pkl and metrics to model_metrics.json.
    """
    if not os.path.exists(data_path):
        from generate_dataset import generate_student_dataset
        generate_student_dataset(output_path=data_path)

    df = pd.read_csv(data_path)

    # Validate columns
    missing_cols = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset missing required columns: {missing_cols}")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN].astype(int)

    # Train / Test Split (80/20 stratified to prevent data leakage)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )

    candidate_models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, random_state=random_state),
        'Decision Tree': DecisionTreeClassifier(max_depth=5, min_samples_split=5, random_state=random_state),
        'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=6, random_state=random_state),
        'KNN': KNeighborsClassifier(n_neighbors=7),
        'SVM': CalibratedClassifierCV(SVC(kernel='rbf', random_state=random_state), ensemble=False)
    }

    comparison_results = {}
    trained_pipelines = {}

    for name, clf in candidate_models.items():
        # Pipeline: median imputer -> standard scaler -> classifier
        pipe = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('classifier', clf)
        ])

        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        
        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        cm = confusion_matrix(y_test, y_pred).tolist()

        comparison_results[name] = {
            'accuracy': round(acc, 4),
            'precision': round(prec, 4),
            'recall': round(rec, 4),
            'f1_score': round(f1, 4),
            'confusion_matrix': cm  # [[TN, FP], [FN, TP]]
        }
        trained_pipelines[name] = pipe

    # Select best model dynamically based on highest F1-score (with accuracy as secondary)
    best_name = max(
        comparison_results.keys(),
        key=lambda k: (comparison_results[k]['f1_score'], comparison_results[k]['accuracy'])
    )
    best_pipeline = trained_pipelines[best_name]

    # Extract feature importance / coefficients for explainability if supported
    feature_importances = {}
    inner_clf = best_pipeline.named_steps['classifier']
    if hasattr(inner_clf, 'feature_importances_'):
        importances = inner_clf.feature_importances_
        feature_importances = {feat: round(float(imp), 4) for feat, imp in zip(FEATURE_COLUMNS, importances)}
    elif hasattr(inner_clf, 'coef_'):
        coefs = np.abs(inner_clf.coef_[0])
        total_coef = coefs.sum() if coefs.sum() > 0 else 1.0
        normalized = coefs / total_coef
        feature_importances = {feat: round(float(imp), 4) for feat, imp in zip(FEATURE_COLUMNS, normalized)}
    else:
        # Fallback to random forest feature importance if best is SVM/KNN
        rf = trained_pipelines['Random Forest'].named_steps['classifier']
        feature_importances = {feat: round(float(imp), 4) for feat, imp in zip(FEATURE_COLUMNS, rf.feature_importances_)}

    # Save best model pipeline
    joblib.dump(best_pipeline, MODEL_FILE)

    # Save metrics metadata
    metadata = {
        'best_algorithm': best_name,
        'features': FEATURE_COLUMNS,
        'target': TARGET_COLUMN,
        'best_metrics': comparison_results[best_name],
        'comparison': comparison_results,
        'feature_importances': feature_importances,
        'dataset_summary': {
            'total_samples': len(df),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'total_pass': int((y == 1).sum()),
            'total_fail': int((y == 0).sum()),
            'pass_percentage': round(float((y == 1).mean() * 100), 2),
            'fail_percentage': round(float((y == 0).mean() * 100), 2)
        }
    }

    with open(METRICS_FILE, 'w') as f:
        json.dump(metadata, f, indent=4)

    print(f"=== Model Evaluation Results ===")
    for model_name, m in comparison_results.items():
        print(f"{model_name:22s} | Acc: {m['accuracy']*100:.2f}% | Prec: {m['precision']*100:.2f}% | Rec: {m['recall']*100:.2f}% | F1: {m['f1_score']:.4f}")
    print(f"\nDynamically Selected Best Model: {best_name}")
    print(f"Model saved to: {MODEL_FILE}")
    print(f"Metrics saved to: {METRICS_FILE}")

    return metadata

if __name__ == "__main__":
    train_and_evaluate_all_models()
