"""Priority Service — Dynamic rescue priority scoring for SAHAYAK SOS.

This module implements the 5-component priority scoring model:
- Severity: 30%
- Vulnerability: 20%
- Medical Urgency: 25%
- Accessibility: 15%
- Waiting Time: 10%

The priority score is AUTHORITATIVE for rescue prioritization.
ML predictions do NOT influence the priority score.

Structured incident fields from the frontend supplement text-based signals
to provide more accurate priority calculation.
"""

from datetime import datetime
from services.utils import contains_keyword
from services.structured_incident import (
    extract_vulnerability_signals_from_structured,
    extract_medical_signals_from_structured,
    extract_accessibility_signals_from_structured,
    get_hazard_boost_from_structured,
)


# Priority score weights (must sum to 1.0)
WEIGHT_SEVERITY = 0.30
WEIGHT_VULNERABILITY = 0.20
WEIGHT_MEDICAL = 0.25
WEIGHT_ACCESSIBILITY = 0.15
WEIGHT_WAITING_TIME = 0.10


def calculate_priority_score(hazard_level, incident_type, detected_medical_signals, medical,
                             vulnerability_signals, accessibility_signals, timestamp_str=None,
                             structured_incident=None):
    """
    Calculate the dynamic rescue priority score (0-100).

    Args:
        hazard_level: str (CRITICAL, HIGH, MEDIUM, LOW)
        incident_type: str
        detected_medical_signals: list of medical signal strings
        medical: str ("YES" or "NO")
        vulnerability_signals: list of vulnerability signal strings
        accessibility_signals: list of accessibility signal strings
        timestamp_str: str or None (ISO format)
        structured_incident: dict or None (structured incident data from frontend)

    Returns a dict with:
    - priority_score: float (0-100)
    - priority_breakdown: dict with component details
    """
    # Integrate structured incident data with text-based signals
    if structured_incident:
        # Enhance vulnerability signals with structured data
        structured_vulnerability = extract_vulnerability_signals_from_structured(structured_incident)
        for signal in structured_vulnerability:
            if signal not in vulnerability_signals:
                vulnerability_signals.append(signal)

        # Enhance medical signals with structured data
        structured_medical = extract_medical_signals_from_structured(structured_incident)
        for signal in structured_medical:
            if signal not in detected_medical_signals:
                detected_medical_signals.append(signal)
        # If injury is reported, ensure medical is YES
        if structured_incident.get("injury") == True and medical != "YES":
            medical = "YES"

        # Enhance accessibility signals with structured data
        structured_accessibility = extract_accessibility_signals_from_structured(structured_incident)
        for signal in structured_accessibility:
            if signal not in accessibility_signals:
                accessibility_signals.append(signal)

        # Boost hazard level based on structured data
        hazard_level = get_hazard_boost_from_structured(structured_incident, hazard_level)

    # --- SEVERITY COMPONENT (0-100) ---
    severity_score = _calculate_severity_score(hazard_level)

    # --- VULNERABILITY COMPONENT (0-100) ---
    vulnerability_score = _calculate_vulnerability_score(vulnerability_signals)

    # --- MEDICAL URGENCY COMPONENT (0-100) ---
    medical_urgency_score = _calculate_medical_urgency_score(detected_medical_signals, medical)

    # --- ACCESSIBILITY COMPONENT (0-100) ---
    accessibility_score = _calculate_accessibility_score(accessibility_signals)

    # --- WAITING TIME COMPONENT (0-100) ---
    waiting_time_score = _calculate_waiting_time_score(timestamp_str)

    # --- CALCULATE DYNAMIC PRIORITY SCORE ---
    priority_score = min(100.0, max(0.0,
        (WEIGHT_SEVERITY * severity_score) +
        (WEIGHT_VULNERABILITY * vulnerability_score) +
        (WEIGHT_MEDICAL * medical_urgency_score) +
        (WEIGHT_ACCESSIBILITY * accessibility_score) +
        (WEIGHT_WAITING_TIME * waiting_time_score)
    ))

    priority_score = round(priority_score, 1)

    # --- BUILD PRIORITY BREAKDOWN ---
    priority_breakdown = {
        "weights": {
            "severity": WEIGHT_SEVERITY,
            "vulnerability": WEIGHT_VULNERABILITY,
            "medical": WEIGHT_MEDICAL,
            "accessibility": WEIGHT_ACCESSIBILITY,
            "waiting_time": WEIGHT_WAITING_TIME
        },
        "components": {
            "severity": {
                "weight": WEIGHT_SEVERITY,
                "score": round(severity_score, 1),
                "contribution": round(WEIGHT_SEVERITY * severity_score, 1)
            },
            "vulnerability": {
                "weight": WEIGHT_VULNERABILITY,
                "score": round(vulnerability_score, 1),
                "contribution": round(WEIGHT_VULNERABILITY * vulnerability_score, 1),
                "signals": vulnerability_signals
            },
            "medical": {
                "weight": WEIGHT_MEDICAL,
                "score": round(medical_urgency_score, 1),
                "contribution": round(WEIGHT_MEDICAL * medical_urgency_score, 1),
                "signals": detected_medical_signals if medical == "YES" else []
            },
            "accessibility": {
                "weight": WEIGHT_ACCESSIBILITY,
                "score": round(accessibility_score, 1),
                "contribution": round(WEIGHT_ACCESSIBILITY * accessibility_score, 1),
                "signals": accessibility_signals
            },
            "waiting_time": {
                "weight": WEIGHT_WAITING_TIME,
                "score": round(waiting_time_score, 1),
                "contribution": round(WEIGHT_WAITING_TIME * waiting_time_score, 1)
            }
        },
        "final_score": round(priority_score, 1)
    }

    return {
        "priority_score": priority_score,
        "priority_breakdown": priority_breakdown
    }


def extract_vulnerability_signals(text):
    """Detect children, elderly, and other vulnerable persons from text."""
    vulnerable_keywords = {
        "child": "Children present",
        "children": "Children present",
        "kid": "Children present",
        "kids": "Children present",
        "baby": "Infant present",
        "baccha": "Children present",
        "बच्चा": "Children present",
        "शिशु": "Infant present",
        "elderly": "Elderly person",
        "old": "Elderly person",
        "aged": "Elderly person",
        "senior": "Elderly person",
        "bujurg": "Elderly person",
        "बुजुर्ग": "Elderly person",
        "pregnant": "Pregnant woman",
        "गर्भवती": "Pregnant woman",
        "disabled": "Disabled person",
        "विकलांग": "Disabled person",
        "trapped": "Trapped person"
    }
    detected_vulnerability = []
    for keyword, signal in vulnerable_keywords.items():
        if contains_keyword(text, keyword):
            if signal not in detected_vulnerability:
                detected_vulnerability.append(signal)
    return detected_vulnerability


def extract_accessibility_signals(text):
    """Detect accessibility constraints from text."""
    accessibility_keywords = {
        "blocked": "Road blocked",
        "barrier": "Road blocked",
        "रोडा": "Road blocked",
        "रुकावट": "Road blocked",
        "trapped": "Trapped location",
        "फंसा": "Trapped location",
        "फंसे": "Trapped location",
        "isolated": "Isolated location",
        "अलग": "Isolated location",
        "inaccessible": "Difficult access",
        "innaccessible": "Difficult access",
        "difficult access": "Difficult access",
        "कठिन": "Difficult access",
        "unreachable": "Unreachable location",
        "पहुंचना मुश्किल": "Difficult access",
        "remote": "Remote location",
        "दूरस्थ": "Remote location"
    }
    detected_accessibility = []
    for keyword, signal in accessibility_keywords.items():
        if contains_keyword(text, keyword):
            if signal not in detected_accessibility:
                detected_accessibility.append(signal)
    return detected_accessibility


def _calculate_severity_score(hazard_level):
    """Calculate severity component score from hazard level."""
    if hazard_level == "CRITICAL":
        return 95.0
    elif hazard_level == "HIGH":
        return 75.0
    elif hazard_level == "Medium":
        return 50.0
    else:
        return 30.0


def _calculate_vulnerability_score(signals):
    """Calculate vulnerability component score from detected signals."""
    if not signals:
        return 20.0  # Low baseline (generic caller)
    elif "Children present" in signals or "Infant present" in signals:
        return 85.0  # Very high for children
    elif "Trapped person" in signals:
        return 80.0  # Very high for trapped
    elif "Elderly person" in signals or "Pregnant woman" in signals:
        return 70.0  # High for elderly/pregnant
    elif "Disabled person" in signals:
        return 60.0  # Moderate for disabled
    else:
        return 40.0  # Moderate for other vulnerable signals


def _calculate_medical_urgency_score(detected_signals, medical_status):
    """Calculate medical urgency component score."""
    if medical_status != "YES":
        return 0.0  # No medical urgency if not medical

    # Tier 1: Life-threatening conditions (highest)
    critical_medical = {
        "Cardiac Arrest Emergency",
        "Unconscious Patient",
        "Severe Bleeding Trauma"
    }

    # Tier 2: Serious conditions
    serious_medical = {
        "Critical Physical Injury",
        "Multiple Trauma Injury",
        "Venomous Snake Bite"
    }

    # Check for any detected signals
    if not detected_signals:
        return 40.0  # Generic medical request

    # Check critical first
    for signal in detected_signals:
        if signal in critical_medical:
            return 95.0  # Highest medical urgency

    # Check serious
    for signal in detected_signals:
        if signal in serious_medical:
            return 75.0  # High medical urgency

    # Other medical signals
    if any("Acute Medical" in s or "Medical assistance" in s for s in detected_signals):
        return 60.0

    if any("Cardiac" in s or "Cardiac symptoms" in s for s in detected_signals):
        return 80.0

    if any("Pain" in s or "pain" in s.lower() for s in detected_signals):
        return 50.0

    return 40.0  # Generic medical assistance


def _calculate_accessibility_score(signals):
    """
    Calculate accessibility component score.
    LOWER accessibility = HIGHER urgency (higher score)
    """
    if not signals:
        return 30.0  # Normal/moderate accessibility (lower urgency contribution)

    # Trapped or blocked = very hard to access = highest urgency
    if "Trapped location" in signals or "Road blocked" in signals:
        return 90.0

    # Isolated or difficult = high urgency
    if "Isolated location" in signals or "Difficult access" in signals:
        return 70.0

    # Remote = moderate-high urgency
    if "Remote location" in signals:
        return 60.0

    # Unreachable = extreme urgency
    if "Unreachable location" in signals:
        return 95.0

    return 40.0  # Some accessibility constraint


def _calculate_waiting_time_score(timestamp_str):
    """
    Calculate waiting time component score.
    Bounded function: increases over time but cannot exceed 100.
    """
    if not timestamp_str:
        return 0.0  # Newly received SOS

    try:
        created_time = datetime.fromisoformat(timestamp_str)
        current_time = datetime.utcnow()
        elapsed_seconds = (current_time - created_time).total_seconds()

        # 0 seconds = 0 score
        # 300 seconds (5 min) = 25 score
        # 600 seconds (10 min) = 50 score
        # 1200 seconds (20 min) = 75 score
        # 1800 seconds (30 min) = 90 score
        # Beyond 30 min caps at 95

        if elapsed_seconds <= 0:
            return 0.0
        elif elapsed_seconds <= 300:
            return (elapsed_seconds / 300.0) * 25.0
        elif elapsed_seconds <= 600:
            return 25.0 + ((elapsed_seconds - 300) / 300.0) * 25.0
        elif elapsed_seconds <= 1200:
            return 50.0 + ((elapsed_seconds - 600) / 600.0) * 25.0
        elif elapsed_seconds <= 1800:
            return 75.0 + ((elapsed_seconds - 1200) / 600.0) * 15.0
        else:
            return 95.0
    except Exception:
        return 0.0  # Invalid timestamp
