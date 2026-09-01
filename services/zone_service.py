"""Zone Service — Geographic zone management for SAHAYAK SOS.

This module handles:
- Prototype zone definitions
- Prototype resource locations
- Haversine distance calculation
- Zone assignment (nearest-centroid)
- Zone aggregation and statistics

IMPORTANT: All resource locations and zones are PROTOTYPE/DEMO data.
They are NOT real government/emergency-service infrastructure.
"""

import math
from services.resource_service import DEFAULT_RESOURCE_INVENTORY

# Resource type list (order is consistent throughout)
_RESOURCE_TYPES = ["ndrf", "ambulance", "boat", "shelter", "hospital", "fire"]

# Prototype zone definitions
# Centered on the Bhubaneswar demo GPS area
PROTOTYPE_ZONES = [
    {
        "zone_id": "ZONE-A",
        "name": "North Zone",
        "center": {"lat": 20.360, "lng": 85.820},
        "location_type": "prototype"
    },
    {
        "zone_id": "ZONE-B",
        "name": "South Zone",
        "center": {"lat": 20.230, "lng": 85.820},
        "location_type": "prototype"
    },
    {
        "zone_id": "ZONE-C",
        "name": "East Zone",
        "center": {"lat": 20.296, "lng": 85.900},
        "location_type": "prototype"
    },
    {
        "zone_id": "ZONE-D",
        "name": "West Zone",
        "center": {"lat": 20.296, "lng": 85.750},
        "location_type": "prototype"
    },
]

# Prototype resource locations (56 units total = default inventory)
# Spread across the four zones to create meaningful distance variation.
PROTOTYPE_RESOURCE_LOCATIONS = [
    # --- NDRF teams (8) ---
    {"resource_id": "NDRF-01", "resource_type": "ndrf", "lat": 20.355, "lng": 85.818, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-02", "resource_type": "ndrf", "lat": 20.372, "lng": 85.832, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-03", "resource_type": "ndrf", "lat": 20.237, "lng": 85.812, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-04", "resource_type": "ndrf", "lat": 20.221, "lng": 85.834, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-05", "resource_type": "ndrf", "lat": 20.298, "lng": 85.892, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-06", "resource_type": "ndrf", "lat": 20.281, "lng": 85.908, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-07", "resource_type": "ndrf", "lat": 20.310, "lng": 85.758, "available": True, "location_type": "prototype"},
    {"resource_id": "NDRF-08", "resource_type": "ndrf", "lat": 20.274, "lng": 85.742, "available": True, "location_type": "prototype"},
    # --- Ambulances (21) ---
    {"resource_id": "AMB-01", "resource_type": "ambulance", "lat": 20.358, "lng": 85.815, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-02", "resource_type": "ambulance", "lat": 20.362, "lng": 85.824, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-03", "resource_type": "ambulance", "lat": 20.368, "lng": 85.812, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-04", "resource_type": "ambulance", "lat": 20.375, "lng": 85.828, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-05", "resource_type": "ambulance", "lat": 20.352, "lng": 85.835, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-06", "resource_type": "ambulance", "lat": 20.345, "lng": 85.820, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-07", "resource_type": "ambulance", "lat": 20.235, "lng": 85.817, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-08", "resource_type": "ambulance", "lat": 20.222, "lng": 85.825, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-09", "resource_type": "ambulance", "lat": 20.240, "lng": 85.808, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-10", "resource_type": "ambulance", "lat": 20.228, "lng": 85.838, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-11", "resource_type": "ambulance", "lat": 20.218, "lng": 85.812, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-12", "resource_type": "ambulance", "lat": 20.295, "lng": 85.895, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-13", "resource_type": "ambulance", "lat": 20.302, "lng": 85.905, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-14", "resource_type": "ambulance", "lat": 20.288, "lng": 85.910, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-15", "resource_type": "ambulance", "lat": 20.310, "lng": 85.898, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-16", "resource_type": "ambulance", "lat": 20.280, "lng": 85.888, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-17", "resource_type": "ambulance", "lat": 20.300, "lng": 85.755, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-18", "resource_type": "ambulance", "lat": 20.292, "lng": 85.745, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-19", "resource_type": "ambulance", "lat": 20.312, "lng": 85.760, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-20", "resource_type": "ambulance", "lat": 20.285, "lng": 85.750, "available": True, "location_type": "prototype"},
    {"resource_id": "AMB-21", "resource_type": "ambulance", "lat": 20.305, "lng": 85.742, "available": True, "location_type": "prototype"},
    # --- Boats (12) ---
    {"resource_id": "BOAT-01", "resource_type": "boat", "lat": 20.358, "lng": 85.825, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-02", "resource_type": "boat", "lat": 20.365, "lng": 85.818, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-03", "resource_type": "boat", "lat": 20.350, "lng": 85.830, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-04", "resource_type": "boat", "lat": 20.228, "lng": 85.820, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-05", "resource_type": "boat", "lat": 20.235, "lng": 85.826, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-06", "resource_type": "boat", "lat": 20.222, "lng": 85.815, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-07", "resource_type": "boat", "lat": 20.292, "lng": 85.898, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-08", "resource_type": "boat", "lat": 20.300, "lng": 85.905, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-09", "resource_type": "boat", "lat": 20.285, "lng": 85.892, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-10", "resource_type": "boat", "lat": 20.302, "lng": 85.748, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-11", "resource_type": "boat", "lat": 20.290, "lng": 85.758, "available": True, "location_type": "prototype"},
    {"resource_id": "BOAT-12", "resource_type": "boat", "lat": 20.315, "lng": 85.752, "available": True, "location_type": "prototype"},
    # --- Shelters (6) ---
    {"resource_id": "SHE-01", "resource_type": "shelter", "lat": 20.362, "lng": 85.820, "available": True, "location_type": "prototype"},
    {"resource_id": "SHE-02", "resource_type": "shelter", "lat": 20.350, "lng": 85.815, "available": True, "location_type": "prototype"},
    {"resource_id": "SHE-03", "resource_type": "shelter", "lat": 20.235, "lng": 85.820, "available": True, "location_type": "prototype"},
    {"resource_id": "SHE-04", "resource_type": "shelter", "lat": 20.224, "lng": 85.828, "available": True, "location_type": "prototype"},
    {"resource_id": "SHE-05", "resource_type": "shelter", "lat": 20.298, "lng": 85.898, "available": True, "location_type": "prototype"},
    {"resource_id": "SHE-06", "resource_type": "shelter", "lat": 20.300, "lng": 85.752, "available": True, "location_type": "prototype"},
    # --- Hospitals (9) ---
    {"resource_id": "HOSP-01", "resource_type": "hospital", "lat": 20.360, "lng": 85.822, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-02", "resource_type": "hospital", "lat": 20.368, "lng": 85.815, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-03", "resource_type": "hospital", "lat": 20.352, "lng": 85.830, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-04", "resource_type": "hospital", "lat": 20.228, "lng": 85.818, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-05", "resource_type": "hospital", "lat": 20.238, "lng": 85.825, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-06", "resource_type": "hospital", "lat": 20.295, "lng": 85.900, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-07", "resource_type": "hospital", "lat": 20.285, "lng": 85.895, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-08", "resource_type": "hospital", "lat": 20.305, "lng": 85.755, "available": True, "location_type": "prototype"},
    {"resource_id": "HOSP-09", "resource_type": "hospital", "lat": 20.290, "lng": 85.745, "available": True, "location_type": "prototype"},
    # --- Fire Tenders (6) ---
    {"resource_id": "FIRE-01", "resource_type": "fire", "lat": 20.356, "lng": 85.820, "available": True, "location_type": "prototype"},
    {"resource_id": "FIRE-02", "resource_type": "fire", "lat": 20.365, "lng": 85.828, "available": True, "location_type": "prototype"},
    {"resource_id": "FIRE-03", "resource_type": "fire", "lat": 20.232, "lng": 85.815, "available": True, "location_type": "prototype"},
    {"resource_id": "FIRE-04", "resource_type": "fire", "lat": 20.225, "lng": 85.830, "available": True, "location_type": "prototype"},
    {"resource_id": "FIRE-05", "resource_type": "fire", "lat": 20.296, "lng": 85.895, "available": True, "location_type": "prototype"},
    {"resource_id": "FIRE-06", "resource_type": "fire", "lat": 20.298, "lng": 85.750, "available": True, "location_type": "prototype"},
]


def calculate_distance_km(lat1, lng1, lat2, lng2):
    """
    Compute the straight-line (great-circle) distance between two WGS-84
    coordinates in kilometres using the Haversine formula.

    This is NOT travel time or road distance.
    Returns float >= 0.0.  Returns 0.0 if any coordinate is invalid.
    """
    try:
        R = 6371.0  # Earth radius in km
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        dphi = math.radians(float(lat2) - float(lat1))
        dlam = math.radians(float(lng2) - float(lng1))
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return round(R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a)))), 4)
    except (TypeError, ValueError):
        return 0.0


def assign_case_to_zone(case, zones=None):
    """
    Assign a case dict to the nearest prototype zone (nearest centroid by
    Haversine distance).  Returns the zone_id string.

    Deterministic: identical (lat, lng) always returns the same zone_id.
    Falls back to the first zone if coordinates are missing/invalid.
    """
    if zones is None:
        zones = PROTOTYPE_ZONES
    if not zones:
        return "ZONE-UNKNOWN"

    try:
        lat = float(case.get("lat", case.get("location", {}).get("lat", 20.296)))
        lng = float(case.get("lng", case.get("location", {}).get("lng", 85.824)))
    except (TypeError, ValueError):
        lat, lng = 20.296, 85.824  # demo fallback

    best_zone_id = zones[0]["zone_id"]
    best_dist = float("inf")
    for zone in zones:
        try:
            zc = zone["center"]
            d = calculate_distance_km(lat, lng, float(zc["lat"]), float(zc["lng"]))
        except (KeyError, TypeError, ValueError):
            d = float("inf")
        if d < best_dist:
            best_dist = d
            best_zone_id = zone["zone_id"]
    return best_zone_id


def aggregate_cases_by_zone(cases, zones=None):
    """
    Group a list of case dicts by zone and compute per-zone statistics.

    Uses existing priority_score and get_required_resources() — does NOT
    recalculate priority or introduce a competing formula.

    Returns a list of zone summary dicts ordered by descending priority_demand.
    """
    if zones is None:
        zones = PROTOTYPE_ZONES

    # Import here to avoid circular import
    from services.resource_service import get_required_resources

    # Build empty zone buckets
    zone_map = {}
    for zone in zones:
        zid = zone["zone_id"]
        zone_map[zid] = {
            "zone_id": zid,
            "name": zone.get("name", zid),
            "center": zone.get("center", {}),
            "location_type": zone.get("location_type", "prototype"),
            "cases": [],
            "case_count": 0,
            "critical_cases": 0,
            "high_priority_cases": 0,
            "priority_demand": 0.0,
            "medical_demand": 0,
            "resource_demand": {r: 0 for r in _RESOURCE_TYPES},
        }

    # Assign cases and accumulate stats
    for case in cases:
        if not isinstance(case, dict):
            continue
        zid = assign_case_to_zone(case, zones)
        if zid not in zone_map:
            # Safety: if zone not in map (edge case), use first zone
            zid = zones[0]["zone_id"] if zones else "ZONE-UNKNOWN"
            if zid not in zone_map:
                continue

        bucket = zone_map[zid]
        bucket["cases"].append(case.get("incident_id", "UNKNOWN"))
        bucket["case_count"] += 1

        score = float(case.get("priority_score", 0))
        bucket["priority_demand"] = round(bucket["priority_demand"] + score, 2)

        hazard = case.get("hazard_level", "")
        if hazard == "CRITICAL":
            bucket["critical_cases"] += 1
        elif score >= 60:
            bucket["high_priority_cases"] += 1

        if case.get("medical_emergency", "NO") == "YES":
            bucket["medical_demand"] += 1

        # Aggregate resource demand using existing rules
        try:
            req = get_required_resources(case)
        except Exception:
            req = []
        for r in req:
            if r in bucket["resource_demand"]:
                bucket["resource_demand"][r] += 1

    result = list(zone_map.values())
    result.sort(key=lambda z: -z["priority_demand"])
    return result
