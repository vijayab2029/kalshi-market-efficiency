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


def classify_event_confidence(event: EventSchema) -> dict:
    strike_types = {m.strike_type for m in event.markets}

    if len(event.markets) == 1:
        return {
            "exhaustiveness": Exhaustiveness.THEORETICAL,
            "structure": Structure.SINGLE_BINARY,
            "reason": "Single binary market; YES/NO covers the outcome space",
            "gap_stats": None,
        }

    if strike_types <= {"less", "between", "greater"}:
        bracket_result = _check_brackets(event.markets)

        if bracket_result["exhaustive"] and event.mutually_exclusive:
            return {
                "exhaustiveness": Exhaustiveness.THEORETICAL,
                "structure": Structure.BRACKET,
                "reason": "Exhaustive set of brackets covering all values",
                "gap_stats": bracket_result["gap_stats"],
            }

        if bracket_result["exhaustive"]:
            return {
                "exhaustiveness": Exhaustiveness.THEORETICAL,
                "structure": Structure.CUMULATIVE,
                "reason": "Cumulative ladder; exhaustive but overlapping",
                "gap_stats": bracket_result["gap_stats"],
            }

        return {
            "exhaustiveness": Exhaustiveness.SUSPECT,
            "structure": Structure.BRACKET_SUSPECT,
            "reason": bracket_result["reason"],
            "gap_stats": bracket_result["gap_stats"],
        }

    if event.mutually_exclusive:
        return {
            "exhaustiveness": Exhaustiveness.NON_EXHAUSTIVE,
            "structure": Structure.OPEN,
            "reason": "Named-entity field; exhaustiveness not provable",
            "gap_stats": None,
        }

    return {
        "exhaustiveness": None,
        "structure": None,
        "reason": "Not mutually exclusive and no numeric structure",
        "gap_stats": None,
    }


def _check_brackets(markets: list[MarketSchema]) -> dict:
    less = [m for m in markets if m.strike_type == "less"]
    greater = [m for m in markets if m.strike_type == "greater"]
    between = [m for m in markets if m.strike_type == "between"]

    if len(less) != 1 or len(greater) != 1:
        one_sided = (greater and not less and not between) or (less and not greater and not between)
        if one_sided:
            return {
                "exhaustive": True,
                "reason": "One-sided ladder, exhaustive but not mutually exclusive",
                "gap_stats": None,
            }
        return {
            "exhaustive": False,
            "reason": "missing open-ended bucket",
            "gap_stats": None,
        }

    if less[0].cap_strike is None or greater[0].floor_strike is None:
        return {
            "exhaustive": False,
            "reason": "No bound provided on an open ladder",
            "gap_stats": None,
        }

    if any(m.floor_strike is None or m.cap_strike is None for m in between):
        return {
            "exhaustive": False,
            "reason": "bounded bucket missing a bound",
            "gap_stats": None,
        }

    ordered = sorted(between, key=lambda m: m.floor_strike)

    gap_list = []
    prev_cap = less[0].cap_strike

    for m in ordered:
        gap_list.append(m.floor_strike - prev_cap)
        prev_cap = m.cap_strike

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
    }