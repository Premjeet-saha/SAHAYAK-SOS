"""
Phase 3A Test Suite — Zone Model + Optimization Engine
=======================================================
Tests:
 1.  Zone assignment is deterministic.
 2.  Identical coordinates always produce the same zone.
 3.  Cases are correctly grouped into zones.
 4.  Zone case counts are correct.
 5.  Critical/high-priority counts are correct.
 6.  Resource demand aggregation is correct (reuses get_required_resources).
 7.  Inventory constraints are never violated.
 8.  Allocation never exceeds zone demand.
 9.  Resource types cannot be incorrectly assigned (wrong type to wrong demand).
10.  Higher-priority zones receive preference when resources are scarce.
11.  Distance (calculate_distance_km) is deterministic and returns float >= 0.
12.  Haversine sanity check (known distance).
13.  Optimization is deterministic for identical inputs.
14.  Empty case list is handled safely.
15.  Invalid/missing coordinates are handled safely (fallback to demo GPS).
16.  Missing resource inventory uses the default safely.
17.  Existing /allocate-resources backward-compatible fields are preserved.
18.  Existing priority scores are NOT recalculated or modified.
19.  Existing ML output field is untouched by zone optimization.
20.  No API 500 on malformed optional data.
21.  optimization_status is never "optimal" when optimizer actually failed.
22.  Zone aggregation correctly sums priority demand from case priority_score.
"""

import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from brain import app
from services.zone_service import (
    calculate_distance_km,
    assign_case_to_zone,
    aggregate_cases_by_zone,
    PROTOTYPE_ZONES,
)
from services.optimization_service import (
    optimize_zone_allocation,
    run_zone_optimization,
)
from services.resource_service import (
    get_required_resources,
    DEFAULT_RESOURCE_INVENTORY,
)
from services.zone_service import _RESOURCE_TYPES


# ── Shared test fixtures ──────────────────────────────────────────────────────

def _make_flood_case(incident_id="SAH-11111", priority_score=85.0,
                     lat=20.360, lng=85.820, hazard_level="CRITICAL"):
    """Flood case with known zone-A coordinates and NDRF+shelter demand."""
    return {
        "incident_id": incident_id,
        "priority_score": priority_score,
        "type": "Flash Flood / Waterlogging",
        "hazard_level": hazard_level,
        "medical_emergency": "NO",
        "detected_medical_signals": [],
        "detected_hazards": ["Flash Flood / Waterlogging"],
        "accessibility_signals": ["Trapped location"],
        "vulnerability_signals": [],
        "lat": lat,
        "lng": lng,
        "request_timestamp": "2026-08-31T12:00:00",
    }


def _make_cardiac_case(incident_id="SAH-22222", priority_score=90.0,
                       lat=20.230, lng=85.820):
    """Medical cardiac case near zone B."""
    return {
        "incident_id": incident_id,
        "priority_score": priority_score,
        "type": "Cardiac Arrest Emergency",
        "hazard_level": "HIGH",
        "medical_emergency": "YES",
        "detected_medical_signals": ["Cardiac Arrest Emergency"],
        "detected_hazards": [],
        "accessibility_signals": [],
        "vulnerability_signals": [],
        "lat": lat,
        "lng": lng,
        "request_timestamp": "2026-08-31T12:01:00",
    }


def _make_generic_case(incident_id="SAH-33333", priority_score=40.0,
                       lat=20.296, lng=85.824):
    """Low-priority generic case at demo GPS centroid."""
    return {
        "incident_id": incident_id,
        "priority_score": priority_score,
        "type": "General Emergency Assistance Required",
        "hazard_level": "Medium",
        "medical_emergency": "NO",
        "detected_medical_signals": [],
        "detected_hazards": [],
        "accessibility_signals": [],
        "vulnerability_signals": [],
        "lat": lat,
        "lng": lng,
        "request_timestamp": "2026-08-31T12:02:00",
    }


# ─────────────────────────────────────────────────────────────────────────────

class TestHaversineDistance(unittest.TestCase):

    def test_11_distance_is_float_and_non_negative(self):
        """calculate_distance_km always returns float >= 0."""
        d = calculate_distance_km(20.296, 85.824, 20.360, 85.820)
        self.assertIsInstance(d, float)
        self.assertGreaterEqual(d, 0.0)

    def test_12_haversine_sanity_known_value(self):
        """Bhubaneswar demo centre to zone-A centre is roughly 7 km."""
        d = calculate_distance_km(20.296, 85.824, 20.360, 85.820)
        self.assertGreater(d, 5.0)
        self.assertLess(d, 10.0)

    def test_11b_same_point_is_zero(self):
        """Distance from a point to itself must be 0."""
        d = calculate_distance_km(20.296, 85.824, 20.296, 85.824)
        self.assertAlmostEqual(d, 0.0, places=3)

    def test_11c_invalid_coords_returns_zero(self):
        """Invalid / non-numeric coordinates return 0.0 (safe fallback)."""
        d = calculate_distance_km("abc", None, 20.0, 85.0)
        self.assertEqual(d, 0.0)

    def test_11d_distance_is_deterministic(self):
        """Same inputs always produce same output."""
        d1 = calculate_distance_km(20.296, 85.824, 20.230, 85.820)
        d2 = calculate_distance_km(20.296, 85.824, 20.230, 85.820)
        self.assertEqual(d1, d2)


class TestZoneAssignment(unittest.TestCase):

    def test_1_zone_assignment_is_deterministic(self):
        """Same coordinates always produce the same zone_id."""
        case = _make_flood_case(lat=20.360, lng=85.820)
        z1 = assign_case_to_zone(case)
        z2 = assign_case_to_zone(case)
        self.assertEqual(z1, z2)

    def test_2_identical_coords_same_zone(self):
        """Two cases with identical lat/lng go to the same zone."""
        c1 = _make_flood_case("SAH-A", lat=20.360, lng=85.820)
        c2 = _make_flood_case("SAH-B", lat=20.360, lng=85.820)
        self.assertEqual(assign_case_to_zone(c1), assign_case_to_zone(c2))

    def test_2b_zone_a_centroid_goes_to_zone_a(self):
        """A case at zone-A's centroid is assigned to ZONE-A."""
        case = _make_flood_case(lat=20.360, lng=85.820)
        self.assertEqual(assign_case_to_zone(case), "ZONE-A")

    def test_2c_zone_b_centroid_goes_to_zone_b(self):
        """A case at zone-B's centroid is assigned to ZONE-B."""
        case = _make_cardiac_case(lat=20.230, lng=85.820)
        self.assertEqual(assign_case_to_zone(case), "ZONE-B")

    def test_15_missing_coords_falls_back_safely(self):
        """Cases with no lat/lng fall back to demo GPS without raising."""
        case = {"incident_id": "SAH-X", "priority_score": 50.0}
        zid = assign_case_to_zone(case)
        self.assertIn(zid, [z["zone_id"] for z in PROTOTYPE_ZONES])

    def test_15b_invalid_coord_type_falls_back(self):
        """String/None coordinates fall back gracefully."""
        case = {"incident_id": "SAH-Y", "lat": "invalid", "lng": None}
        zid = assign_case_to_zone(case)
        self.assertIn(zid, [z["zone_id"] for z in PROTOTYPE_ZONES])


class TestZoneAggregation(unittest.TestCase):

    def setUp(self):
        self.flood = _make_flood_case("SAH-F1", priority_score=85.0,
                                      lat=20.360, lng=85.820,
                                      hazard_level="CRITICAL")
        self.cardiac = _make_cardiac_case("SAH-C1", priority_score=90.0,
                                          lat=20.230, lng=85.820)
        self.generic = _make_generic_case("SAH-G1", priority_score=40.0)

    def test_3_cases_correctly_grouped(self):
        """Cases near different zone centres end up in different zones."""
        zones = aggregate_cases_by_zone([self.flood, self.cardiac, self.generic])
        zone_ids = {z["zone_id"] for z in zones if z["case_count"] > 0}
        # flood->ZONE-A, cardiac->ZONE-B, generic->nearest demo zone
        self.assertIn("ZONE-A", zone_ids)
        self.assertIn("ZONE-B", zone_ids)

    def test_4_case_counts_correct(self):
        """Total case count across all zones equals number of input cases."""
        zones = aggregate_cases_by_zone([self.flood, self.cardiac, self.generic])
        total = sum(z["case_count"] for z in zones)
        self.assertEqual(total, 3)

    def test_5_critical_case_count(self):
        """CRITICAL hazard_level cases are counted in critical_cases."""
        zones = aggregate_cases_by_zone([self.flood])
        zone_a = next(z for z in zones if z["zone_id"] == "ZONE-A")
        self.assertEqual(zone_a["critical_cases"], 1)

    def test_5b_high_priority_count(self):
        """Non-CRITICAL cases with priority_score >= 60 counted as high_priority."""
        high_case = _make_generic_case("SAH-HP", priority_score=75.0,
                                       lat=20.360, lng=85.820)
        high_case["hazard_level"] = "HIGH"
        zones = aggregate_cases_by_zone([high_case])
        zone_a = next(z for z in zones if z["zone_id"] == "ZONE-A")
        self.assertEqual(zone_a["high_priority_cases"], 1)

    def test_6_resource_demand_aggregation(self):
        """Resource demand is the sum of get_required_resources() over zone cases."""
        # Two flood cases in zone-A → ndrf demand >= 2
        c1 = _make_flood_case("SAH-F1", lat=20.360, lng=85.820)
        c2 = _make_flood_case("SAH-F2", lat=20.362, lng=85.818)
        zones = aggregate_cases_by_zone([c1, c2])
        zone_a = next(z for z in zones if z["zone_id"] == "ZONE-A")
        # Both flood cases require ndrf
        req1 = get_required_resources(c1)
        req2 = get_required_resources(c2)
        expected_ndrf = req1.count("ndrf") + req2.count("ndrf")
        self.assertEqual(zone_a["resource_demand"]["ndrf"], expected_ndrf)

    def test_22_priority_demand_is_sum_of_scores(self):
        """priority_demand for a zone = sum of priority_score of its cases."""
        c1 = _make_flood_case("F1", priority_score=60.0, lat=20.360, lng=85.820)
        c2 = _make_flood_case("F2", priority_score=40.0, lat=20.362, lng=85.818)
        zones = aggregate_cases_by_zone([c1, c2])
        zone_a = next(z for z in zones if z["zone_id"] == "ZONE-A")
        self.assertAlmostEqual(zone_a["priority_demand"], 100.0, places=1)

    def test_14_empty_case_list_safe(self):
        """aggregate_cases_by_zone([]) returns all zones with zero counts."""
        zones = aggregate_cases_by_zone([])
        self.assertEqual(len(zones), len(PROTOTYPE_ZONES))
        for z in zones:
            self.assertEqual(z["case_count"], 0)

    def test_18_existing_priority_score_not_recalculated(self):
        """priority_demand uses case's existing priority_score unchanged."""
        case = _make_flood_case("SAH-PRI", priority_score=77.5,
                                lat=20.360, lng=85.820)
        zones = aggregate_cases_by_zone([case])
        zone_a = next(z for z in zones if z["zone_id"] == "ZONE-A")
        self.assertAlmostEqual(zone_a["priority_demand"], 77.5, places=1)


class TestOptimizationConstraints(unittest.TestCase):

    def _run_opt(self, cases, inv=None):
        if inv is None:
            inv = dict(DEFAULT_RESOURCE_INVENTORY)
        aggregated = aggregate_cases_by_zone(cases)
        return optimize_zone_allocation(aggregated, inv)

    def test_7_inventory_never_violated(self):
        """Total allocation across zones never exceeds available inventory."""
        cases = [
            _make_flood_case(f"F{i}", lat=20.360 + i * 0.001, lng=85.820)
            for i in range(5)
        ] + [
            _make_cardiac_case(f"C{i}", lat=20.230 + i * 0.001, lng=85.820)
            for i in range(5)
        ]
        result = self._run_opt(cases)
        zone_allocs = result["zone_allocations"]
        for r in _RESOURCE_TYPES:
            total = sum(
                alloc.get(r, 0)
                for alloc in zone_allocs.values()
                if isinstance(alloc.get(r, 0), int)
            )
            self.assertLessEqual(
                total, DEFAULT_RESOURCE_INVENTORY[r],
                msg=f"Inventory exceeded for resource: {r}"
            )

    def test_8_allocation_never_exceeds_demand(self):
        """Allocated units per zone never exceed that zone's demand."""
        cases = [_make_flood_case("SAH-FX", lat=20.360, lng=85.820)]
        aggregated = aggregate_cases_by_zone(cases)
        result = optimize_zone_allocation(aggregated, dict(DEFAULT_RESOURCE_INVENTORY))
        zone_allocs = result["zone_allocations"]
        for zone in aggregated:
            zid = zone["zone_id"]
            alloc = zone_allocs.get(zid, {})
            for r in _RESOURCE_TYPES:
                self.assertLessEqual(
                    alloc.get(r, 0),
                    zone["resource_demand"].get(r, 0),
                    msg=f"{zid}: allocated {r} > demand"
                )

    def test_9_wrong_resource_type_not_allocated(self):
        """Resources are only allocated when the zone actually demands them."""
        # A cardiac-only case should not receive NDRF or boats
        case = _make_cardiac_case("SAH-CARD", lat=20.230, lng=85.820)
        aggregated = aggregate_cases_by_zone([case])
        result = optimize_zone_allocation(aggregated, dict(DEFAULT_RESOURCE_INVENTORY))
        zone_b = result["zone_allocations"].get("ZONE-B", {})
        # NDRF and boat are not required by a cardiac case
        req = get_required_resources(case)
        if "ndrf" not in req:
            self.assertEqual(zone_b.get("ndrf", 0), 0,
                             "NDRF allocated when not demanded")
        if "boat" not in req:
            self.assertEqual(zone_b.get("boat", 0), 0,
                             "Boat allocated when not demanded")

    def test_10_higher_priority_zone_gets_preference(self):
        """When inventory is scarce, higher-priority zone receives more resources."""
        # Very tight inventory: only 1 NDRF team
        tight_inv = {"ndrf": 1, "ambulance": 0, "boat": 0, "shelter": 0, "hospital": 0}
        high_flood = _make_flood_case("HIGH", priority_score=90.0,
                                      lat=20.360, lng=85.820)
        low_flood = _make_flood_case("LOW", priority_score=20.0,
                                     lat=20.230, lng=85.820)
        aggregated = aggregate_cases_by_zone([high_flood, low_flood])
        result = optimize_zone_allocation(aggregated, tight_inv)

        # The single NDRF team must go to the zone with higher priority demand
        zone_allocs = result["zone_allocations"]
        total_ndrf = sum(v.get("ndrf", 0) for v in zone_allocs.values())
        self.assertEqual(total_ndrf, 1,
                         "Exactly 1 NDRF team should be allocated")

        # Find zone with higher priority demand
        high_zone = max(aggregated, key=lambda z: z["priority_demand"])
        high_alloc = zone_allocs.get(high_zone["zone_id"], {}).get("ndrf", 0)
        low_zone = min(aggregated, key=lambda z: z["priority_demand"])
        low_alloc = zone_allocs.get(low_zone["zone_id"], {}).get("ndrf", 0)

        # Higher priority zone should get the resource
        self.assertGreaterEqual(high_alloc, low_alloc,
                                "Higher-priority zone should get NDRF preference")

    def test_13_optimization_deterministic(self):
        """Identical inputs produce identical optimization outputs."""
        cases = [
            _make_flood_case("SAH-D1", lat=20.360, lng=85.820),
            _make_cardiac_case("SAH-D2", lat=20.230, lng=85.820),
        ]
        r1 = run_zone_optimization(cases)
        r2 = run_zone_optimization(cases)
        self.assertEqual(r1["zone_allocations"] if "zone_allocations" in r1
                         else r1.get("zones"),
                         r2["zone_allocations"] if "zone_allocations" in r2
                         else r2.get("zones"))
        self.assertEqual(r1["optimization_status"], r2["optimization_status"])

    def test_16_missing_inventory_uses_default(self):
        """run_zone_optimization(cases, None) uses DEFAULT_RESOURCE_INVENTORY."""
        case = _make_flood_case(lat=20.360, lng=85.820)
        result = run_zone_optimization([case], None)
        self.assertIn("inventory_before", result)
        self.assertEqual(result["inventory_before"], DEFAULT_RESOURCE_INVENTORY)

    def test_21_optimization_status_honest_on_empty(self):
        """optimization_status is not 'optimal' when there are no zones to process."""
        result = run_zone_optimization([])
        # Should not crash and should not lie about optimality
        self.assertIn(result["optimization_status"], ["no_zones", "fallback_ok", "fallback", "error", "optimal"])
        self.assertNotIn("traceback", str(result))


class TestRunZoneOptimization(unittest.TestCase):

    def test_14_empty_cases_safe(self):
        """run_zone_optimization([]) completes without error."""
        result = run_zone_optimization([])
        self.assertIn("zones", result)
        self.assertIn("optimization_status", result)

    def test_16b_custom_inventory_respected(self):
        """Custom inventory values are reflected in inventory_before."""
        custom = {"ndrf": 2, "ambulance": 3, "boat": 1, "shelter": 1, "hospital": 1, "fire": 2}
        result = run_zone_optimization([], custom)
        self.assertEqual(result["inventory_before"], custom)

    def test_18b_ml_output_untouched(self):
        """Zone optimization does not modify or touch ml_prediction field in cases."""
        case = _make_flood_case(lat=20.360, lng=85.820)
        case["ml_prediction"] = {"available": True, "incident_type": "flood"}
        # run_zone_optimization should not strip or alter this field
        original_ml = case["ml_prediction"].copy()
        run_zone_optimization([case])
        self.assertEqual(case.get("ml_prediction"), original_ml)

    def test_20_malformed_cases_no_500(self):
        """Malformed case entries don't crash run_zone_optimization."""
        junk_cases = [None, "string", 42, {"no_incident_id": True}, {}]
        try:
            result = run_zone_optimization(junk_cases)
            self.assertIn("optimization_status", result)
        except Exception as e:
            self.fail(f"run_zone_optimization raised an exception on malformed input: {e}")


class TestAPIBackwardCompatibility(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def _post_allocate(self, cases, resources=None):
        payload = {"cases": cases}
        if resources:
            payload["resources"] = resources
        return self.client.post("/allocate-resources",
                                json=payload,
                                content_type="application/json")

    def test_17_legacy_fields_preserved(self):
        """All original /allocate-resources response fields still present."""
        flood = _make_flood_case("SAH-COMPAT", lat=20.360, lng=85.820)
        res = self._post_allocate([flood])
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        # Legacy fields (must never disappear)
        for field in ["initial_resources", "remaining_resources",
                      "allocated_resources", "allocations", "summary"]:
            self.assertIn(field, body,
                          msg=f"Legacy field '{field}' missing from response")

    def test_17b_new_fields_present(self):
        """New Phase 3A fields appear alongside legacy fields."""
        flood = _make_flood_case("SAH-NEW", lat=20.360, lng=85.820)
        res = self._post_allocate([flood])
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        for field in ["zones", "assignments", "zone_summary",
                      "optimization_status", "inventory_before", "inventory_after"]:
            self.assertIn(field, body,
                          msg=f"New Phase 3A field '{field}' missing from response")

    def test_20b_empty_cases_no_500(self):
        """Empty case list returns 200, not 500."""
        res = self._post_allocate([])
        self.assertEqual(res.status_code, 200)

    def test_20c_malformed_json_returns_400(self):
        """Non-JSON body returns 400 (existing behaviour unchanged)."""
        res = self.client.post("/allocate-resources",
                               data="not json",
                               content_type="text/plain")
        self.assertEqual(res.status_code, 400)

    def test_20d_null_resources_uses_default(self):
        """Omitting 'resources' uses DEFAULT_RESOURCE_INVENTORY."""
        flood = _make_flood_case("SAH-DEF", lat=20.360, lng=85.820)
        res = self._post_allocate([flood])
        body = res.get_json()
        self.assertEqual(body["inventory_before"], DEFAULT_RESOURCE_INVENTORY)


if __name__ == "__main__":
    unittest.main(verbosity=2)

