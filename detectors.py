# TODO: Implement fee calculations with the endpoint instead of the flat formula from docs
# TODO: Add those empirically exhaustive events, and theoretically exhuastive sporting events

from schema import MarketSchema, EventSchema
from statistics import mean
from enum import Enum


class Exhaustiveness(str, Enum):
    THEORETICAL = "theoretical"
    EMPIRICAL = "empirical"
    NON_EXHAUSTIVE = "non_exhaustive"
    SUSPECT = "suspect"


class Structure(str, Enum):
    SINGLE_BINARY = "single_binary"
    BRACKET = "bracket"
    CUMULATIVE = "cumulative"
    BRACKET_SUSPECT = "bracket_suspect"
    OPEN = "open"


ARBITRAGE_STRUCTURES = (Structure.BRACKET, Structure.SINGLE_BINARY)


def compute_overround(markets: list[MarketSchema]) -> dict:
    total_yes_ask = 0.0
    missing_count = 0

    for market in markets:
        if market.yes_ask_dollars is not None:
            total_yes_ask += market.yes_ask_dollars
        else:
            missing_count += 1

    return {
        "total": total_yes_ask,
        "missing_count": missing_count,
        "market_count": len(markets),
        "method": "cross_market_sum",
    }


def compute_complementarity(market: MarketSchema) -> dict:
    yes_ask = market.yes_ask_dollars
    no_ask = market.no_ask_dollars

    missing_count = sum(1 for side in (yes_ask, no_ask) if side is None)

    if missing_count == 2:
        total = 0.0
    else:
        total = (yes_ask or 0.0) + (no_ask or 0.0)

    return {
        "total": total,
        "missing_count": missing_count,
        "market_count": 1,
        "method": "complementarity",
    }


def check_arbitrage(market_classification: dict, computation: dict) -> dict:
    structure = market_classification["structure"]

    if structure not in ARBITRAGE_STRUCTURES:
        return {
            "eligible": False,
            "positive_residual": False,
            "residual": None,
            "reason": f"This structure {structure} does not support arbitrage",
            "fees_applied": False,
        }

    if computation["missing_count"] > 0:
        return {
            "eligible": False,
            "positive_residual": False,
            "residual": None,
            "reason": "Ineligible: some markets have no ask price",
            "fees_applied": False,
        }

    total = computation["total"]
    residual = 1.0 - total

    if residual <= 0:
        return {
            "eligible": True,
            "positive_residual": False,
            "residual": residual,
            "reason": "no arbitrage; sum of ask prices is more than 1 dollar",
            "fees_applied": False,
        }

    return {
        "eligible": True,
        "positive_residual": True,
        "residual": residual,
        "reason": "arbitrage before fees exists, ask sum is less than $1",
        "fees_applied": False,
    }


def check_monotonicity(event: EventSchema, market_classification: dict) -> dict:
    if market_classification["structure"] != Structure.CUMULATIVE:
        return {
            "eligible": False,
            "violations": [],
            "pairs_checked": 0,
            "pairs_skipped": 0,
            "reason": "monotonicity only applies to cumulative ladders",
        }

    structures = {m.market_structure for m in event.markets}

    if structures == {"greater"}:
        threshold_of = lambda m: m.floor_strike
        expect_decreasing = True
    elif structures == {"less"}:
        threshold_of = lambda m: m.effective_cap
        expect_decreasing = False
    else:
        return {
            "eligible": False,
            "violations": [],
            "pairs_checked": 0,
            "pairs_skipped": 0,
            "reason": f"mixed or unexpected structures in cumulative ladder: {structures}",
        }

    usable = [m for m in event.markets if threshold_of(m) is not None]
    ordered = sorted(usable, key=threshold_of)

    violations = []
    pairs_checked = 0
    pairs_skipped = 0

    for lower, higher in zip(ordered, ordered[1:]):
        if lower.yes_ask_dollars is None or higher.yes_ask_dollars is None:
            pairs_skipped += 1
            continue

        pairs_checked += 1

        if expect_decreasing:
            magnitude = higher.yes_ask_dollars - lower.yes_ask_dollars
        else:
            magnitude = lower.yes_ask_dollars - higher.yes_ask_dollars

        if magnitude > 0:
            violations.append({
                "lower_ticker": lower.ticker,
                "lower_threshold": threshold_of(lower),
                "lower_ask": lower.yes_ask_dollars,
                "higher_ticker": higher.ticker,
                "higher_threshold": threshold_of(higher),
                "higher_ask": higher.yes_ask_dollars,
                "magnitude": magnitude,
            })

    return {
        "eligible": True,
        "violations": violations,
        "pairs_checked": pairs_checked,
        "pairs_skipped": pairs_skipped,
        "reason": (
            f"{len(violations)} violations across {pairs_checked} pairs"
            if violations
            else f"monotonic across {pairs_checked} pairs"
        ),
    }


def classify_event_confidence(event: EventSchema) -> dict:
    structures = {m.market_structure for m in event.markets}

    if len(event.markets) == 1:
        return {
            "exhaustiveness": Exhaustiveness.THEORETICAL,
            "structure": Structure.SINGLE_BINARY,
            "reason": "Single binary market; YES/NO covers the outcome space",
            "gap_stats": None,
            "date_event": event.markets[0].strike_date is not None,
        }

    if structures <= {"less", "between", "greater"}:
        bracket_result = _check_brackets(event.markets)

        if bracket_result["not_a_ladder"]:
            if event.mutually_exclusive:
                return {
                    "exhaustiveness": Exhaustiveness.NON_EXHAUSTIVE,
                    "structure": Structure.OPEN,
                    "reason": bracket_result["reason"],
                    "gap_stats": None,
                    "date_event": bracket_result["date_event"],
                }
            return {
                "exhaustiveness": None,
                "structure": None,
                "reason": bracket_result["reason"],
                "gap_stats": None,
                "date_event": bracket_result["date_event"],
            }

        if bracket_result["exhaustive"] and event.mutually_exclusive:
            return {
                "exhaustiveness": Exhaustiveness.THEORETICAL,
                "structure": Structure.BRACKET,
                "reason": "Exhaustive set of brackets covering all values",
                "gap_stats": bracket_result["gap_stats"],
                "date_event": bracket_result["date_event"],
            }

        if bracket_result["exhaustive"]:
            return {
                "exhaustiveness": Exhaustiveness.THEORETICAL,
                "structure": Structure.CUMULATIVE,
                "reason": "Cumulative ladder; exhaustive but overlapping",
                "gap_stats": bracket_result["gap_stats"],
                "date_event": bracket_result["date_event"],
            }

        return {
            "exhaustiveness": Exhaustiveness.SUSPECT,
            "structure": Structure.BRACKET_SUSPECT,
            "reason": bracket_result["reason"],
            "gap_stats": bracket_result["gap_stats"],
            "date_event": bracket_result["date_event"],
        }

    if event.mutually_exclusive:
        return {
            "exhaustiveness": Exhaustiveness.NON_EXHAUSTIVE,
            "structure": Structure.OPEN,
            "reason": "Named-entity field; exhaustiveness not provable",
            "gap_stats": None,
            "date_event": False,
        }

    return {
        "exhaustiveness": None,
        "structure": None,
        "reason": "Not mutually exclusive and no numeric structure",
        "gap_stats": None,
        "date_event": False,
    }


def _check_brackets(markets: list[MarketSchema]) -> dict:
    date_event = any(m.strike_date is not None for m in markets)

    caps = [m.effective_cap for m in markets if m.effective_cap is not None]
    floors = [m.floor_strike for m in markets if m.floor_strike is not None]

    caps_all_same = len(caps) > 1 and len(set(caps)) == 1
    floors_all_same = len(floors) > 1 and len(set(floors)) == 1

    if caps_all_same or floors_all_same:
        return {
            "exhaustive": False,
            "reason": (
                "all caps identical; shared qualifier, not a ladder"
                if caps_all_same
                else "all floors identical; shared qualifier, not a ladder"
            ),
            "gap_stats": None,
            "date_event": date_event,
            "not_a_ladder": True,
        }

    less = [m for m in markets if m.market_structure == "less"]
    greater = [m for m in markets if m.market_structure == "greater"]
    between = [m for m in markets if m.market_structure == "between"]

    if len(less) != 1 or len(greater) != 1:
        one_sided = (greater and not less and not between) or (less and not greater and not between)
        if one_sided:
            return {
                "exhaustive": True,
                "reason": "One-sided ladder, exhaustive but not mutually exclusive",
                "gap_stats": None,
                "date_event": date_event,
                "not_a_ladder": False,
            }
        return {
            "exhaustive": False,
            "reason": "missing open-ended bucket",
            "gap_stats": None,
            "date_event": date_event,
            "not_a_ladder": False,
        }

    if less[0].effective_cap is None or greater[0].floor_strike is None:
        return {
            "exhaustive": False,
            "reason": "No bound provided on an open ladder",
            "gap_stats": None,
            "date_event": date_event,
            "not_a_ladder": False,
        }

    if any(m.floor_strike is None or m.effective_cap is None for m in between):
        return {
            "exhaustive": False,
            "reason": "bounded bucket missing a bound",
            "gap_stats": None,
            "date_event": date_event,
            "not_a_ladder": False,
        }

    ordered = sorted(between, key=lambda m: m.floor_strike)

    gap_list = []
    prev_cap = less[0].effective_cap

    for m in ordered:
        gap_list.append(m.floor_strike - prev_cap)
        prev_cap = m.effective_cap

    gap_list.append(greater[0].floor_strike - prev_cap)

    gap_stats = {
        "mean": mean(gap_list),
        "min": min(gap_list),
        "max": max(gap_list),
        "negative_gap": any(gap < 0 for gap in gap_list),
    }

    return {
        "exhaustive": True,
        "reason": "Unbounded on both sides and filled in the middle",
        "gap_stats": gap_stats,
        "date_event": date_event,
        "not_a_ladder": False,
    }