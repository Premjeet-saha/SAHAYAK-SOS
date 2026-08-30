from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random

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
    raw_input = raw_input_original.lower()
    
    incident_id = f"SAH-{random.randint(10000, 99999)}"
    
    incident_type = "Urgent Citizen Distress Call"
    hazard_level = "HIGH"
    service_dispatched = "Emergency Response Police Unit & Rapid Patrol"
    people = 1
    medical = "NO"

    if input_type == 'image' or "base64," in raw_input_original:
        incident_type = "Critical Infrastructure Damage / Disaster Threat"
        hazard_level = "CRITICAL"
        service_dispatched = "NDRF & State Disaster Management (SDRF)"
        people = "Multiple / Visual Threat"
        medical = "NO"
    else:
        keyword_map = {
            # Fire & Industrial
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
            "heart attack": "Cardiac Arrest Emergency", "behosh": "Unconscious Patient", "बेहोश": "Unconscious Patient", 
            "khoon": "Severe Bleeding Trauma", "खून": "Severe Bleeding Trauma", "chot": "Critical Physical Injury", 
            "चोट": "Critical Physical Injury", "injured": "Multiple Trauma Injury", "bimar": "Acute Medical Emergency",
            "snake bite": "Venomous Snake Bite", "सांप": "Venomous Snake Bite", "saanp": "Venomous Snake Bite",

            # Accidents & Public Safety
            "accident": "Road Traffic Collision (RTA)", "crash": "Vehicle Crash", "takkar": "High-Speed Vehicle Collision", 
            "टक्कर": "High-Speed Vehicle Collision", "train": "Railway Derailment", "stampede": "Crowd Crush Stampede"
        }

        matched = False
        for keyword, official_type in keyword_map.items():
            if keyword in raw_input or keyword in raw_input_original:
                incident_type = official_type
                matched = True
                break 

        # Intelligent Resource & Service Routing (Without dial numbers)
        if "Fire" in incident_type or "Gas" in incident_type or "Cylinder" in incident_type:
            hazard_level = "CRITICAL"
            service_dispatched = "State Fire Services & Fire Tender Units"
            medical = "YES"
        elif "Flood" in incident_type or "Earthquake" in incident_type or "Landslide" in incident_type or "Cloudburst" in incident_type:
            hazard_level = "CRITICAL"
            service_dispatched = "NDRF & State Disaster Response Force (SDRF)"
            medical = "YES"
        elif "Cardiac" in incident_type or "Patient" in incident_type or "Trauma" in incident_type or "Injury" in incident_type or "Snake" in incident_type or "Medical" in incident_type:
            hazard_level = "HIGH"
            service_dispatched = "National Emergency Ambulance & Medical Response Team"
            medical = "YES"
        elif not matched and len(raw_input.strip()) > 3:
            incident_type = "General Emergency Assistance Required"
            hazard_level = "Medium"
            service_dispatched = "Nearest Emergency Patrol & Response Unit"

        # People count extraction
        if any(w in raw_input or w in raw_input_original for w in ["10", "दस", "dasa"]): people = 10
        elif any(w in raw_input or w in raw_input_original for w in ["5", "पांच", "panch"]): people = 5
        elif any(w in raw_input or w in raw_input_original for w in ["2", "दो", "do"]): people = 2
        elif any(w in raw_input or w in raw_input_original for w in ["3", "तीन", "teen"]): people = 3
        elif any(w in raw_input or w in raw_input_original for w in ["4", "चार", "char"]): people = 4
        
        # Explicit medical keyword check
        if any(word in raw_input or word in raw_input_original for word in ["elderly", "maa", "bujurg", "बुजुर्ग", "injured", "medical", "chot", "चोट", "khoon", "खून", "behosh", "बेहोश", "bimar", "saanp", "सांप", "heart", "pain", "hospital", "doctor"]): 
            medical = "YES"

    # Priority calculation
    base_score = 30
    if hazard_level == "CRITICAL":
        base_score = 75
    elif hazard_level == "HIGH":
        base_score = 55
    elif hazard_level == "Medium":
        base_score = 40

    if medical == "YES": 
        base_score += 15

    priority_score = min(int(base_score), 100)

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
        "resource_needed": service_dispatched
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
