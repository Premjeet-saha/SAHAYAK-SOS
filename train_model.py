"""
Train Model Pipeline for SAHAYAK SOS Emergency Distress Triage (Phase 2B - Leakage-Resistant).
Trains lightweight, explainable, multi-output NLP models on the emergency distress benchmark
using Group-Stratified train/test splitting to strictly eliminate template leakage.

Targets:
1. incident_type (Multi-class: 6 classes)
2. severity (Ordinal/Multi-class: CRITICAL, HIGH, MEDIUM, LOW)
3. medical_urgency (Binary: YES, NO)
"""

import json
import os
import sys
import numpy as np
from datetime import datetime, timezone
import joblib
from collections import Counter

from sklearn.model_selection import StratifiedGroupKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)

# Configuration & Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "emergency_distress_benchmark.jsonl")
MODELS_DIR = os.path.join(BASE_DIR, "models")
EVAL_DIR = os.path.join(BASE_DIR, "evaluation")
RANDOM_SEED = 42
N_SPLITS = 5
MODEL_VERSION = "sahayak_triage_v1.1_grouped"


def load_and_validate_dataset(filepath):
    """Load JSONL benchmark dataset and validate schema including template_id."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found at {filepath}")

    records = []
    required_keys = {"id", "template_id", "text", "language", "incident_type", "severity", "medical_urgency", "source_type"}
    allowed_languages = {"en", "hi", "hinglish"}
    allowed_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    allowed_medical = {"YES", "NO"}
    allowed_sources = {"public_derived", "curated", "synthetic"}

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}")

            missing = required_keys - set(item.keys())
            if missing:
                raise ValueError(f"Line {line_num} missing required keys: {missing}")

            if not item["template_id"] or not str(item["template_id"]).strip():
                raise ValueError(f"Line {line_num} has empty template_id")
            if item["language"] not in allowed_languages:
                raise ValueError(f"Line {line_num} invalid language: {item['language']}")
            if item["severity"] not in allowed_severities:
                raise ValueError(f"Line {line_num} invalid severity: {item['severity']}")
            if item["medical_urgency"] not in allowed_medical:
                raise ValueError(f"Line {line_num} invalid medical_urgency: {item['medical_urgency']}")
            if item["source_type"] not in allowed_sources:
                raise ValueError(f"Line {line_num} invalid source_type: {item['source_type']}")

            records.append(item)

    if len(records) < 10:
        raise ValueError(f"Dataset too small ({len(records)} records)")

    return records


def build_feature_extractor():
    """
    Build a hybrid word and character n-gram TF-IDF feature extractor.
    Captures multilingual Indian English, Hindi Devanagari, and Hinglish phonetic roots.
    """
    word_vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        strip_accents=None,
        lowercase=True
    )

    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        sublinear_tf=True,
        min_df=2,
        lowercase=True
    )

    union = FeatureUnion([
        ("word_tfidf", word_vectorizer),
        ("char_tfidf", char_vectorizer),
    ])

    return union


def evaluate_target(model, X_vec, y_true, target_name):
    """Compute comprehensive classification evaluation metrics."""
    y_pred = model.predict(X_vec)
    classes = list(model.classes_)

    acc = float(accuracy_score(y_true, y_pred))
    p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    p_weighted, r_weighted, f1_weighted, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    p_per, r_per, f1_per, sup_per = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, average=None, zero_division=0
    )

    per_class = {}
    for idx, c in enumerate(classes):
        per_class[c] = {
            "precision": float(p_per[idx]),
            "recall": float(r_per[idx]),
            "f1_score": float(f1_per[idx]),
            "support": int(sup_per[idx]),
        }

    cm = confusion_matrix(y_true, y_pred, labels=classes).tolist()

    return {
        "target": target_name,
        "sample_count": len(y_true),
        "accuracy": acc,
        "macro_metrics": {
            "precision": float(p_macro),
            "recall": float(r_macro),
            "f1_score": float(f1_macro),
        },
        "weighted_metrics": {
            "precision": float(p_weighted),
            "recall": float(r_weighted),
            "f1_score": float(f1_weighted),
        },
        "per_class": per_class,
        "confusion_matrix": {
            "labels": classes,
            "matrix": cm
        }
    }


def train_and_evaluate():
    """Execute leakage-resistant group-stratified training, evaluation, and serialization."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(EVAL_DIR, exist_ok=True)

    print(f"[1/6] Loading benchmark dataset from {DATA_PATH}...")
    records = load_and_validate_dataset(DATA_PATH)
    total_samples = len(records)
    total_templates = len(set(r["template_id"] for r in records))
    print(f"      Loaded {total_samples} valid samples across {total_templates} unique template groups.")

    texts = [r["text"] for r in records]
    y_incident = [r["incident_type"] for r in records]
    y_severity = [r["severity"] for r in records]
    y_medical = [r["medical_urgency"] for r in records]
    groups = [r["template_id"] for r in records]

    print(f"[2/6] Performing Group-Stratified Split (StratifiedGroupKFold, 5-fold, seed={RANDOM_SEED})...")
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_SEED)
    train_idx, test_idx = next(sgkf.split(texts, y_incident, groups))

    # Strict Leakage Checks & Assertions
    train_groups = set(groups[i] for i in train_idx)
    test_groups = set(groups[i] for i in test_idx)
    group_overlap = train_groups.intersection(test_groups)

    train_texts_set = set(texts[i] for i in train_idx)
    test_texts_set = set(texts[i] for i in test_idx)
    text_overlap = train_texts_set.intersection(test_texts_set)

    assert len(group_overlap) == 0, f"FATAL: Template leakage detected! Shared template_ids: {group_overlap}"
    assert len(text_overlap) == 0, f"FATAL: Exact text leakage detected! Shared texts: {text_overlap}"

    X_train = [texts[i] for i in train_idx]
    X_test = [texts[i] for i in test_idx]

    y_train_inc = [y_incident[i] for i in train_idx]
    y_test_inc = [y_incident[i] for i in test_idx]

    y_train_sev = [y_severity[i] for i in train_idx]
    y_test_sev = [y_severity[i] for i in test_idx]

    y_train_med = [y_medical[i] for i in train_idx]
    y_test_med = [y_medical[i] for i in test_idx]

    print(f"      Train Split: {len(X_train)} samples ({len(train_groups)} unique template groups)")
    print(f"      Test Split:  {len(X_test)} samples ({len(test_groups)} unique template groups)")
    print(f"      Template ID Overlap: {len(group_overlap)} (ZERO LEAKAGE CONFIRMED)")
    print(f"      Exact Text Overlap:  {len(text_overlap)} (ZERO LEAKAGE CONFIRMED)")

    # Identify Human-Authored / OOD subset in test set
    human_test_indices = [idx for idx, i in enumerate(test_idx) if records[i]["source_type"] in ("curated", "public_derived")]
    print(f"      Test Set Source Breakdown: {dict(Counter(records[i]['source_type'] for i in test_idx))}")
    print(f"      Human-Authored/OOD Test Count: {len(human_test_indices)} / {len(X_test)}")

    print("[3/6] Fitting hybrid word/char TF-IDF feature extractor...")
    vectorizer = build_feature_extractor()
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    feature_count = X_train_vec.shape[1]
    print(f"      Extracted {feature_count} n-gram features from training data.")

    print("[4/6] Training classifiers with balanced Logistic Regression...")
    clf_incident = LogisticRegression(C=2.0, max_iter=1000, random_state=RANDOM_SEED, class_weight="balanced")
    clf_severity = LogisticRegression(C=2.0, max_iter=1000, random_state=RANDOM_SEED, class_weight="balanced")
    clf_medical = LogisticRegression(C=2.0, max_iter=1000, random_state=RANDOM_SEED, class_weight="balanced")

    clf_incident.fit(X_train_vec, y_train_inc)
    clf_severity.fit(X_train_vec, y_train_sev)
    clf_medical.fit(X_train_vec, y_train_med)

    print("[5/6] Evaluating on held-out Primary Grouped Test Set (N=80)...")
    eval_incident = evaluate_target(clf_incident, X_test_vec, y_test_inc, "incident_type")
    eval_severity = evaluate_target(clf_severity, X_test_vec, y_test_sev, "severity")
    eval_medical = evaluate_target(clf_medical, X_test_vec, y_test_med, "medical_urgency")

    print(f"      -> Primary Test Incident Type Accuracy: {eval_incident['accuracy']*100:.2f}%, Weighted F1: {eval_incident['weighted_metrics']['f1_score']*100:.2f}%")
    print(f"      -> Primary Test Severity Accuracy:      {eval_severity['accuracy']*100:.2f}%, Weighted F1: {eval_severity['weighted_metrics']['f1_score']*100:.2f}%")
    print(f"      -> Primary Test Medical Need Accuracy:  {eval_medical['accuracy']*100:.2f}%, Weighted F1: {eval_medical['weighted_metrics']['f1_score']*100:.2f}%")

    # Evaluate Human-Authored / OOD Test Subset
    print("\n      Evaluating on Human-Authored / OOD Test Subset (N=26)...")
    X_test_human_vec = X_test_vec[human_test_indices]
    y_human_inc = [y_test_inc[idx] for idx in human_test_indices]
    y_human_sev = [y_test_sev[idx] for idx in human_test_indices]
    y_human_med = [y_test_med[idx] for idx in human_test_indices]

    eval_human_incident = evaluate_target(clf_incident, X_test_human_vec, y_human_inc, "incident_type (human_authored_ood)")
    eval_human_severity = evaluate_target(clf_severity, X_test_human_vec, y_human_sev, "severity (human_authored_ood)")
    eval_human_medical = evaluate_target(clf_medical, X_test_human_vec, y_human_med, "medical_urgency (human_authored_ood)")

    print(f"      -> OOD Human Incident Type Accuracy: {eval_human_incident['accuracy']*100:.2f}%, Weighted F1: {eval_human_incident['weighted_metrics']['f1_score']*100:.2f}%")
    print(f"      -> OOD Human Severity Accuracy:      {eval_human_severity['accuracy']*100:.2f}%, Weighted F1: {eval_human_severity['weighted_metrics']['f1_score']*100:.2f}%")
    print(f"      -> OOD Human Medical Need Accuracy:  {eval_human_medical['accuracy']*100:.2f}%, Weighted F1: {eval_human_medical['weighted_metrics']['f1_score']*100:.2f}%")

    print("\n[6/6] Saving serialized model artifacts and evaluation report...")
    vectorizer_path = os.path.join(MODELS_DIR, "vectorizer.joblib")
    clf_inc_path = os.path.join(MODELS_DIR, "incident_classifier.joblib")
    clf_sev_path = os.path.join(MODELS_DIR, "severity_classifier.joblib")
    clf_med_path = os.path.join(MODELS_DIR, "medical_classifier.joblib")
    metadata_path = os.path.join(MODELS_DIR, "model_metadata.json")
    report_path = os.path.join(EVAL_DIR, "evaluation_report.json")

    joblib.dump(vectorizer, vectorizer_path)
    joblib.dump(clf_incident, clf_inc_path)
    joblib.dump(clf_severity, clf_sev_path)
    joblib.dump(clf_medical, clf_med_path)

    metadata = {
        "model_version": MODEL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "split_methodology": "StratifiedGroupKFold (n_splits=5, fold=0, groups=template_id)",
        "leakage_audit": {
            "template_id_overlap": len(group_overlap),
            "exact_text_overlap": len(text_overlap),
            "leakage_resistant": True
        },
        "total_dataset_samples": total_samples,
        "total_template_groups": total_templates,
        "train_samples": len(X_train),
        "train_template_groups": len(train_groups),
        "test_samples": len(X_test),
        "test_template_groups": len(test_groups),
        "test_source_breakdown": dict(Counter(records[i]["source_type"] for i in test_idx)),
        "human_authored_ood_test_samples": len(human_test_indices),
        "feature_count": int(feature_count),
        "incident_classes": list(clf_incident.classes_),
        "severity_classes": list(clf_severity.classes_),
        "medical_classes": list(clf_medical.classes_),
        "vectorizer_config": {
            "word_ngram_range": [1, 2],
            "char_ngram_range": [3, 5],
            "sublinear_tf": True
        },
        "classifier_config": {
            "type": "LogisticRegression",
            "C": 2.0,
            "max_iter": 1000,
            "class_weight": "balanced"
        }
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    evaluation_report = {
        "metadata": metadata,
        "primary_grouped_test_evaluation": {
            "sample_count": len(X_test),
            "template_groups_count": len(test_groups),
            "incident_type": {
                "accuracy": eval_incident["accuracy"],
                "macro_f1": eval_incident["macro_metrics"]["f1_score"],
                "weighted_f1": eval_incident["weighted_metrics"]["f1_score"],
            },
            "severity": {
                "accuracy": eval_severity["accuracy"],
                "macro_f1": eval_severity["macro_metrics"]["f1_score"],
                "weighted_f1": eval_severity["weighted_metrics"]["f1_score"],
            },
            "medical_urgency": {
                "accuracy": eval_medical["accuracy"],
                "macro_f1": eval_medical["macro_metrics"]["f1_score"],
                "weighted_f1": eval_medical["weighted_metrics"]["f1_score"],
            },
        },
        "human_authored_ood_test_evaluation": {
            "sample_count": len(human_test_indices),
            "incident_type": {
                "accuracy": eval_human_incident["accuracy"],
                "macro_f1": eval_human_incident["macro_metrics"]["f1_score"],
                "weighted_f1": eval_human_incident["weighted_metrics"]["f1_score"],
            },
            "severity": {
                "accuracy": eval_human_severity["accuracy"],
                "macro_f1": eval_human_severity["macro_metrics"]["f1_score"],
                "weighted_f1": eval_human_severity["weighted_metrics"]["f1_score"],
            },
            "medical_urgency": {
                "accuracy": eval_human_medical["accuracy"],
                "macro_f1": eval_human_medical["macro_metrics"]["f1_score"],
                "weighted_f1": eval_human_medical["weighted_metrics"]["f1_score"],
            },
        },
        "detailed_evaluations": {
            "primary_grouped_test": {
                "incident_type": eval_incident,
                "severity": eval_severity,
                "medical_urgency": eval_medical,
            },
            "human_authored_ood_test": {
                "incident_type": eval_human_incident,
                "severity": eval_human_severity,
                "medical_urgency": eval_human_medical,
            }
        }
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Leakage-resistant training pipeline completed!")
    print(f"          Models saved to:     {MODELS_DIR}")
    print(f"          Evaluation saved to: {report_path}")

    return evaluation_report


class DistressTriageModel:
    """Inference wrapper for loading and evaluating trained SAHAYAK triage models."""
    def __init__(self, models_dir=MODELS_DIR):
        self.models_dir = models_dir
        self.vectorizer = joblib.load(os.path.join(models_dir, "vectorizer.joblib"))
        self.clf_incident = joblib.load(os.path.join(models_dir, "incident_classifier.joblib"))
        self.clf_severity = joblib.load(os.path.join(models_dir, "severity_classifier.joblib"))
        self.clf_medical = joblib.load(os.path.join(models_dir, "medical_classifier.joblib"))
        
        with open(os.path.join(models_dir, "model_metadata.json"), "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    def predict(self, text):
        """Run multi-output triage inference on raw distress text."""
        if not text or not str(text).strip():
            return {
                "incident_type": "General Emergency Assistance",
                "incident_confidence": 0.0,
                "severity": "LOW",
                "severity_confidence": 0.0,
                "medical_urgency": "NO",
                "medical_confidence": 0.0,
                "model_version": self.metadata.get("model_version", "unknown")
            }

        vec = self.vectorizer.transform([str(text)])

        inc_probs = self.clf_incident.predict_proba(vec)[0]
        inc_idx = int(np.argmax(inc_probs))
        inc_pred = self.clf_incident.classes_[inc_idx]
        inc_conf = float(inc_probs[inc_idx])

        sev_probs = self.clf_severity.predict_proba(vec)[0]
        sev_idx = int(np.argmax(sev_probs))
        sev_pred = self.clf_severity.classes_[sev_idx]
        sev_conf = float(sev_probs[sev_idx])

        med_probs = self.clf_medical.predict_proba(vec)[0]
        med_idx = int(np.argmax(med_probs))
        med_pred = self.clf_medical.classes_[med_idx]
        med_conf = float(med_probs[med_idx])

        return {
            "incident_type": str(inc_pred),
            "incident_confidence": round(inc_conf, 4),
            "incident_probabilities": {c: round(float(p), 4) for c, p in zip(self.clf_incident.classes_, inc_probs)},
            "severity": str(sev_pred),
            "severity_confidence": round(sev_conf, 4),
            "severity_probabilities": {c: round(float(p), 4) for c, p in zip(self.clf_severity.classes_, sev_probs)},
            "medical_urgency": str(med_pred),
            "medical_confidence": round(med_conf, 4),
            "medical_probabilities": {c: round(float(p), 4) for c, p in zip(self.clf_medical.classes_, med_probs)},
            "model_version": self.metadata.get("model_version", "unknown")
        }


if __name__ == "__main__":
    train_and_evaluate()
