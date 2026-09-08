from datetime import datetime, timezone

from models import EventSchema
from detectors import (
    classify_event_confidence,
    compute_event_sum,
    classify_event_sum,
    check_monotonicity,
    evaluate_arbitrage_with_fees,
    MarketSumInefficiencies,
    Structure,
)
from fees import compute_event_fees, determine_fee_multiplier

OVERROUND_THRESHOLD = 0.30
OVERROUND_STRUCTURES = {Structure.SINGLE_BINARY, Structure.BRACKET}

open_violations = {}


def detect_violations(event: EventSchema, series_fee_store: dict) -> list[dict]:
    violations = []
    classification = classify_event_confidence(event)
    structure = classification.get("structure")

    if structure in OVERROUND_STRUCTURES:
        computed_sum = compute_event_sum(event)
        classification_sum = classify_event_sum(computed_sum, classification)

        if classification_sum["sum_inefficiency_type"] == MarketSumInefficiencies.OVERROUND:
            overround = computed_sum["total"] - 1.0
            if overround >= OVERROUND_THRESHOLD:
                violations.append({
                    "event_ticker": event.event_ticker,
                    "violation_type": "overround",
                    "size": round(overround, 4),
                    "size_after_fees": None,
                    "sub_violation_count": None,
                })

        elif classification_sum["sum_inefficiency_type"] == MarketSumInefficiencies.ARBITRAGE_SUM:
            fee_multiplier = determine_fee_multiplier(event, series_fee_store)
            event_fees = compute_event_fees(event, fee_multiplier)
            arbitrage_result = evaluate_arbitrage_with_fees(classification_sum, event_fees)

            residual_before_fees = arbitrage_result.get("residual")
            residual_after = arbitrage_result.get("net_residual")

            if residual_before_fees is not None and residual_before_fees > 0:
                violations.append({
                    "event_ticker": event.event_ticker,
                    "violation_type": "arbitrage",
                    "size": round(residual_before_fees, 4),
                    "size_after_fees": round(residual_after, 4) if residual_after is not None else None,
                    "sub_violation_count": None,
                })

    monotonicity_result = check_monotonicity(event, classification)
    if monotonicity_result["eligible"] and monotonicity_result["violations"]:
        magnitudes = [v["magnitude"] for v in monotonicity_result["violations"]]
        violations.append({
            "event_ticker": event.event_ticker,
            "violation_type": "monotonicity",
            "size": round(max(magnitudes), 4),
            "size_after_fees": None,
            "sub_violation_count": len(monotonicity_result["violations"]),
        })

    return violations


def update_tracker(violations_for_cycle: list[dict]) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    current_keys = set()

    new_count = 0
    continued_count = 0

    for v in violations_for_cycle:
        key = (v["event_ticker"], v["violation_type"])
        current_keys.add(key)

        if key not in open_violations:
            open_violations[key] = {
                "event_ticker": v["event_ticker"],
                "violation_type": v["violation_type"],
                "first_seen": now,
                "last_seen": now,
                "max_size": v["size"],
                "max_size_after_fees": v["size_after_fees"],
                "sub_violation_count": v["sub_violation_count"],
            }
            new_count += 1
        else:
            entry = open_violations[key]
            entry["last_seen"] = now

            if v["size"] is not None and v["size"] > entry["max_size"]:
                entry["max_size"] = v["size"]

            if v["size_after_fees"] is not None and entry["max_size_after_fees"] is not None:
                if v["size_after_fees"] > entry["max_size_after_fees"]:
                    entry["max_size_after_fees"] = v["size_after_fees"]
            elif v["size_after_fees"] is not None:
                entry["max_size_after_fees"] = v["size_after_fees"]

            if v["sub_violation_count"] is not None and entry["sub_violation_count"] is not None:
                if v["sub_violation_count"] > entry["sub_violation_count"]:
                    entry["sub_violation_count"] = v["sub_violation_count"]
            elif v["sub_violation_count"] is not None:
                entry["sub_violation_count"] = v["sub_violation_count"]

            continued_count += 1

    closed_keys = set(open_violations.keys()) - current_keys
    closed_count = len(closed_keys)
    for key in closed_keys:
        del open_violations[key]

    return {
        "new": new_count,
        "continued": continued_count,
        "closed": closed_count,
        "total_open": len(open_violations),
    }


def get_open_violations() -> list[dict]:
    return list(open_violations.values())