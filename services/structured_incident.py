"""Structured Incident Service — Extract structured incident data from natural language.

This module handles:
- Extracting structured incident attributes from citizen's natural language SOS
- Supporting English, Hindi, and Hinglish input
- Integration with priority engine signals

IMPORTANT: Only extract information explicitly stated in the text.
Use UNKNOWN for values that cannot be reliably inferred.
Do NOT fabricate or assume missing information.
"""

import re
from services.utils import contains_keyword


def extract_structured_incident(text, incident_type="", hazard_level=""):
    """
    Extract structured incident attributes from natural language text.

    Args:
        text: The citizen's SOS message (text or speech transcription)
        incident_type: The classified incident type from triage_service
        hazard_level: The hazard level from triage_service

    Returns:
        dict with extracted structured incident fields.
        Fields not found will have value "unknown".
    """
    if not text or not isinstance(text, str):
        return _empty_structured_incident()

    normalized = " ".join(text.casefold().split())
    structured = {}

    # Extract number of people
    people = _extract_people_count(normalized)
    structured["number_of_people"] = people if people is not None else "unknown"

    # Extract children count
    children = _extract_count(normalized, _CHILDREN_KEYWORDS, "children")
    structured["children"] = children if children is not None else "unknown"

    # Extract elderly count
    elderly = _extract_count(normalized, _ELDERLY_KEYWORDS, "elderly")
    structured["elderly"] = elderly if elderly is not None else "unknown"

    # Extract pregnant count
    pregnant = _extract_count(normalized, _PREGNANT_KEYWORDS, "pregnant")
    structured["pregnant"] = pregnant if pregnant is not None else "unknown"

    # Extract injury
    injury = _extract_boolean(normalized, _INJURY_KEYWORDS)
    structured["injury"] = injury if injury is not None else "unknown"

    # Extract trapped
    trapped = _extract_boolean(normalized, _TRAPPED_KEYWORDS)
    structured["trapped"] = trapped if trapped is not None else "unknown"

    # Extract flood depth
    flood_depth = _extract_flood_depth(normalized)
    structured["flood_depth_m"] = flood_depth if flood_depth is not None else "unknown"

    # Extract fire
    fire = _extract_boolean(normalized, _FIRE_KEYWORDS)
    # Also infer from incident type if not explicitly stated
    if fire is None and "Fire" in incident_type:
        fire = True
    structured["fire"] = fire if fire is not None else "unknown"

    # Extract building damage
    building_damage = _extract_building_damage(normalized)
    structured["building_damage"] = building_damage if building_damage is not None else "unknown"

    # Extract communication availability
    communication = _extract_communication(normalized)
    structured["communication"] = communication if communication is not None else "unknown"

    return structured


def extract_vulnerability_signals_from_structured(structured):
    """
    Extract vulnerability signals from structured incident data.

    Returns a list of signal strings compatible with priority_service.
    """
    signals = []

    if not structured:
        return signals

    children = structured.get("children")
    if isinstance(children, int) and children > 0:
        signals.append("Children present")

    elderly = structured.get("elderly")
    if isinstance(elderly, int) and elderly > 0:
        signals.append("Elderly person")

    pregnant = structured.get("pregnant")
    if isinstance(pregnant, int) and pregnant > 0:
        signals.append("Pregnant woman")

    if structured.get("trapped") == True:
        signals.append("Trapped person")

    return signals


def extract_medical_signals_from_structured(structured):
    """
    Extract medical signals from structured incident data.

    Returns a list of signal strings compatible with priority_service.
    """
    signals = []

    if not structured:
        return signals

    if structured.get("injury") == True:
        signals.append("Injury reported")

    return signals


def extract_accessibility_signals_from_structured(structured):
    """
    Extract accessibility signals from structured incident data.

    Returns a list of signal strings compatible with priority_service.
    """
    signals = []

    if not structured:
        return signals

    if structured.get("trapped") == True:
        signals.append("Trapped location")

    communication = structured.get("communication")
    if communication == "unavailable":
        signals.append("Communication unavailable")

    return signals


def get_hazard_boost_from_structured(structured, current_hazard_level):
    """
    Determine if structured incident data should boost hazard level.

    Returns the boosted hazard level.
    Hazard levels: LOW < MEDIUM < HIGH < CRITICAL
    """
    if not structured:
        return current_hazard_level

    hazard_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    current_idx = hazard_levels.index(current_hazard_level) if current_hazard_level in hazard_levels else 1

    # Fire with building damage boosts severity
    if structured.get("fire") == True:
        building_damage = structured.get("building_damage", "unknown")
        if building_damage == "major":
            current_idx = max(current_idx, 3)  # CRITICAL
        elif building_damage == "minor":
            current_idx = max(current_idx, 2)  # HIGH

    # High flood depth boosts severity
    flood_depth = structured.get("flood_depth_m")
    if isinstance(flood_depth, (int, float)):
        if flood_depth > 2.0:
            current_idx = max(current_idx, 3)  # CRITICAL
        elif flood_depth > 1.0:
            current_idx = max(current_idx, 2)  # HIGH

    # Trapped persons boost severity
    if structured.get("trapped") == True:
        current_idx = max(current_idx, 2)  # HIGH

    return hazard_levels[min(current_idx, 3)]


# ============================================================
# KEYWORD DEFINITIONS
# ============================================================

_CHILDREN_KEYWORDS = [
    "child", "children", "kid", "kids", "baby", "infant",
    "baccha", "bachcha", "bachche", "bachhe", "shishu",
    "बच्चा", "बच्चे", "शिशु",
]

_ELDERLY_KEYWORDS = [
    "elderly", "old", "aged", "senior", "bujurg", "boodhe",
    "बुजुर्ग", "बूढ़े",
]

_PREGNANT_KEYWORDS = [
    "pregnant", "garbhvati", "pet wali",
    "गर्भवती",
]

_INJURY_KEYWORDS = [
    "injured", "injury", "hurt", "wounded", "bleeding",
    "ghayal", "chot", "zakhmi", "khoon",
    "घायल", "चोट", "खून", "ज़ख्मी",
]

_TRAPPED_KEYWORDS = [
    "trapped", "stuck", "confined", "unable to move",
    "fansa", "fanse", "phansa", "phase",
    "फंसा", "फंसे",
]

_FIRE_KEYWORDS = [
    "fire", "flames", "burning", "smoke", "aag", "dhuan",
    "आग", "धुआं", "जल",
]

_BUILDING_DAMAGE_KEYWORDS = {
    "major": ["collapsed", "demolished", "girna", "girne", "dhwas", "तूट", "गिरने", "ध्वस्त"],
    "minor": ["cracked", "damage", "crack", "nuksan", "क्षति", "दरार"],
    "none": ["no damage", "safe", "kshatihin", "क्षतिहीन"],
}

_COMMUNICATION_KEYWORDS = {
    "unavailable": ["no signal", "no network", "communication lost", "phone not working", "no phone"],
    "available": ["phone available", "can call", "network available", "communication ok"],
}


# ============================================================
# EXTRACTION FUNCTIONS
# ============================================================

def _empty_structured_incident():
    """Return a structured incident with all fields set to unknown."""
    return {
        "number_of_people": "unknown",
        "children": "unknown",
        "elderly": "unknown",
        "pregnant": "unknown",
        "injury": "unknown",
        "trapped": "unknown",
        "flood_depth_m": "unknown",
        "fire": "unknown",
        "building_damage": "unknown",
        "communication": "unknown",
    }


def _extract_people_count(text):
    """
    Extract the total number of people involved.

    Looks for patterns like:
    - "8 people"
    - "8 log"
    - "8 log hain"
    - "8 persons"
    - "around 10 people"

    Returns the count from the match that appears earliest in the text.
    """
    candidates = []

    # Digit patterns: number followed by people/persons/log/vyakti
    digit_patterns = [
        r'(\d+)\s*(?:people|persons?|log(?:on)?|vyakti|व्यक्ति|लोग)',
        r'(\d+)\s*(?:individuals?|souls?|jan|जन)',
    ]
    for pattern in digit_patterns:
        for match in re.finditer(pattern, text):
            count = int(match.group(1))
            if 1 <= count <= 10000:
                candidates.append((match.start(), count))

    # "around/approximately X people"
    approx_pattern = r'(?:around|approx|approximately|lagbhag|करीब|लगभग)\s*(\d+)\s*(?:people|persons?|log|vyakti|व्यक्ति|लोग)'
    for match in re.finditer(approx_pattern, text):
        count = int(match.group(1))
        if 1 <= count <= 10000:
            candidates.append((match.start(), count))

    # "total X people"
    total_pattern = r'(?:total|kul|कुल)\s*(\d+)\s*(?:people|persons?|log|vyakti|व्यक्ति|लोग)'
    for match in re.finditer(total_pattern, text):
        count = int(match.group(1))
        if 1 <= count <= 10000:
            candidates.append((match.start(), count))

    # Number words
    number_words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
        "thirty": 30, "fifty": 50, "hundred": 100,
        "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5,
        "chhah": 6, "saat": 7, "aath": 8, "nau": 9, "dasa": 10, "das": 10,
        "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    }

    for word, num in number_words.items():
        pattern = rf'(?<![\w]){re.escape(word)}(?![\w])\s*(?:people|persons?|log(?:on)?|vyakti|व्यक्ति|लोग)'
        for match in re.finditer(pattern, text):
            candidates.append((match.start(), num))

    if candidates:
        # Return the count from the match that appears earliest in the text
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return None


def _extract_count(text, keywords, category):
    """
    Extract count for a specific category (children, elderly, pregnant).

    Looks for patterns like:
    - "2 children"
    - "2 bachche"
    - "do bachche"
    - "2 injured children"

    Returns the count from the match that appears earliest in the text.
    """
    candidates = []

    # Pattern: number + keyword
    for keyword in keywords:
        pattern = rf'(\d+)\s*{re.escape(keyword)}'
        for match in re.finditer(pattern, text):
            count = int(match.group(1))
            if 0 <= count <= 1000:
                candidates.append((match.start(), count))

        # Pattern: keyword + number (e.g., "children 2")
        pattern = rf'{re.escape(keyword)}\s*(\d+)'
        for match in re.finditer(pattern, text):
            count = int(match.group(1))
            if 0 <= count <= 1000:
                candidates.append((match.start(), count))

    # Number words
    number_words = {
        "ek": 1, "one": 1, "एक": 1,
        "do": 2, "two": 2, "दो": 2,
        "teen": 3, "three": 3, "तीन": 3,
        "char": 4, "four": 4, "चार": 4,
        "paanch": 5, "panch": 5, "five": 5, "पांच": 5,
        "chhah": 6, "six": 6, "छह": 6,
        "saat": 7, "seven": 7, "सात": 7,
        "aath": 8, "eight": 8, "आठ": 8,
        "nau": 9, "nine": 9, "नौ": 9,
        "dasa": 10, "das": 10, "ten": 10, "दस": 10,
    }

    for word, num in number_words.items():
        for keyword in keywords:
            pattern = rf'(?<![\w]){re.escape(word)}(?![\w])\s*{re.escape(keyword)}'
            for match in re.finditer(pattern, text):
                candidates.append((match.start(), num))

    # Special pattern: "X bachche hain" / "X children are"
    for keyword in keywords:
        pattern = rf'(\d+)\s*{re.escape(keyword)}\s*(?:hain|hai|hein|are|हैं|है)'
        for match in re.finditer(pattern, text):
            count = int(match.group(1))
            if 0 <= count <= 1000:
                candidates.append((match.start(), count))

    if candidates:
        # Return the count from the match that appears earliest in the text
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return None


def _extract_boolean(text, keywords):
    """
    Extract a boolean value based on keyword presence.

    Returns True if any keyword is found, None if not found.
    Does NOT return False for absence (use "unknown" instead).
    """
    for keyword in keywords:
        if contains_keyword(text, keyword):
            return True
    return None


def _extract_flood_depth(text):
    """
    Extract flood depth in meters.

    Looks for patterns like:
    - "1.5 meters"
    - "2m"
    - "3 feet"
    - "1.5m deep"
    """
    # Pattern: number + m/meter/meters/metra
    patterns = [
        r'(\d+\.?\d*)\s*(?:m|meter|meters|metre|metres|मीटर)',
        r'(\d+\.?\d*)\s*(?:meter|metre)\s*(?:deep|gehra|gehraai)',
        r'(?:water|paani|pani)\s*(?:level|height|gehraai|gehra)\s*(?:is|hai|he)?\s*(\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            depth = float(match.group(1))
            if 0 <= depth <= 20:
                return round(depth, 2)

    # Pattern: number + feet
    feet_pattern = r'(\d+\.?\d*)\s*(?:ft|foot|feet|फीट)'
    match = re.search(feet_pattern, text)
    if match:
        feet = float(match.group(1))
        meters = feet * 0.3048
        if 0 <= meters <= 20:
            return round(meters, 2)

    return None


def _extract_building_damage(text):
    """
    Extract building damage level.

    Returns: "major", "minor", "none", or None
    """
    # Check for major damage
    for keyword in _BUILDING_DAMAGE_KEYWORDS["major"]:
        if contains_keyword(text, keyword):
            return "major"

    # Check for minor damage
    for keyword in _BUILDING_DAMAGE_KEYWORDS["minor"]:
        if contains_keyword(text, keyword):
            return "minor"

    # Check for no damage
    for keyword in _BUILDING_DAMAGE_KEYWORDS["none"]:
        if contains_keyword(text, keyword):
            return "none"

    return None


def _extract_communication(text):
    """
    Extract communication availability.

    Returns: "available", "unavailable", or None
    """
    # Check for unavailable first (more specific)
    for keyword in _COMMUNICATION_KEYWORDS["unavailable"]:
        if contains_keyword(text, keyword):
            return "unavailable"

    # Check for available
    for keyword in _COMMUNICATION_KEYWORDS["available"]:
        if contains_keyword(text, keyword):
            return "available"

    return None
