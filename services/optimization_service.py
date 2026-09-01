"""Optimization Service — MILP-based resource optimization for SAHAYAK SOS.

This module implements the zone-level optimization engine using:
- scipy.optimize.milp (integer linear programming)
- Priority-based utility function
- Distance penalty
- Greedy fallback when scipy is unavailable

The optimizer decides how many units of each resource type to allocate to each zone.
"""

import logging

from services.zone_service import (
    PROTOTYPE_ZONES,
    PROTOTYPE_RESOURCE_LOCATIONS,
    _RESOURCE_TYPES,
    calculate_distance_km,
    assign_case_to_zone,
    aggregate_cases_by_zone,
)
from services.resource_service import (
    DEFAULT_RESOURCE_INVENTORY,
    validate_resource_inventory,
    get_required_resources,
)
from services.explanation_service import generate_zone_reasoning

logger = logging.getLogger("SAHAYAK_OPTIMIZATION_SERVICE")

# Optional scipy for genuine MILP zone optimization
try:
    from scipy.optimize import milp as _scipy_milp
    from scipy.optimize import LinearConstraint as _ScipyLinearConstraint
    from scipy.optimize import Bounds as _ScipyBounds
    import numpy as _np
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


def optimize_zone_allocation(aggregated_zones, inventory):
    """
    Determine how many units of each resource type to allocate to each zone.

    Uses scipy.optimize.milp (integer linear programme) when available.
    Falls back to a priority-sorted greedy allocator otherwise.

    Decision variables  x[z, r]  =  units of resource r sent to zone z.

    Objective (maximise):
        sum_{z,r}  utility[z, r] * x[z, r]

    Constraints:
        - Inventory:  sum_z x[z, r] <= available[r]       for every r
        - Demand cap: x[z, r] <= zone_demand[z, r]         for every z, r
        - Non-negative: x[z, r] >= 0 (integer)

    Utility[z, r]:
        = zone_weight[z]  *  demand_indicator[z, r]
        - 0.08 * normalised_avg_distance[z, r]

    where zone_weight[z] is computed from priority_demand, critical/high-priority
    case counts, and medical demand — using the EXISTING priority_score values
    without recalculating them.

    Returns
    -------
    dict with keys:
        optimization_method, optimization_status, zone_allocations,
        unmet_demand, objective_value
    """
    if not isinstance(aggregated_zones, list) or not aggregated_zones:
        return {
            "optimization_method": "none",
            "optimization_status": "no_zones",
            "zone_allocations": {},
            "unmet_demand": {},
            "objective_value": 0.0,
        }

    inv = dict(DEFAULT_RESOURCE_INVENTORY)
    if isinstance(inventory, dict):
        for r in _RESOURCE_TYPES:
            if r in inventory and isinstance(inventory[r], int) and inventory[r] >= 0:
                inv[r] = inventory[r]

    Z = len(aggregated_zones)
    R = len(_RESOURCE_TYPES)

    # ── Compute zone weights ──────────────────────────────────────────────────
    max_pd = max((z["priority_demand"] for z in aggregated_zones), default=1.0) or 1.0
    max_cc = max((z["critical_cases"] for z in aggregated_zones), default=1) or 1
    max_hc = max((z["high_priority_cases"] for z in aggregated_zones), default=1) or 1
    max_med = max((z["medical_demand"] for z in aggregated_zones), default=1) or 1

    zone_weights = []
    for z in aggregated_zones:
        w = (
            0.50 * z["priority_demand"] / max_pd
            + 0.25 * z["critical_cases"] / max_cc
            + 0.15 * z["high_priority_cases"] / max_hc
            + 0.10 * z["medical_demand"] / max_med
        )
        zone_weights.append(max(w, 1e-9))  # avoid zero weights

    # ── Average straight-line distance: resource depot → zone centre ──────────
    # Used as a minor penalty in the utility (0.08 weight)
    type_to_locs = {r: [] for r in _RESOURCE_TYPES}
    for loc in PROTOTYPE_RESOURCE_LOCATIONS:
        rt = loc.get("resource_type")
        if rt in type_to_locs:
            type_to_locs[rt].append((loc["lat"], loc["lng"]))

    max_dist = 0.01  # avoid /0; will be updated below
    avg_dist = {}   # avg_dist[(z_idx, r_idx)]
    for zi, zone in enumerate(aggregated_zones):
        zc = zone.get("center", {})
        zlat = float(zc.get("lat", 20.296))
        zlng = float(zc.get("lng", 85.824))
        for ri, r in enumerate(_RESOURCE_TYPES):
            locs = type_to_locs[r]
            if locs:
                d = sum(calculate_distance_km(zlat, zlng, la, lo) for la, lo in locs) / len(locs)
            else:
                d = 0.0
            avg_dist[(zi, ri)] = d
            if d > max_dist:
                max_dist = d

    # ── Build utility matrix (Z×R flattened) ─────────────────────────────────
    # utility_flat[zi * R + ri] = utility for (zone zi, resource ri)
    utility_flat = []
    for zi, zone in enumerate(aggregated_zones):
        for ri, r in enumerate(_RESOURCE_TYPES):
            demand = zone["resource_demand"].get(r, 0)
            if demand <= 0:
                utility_flat.append(0.0)
            else:
                distance_penalty = 0.08 * (avg_dist.get((zi, ri), 0.0) / max_dist)
                utility_flat.append(max(zone_weights[zi] - distance_penalty, 0.0))

    # ── Demand cap upper bounds for each (z, r) ───────────────────────────────
    ub_demand = []
    for zi, zone in enumerate(aggregated_zones):
        for r in _RESOURCE_TYPES:
            ub_demand.append(float(zone["resource_demand"].get(r, 0)))

    # ── Try scipy MILP ────────────────────────────────────────────────────────
    opt_method = "greedy_fallback"
    opt_status = "fallback"
    x_result = None
    obj_value = 0.0

    if _SCIPY_AVAILABLE:
        try:
            n_vars = Z * R  # one integer variable per (zone, resource) pair

            # Objective: minimise -utility (scipy minimises)
            c = _np.array([-u for u in utility_flat], dtype=float)

            # Inventory constraints: sum_z x[z, r] <= available[r]
            # One row per resource type
            A_inv = _np.zeros((R, n_vars), dtype=float)
            for ri, r in enumerate(_RESOURCE_TYPES):
                for zi in range(Z):
                    A_inv[ri, zi * R + ri] = 1.0

            lb_inv = _np.full(R, -_np.inf)
            ub_inv = _np.array([float(inv[r]) for r in _RESOURCE_TYPES])

            # Demand-cap constraints: x[z, r] <= demand[z, r]
            # Encoded via variable upper bounds (Bounds)
            lb_vars = _np.zeros(n_vars)
            ub_vars = _np.array(ub_demand, dtype=float)

            constraints = _ScipyLinearConstraint(A_inv, lb_inv, ub_inv)
            bounds = _ScipyBounds(lb_vars, ub_vars)
            integrality = _np.ones(n_vars)  # all integer

            res = _scipy_milp(
                c=c,
                constraints=constraints,
                integrality=integrality,
                bounds=bounds,
            )

            if res.success:
                x_result = [max(0, round(float(v))) for v in res.x]
                obj_value = round(-float(res.fun), 4)
                opt_method = "scipy_milp"
                opt_status = "optimal"
            else:
                logger.warning("scipy MILP did not find optimal; using greedy fallback.")
        except Exception as e:
            logger.warning(f"MILP optimization error ({e}); using greedy fallback.")

    # ── Greedy fallback (priority-sorted, inventory-respecting) ──────────────
    if x_result is None:
        inv_remaining = dict(inv)
        x_result = [0] * (Z * R)

        # Build (priority_demand, zone_idx, resource_idx) priority queue
        items = []
        for zi, zone in enumerate(aggregated_zones):
            for ri, r in enumerate(_RESOURCE_TYPES):
                demand = int(zone["resource_demand"].get(r, 0))
                if demand > 0 and utility_flat[zi * R + ri] > 0:
                    items.append((-zone_weights[zi], zi, ri, demand))
        items.sort()  # sorted by descending zone_weight then zone/resource order

        for _, zi, ri, demand in items:
            r = _RESOURCE_TYPES[ri]
            allocatable = min(demand, inv_remaining[r])
            x_result[zi * R + ri] = allocatable
            inv_remaining[r] -= allocatable
            obj_value += allocatable * utility_flat[zi * R + ri]

        obj_value = round(obj_value, 4)
        opt_method = "greedy_fallback"
        opt_status = "fallback_ok"

    # ── Build structured output ───────────────────────────────────────────────
    zone_allocations = {}
    unmet_demand = {}
    for zi, zone in enumerate(aggregated_zones):
        zid = zone["zone_id"]
        alloc = {}
        unmet = {}
        for ri, r in enumerate(_RESOURCE_TYPES):
            allocated = int(x_result[zi * R + ri])
            demanded = int(zone["resource_demand"].get(r, 0))
            if demanded > 0:
                alloc[r] = allocated
                shortfall = max(0, demanded - allocated)
                if shortfall > 0:
                    unmet[r] = shortfall
        zone_allocations[zid] = alloc
        unmet_demand[zid] = unmet

    return {
        "optimization_method": opt_method,
        "optimization_status": opt_status,
        "zone_allocations": zone_allocations,
        "unmet_demand": unmet_demand,
        "objective_value": obj_value,
    }


def assign_resource_units_to_zones(zone_allocations, zones, inventory):
    """
    Given zone-level counts (from the MILP), assign specific resource unit IDs
    to zones by picking the closest available prototype resource to each zone
    centre (nearest-first greedy).

    Returns list of assignment dicts:
        {resource_id, resource_type, zone_id, distance_km, reason}
    """
    assignments = []
    # Working copy — mark each prototype location as available or not
    available_units = {r: [] for r in _RESOURCE_TYPES}
    for loc in PROTOTYPE_RESOURCE_LOCATIONS:
        rt = loc.get("resource_type")
        if rt in available_units and loc.get("available", True):
            available_units[rt].append(dict(loc))

    zone_center_map = {z["zone_id"]: z.get("center", {}) for z in zones}

    # Process zones in order of their appearance in zone_allocations (already priority-sorted)
    for zid, alloc in zone_allocations.items():
        zc = zone_center_map.get(zid, {})
        zlat = float(zc.get("lat", 20.296))
        zlng = float(zc.get("lng", 85.824))

        for r, count in alloc.items():
            if not isinstance(count, int) or count <= 0:
                continue
            # Sort available units of this type by distance to zone centre
            candidates = available_units.get(r, [])
            candidates_with_dist = []
            for unit in candidates:
                d = calculate_distance_km(zlat, zlng, unit["lat"], unit["lng"])
                candidates_with_dist.append((d, unit))
            candidates_with_dist.sort(key=lambda x: x[0])

            assigned = 0
            for d, unit in candidates_with_dist:
                if assigned < count:
                    assignments.append({
                        "resource_id": unit["resource_id"],
                        "resource_type": r,
                        "zone_id": zid,
                        "distance_km": d,
                        "reason": (
                            f"{unit['resource_id']} assigned to {zid}: "
                            f"nearest available {r.upper()} unit "
                            f"({d:.2f} km straight-line)."
                        ),
                    })
                    assigned += 1

            # Keep the un-selected units for subsequent zones
            available_units[r] = [u for d, u in candidates_with_dist[assigned:]]

    return assignments


def run_zone_optimization(cases, custom_inventory=None):
    """
    Full Phase 3A orchestration:

        1. Validate inventory.
        2. Aggregate cases into zones (nearest-centroid, deterministic).
        3. Run MILP optimization (scipy) or greedy fallback.
        4. Assign specific resource units to zones (nearest-first).
        5. Generate per-zone reasoning.
        6. Return a complete, transparent result dict.

    Never raises.  Returns optimization_status="error" on unexpected failure.
    """
    try:
        # Resolve inventory
        if custom_inventory is not None and validate_resource_inventory(custom_inventory):
            inventory = dict(custom_inventory)
        else:
            inventory = dict(DEFAULT_RESOURCE_INVENTORY)

        inventory_before = dict(inventory)

        # Aggregate zones
        zones = PROTOTYPE_ZONES
        aggregated = aggregate_cases_by_zone(cases, zones)

        # Optimize
        opt_result = optimize_zone_allocation(aggregated, inventory)
        zone_allocations = opt_result["zone_allocations"]
        unmet_demand = opt_result["unmet_demand"]

        # Compute remaining inventory after zone-level allocation
        inventory_after = dict(inventory)
        for zid, alloc in zone_allocations.items():
            for r, qty in alloc.items():
                if r in inventory_after and isinstance(qty, int):
                    inventory_after[r] = max(0, inventory_after[r] - qty)

        # Assign specific resource unit IDs
        assignments = assign_resource_units_to_zones(zone_allocations, zones, inventory)

        # Build per-zone output with reasoning
        zone_summaries = []
        for zone in aggregated:
            zid = zone["zone_id"]
            alloc = zone_allocations.get(zid, {})
            unmet = unmet_demand.get(zid, {})
            reasoning = generate_zone_reasoning(zone, alloc, unmet, inventory_before, inventory_after)

            total_alloc = sum(v for v in alloc.values() if isinstance(v, int))
            alloc_score = round(zone.get("priority_demand", 0) * (total_alloc / max(total_alloc + sum(unmet.values()), 1)), 2)

            zone_summaries.append({
                "zone_id": zid,
                "name": zone.get("name", zid),
                "case_count": zone["case_count"],
                "critical_cases": zone["critical_cases"],
                "high_priority_cases": zone["high_priority_cases"],
                "priority_demand": zone["priority_demand"],
                "medical_demand": zone["medical_demand"],
                "resource_demand": zone["resource_demand"],
                "allocation": alloc,
                "unmet_demand": unmet,
                "allocation_score": alloc_score,
                "reason": reasoning["explanation"],
                "reason_codes": reasoning["reason_codes"],
            })

        return {
            "optimization_method": opt_result["optimization_method"],
            "optimization_status": opt_result["optimization_status"],
            "inventory_before": inventory_before,
            "inventory_after": inventory_after,
            "zones": zone_summaries,
            "assignments": assignments,
            "objective_value": opt_result["objective_value"],
            "zone_summary": {
                "total_zones": len(aggregated),
                "zones_with_cases": sum(1 for z in aggregated if z["case_count"] > 0),
                "zones_fully_met": sum(
                    1 for z in aggregated
                    if z["case_count"] > 0 and not unmet_demand.get(z["zone_id"])
                ),
                "total_cases": sum(z["case_count"] for z in aggregated),
            },
        }

    except Exception as exc:
        logger.error(f"Zone optimization error: {exc}")
        return {
            "optimization_method": "none",
            "optimization_status": "error",
            "optimization_error": str(exc),
            "inventory_before": dict(custom_inventory) if isinstance(custom_inventory, dict) else dict(DEFAULT_RESOURCE_INVENTORY),
            "inventory_after": {},
            "zones": [],
            "assignments": [],
            "zone_summary": {},
            "objective_value": 0.0,
        }
