"""
Unit & Integration Tests for SAHAYAK SOS ML Pipeline (Phase 2B - Leakage-Resistant).
Verifies dataset integrity, template_id assignment, zero-leakage grouped splits,
model artifact deserialization, inference, and reproducibility.
"""

import os
import json
import joblib
import unittest
import numpy as np

# Adjust path to import from project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in os.sys.path:
    os.sys.path.insert(0, BASE_DIR)

from train_model import (
    load_and_validate_dataset,
    train_and_evaluate,
    DistressTriageModel,
    DATA_PATH,
    MODELS_DIR,
    EVAL_DIR,
    RANDOM_SEED
)
from sklearn.model_selection import StratifiedGroupKFold


def test_dataset_schema_and_template_ids():
    """Verify dataset existence, length, schema, and valid template_id values."""
    records = load_and_validate_dataset(DATA_PATH)
    assert len(records) == 399, f"Expected 399 records, found {len(records)}"

    languages = set(r["language"] for r in records)
    assert languages == {"en", "hi", "hinglish"}, f"Missing expected languages: {languages}"

    incident_types = set(r["incident_type"] for r in records)
    assert len(incident_types) == 6, f"Expected 6 incident types, found {len(incident_types)}"

    severities = set(r["severity"] for r in records)
    assert severities == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    medical = set(r["medical_urgency"] for r in records)
    assert medical == {"YES", "NO"}

    # Verify template_id formatting and grouping
    template_ids = [r["template_id"] for r in records]
    assert all(t and t.startswith("TPL-") for t in template_ids), "Invalid template_id found"
    
    unique_templates = len(set(template_ids))
    assert unique_templates == 214, f"Expected 214 unique templates, found {unique_templates}"


def test_grouped_split_zero_leakage():
    """Verify that Group-Stratified Split strictly enforces zero template and zero text overlap."""
    records = load_and_validate_dataset(DATA_PATH)
    texts = [r["text"] for r in records]
    y_incident = [r["incident_type"] for r in records]
    groups = [r["template_id"] for r in records]

    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    train_idx, test_idx = next(sgkf.split(texts, y_incident, groups))

    train_groups = set(groups[i] for i in train_idx)
    test_groups = set(groups[i] for i in test_idx)
    group_overlap = train_groups.intersection(test_groups)

    train_texts = set(texts[i] for i in train_idx)
    test_texts = set(texts[i] for i in test_idx)
    text_overlap = train_texts.intersection(test_texts)

    assert len(group_overlap) == 0, f"Template leakage detected! Overlap: {group_overlap}"
    assert len(text_overlap) == 0, f"Text leakage detected! Overlap: {text_overlap}"
    assert len(train_idx) == 319, f"Expected 319 train samples, got {len(train_idx)}"
    assert len(test_idx) == 80, f"Expected 80 test samples, got {len(test_idx)}"


def test_artifacts_exist_and_loadable():
    """Verify all saved model artifacts exist and can be deserialized."""
    expected_files = [
        "vectorizer.joblib",
        "incident_classifier.joblib",
        "severity_classifier.joblib",
        "medical_classifier.joblib",
        "model_metadata.json"
    ]
    for filename in expected_files:
        filepath = os.path.join(MODELS_DIR, filename)
        assert os.path.exists(filepath), f"Missing artifact: {filepath}"

    vectorizer = joblib.load(os.path.join(MODELS_DIR, "vectorizer.joblib"))
    clf_inc = joblib.load(os.path.join(MODELS_DIR, "incident_classifier.joblib"))
    clf_sev = joblib.load(os.path.join(MODELS_DIR, "severity_classifier.joblib"))
    clf_med = joblib.load(os.path.join(MODELS_DIR, "medical_classifier.joblib"))

    assert hasattr(vectorizer, "transform")
    assert hasattr(clf_inc, "predict_proba")
    assert hasattr(clf_sev, "predict_proba")
    assert hasattr(clf_med, "predict_proba")


def test_model_inference_multilingual():
    """Verify that inference works correctly on English, Hindi, and Hinglish inputs with valid confidence bounds."""
    model = DistressTriageModel(MODELS_DIR)

    test_cases = [
        # English
        {
            "text": "Huge fire in market building, cylinder exploded and flames spreading rapidly!",
            "expected_type": "Major Fire Outbreak",
            "expected_sev": "CRITICAL"
        },
        # Hinglish
        {
            "text": "Dadaji behosh ho gaye hain unhe bohot tez chest pain ho raha hai jaldi ambulance bhejo.",
            "expected_type": "Medical Emergency",
            "expected_med": "YES"
        },
        # Hindi Devanagari
        {
            "text": "नदी का तटबंध टूट गया है, गांव में बाढ़ का पानी घुस गया है, नाव भेजिए।",
            "expected_type": "Flash Flood / Waterlogging"
        }
    ]

    for tc in test_cases:
        res = model.predict(tc["text"])
        assert "incident_type" in res
        assert "incident_confidence" in res
        assert 0.0 <= res["incident_confidence"] <= 1.0
        assert "severity" in res
        assert 0.0 <= res["severity_confidence"] <= 1.0
        assert "medical_urgency" in res
        assert 0.0 <= res["medical_confidence"] <= 1.0
        assert "model_version" in res

        if "expected_type" in tc:
            assert res["incident_type"] == tc["expected_type"], f"Got {res['incident_type']}, expected {tc['expected_type']}"
        if "expected_sev" in tc:
            assert res["severity"] == tc["expected_sev"], f"Got {res['severity']}, expected {tc['expected_sev']}"
        if "expected_med" in tc:
            assert res["medical_urgency"] == tc["expected_med"], f"Got {res['medical_urgency']}, expected {tc['expected_med']}"


def test_training_reproducibility():
    """Verify that training pipeline with seed=42 produces identical evaluation metrics."""
    eval1 = train_and_evaluate()
    eval2 = train_and_evaluate()

    acc1_inc = eval1["primary_grouped_test_evaluation"]["incident_type"]["accuracy"]
    acc2_inc = eval2["primary_grouped_test_evaluation"]["incident_type"]["accuracy"]
    assert acc1_inc == acc2_inc, f"Accuracy mismatch: {acc1_inc} vs {acc2_inc}"

    acc1_sev = eval1["primary_grouped_test_evaluation"]["severity"]["accuracy"]
    acc2_sev = eval2["primary_grouped_test_evaluation"]["severity"]["accuracy"]
    assert acc1_sev == acc2_sev, f"Severity accuracy mismatch: {acc1_sev} vs {acc2_sev}"


if __name__ == "__main__":
    test_dataset_schema_and_template_ids()
    print("[PASS] test_dataset_schema_and_template_ids passed")
    test_grouped_split_zero_leakage()
    print("[PASS] test_grouped_split_zero_leakage passed")
    test_artifacts_exist_and_loadable()
    print("[PASS] test_artifacts_exist_and_loadable passed")
    test_model_inference_multilingual()
    print("[PASS] test_model_inference_multilingual passed")
    test_training_reproducibility()
    print("[PASS] test_training_reproducibility passed")
    print("\nAll leakage-resistant ML pipeline tests PASSED successfully!")
