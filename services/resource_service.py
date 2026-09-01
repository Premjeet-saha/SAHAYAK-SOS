"""Resource Service — Resource requirements and allocation for SAHAYAK SOS.

This module handles:
- Default resource inventory
- Resource requirement determination based on incident characteristics
- Case-level resource allocation
- Resource inventory validation

Default inventory:
- NDRF: 8
- Ambulance: 21
- Boat: 12
- Shelter: 6
- Hospital: 9
- Fire: 6
"""

# Default resource inventory
DEFAULT_RESOURCE_INVENTORY = {
    "ndrf": 8,
    "ambulance": 21,
    "boat": 12,
    "shelter": 6,
    "hospital": 9,
    "fire": 6
}


def validate_resource_inventory(inventory):
    """Validate resource inventory structure and values."""
    if not isinstance(inventory, dict):
        return False

    required_keys = {"ndrf", "ambulance", "boat", "shelter", "hospital", "fire"}
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
    structured_incident = case.get("structured_incident", {})

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

    # FIRE / INDUSTRIAL - Fire tender units required
    if "Fire" in incident_type or "Gas" in incident_type or "Cylinder" in incident_type:
        required.append("fire")
        # NDRF also responds to major fires for rescue operations
        if "Fire" in incident_type:
            required.append("ndrf")
        # Ambulance/hospital if medical signals exist
        if medical_emergency == "YES" and detected_medical_signals:
            required.append("ambulance")
            required.append("hospital")

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

    # ROAD ACCIDENT / COLLISION
    if "Collision" in incident_type or "Accident" in incident_type or "Crash" in incident_type or "Derailment" in incident_type:
        if medical_emergency == "YES" and detected_medical_signals:
            required.append("ambulance")
            required.append("hospital")

    # STRUCTURED INCIDENT: Fire flag explicitly set
    if structured_incident and structured_incident.get("fire") == True:
        if "fire" not in required:
            required.append("fire")

    # STRUCTURED INCIDENT: Flood depth > 0
    flood_depth = structured_incident.get("flood_depth_m", 0)
    if isinstance(flood_depth, (int, float)) and flood_depth > 0:
        if "ndrf" not in required:
            required.append("ndrf")
        if flood_depth > 1.5 and "boat" not in required:
            required.append("boat")

    # STRUCTURED INCIDENT: Trapped persons need NDRF
    if structured_incident and structured_incident.get("trapped") == True:
        if "ndrf" not in required:
            required.append("ndrf")

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
