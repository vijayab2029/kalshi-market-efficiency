import requests
from schema import EventSchema
from detectors import (
    classify_event_confidence,
    compute_overround,
    compute_complementarity,
    Structure,
)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

response = requests.get(
    f"{BASE_URL}/events",
    params={"limit": 50, "status": "open", "with_nested_markets": "true"}
)
raw_data = response.json()

validation_errors = []
results = []

for raw_event in raw_data["events"]:
    try:
        event = EventSchema(**raw_event)
    except Exception as e:
        validation_errors.append((raw_event.get("event_ticker", "unknown"), str(e)))
        continue

    classification = classify_event_confidence(event)

    if classification["structure"] == Structure.SINGLE_BINARY:
        computation = compute_complementarity(event.markets[0])
    else:
        computation = compute_overround(event.markets)

    results.append({
        "ticker": event.event_ticker,
        "markets": len(event.markets),
        "structure": classification["structure"],
        "exhaustiveness": classification["exhaustiveness"],
        "reason": classification["reason"],
        "gap_stats": classification["gap_stats"],
        "total": computation["total"],
        "method": computation["method"],
        "missing": computation["missing_count"],
    })

print(f"Classified {len(results)} events | {len(validation_errors)} validation errors\n")

by_structure = {}
for r in results:
    key = r["structure"] or "none"
    by_structure.setdefault(key, []).append(r)

for structure, group in by_structure.items():
    print(f"=== {structure} ({len(group)}) ===")
    for r in group:
        print(f"  {r['ticker']:<32} | markets: {r['markets']:>2} | total: {r['total']:.3f} | missing: {r['missing']} | {r['method']}")
        if r["gap_stats"]:
            print(f"      gaps: {r['gap_stats']}")
    print()

if validation_errors:
    print("=== validation errors ===")
    for ticker, err in validation_errors:
        print(f"  {ticker}: {err}")