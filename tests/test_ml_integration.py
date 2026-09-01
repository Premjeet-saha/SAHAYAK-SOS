"""
Integration Test Suite for SAHAYAK SOS ML Integration (Phase 2C).
Tests:
1. Normal English SOS
2. Hindi SOS
3. Hinglish SOS
4. Empty/invalid input
5. Missing model artifact fail-safe
6. Model inference failure fail-safe
7. Existing deterministic classification intact
8. Existing priority score formula intact
9. Existing API fields intact
10. Repeated identical input produces identical predictions
11. Probability values valid (bounds [0, 1] and sum to ~1.0)
12. ML failure does not break emergency processing
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in os.sys.path:
    os.sys.path.insert(0, BASE_DIR)

from brain import app
from services.ml_service import predict_ml_triage
from services.ml_service import get_ml_cache


_ML_CACHE = get_ml_cache()


class TestMLIntegration(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_1_english_sos(self):
        """Test standard English distress message processing with ML triage."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "Huge fire broke out in market building, cylinder exploded and flames spreading rapidly!",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        
        # Deterministic checks
        self.assertIn("Fire", data["structured_data"]["type"])
        self.assertEqual(data["structured_data"]["hazard_level"], "CRITICAL")
        
        # ML Prediction checks
        ml = data["ml_prediction"]
        self.assertTrue(ml["available"])
        self.assertEqual(ml["incident_type"], "Major Fire Outbreak")
        self.assertIn(ml["severity"], ["CRITICAL", "HIGH"])
        self.assertIn("confidence", ml)
        self.assertTrue(0.0 <= ml["confidence"]["incident_type"] <= 1.0)

    def test_2_hindi_sos(self):
        """Test Hindi (Devanagari) distress message processing with ML triage."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "नदी का तटबंध टूट गया है, गांव में बाढ़ का पानी घुस गया है, नाव भेजिए।",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        
        ml = data["ml_prediction"]
        self.assertTrue(ml["available"])
        self.assertEqual(ml["incident_type"], "Flash Flood / Waterlogging")
        self.assertTrue(0.0 <= ml["confidence"]["incident_type"] <= 1.0)

    def test_3_hinglish_sos(self):
        """Test Hinglish distress message processing with ML triage."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "Dadaji behosh ho gaye hain unhe bohot tez chest pain ho raha hai jaldi ambulance bhejo.",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        
        ml = data["ml_prediction"]
        self.assertTrue(ml["available"])
        self.assertEqual(ml["incident_type"], "Medical Emergency")
        self.assertEqual(ml["medical_urgency"], "YES")
        self.assertTrue(0.0 <= ml["confidence"]["medical_urgency"] <= 1.0)

    def test_4_empty_invalid_input(self):
        """Test that empty or non-string input returns a safe fail-state for ML without crashing."""
        res = predict_ml_triage("")
        self.assertFalse(res["available"])
        self.assertIn("error", res)

        res_none = predict_ml_triage(None)
        self.assertFalse(res_none["available"])
        self.assertIn("error", res_none)

        # HTTP Endpoint with empty payload
        response = self.client.post("/report-emergency", json={"raw_input": "", "type": "text"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertFalse(data["ml_prediction"]["available"])

    def test_5_missing_model_artifact_failsafe(self):
        """Test fail-safe handling when a model artifact path is unavailable."""
        with patch("os.path.exists", return_value=False):
            # Temporarily clear cache to trigger reload attempt
            old_loaded = _ML_CACHE["loaded"]
            _ML_CACHE["loaded"] = False
            
            res = predict_ml_triage("Fire in building")
            self.assertFalse(res["available"])
            self.assertIn("error", res)
            
            # Restore cache state
            _ML_CACHE["loaded"] = old_loaded

    def test_6_model_inference_exception_failsafe(self):
        """Test fail-safe handling when transform/inference raises an unexpected exception."""
        with patch.object(_ML_CACHE["vectorizer"], "transform", side_effect=RuntimeError("Vectorization crash")):
            res = predict_ml_triage("Test distress message")
            self.assertFalse(res["available"])
            self.assertIn("error", res)

    def test_7_existing_deterministic_classification_intact(self):
        """Verify that existing deterministic keyword routing produces expected categories."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "gas leak near factory with toxic fumes",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]["structured_data"]
        self.assertEqual(data["type"], "Industrial Gas Leak")
        self.assertEqual(data["hazard_level"], "CRITICAL")
        self.assertEqual(data["resource_needed"], "State Fire Services & Fire Tender Units")

    def test_8_existing_priority_score_formula_intact(self):
        """Verify that 5-component priority calculation formula and weights are strictly preserved."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "Severe accident on highway with trapped passengers, elderly person with heavy bleeding",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        breakdown = res.get_json()["data"]["structured_data"]["priority_breakdown"]
        
        # Verify 5 components exist with exact formula weights
        self.assertIn("severity", breakdown["components"])
        self.assertEqual(breakdown["components"]["severity"]["weight"], 0.30)
        self.assertIn("vulnerability", breakdown["components"])
        self.assertEqual(breakdown["components"]["vulnerability"]["weight"], 0.20)
        self.assertIn("medical", breakdown["components"])
        self.assertEqual(breakdown["components"]["medical"]["weight"], 0.25)
        self.assertIn("accessibility", breakdown["components"])
        self.assertEqual(breakdown["components"]["accessibility"]["weight"], 0.15)
        self.assertIn("waiting_time", breakdown["components"])
        self.assertEqual(breakdown["components"]["waiting_time"]["weight"], 0.10)
        
        # Verify final score sum matches
        computed_sum = sum(c["contribution"] for c in breakdown["components"].values())
        self.assertAlmostEqual(breakdown["final_score"], computed_sum, delta=0.5)

    def test_9_existing_api_fields_present(self):
        """Verify that all historical API response fields remain present and backwards-compatible."""
        res = self.client.post("/report-emergency", json={
            "raw_input": "Water level rising, flood in neighborhood",
            "type": "text"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        
        # Top-level fields
        expected_top_keys = {
            "lat", "lng", "status", "priority_score", "structured_data",
            "gemini_explanation", "location_source", "request_timestamp", "ml_prediction"
        }
        for k in expected_top_keys:
            self.assertIn(k, data, f"Missing top-level key: {k}")

        # structured_data fields
        struct = data["structured_data"]
        expected_struct_keys = {
            "incident_id", "type", "hazard_level", "people_involved", "medical_emergency",
            "resource_needed", "detected_hazards", "detected_medical_signals", "detected_keywords",
            "priority_breakdown", "location_source", "request_timestamp", "vulnerability_signals",
            "accessibility_signals", "ml_prediction"
        }
        for k in expected_struct_keys:
            self.assertIn(k, struct, f"Missing structured_data key: {k}")

    def test_10_repeated_identical_input_deterministic(self):
        """Verify that identical inputs yield 100% deterministic probability distributions."""
        text = "Building collapsed after heavy earthquake tremors, people trapped under concrete debris."
        res1 = predict_ml_triage(text)
        res2 = predict_ml_triage(text)
        
        self.assertEqual(res1["incident_type"], res2["incident_type"])
        self.assertEqual(res1["severity"], res2["severity"])
        self.assertEqual(res1["medical_urgency"], res2["medical_urgency"])
        self.assertEqual(res1["confidence"], res2["confidence"])
        self.assertEqual(res1["probabilities"], res2["probabilities"])

    def test_11_probability_bounds_and_sum(self):
        """Verify that probability values are in [0.0, 1.0] and sum to ~1.0 for each head."""
        res = predict_ml_triage("Severe collision between bus and truck on highway, multiple critical injuries")
        self.assertTrue(res["available"])
        
        for head in ["incident_type", "severity", "medical_urgency"]:
            probs = res["probabilities"][head]
            prob_sum = sum(probs.values())
            self.assertAlmostEqual(prob_sum, 1.0, places=2, msg=f"Probabilities for {head} do not sum to 1.0")
            for cls_name, p in probs.items():
                self.assertTrue(0.0 <= p <= 1.0, f"Probability {p} out of bounds for {cls_name}")

    def test_12_ml_failure_does_not_break_endpoint(self):
        """Verify that complete ML model failure still returns HTTP 200 with active deterministic response."""
        with patch("brain.predict_ml_triage", return_value={"available": False, "error": "Simulated ML failure"}):
            res = self.client.post("/report-emergency", json={
                "raw_input": "Fire in apartment building, send fire brigade immediately",
                "type": "text"
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()["data"]
            
            # Deterministic pipeline still dispatched successfully
            self.assertEqual(data["structured_data"]["type"], "Major Fire Outbreak")
            self.assertIn("Fire", data["status"])
            self.assertGreater(data["priority_score"], 0)
            self.assertFalse(data["ml_prediction"]["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
