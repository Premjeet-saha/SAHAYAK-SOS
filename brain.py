from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import re

app = Flask(__name__)
CORS(app)

latest_incident = {
    "lat": 20.296, "lng": 85.824,
    "status": "SAHAYAK Engine Online: Intelligent Priority Triage Active",
    "priority_score": 0,
    "structured_data": {},
    "gemini_explanation": "Awaiting citizen emergency broadcast..."
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

    # Priority calculation
    base_score = 30
    if hazard_level == "CRITICAL":
        base_score = 75
    elif hazard_level == "HIGH":
        base_score = 55
    elif hazard_level == "Medium":
        base_score = 40

    medical_modifier = 10 if medical == "YES" else 0

    people_modifier = 0
    if isinstance(people, int):
        if people >= 10:
            people_modifier = 15
        elif people >= 5:
            people_modifier = 10
        elif people >= 2:
            people_modifier = 5

    multi_signal_modifier = 5 if len(detected_hazards) > 1 else 0
    severe_medical_types = {
        "Cardiac Arrest Emergency", "Unconscious Patient", "Severe Bleeding Trauma",
        "Critical Physical Injury", "Multiple Trauma Injury", "Venomous Snake Bite"
    }
    severe_incident_modifier = 5 if hazard_level == "HIGH" and incident_type in severe_medical_types else 0

    priority_score = max(0, min(
        base_score + medical_modifier + people_modifier + multi_signal_modifier + severe_incident_modifier,
        100
    ))
    priority_breakdown = {
        "base_score": base_score,
        "medical_modifier": medical_modifier,
        "people_modifier": people_modifier,
        "multi_signal_modifier": multi_signal_modifier,
        "severe_incident_modifier": severe_incident_modifier,
        "final_score": priority_score
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
        "priority_breakdown": priority_breakdown
    }

    explanation = f"SAHAYAK Intelligent Triage ({priority_score}/100): Matched category '{incident_type}' with '{hazard_level}' hazard level. Medical Status: {medical}. Routed to: {service_dispatched}."

    latest_incident.update({
        "lat": lat,
        "lng": lng,
        "status": f"Active Dispatch: {incident_type}",
        "priority_score": priority_score,
        "structured_data": structured_data,
        "gemini_explanation": explanation
    })

    return jsonify({"status": "Success", "data": latest_incident}), 200

@app.route('/get-victim', methods=['GET'])
def get_victim():
    return jsonify(latest_incident), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
