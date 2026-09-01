"""
SAHAYAK SOS — Flask API Orchestration Layer

This module is the main entry point for the SAHAYAK SOS emergency response system.
It handles:
- Flask application setup and configuration
- API route definitions
- Request parsing and validation
- Calling service modules in the correct order
- Assembling API responses

All business logic is delegated to service modules in services/.
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import logging
from datetime import datetime

from services.ml_service import predict_ml_triage, get_ml_cache
from services.triage_service import classify_emergency
from services.priority_service import (
    calculate_priority_score,
    extract_vulnerability_signals,
    extract_accessibility_signals,
)
from services.resource_service import (
    DEFAULT_RESOURCE_INVENTORY,
    allocate_resources_to_cases,
)
from services.zone_service import (
    PROTOTYPE_RESOURCE_LOCATIONS,
    _RESOURCE_TYPES,
)
from services.optimization_service import run_zone_optimization
from services.structured_incident import extract_structured_incident

logger = logging.getLogger("SAHAYAK_BRAIN")

app = Flask(__name__)
CORS(app)

# Application state
latest_incident = {
    "lat": 20.296, "lng": 85.824,
    "status": "SAHAYAK Engine Online: Intelligent Priority Triage Active",
    "priority_score": 0,
    "structured_data": {},
    "gemini_explanation": "Awaiting citizen emergency broadcast...",
    "location_source": "demo_fallback",
    "request_timestamp": None,
    "ml_prediction": {"available": False, "status": "Awaiting emergency input"}
}

# Command-center case history (in-memory for prototype/demo)
_case_history = []


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/report-emergency', methods=['POST'])
def report_emergency():
    """Process an incoming emergency report."""
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
    raw_input_normalized = " ".join(raw_input_original.casefold().split())

    # Generate incident ID
    incident_id = f"SAH-{random.randint(10000, 99999)}"

    # Step 1: Deterministic triage classification
    triage_result = classify_emergency(raw_input_normalized, input_type)

    incident_type = triage_result["incident_type"]
    hazard_level = triage_result["hazard_level"]
    service_dispatched = triage_result["service_dispatched"]
    people = triage_result["people"]
    medical = triage_result["medical"]
    detected_hazards = triage_result["detected_hazards"]
    detected_medical_signals = triage_result["detected_medical_signals"]
    detected_keywords = triage_result["detected_keywords"]

    # Step 2: Extract priority signals
    vulnerability_signals = extract_vulnerability_signals(raw_input_normalized)
    accessibility_signals = extract_accessibility_signals(raw_input_normalized)

    # Step 3: Extract structured incident from natural language
    structured_incident = extract_structured_incident(
        text=raw_input_original,
        incident_type=incident_type,
        hazard_level=hazard_level
    )

    # Step 4: Calculate priority score (with structured incident integration)
    request_timestamp = datetime.utcnow().isoformat()
    priority_result = calculate_priority_score(
        hazard_level=hazard_level,
        incident_type=incident_type,
        detected_medical_signals=detected_medical_signals,
        medical=medical,
        vulnerability_signals=vulnerability_signals,
        accessibility_signals=accessibility_signals,
        timestamp_str=None,  # New incident, waiting time starts at 0
        structured_incident=structured_incident,
    )

    priority_score = priority_result["priority_score"]
    priority_breakdown = priority_result["priority_breakdown"]

    # Step 4: GPS handling
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

    # Step 5: ML Triage Prediction (supplementary only)
    ml_prediction = predict_ml_triage(raw_input_original if input_type != 'image' else 'Visual disaster threat image')

    # Build structured data
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
        "accessibility_signals": accessibility_signals,
        "ml_prediction": ml_prediction,
        "structured_incident": structured_incident,
    }

    # Build explanation
    explanation_parts = [f"Priority: {priority_score}/100"]

    severity_score = priority_breakdown["components"]["severity"]["score"]
    medical_urgency_score = priority_breakdown["components"]["medical"]["score"]

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

    # Update latest incident
    latest_incident.update({
        "lat": lat,
        "lng": lng,
        "status": f"Active Dispatch: {incident_type}",
        "priority_score": priority_score,
        "structured_data": structured_data,
        "gemini_explanation": explanation,
        "location_source": location_source,
        "request_timestamp": request_timestamp,
        "ml_prediction": ml_prediction
    })

    # Append to case history for command-center display
    _case_history.append({
        "incident_id": incident_id,
        "type": incident_type,
        "hazard_level": hazard_level,
        "priority_score": priority_score,
        "medical_emergency": medical,
        "lat": lat,
        "lng": lng,
        "location_source": location_source,
        "request_timestamp": request_timestamp,
        "ml_prediction": ml_prediction,
        "priority_breakdown": priority_breakdown,
        "vulnerability_signals": vulnerability_signals,
        "accessibility_signals": accessibility_signals,
        "detected_medical_signals": detected_medical_signals,
        "detected_hazards": detected_hazards,
        "people_involved": people,
        "resource_needed": service_dispatched,
        "structured_incident": structured_incident,
    })

    return jsonify({"status": "Success", "data": latest_incident}), 200


@app.route('/allocation-state', methods=['GET'])
def allocation_state():
    """
    Return the current command-center state including all cases,
    zone aggregation, optimization results, and resource inventory.
    This is the primary endpoint for the frontend dashboard.
    """
    # Build cases list from history
    cases = []
    for c in _case_history:
        cases.append({
            "incident_id": c.get("incident_id", "UNKNOWN"),
            "priority_score": c.get("priority_score", 0),
            "type": c.get("type", ""),
            "hazard_level": c.get("hazard_level", ""),
            "medical_emergency": c.get("medical_emergency", "NO"),
            "lat": c.get("lat", 20.296),
            "lng": c.get("lng", 85.824),
            "location_source": c.get("location_source", "demo_fallback"),
            "request_timestamp": c.get("request_timestamp"),
            "ml_prediction": c.get("ml_prediction", {"available": False}),
            "priority_breakdown": c.get("priority_breakdown", {}),
            "vulnerability_signals": c.get("vulnerability_signals", []),
            "accessibility_signals": c.get("accessibility_signals", []),
            "detected_medical_signals": c.get("detected_medical_signals", []),
            "detected_hazards": c.get("detected_hazards", []),
            "people_involved": c.get("people_involved", 1),
            "resource_needed": c.get("resource_needed", ""),
            "structured_incident": c.get("structured_incident", {}),
        })

    # Run zone optimization
    zone_result = run_zone_optimization(cases)

    # Build resource locations with allocation status
    allocated_resource_ids = set()
    for assignment in zone_result.get("assignments", []):
        allocated_resource_ids.add(assignment.get("resource_id"))

    resources = []
    for loc in PROTOTYPE_RESOURCE_LOCATIONS:
        res_copy = dict(loc)
        res_copy["allocated"] = loc["resource_id"] in allocated_resource_ids
        # Find which zone this resource is assigned to
        for assignment in zone_result.get("assignments", []):
            if assignment.get("resource_id") == loc["resource_id"]:
                res_copy["assigned_zone"] = assignment.get("zone_id")
                res_copy["distance_km"] = assignment.get("distance_km", 0)
                break
        resources.append(res_copy)

    # Build inventory summary
    inventory = {}
    inv_before = zone_result.get("inventory_before", DEFAULT_RESOURCE_INVENTORY)
    inv_after = zone_result.get("inventory_after", DEFAULT_RESOURCE_INVENTORY)
    for r in _RESOURCE_TYPES:
        allocated_count = inv_before.get(r, 0) - inv_after.get(r, 0)
        # Calculate demand from zones
        demand = 0
        for zone in zone_result.get("zones", []):
            demand += zone.get("resource_demand", {}).get(r, 0)
        inventory[r] = {
            "available": inv_after.get(r, 0),
            "allocated": allocated_count,
            "total": inv_before.get(r, 0),
            "demand": demand,
            "unmet": max(0, demand - allocated_count),
        }

    return jsonify({
        "status": "success",
        "case_count": len(cases),
        "cases": cases,
        "optimization": {
            "method": zone_result.get("optimization_method", "none"),
            "status": zone_result.get("optimization_status", "no_zones"),
            "objective_value": zone_result.get("objective_value", 0),
            "note": zone_result.get("optimization_note", ""),
        },
        "inventory": inventory,
        "zones": zone_result.get("zones", []),
        "assignments": zone_result.get("assignments", []),
        "resources": resources,
        "zone_summary": zone_result.get("zone_summary", {}),
        "prototype_notice": "Resource locations and zones are PROTOTYPE/DEMO data for hackathon demonstration."
    }), 200


@app.route('/get-victim', methods=['GET'])
def get_victim():
    """Return the latest incident data."""
    return jsonify(latest_incident), 200


@app.route('/allocate-resources', methods=['POST'])
def allocate_resources():
    """
    Resource allocation decision-support endpoint (Phase 3A enhanced).

    Accepts (existing format, unchanged):
    {
        "cases": [...],
        "resources": { "ndrf": 8, "ambulance": 21, ... }  // optional
    }

    Returns all existing fields PLUS new additive fields:
        optimization_method, optimization_status, inventory_before,
        inventory_after, zones, assignments, zone_summary,
        objective_value, optimization_note
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON"}), 400

    cases = data.get("cases", [])
    custom_resources = data.get("resources", None)

    # Existing case-level allocation (preserved, unchanged)
    legacy_result = allocate_resources_to_cases(cases, custom_resources)

    # Phase 3A zone-level optimization (additive)
    zone_result = run_zone_optimization(cases, custom_resources)

    # Merge: existing fields + new fields
    merged = dict(legacy_result)
    merged["optimization_method"] = zone_result["optimization_method"]
    merged["optimization_status"] = zone_result["optimization_status"]
    merged["inventory_before"] = zone_result["inventory_before"]
    merged["inventory_after"] = zone_result["inventory_after"]
    merged["zones"] = zone_result["zones"]
    merged["assignments"] = zone_result["assignments"]
    merged["zone_summary"] = zone_result["zone_summary"]
    merged["objective_value"] = zone_result["objective_value"]
    merged["optimization_note"] = (
        "MILP integer-linear optimization via scipy."
        if zone_result["optimization_method"] == "scipy_milp"
        else "Greedy priority-sorted fallback (scipy unavailable or MILP infeasible)."
    )
    if "optimization_error" in zone_result:
        merged["optimization_error"] = zone_result["optimization_error"]

    return jsonify(merged), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
