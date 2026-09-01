"""ML Service — ML model loading and inference for SAHAYAK SOS.

This module handles all ML-related functionality including:
- Model loading and caching
- ML triage prediction (incident type, severity, medical urgency)
- Fail-safe behavior when models are unavailable

ML is SUPPLEMENTARY — it does NOT determine:
- final priority_score
- resource allocation
- zone allocation
- dispatch decisions
"""

import os
import json
import logging
import joblib
import numpy as np

logger = logging.getLogger("SAHAYAK_ML_SERVICE")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

_ML_CACHE = {
    "loaded": False,
    "vectorizer": None,
    "incident_classifier": None,
    "severity_classifier": None,
    "medical_classifier": None,
    "metadata": {},
    "error": None
}


def _get_ml_models():
    """Safely load and cache ML model artifacts with fail-safe error handling."""
    if _ML_CACHE["loaded"]:
        return _ML_CACHE

    try:
        vec_path = os.path.join(MODELS_DIR, "vectorizer.joblib")
        inc_path = os.path.join(MODELS_DIR, "incident_classifier.joblib")
        sev_path = os.path.join(MODELS_DIR, "severity_classifier.joblib")
        med_path = os.path.join(MODELS_DIR, "medical_classifier.joblib")
        meta_path = os.path.join(MODELS_DIR, "model_metadata.json")

        for path in [vec_path, inc_path, sev_path, med_path, meta_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing model artifact: {os.path.basename(path)}")

        _ML_CACHE["vectorizer"] = joblib.load(vec_path)
        _ML_CACHE["incident_classifier"] = joblib.load(inc_path)
        _ML_CACHE["severity_classifier"] = joblib.load(sev_path)
        _ML_CACHE["medical_classifier"] = joblib.load(med_path)

        with open(meta_path, "r", encoding="utf-8") as f:
            _ML_CACHE["metadata"] = json.load(f)

        _ML_CACHE["loaded"] = True
        _ML_CACHE["error"] = None
        logger.info("SAHAYAK ML triage models loaded successfully.")
    except Exception as e:
        _ML_CACHE["loaded"] = False
        _ML_CACHE["error"] = str(e)
        logger.warning(f"SAHAYAK ML models unavailable: {e}")

    return _ML_CACHE


def predict_ml_triage(text):
    """
    Predict emergency incident type, severity, and medical urgency from text.
    Fail-safe: returns available=False if models fail to load or inference errors out.
    """
    if not text or not str(text).strip():
        return {
            "available": False,
            "error": "No input text provided"
        }

    cache = _get_ml_models()
    if not cache["loaded"]:
        return {
            "available": False,
            "error": "ML model unavailable"
        }

    try:
        vec = cache["vectorizer"].transform([str(text)])

        # Incident type prediction
        clf_inc = cache["incident_classifier"]
        inc_probs = clf_inc.predict_proba(vec)[0]
        inc_idx = int(np.argmax(inc_probs))
        inc_pred = str(clf_inc.classes_[inc_idx])
        inc_conf = float(inc_probs[inc_idx])

        # Severity prediction
        clf_sev = cache["severity_classifier"]
        sev_probs = clf_sev.predict_proba(vec)[0]
        sev_idx = int(np.argmax(sev_probs))
        sev_pred = str(clf_sev.classes_[sev_idx])
        sev_conf = float(sev_probs[sev_idx])

        # Medical urgency prediction
        clf_med = cache["medical_classifier"]
        med_probs = clf_med.predict_proba(vec)[0]
        med_idx = int(np.argmax(med_probs))
        med_pred = str(clf_med.classes_[med_idx])
        med_conf = float(med_probs[med_idx])

        return {
            "available": True,
            "incident_type": inc_pred,
            "severity": sev_pred,
            "medical_urgency": med_pred,
            "confidence": {
                "incident_type": round(inc_conf, 4),
                "severity": round(sev_conf, 4),
                "medical_urgency": round(med_conf, 4)
            },
            "probabilities": {
                "incident_type": {c: round(float(p), 4) for c, p in zip(clf_inc.classes_, inc_probs)},
                "severity": {c: round(float(p), 4) for c, p in zip(clf_sev.classes_, sev_probs)},
                "medical_urgency": {c: round(float(p), 4) for c, p in zip(clf_med.classes_, med_probs)}
            },
            "model_version": cache["metadata"].get("model_version", "sahayak_triage_v1.1_grouped")
        }
    except Exception as e:
        logger.error(f"Inference exception: {e}")
        return {
            "available": False,
            "error": "Inference computation error"
        }


def get_ml_cache():
    """Return the ML cache state (for testing/fail-safe verification)."""
    return _ML_CACHE
