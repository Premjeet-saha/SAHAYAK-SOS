"""Tests for structured incident extraction from natural language."""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.structured_incident import (
    extract_structured_incident,
    extract_vulnerability_signals_from_structured,
    extract_medical_signals_from_structured,
    extract_accessibility_signals_from_structured,
    get_hazard_boost_from_structured,
)
from services.resource_service import get_required_resources, DEFAULT_RESOURCE_INVENTORY
from services.priority_service import calculate_priority_score


class TestNaturalLanguageExtraction(unittest.TestCase):
    """Test structured incident extraction from natural language text."""

    def test_hinglish_fire_extraction(self):
        """Extract structured data from Hinglish fire description."""
        text = "Building mein aag lagi hai, 8 log andar hain, 2 bachche hain aur ek aadmi injured hai. Do log trapped hain."
        result = extract_structured_incident(text, "Major Fire Outbreak", "CRITICAL")
        self.assertEqual(result["number_of_people"], 8)
        self.assertEqual(result["children"], 2)
        self.assertEqual(result["injury"], True)
        self.assertEqual(result["trapped"], True)
        self.assertEqual(result["fire"], True)
        self.assertEqual(result["elderly"], "unknown")
        self.assertEqual(result["pregnant"], "unknown")
        self.assertEqual(result["flood_depth_m"], "unknown")

    def test_english_fire_extraction(self):
        """Extract structured data from English fire description."""
        text = "There is a fire in the building. 8 people are inside. Two children are injured and 2 people are trapped."
        result = extract_structured_incident(text, "Major Fire Outbreak", "CRITICAL")
        self.assertEqual(result["number_of_people"], 8)
        self.assertEqual(result["children"], 2)
        self.assertEqual(result["injury"], True)
        self.assertEqual(result["trapped"], True)
        self.assertEqual(result["fire"], True)

    def test_hindi_fire_extraction(self):
        """Extract structured data from Hindi fire description."""
        text = "इमारत में आग लगी है। अंदर आठ लोग हैं। दो बच्चे घायल हैं और दो लोग फंसे हुए हैं।"
        result = extract_structured_incident(text, "Major Fire Outbreak", "CRITICAL")
        self.assertEqual(result["number_of_people"], 8)
        self.assertEqual(result["children"], 2)
        self.assertEqual(result["injury"], True)
        self.assertEqual(result["trapped"], True)
        self.assertEqual(result["fire"], True)

    def test_unknown_values_not_fabricated(self):
        """Values not stated should be 'unknown', not fabricated."""
        text = "There is a fire in the building."
        result = extract_structured_incident(text, "Major Fire Outbreak", "CRITICAL")
        self.assertEqual(result["fire"], True)
        self.assertEqual(result["number_of_people"], "unknown")
        self.assertEqual(result["children"], "unknown")
        self.assertEqual(result["elderly"], "unknown")
        self.assertEqual(result["pregnant"], "unknown")
        self.assertEqual(result["injury"], "unknown")
        self.assertEqual(result["trapped"], "unknown")

    def test_flood_depth_extraction(self):
        """Extract flood depth from text."""
        text = "Flood water is 1.5 meters deep. 5 people trapped."
        result = extract_structured_incident(text, "Flash Flood / Waterlogging", "CRITICAL")
        self.assertEqual(result["flood_depth_m"], 1.5)
        self.assertEqual(result["number_of_people"], 5)
        self.assertEqual(result["trapped"], True)

    def test_elderly_extraction(self):
        """Extract elderly count from text."""
        text = "3 elderly people and 2 children are trapped in the building."
        result = extract_structured_incident(text, "Earthquake Tremors", "CRITICAL")
        self.assertEqual(result["elderly"], 3)
        self.assertEqual(result["children"], 2)
        self.assertEqual(result["trapped"], True)

    def test_pregnant_extraction(self):
        """Extract pregnant count from text."""
        text = "2 pregnant women and 4 children need evacuation."
        result = extract_structured_incident(text, "Flood Emergency", "HIGH")
        self.assertEqual(result["pregnant"], 2)
        self.assertEqual(result["children"], 4)

    def test_empty_text_returns_unknown(self):
        """Empty text returns all unknown values."""
        result = extract_structured_incident("", "General Emergency", "Medium")
        self.assertEqual(result["number_of_people"], "unknown")
        self.assertEqual(result["fire"], "unknown")

    def test_none_text_returns_unknown(self):
        """None text returns all unknown values."""
        result = extract_structured_incident(None, "General Emergency", "Medium")
        self.assertEqual(result["number_of_people"], "unknown")


class TestSignalExtraction(unittest.TestCase):
    """Test signal extraction from structured incident data."""

    def test_vulnerability_from_children(self):
        """Children count > 0 produces Children present signal."""
        si = {"children": 2}
        signals = extract_vulnerability_signals_from_structured(si)
        self.assertIn("Children present", signals)

    def test_vulnerability_from_structured_data(self):
        """Structured data produces correct vulnerability signals."""
        si = {"children": 2, "elderly": 1, "pregnant": 1, "trapped": True}
        signals = extract_vulnerability_signals_from_structured(si)
        self.assertIn("Children present", signals)
        self.assertIn("Elderly person", signals)
        self.assertIn("Pregnant woman", signals)
        self.assertIn("Trapped person", signals)

    def test_unknown_values_dont_produce_signals(self):
        """Unknown values should not produce signals."""
        si = {"children": "unknown", "elderly": "unknown"}
        signals = extract_vulnerability_signals_from_structured(si)
        self.assertEqual(signals, [])

    def test_medical_from_injury(self):
        """Injury flag produces Injury reported signal."""
        si = {"injury": True}
        signals = extract_medical_signals_from_structured(si)
        self.assertIn("Injury reported", signals)

    def test_accessibility_from_trapped(self):
        """Trapped flag produces Trapped location signal."""
        si = {"trapped": True}
        signals = extract_accessibility_signals_from_structured(si)
        self.assertIn("Trapped location", signals)


class TestHazardBoost(unittest.TestCase):
    """Test hazard level boosting from structured data."""

    def test_fire_with_major_damage_boosts_to_critical(self):
        """Fire with major building damage boosts hazard to CRITICAL."""
        si = {"fire": True, "building_damage": "major"}
        result = get_hazard_boost_from_structured(si, "HIGH")
        self.assertEqual(result, "CRITICAL")

    def test_fire_inferred_from_incident_type(self):
        """Fire can be inferred from incident type when extracting."""
        text = "Building mein aag lagi hai."
        result = extract_structured_incident(text, "Major Fire Outbreak", "CRITICAL")
        self.assertEqual(result["fire"], True)

    def test_trapped_boosts_to_high(self):
        """Trapped persons boost hazard to at least HIGH."""
        si = {"trapped": True}
        result = get_hazard_boost_from_structured(si, "MEDIUM")
        self.assertEqual(result, "HIGH")


class TestFireResourceAllocation(unittest.TestCase):
    """Test that fire incidents produce correct resource demand."""

    def test_fire_incident_requires_fire_resource(self):
        """Major Fire Outbreak requires fire resource."""
        case = {
            "type": "Major Fire Outbreak",
            "hazard_level": "CRITICAL",
            "medical_emergency": "NO",
            "detected_medical_signals": [],
        }
        required = get_required_resources(case)
        self.assertIn("fire", required)

    def test_fire_incident_requires_ndrf(self):
        """Major Fire Outbreak also requires NDRF for rescue."""
        case = {
            "type": "Major Fire Outbreak",
            "hazard_level": "CRITICAL",
            "medical_emergency": "NO",
            "detected_medical_signals": [],
        }
        required = get_required_resources(case)
        self.assertIn("ndrf", required)

    def test_fire_with_medical_requires_ambulance(self):
        """Fire with medical signals requires ambulance."""
        case = {
            "type": "Major Fire Outbreak",
            "hazard_level": "CRITICAL",
            "medical_emergency": "YES",
            "detected_medical_signals": ["Injury reported"],
        }
        required = get_required_resources(case)
        self.assertIn("fire", required)
        self.assertIn("ambulance", required)
        self.assertIn("hospital", required)

    def test_structured_trapped_adds_ndrf(self):
        """Structured trapped flag adds NDRF resource."""
        case = {
            "type": "General Emergency Assistance Required",
            "hazard_level": "Medium",
            "medical_emergency": "NO",
            "detected_medical_signals": [],
            "structured_incident": {"trapped": True},
        }
        required = get_required_resources(case)
        self.assertIn("ndrf", required)


class TestPriorityWithExtractedIncident(unittest.TestCase):
    """Test priority calculation with extracted structured incident data."""

    def test_children_increase_vulnerability_score(self):
        """Children in extracted data increase vulnerability component."""
        base_result = calculate_priority_score(
            hazard_level="HIGH",
            incident_type="General Emergency Assistance Required",
            detected_medical_signals=[],
            medical="NO",
            vulnerability_signals=[],
            accessibility_signals=[],
        )
        extracted_result = calculate_priority_score(
            hazard_level="HIGH",
            incident_type="General Emergency Assistance Required",
            detected_medical_signals=[],
            medical="NO",
            vulnerability_signals=[],
            accessibility_signals=[],
            structured_incident={"children": 2},
        )
        self.assertGreater(
            extracted_result["priority_breakdown"]["components"]["vulnerability"]["score"],
            base_result["priority_breakdown"]["components"]["vulnerability"]["score"],
        )

    def test_injury_increases_medical_score(self):
        """Injury in extracted data increase medical component."""
        base_result = calculate_priority_score(
            hazard_level="HIGH",
            incident_type="General Emergency Assistance Required",
            detected_medical_signals=[],
            medical="NO",
            vulnerability_signals=[],
            accessibility_signals=[],
        )
        extracted_result = calculate_priority_score(
            hazard_level="HIGH",
            incident_type="General Emergency Assistance Required",
            detected_medical_signals=[],
            medical="NO",
            vulnerability_signals=[],
            accessibility_signals=[],
            structured_incident={"injury": True},
        )
        self.assertGreater(
            extracted_result["priority_breakdown"]["components"]["medical"]["score"],
            base_result["priority_breakdown"]["components"]["medical"]["score"],
        )


class TestDefaultInventoryIncludesFire(unittest.TestCase):
    """Test that default inventory includes fire resource."""

    def test_fire_in_default_inventory(self):
        """Fire resource type exists in default inventory."""
        self.assertIn("fire", DEFAULT_RESOURCE_INVENTORY)
        self.assertEqual(DEFAULT_RESOURCE_INVENTORY["fire"], 6)


if __name__ == "__main__":
    unittest.main()
