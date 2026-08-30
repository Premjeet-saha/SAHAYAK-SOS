from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

latest_incident = {
    "lat": 20.296, "lng": 85.824,
    "status": "SAHAYAK Engine Online: Intelligent Priority Triage Active",
    "priority_score": 0,
    "structured_data": {},
    "gemini_explanation": "Awaiting citizen emergency broadcast...",
    "location_source": "demo_fallback",
    "request_timestamp": None
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/report-emergency', methods=['POST'])
def report_emergency():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    raw_input_payload = data.get('raw_input', '')
    if raw_input_payload is None:
        raw_input_payload = ''

    input_type = data.get('type', 'text')
    if not isinstance(input_type, str):
        input_type = 'text'
    
    raw_input_original = str(raw_input_payload)
    raw_input = " ".join(raw_input_original.casefold().split())
    
    # Helper functions for keyword matching (used by both classification and priority scoring)
    def contains_keyword(keyword):
        normalized_keyword = " ".join(keyword.casefold().split())
        start = raw_input.find(normalized_keyword)
        while start != -1:
            end = start + len(normalized_keyword)
            before = raw_input[start - 1] if start else ""
            after = raw_input[end] if end < len(raw_input) else ""
            if (not before or not before.isalnum()) and (not after or not after.isalnum()):
                return True
            start = raw_input.find(normalized_keyword, start + 1)
        return False
    
    def add_unique(items, value):
        if value not in items:
            items.append(value)
    
    incident_id = f"SAH-{random.randint(10000, 99999)}"
    
    incident_type = "Urgent Citizen Distress Call"
    hazard_level = "HIGH"
    service_dispatched = "Emergency Response Police Unit & Rapid Patrol"
    people = 1
    medical = "NO"
    detected_hazards = []
    detected_medical_signals = []
    detected_keywords = []

    if input_type == 'image' or "base64," in raw_input_original:
        incident_type = "Critical Infrastructure Damage / Disaster Threat"
        hazard_level = "CRITICAL"
        service_dispatched = "NDRF & State Disaster Management (SDRF)"
        people = "Multiple / Visual Threat"
        medical = "NO"
    else:
        keyword_map = {
            # Fire & Industrial
            "fire": "Major Fire Outbreak",
            "aag": "Major Fire Outbreak", "आग": "Major Fire Outbreak", "lagi hai": "Major Fire Outbreak", 
            "jala": "Major Fire Outbreak", "धुआं": "Heavy Smoke Hazard", "dhuan": "Heavy Smoke Hazard",
            "gas leak": "Industrial Gas Leak", "cylinder": "Cylinder Blast", "सिलेंडर": "Cylinder Blast",

            # Floods & Weather
            "flood": "Flash Flood / Waterlogging", "paani": "Flash Flood / Waterlogging", "pani": "Flash Flood / Waterlogging", 
            "पानी": "Flash Flood / Waterlogging", "बाढ़": "Severe River Flood", "baadh": "Severe River Flood", 
            "doob": "Submerged Area / Drowning Risk", "डूब": "Submerged Area / Drowning Risk", "cloudburst": "Cloudburst & Flash Flood",

            # Earthquakes & Landslides
            "bhookamp": "Earthquake Tremors", "bhukamp": "Earthquake Tremors", "भूकंप": "Earthquake Tremors", 
            "dharti hil": "Earthquake Tremors", "landslide": "Mountain Landslide", "भूस्खलन": "Mountain Landslide", 

            # Medical & Health
            "unconscious": "Unconscious Patient",
            "heart attack": "Cardiac Arrest Emergency", "behosh": "Unconscious Patient", "बेहोश": "Unconscious Patient", 
            "khoon": "Severe Bleeding Trauma", "खून": "Severe Bleeding Trauma", "chot": "Critical Physical Injury", 
            "चोट": "Critical Physical Injury", "injured": "Multiple Trauma Injury", "bimar": "Acute Medical Emergency",
            "snake bite": "Venomous Snake Bite", "सांप": "Venomous Snake Bite", "saanp": "Venomous Snake Bite",

            # Accidents & Public Safety
            "accident": "Road Traffic Collision (RTA)", "crash": "Vehicle Crash", "takkar": "High-Speed Vehicle Collision", 
            "टक्कर": "High-Speed Vehicle Collision", "train": "Railway Derailment", "stampede": "Crowd Crush Stampede"
        }

        medical_categories = {
            "Cardiac Arrest Emergency", "Unconscious Patient", "Severe Bleeding Trauma",
            "Critical Physical Injury", "Multiple Trauma Injury", "Acute Medical Emergency",
            "Venomous Snake Bite"
        }

        matched_categories = []
        for keyword, official_type in keyword_map.items():
            if contains_keyword(keyword):
                add_unique(detected_keywords, keyword)
                add_unique(matched_categories, official_type)
                if official_type in medical_categories:
                    add_unique(detected_medical_signals, official_type)
                else:
                    add_unique(detected_hazards, official_type)

        matched = bool(matched_categories)
        if matched:
            incident_type = matched_categories[0]

        # Intelligent Resource & Service Routing (Without dial numbers)
        if "Fire" in incident_type or "Gas" in incident_type or "Cylinder" in incident_type:
            hazard_level = "CRITICAL"
            service_dispatched = "State Fire Services & Fire Tender Units"
        elif "Flood" in incident_type or "Earthquake" in incident_type or "Landslide" in incident_type or "Cloudburst" in incident_type:
            hazard_level = "CRITICAL"
            service_dispatched = "NDRF & State Disaster Response Force (SDRF)"
        elif "Cardiac" in incident_type or "Patient" in incident_type or "Trauma" in incident_type or "Injury" in incident_type or "Snake" in incident_type or "Medical" in incident_type:
            hazard_level = "HIGH"
            service_dispatched = "National Emergency Ambulance & Medical Response Team"
            medical = "YES"
        elif not matched and len(raw_input.strip()) > 3:
            incident_type = "General Emergency Assistance Required"
            hazard_level = "Medium"
            service_dispatched = "Nearest Emergency Patrol & Response Unit"

        # People count extraction
        def extract_people_count(text):
            number_words = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "do": 2, "teen": 3, "char": 4, "panch": 5, "dasa": 10,
                "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "दस": 10
            }
            number_options = "|".join(re.escape(word) for word in sorted(number_words, key=len, reverse=True))
            count_pattern = rf"(?<!\w)(?P<count>\d{{1,4}}|{number_options})(?!\w)"
            people_terms = r"people|persons?|victims?|injured|trapped|log|लोग"
            candidates = []

            def add_candidate(match, confidence):
                token = match.group("count")
                count = int(token) if token.isdigit() else number_words[token]
                if 1 <= count <= 1000:
                    candidates.append((confidence, match.start("count"), count))

            for match in re.finditer(rf"{count_pattern}\s+(?:{people_terms})(?!\w)", text):
                add_candidate(match, 3)
            for match in re.finditer(rf"(?:{people_terms})(?!\w)\s*(?:are|were|:|=)?\s*{count_pattern}", text):
                add_candidate(match, 3)
            for match in re.finditer(rf"\bthere\s+(?:are|were)\s+{count_pattern}", text):
                add_candidate(match, 2)

            # Prefer the strongest people-related phrase; equally strong matches use the first one in the report.
            return min(candidates, key=lambda candidate: (-candidate[0], candidate[1]))[2] if candidates else 1

        people = extract_people_count(raw_input)
        
        medical_signal_map = {
            "elderly": "Elderly person involved", "maa": "Mother involved",
            "bujurg": "Elderly person involved", "बुजुर्ग": "Elderly person involved",
            "medical": "Medical assistance requested", "heart": "Cardiac symptoms reported",
            "pain": "Pain reported", "hospital": "Hospital care requested",
            "doctor": "Doctor requested"
        }
        for keyword, signal in medical_signal_map.items():
            if contains_keyword(keyword):
                add_unique(detected_keywords, keyword)
                add_unique(detected_medical_signals, signal)

        # Explicit medical keyword check
        if any(contains_keyword(word) for word in ["elderly", "maa", "bujurg", "बुजुर्ग", "injured", "medical", "chot", "चोट", "khoon", "खून", "behosh", "बेहोश", "bimar", "saanp", "सांप", "heart", "pain", "hospital", "doctor"]):
            medical = "YES"

        if detected_medical_signals:
            medical = "YES"

        # Only a generic patrol route yields to an explicit medical signal; specialized hazard routes stay primary.
        if medical == "YES" and incident_type == "General Emergency Assistance Required" and service_dispatched == "Nearest Emergency Patrol & Response Unit":
            service_dispatched = "National Emergency Ambulance & Medical Response Team"

    # ========== DYNAMIC RESCUE PRIORITY SCORE CALCULATION ==========
    # Weights for the 5-component scoring model
    WEIGHT_SEVERITY = 0.30
    WEIGHT_VULNERABILITY = 0.20
    WEIGHT_MEDICAL = 0.25
    WEIGHT_ACCESSIBILITY = 0.15
    WEIGHT_WAITING_TIME = 0.10
    
    # Request timestamp for waiting time calculation
    request_timestamp = datetime.utcnow().isoformat()
    
    # --- SEVERITY COMPONENT (0-100) ---
    # Derived from hazard_level and incident classification
    def calculate_severity_score(hazard_level, incident_type):
        if hazard_level == "CRITICAL":
            return 95.0
        elif hazard_level == "HIGH":
            return 75.0
        elif hazard_level == "Medium":
            return 50.0
        else:
            return 30.0
    
    severity_score = calculate_severity_score(hazard_level, incident_type)
    
    # --- VULNERABILITY COMPONENT (0-100) ---
    # Detect children, elderly, and other vulnerable persons
    def extract_vulnerability_signals(text):
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
            if contains_keyword(keyword):
                if signal not in detected_vulnerability:
                    detected_vulnerability.append(signal)
        return detected_vulnerability
    
    vulnerability_signals = extract_vulnerability_signals(raw_input)
    
    # Vulnerability scoring: presence of vulnerable groups elevates score
    def calculate_vulnerability_score(signals):
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
    
    vulnerability_score = calculate_vulnerability_score(vulnerability_signals)
    
    # --- MEDICAL URGENCY COMPONENT (0-100) ---
    # Severity levels of medical conditions with normalized scores
    def calculate_medical_urgency_score(detected_signals, medical_status):
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
    
    medical_urgency_score = calculate_medical_urgency_score(detected_medical_signals, medical)
    
    # --- ACCESSIBILITY COMPONENT (0-100) ---
    # IMPORTANT: Lower accessibility = higher score (harder to reach = more urgent)
    # Uses explicit incident information, NOT fabricated distance
    def extract_accessibility_signals(text):
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
            if contains_keyword(keyword):
                if signal not in detected_accessibility:
                    detected_accessibility.append(signal)
        return detected_accessibility
    
    accessibility_signals = extract_accessibility_signals(raw_input)
    
    # Accessibility scoring: LOWER accessibility = HIGHER urgency (higher score)
    def calculate_accessibility_score(signals):
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
    
    accessibility_score = calculate_accessibility_score(accessibility_signals)
    
    # --- WAITING TIME COMPONENT (0-100) ---
    # Time since request was received
    # Bounded function: increases over time but cannot exceed 100
    def calculate_waiting_time_score(timestamp_str):
        if not timestamp_str:
            return 0.0  # Newly received SOS
        
        try:
            created_time = datetime.fromisoformat(timestamp_str)
            current_time = datetime.utcnow()
            elapsed_seconds = (current_time - created_time).total_seconds()
            
            # Waiting time scoring function (bounded)
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
        except:
            return 0.0  # Invalid timestamp
    
    # For new incidents, waiting time starts at 0
    waiting_time_score = 0.0
    
    # --- CALCULATE DYNAMIC PRIORITY SCORE ---
    # Weighted sum of all 5 components
    priority_score = min(100.0, max(0.0,
        (WEIGHT_SEVERITY * severity_score) +
        (WEIGHT_VULNERABILITY * vulnerability_score) +
        (WEIGHT_MEDICAL * medical_urgency_score) +
        (WEIGHT_ACCESSIBILITY * accessibility_score) +
        (WEIGHT_WAITING_TIME * waiting_time_score)
    ))
    
    priority_score = round(priority_score, 1)
    
    # --- BUILD PRIORITY BREAKDOWN (for transparency & judge-facing explanation) ---
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

    lat = data.get('lat', 20.296)
    lng = data.get('lng', 85.824)
    try:
        lat = float(lat)
        lng = float(lng)
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError
    except (TypeError, ValueError):
        lat, lng = 20.296, 85.824
    
    location_source = data.get('location_source', 'demo_fallback')
    if not isinstance(location_source, str):
        location_source = 'demo_fallback'
    if location_source not in ('gps', 'demo_fallback'):
        location_source = 'demo_fallback'
    
    structured_data = {
        "incident_id": incident_id,
        "type": incident_type,
        "hazard_level": hazard_level,
        "people_involved": people,
        "medical_emergency": medical,
        "resource_needed": service_dispatched,
        "detected_hazards": detected_hazards,
        "detected_medical_signals": detected_medical_signals,
        "detected_keywords": detected_keywords,
        "priority_breakdown": priority_breakdown,
        "location_source": location_source,
        "request_timestamp": request_timestamp,
        "vulnerability_signals": vulnerability_signals,
        "accessibility_signals": accessibility_signals
    }

    # Judge-facing explanation highlighting priority components
    explanation_parts = [f"Priority: {priority_score}/100"]
    
    if severity_score >= 75:
        explanation_parts.append("High severity incident")
    elif severity_score >= 50:
        explanation_parts.append("Moderate severity incident")
    else:
        explanation_parts.append("Lower severity incident")
    
    if vulnerability_signals:
        explanation_parts.append(f"Vulnerable persons: {', '.join(vulnerability_signals)}")
    
    if medical == "YES" and medical_urgency_score >= 75:
        explanation_parts.append("Critical medical urgency")
    elif medical == "YES" and medical_urgency_score >= 50:
        explanation_parts.append("Medical emergency")
    
    if accessibility_signals:
        explanation_parts.append(f"Access difficulty: {', '.join(accessibility_signals)}")
    
    explanation_parts.append(f"Routed to: {service_dispatched}")
    
    explanation = " | ".join(explanation_parts)

    latest_incident.update({
        "lat": lat,
        "lng": lng,
        "status": f"Active Dispatch: {incident_type}",
        "priority_score": priority_score,
        "structured_data": structured_data,
        "gemini_explanation": explanation,
        "location_source": location_source,
        "request_timestamp": request_timestamp
    })

    return jsonify({"status": "Success", "data": latest_incident}), 200

@app.route('/get-victim', methods=['GET'])
def get_victim():
    return jsonify(latest_incident), 200

# ========== RESOURCE ALLOCATION ENGINE ==========
# Teacher demo scenario resource inventory
DEFAULT_RESOURCE_INVENTORY = {
    "ndrf": 8,
    "ambulance": 21,
    "boat": 12,
    "shelter": 6,
    "hospital": 9
}

def validate_resource_inventory(inventory):
    """Validate resource inventory structure and values."""
    if not isinstance(inventory, dict):
        return False
    
    required_keys = {"ndrf", "ambulance", "boat", "shelter", "hospital"}
    if not all(key in inventory for key in required_keys):
        return False
    
    for key, value in inventory.items():
        if not isinstance(value, int) or value < 0:
            return False
    
    return True

def get_required_resources(case):
    """
    Determine which resources a case requires based on incident type and signals.
    
    Returns a list of required resource types: ["ndrf", "ambulance", "hospital", etc.]
    Uses deterministic rules based on incident characteristics, NOT just high priority score.
    """
    required = []
    
    if not isinstance(case, dict):
        return required
    
    incident_type = case.get("type", "")
    hazard_level = case.get("hazard_level", "")
    medical_emergency = case.get("medical_emergency", "NO")
    detected_medical_signals = case.get("detected_medical_signals", [])
    detected_hazards = case.get("detected_hazards", [])
    accessibility_signals = case.get("accessibility_signals", [])
    vulnerability_signals = case.get("vulnerability_signals", [])
    
    # FLOOD / WATERLOGGING / DISASTER
    if "Flood" in incident_type or "Earthquake" in incident_type or "Landslide" in incident_type or "Cloudburst" in incident_type:
        required.append("ndrf")
        
        # Boat needed if access is severely limited
        if accessibility_signals:
            access_signals_str = " ".join(accessibility_signals).lower()
            if any(term in access_signals_str for term in ["trapped", "isolated", "inaccessible", "unreachable", "blocked"]):
                required.append("boat")
        
        # Shelter needed for displaced disaster victims
        if "Flood" in incident_type or "Earthquake" in incident_type:
            required.append("shelter")
    
    # MEDICAL EMERGENCY
    if medical_emergency == "YES":
        # Critical medical conditions
        critical_conditions = {"Cardiac Arrest Emergency", "Unconscious Patient", "Severe Bleeding Trauma"}
        if detected_medical_signals and any(signal in critical_conditions for signal in detected_medical_signals):
            required.append("ambulance")
            required.append("hospital")
        # Serious injuries/trauma
        elif detected_medical_signals and any(signal in {"Critical Physical Injury", "Multiple Trauma Injury", "Venomous Snake Bite"} for signal in detected_medical_signals):
            required.append("ambulance")
            required.append("hospital")
        # Other medical signals
        elif detected_medical_signals:
            required.append("ambulance")
            if "hospital" in detected_medical_signals or "Hospital care requested" in detected_medical_signals:
                required.append("hospital")
        # Generic medical request without specific signals
        else:
            required.append("ambulance")
    
    # FIRE / INDUSTRIAL - preserve existing routing, do NOT allocate disaster resources
    # Only allocate ambulance/hospital if actual medical signals exist
    if "Fire" in incident_type or "Gas" in incident_type or "Cylinder" in incident_type:
        if medical_emergency == "YES" and detected_medical_signals:
            required.append("ambulance")
            required.append("hospital")
    
    # ROAD ACCIDENT / COLLISION
    if "Collision" in incident_type or "Accident" in incident_type or "Crash" in incident_type or "Derailment" in incident_type:
        if medical_emergency == "YES" and detected_medical_signals:
            required.append("ambulance")
            required.append("hospital")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_required = []
    for resource in required:
        if resource not in seen:
            seen.add(resource)
            unique_required.append(resource)
    
    return unique_required

def allocate_resources_to_cases(cases, custom_inventory=None):
    """
    Allocate limited rescue resources to SOS cases based on priority and compatibility.
    
    Args:
        cases: List of case dictionaries (from SOS reports)
        custom_inventory: Optional dict with resource counts. Defaults to DEFAULT_RESOURCE_INVENTORY.
    
    Returns:
        {
            "initial_resources": {...},
            "remaining_resources": {...},
            "allocated_resources": {...},
            "allocations": [...],
            "unallocated_count": int,
            "summary": {...}
        }
    """
    # Validate input
    if not isinstance(cases, list):
        return {
            "error": "Cases must be a list",
            "initial_resources": DEFAULT_RESOURCE_INVENTORY,
            "allocations": []
        }
    
    # Use provided inventory or default
    if custom_inventory is None:
        inventory = dict(DEFAULT_RESOURCE_INVENTORY)
    else:
        if not validate_resource_inventory(custom_inventory):
            return {
                "error": "Invalid resource inventory",
                "initial_resources": DEFAULT_RESOURCE_INVENTORY,
                "allocations": []
            }
        inventory = dict(custom_inventory)
    
    initial_inventory = dict(inventory)
    allocated_inventory = {key: 0 for key in inventory}
    
    # Validate and prepare cases
    valid_cases = []
    for case in cases:
        if isinstance(case, dict) and "incident_id" in case and "priority_score" in case:
            valid_cases.append(case)
    
    # Sort by priority (descending), then by request_timestamp (ascending), then by incident_id
    def sort_key(case):
        priority = float(case.get("priority_score", 0))
        timestamp = case.get("request_timestamp", "9999-12-31T23:59:59")
        incident_id = case.get("incident_id", "ZZZ-99999")
        
        # Primary: descending priority (negate for reverse sort)
        # Secondary: ascending timestamp (earlier = higher priority)
        # Tertiary: ascending incident_id (deterministic)
        return (-priority, timestamp, incident_id)
    
    sorted_cases = sorted(valid_cases, key=sort_key)
    
    # Process each case
    allocations = []
    for case in sorted_cases:
        required = get_required_resources(case)
        
        incident_id = case.get("incident_id", "UNKNOWN")
        priority_score = case.get("priority_score", 0)
        
        if not required:
            # No resources required
            allocations.append({
                "incident_id": incident_id,
                "priority_score": priority_score,
                "status": "NO_RESOURCE_REQUIRED",
                "required_resources": [],
                "allocated_resources": [],
                "waiting_for": []
            })
            continue
        
        # Try to allocate each required resource
        allocated = []
        waiting = []
        
        for resource_type in required:
            if inventory[resource_type] > 0:
                # Allocate this resource
                inventory[resource_type] -= 1
                allocated_inventory[resource_type] += 1
                allocated.append(resource_type)
            else:
                # Resource not available
                waiting.append(resource_type)
        
        # Determine status
        if not waiting:
            status = "ALLOCATED"
        elif allocated:
            status = "PARTIALLY_ALLOCATED"
        else:
            status = "WAITING_FOR_RESOURCES"
        
        allocations.append({
            "incident_id": incident_id,
            "priority_score": priority_score,
            "status": status,
            "required_resources": required,
            "allocated_resources": allocated,
            "waiting_for": waiting
        })
    
    # Calculate summary
    fully_allocated = sum(1 for a in allocations if a["status"] == "ALLOCATED")
    partially_allocated = sum(1 for a in allocations if a["status"] == "PARTIALLY_ALLOCATED")
    waiting_only = sum(1 for a in allocations if a["status"] == "WAITING_FOR_RESOURCES")
    no_resource_req = sum(1 for a in allocations if a["status"] == "NO_RESOURCE_REQUIRED")
    
    return {
        "initial_resources": initial_inventory,
        "remaining_resources": inventory,
        "allocated_resources": allocated_inventory,
        "allocations": allocations,
        "summary": {
            "total_cases": len(allocations),
            "fully_allocated": fully_allocated,
            "partially_allocated": partially_allocated,
            "waiting_for_resources": waiting_only,
            "no_resource_required": no_resource_req
        }
    }

@app.route('/allocate-resources', methods=['POST'])
def allocate_resources():
    """
    Resource allocation decision-support endpoint.
    
    Expected JSON:
    {
        "cases": [
            {
                "incident_id": "SAH-12345",
                "priority_score": 85.2,
                "type": "Flood Disaster",
                "medical_emergency": "NO",
                "detected_medical_signals": [],
                "detected_hazards": ["Flooding"],
                "accessibility_signals": ["Trapped"],
                "vulnerability_signals": [],
                ...
            },
            ...
        ],
        "resources": {
            "ndrf": 8,
            "ambulance": 21,
            "boat": 12,
            "shelter": 6,
            "hospital": 9
        }
    }
    
    The "resources" field is optional. If omitted, default teacher demo inventory is used.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON"}), 400
    
    cases = data.get("cases", [])
    custom_resources = data.get("resources", None)
    
    result = allocate_resources_to_cases(cases, custom_resources)
    
    return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
