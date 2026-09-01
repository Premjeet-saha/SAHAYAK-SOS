"""Explanation Service — Deterministic allocation reasoning for SAHAYAK SOS.

This module generates human-readable explanations for allocation decisions.
It produces structured reason codes and explanation strings for each zone.

IMPORTANT: This is deterministic optimization metadata, NOT a Gemini call.
Gemini can later use this metadata to produce a richer explanation.
Gemini must never become the final decision-maker.
"""


def generate_zone_reasoning(zone, alloc, unmet, inventory_before, inventory_after):
    """
    Produce structured reason codes and a human-readable explanation string
    for the allocation decision of a single zone.

    This is deterministic optimization metadata, NOT a Gemini call.
    Gemini can later use this metadata to produce a richer explanation.
    """
    reason_codes = []
    notes = []

    pd = zone.get("priority_demand", 0)
    cc = zone.get("critical_cases", 0)
    hc = zone.get("high_priority_cases", 0)
    md = zone.get("medical_demand", 0)
    case_count = zone.get("case_count", 0)
    zid = zone["zone_id"]

    if cc > 0:
        reason_codes.append("CRITICAL_CASES_PRESENT")
        notes.append(f"{cc} critical case(s)")
    if hc > 0:
        reason_codes.append("HIGH_PRIORITY_CONCENTRATION")
        notes.append(f"{hc} high-priority case(s)")
    if md > 0:
        reason_codes.append("MEDICAL_DEMAND")
        notes.append(f"{md} medical emergency case(s)")

    total_allocated = sum(v for v in alloc.values() if isinstance(v, int))
    total_unmet = sum(v for v in unmet.values() if isinstance(v, int))

    if total_unmet > 0:
        reason_codes.append("RESOURCE_SCARCITY")
        notes.append(f"{total_unmet} resource unit(s) could not be met")

    if not reason_codes:
        reason_codes.append("STANDARD_ALLOCATION")

    alloc_desc = ", ".join(f"{v} {k.upper()}" for k, v in alloc.items() if isinstance(v, int) and v > 0) or "none"
    unmet_desc = (", ".join(f"{v} {k.upper()}" for k, v in unmet.items() if isinstance(v, int) and v > 0)
                  if unmet else "none")

    explanation = (
        f"{zid} ({zone.get('name', zid)}) has {case_count} SOS cases "
        f"(priority demand {pd:.1f}, {cc} critical, {hc} high-priority, {md} medical). "
        f"Allocated: {alloc_desc}. Unmet demand: {unmet_desc}."
    )

    return {
        "zone_id": zid,
        "reason_codes": reason_codes,
        "explanation": explanation,
    }
