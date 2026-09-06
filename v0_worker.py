import os
import json
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from upstash_redis import Redis

from models import EventSchema
from detectors import (
    classify_event_confidence, compute_event_sum,
    Structure, Exhaustiveness
)

load_dotenv()

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
LIMIT_PER_PAGE = 200
PAGES_FOR_FETCH = 2
SLEEP_CYCLE = 900
NUM_CYCLES = 4

OVERROUND_THRESHOLD = 0.30
OVERROUND_STRUCTURES = {Structure.SINGLE_BINARY, Structure.BRACKET}
QUALIFYING_STRUCTURES = {Structure.SINGLE_BINARY, Structure.BRACKET, Structure.CUMULATIVE}
QUALIFYING_EXHAUSTIVENESS = {Exhaustiveness.THEORETICAL, Exhaustiveness.EMPIRICAL}

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
)

KEY_1 = "kalshi:live_violations"


def fetch_events(pages=PAGES_FOR_FETCH):
    all_events = []
    cursor = None
    for page_num in range(pages):
        params = {
            "with_nested_markets": "true",
            "limit": LIMIT_PER_PAGE,
            "status": "open",
        }
        if cursor:
            params["cursor"] = cursor
        response = requests.get(f"{BASE_URL}/events", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        events_raw = data.get("events", [])
        if not events_raw:
            break
        for raw in events_raw:
            try:
                parsed = EventSchema(**raw)
                all_events.append(parsed)
            except Exception as e:
                print(f"  [WARN] Skipped {raw.get('event_ticker', '?')}: {e}")
        cursor = data.get("cursor")
        if not cursor:
            break
    return all_events


def detect_violations(events):
    violations = []
    for event in events:
        classification = classify_event_confidence(event)
        structure = classification.get("structure")
        exhaustiveness = classification.get("exhaustiveness")
        if structure not in QUALIFYING_STRUCTURES or exhaustiveness not in QUALIFYING_EXHAUSTIVENESS:
            continue
        if structure not in OVERROUND_STRUCTURES:
            continue

        computed_sum = compute_event_sum(event)
        total_sum = computed_sum.get("total")
        mkt_count = computed_sum.get("market_count", 0)
        if total_sum is None or mkt_count == 0:
            continue

        overround = total_sum - 1.0
        if overround >= OVERROUND_THRESHOLD:
            violations.append({
                "event_ticker": event.event_ticker,
                "structure": structure.value,
                "market_count": mkt_count,
                "overround": round(overround, 4),
                "observed_at": datetime.now(timezone.utc).isoformat(),
            })

    return violations


def main():
    print(f"v0 worker starting at {datetime.now(timezone.utc).isoformat()}")
    print(f"Running {NUM_CYCLES} cycles, {SLEEP_CYCLE}s apart, then exiting.")

    for cycle_num in range(1, NUM_CYCLES + 1):
        cycle_start = time.time()
        now = datetime.now(timezone.utc)
        print(f"\n--- Cycle {cycle_num}/{NUM_CYCLES} at {now.isoformat()} ---")

        try:
            events = fetch_events()
            print(f"  Fetched {len(events)} events")

            violations = detect_violations(events)
            print(f"  Found {len(violations)} violations (overround >= {OVERROUND_THRESHOLD})")

            payload = {
                "updated_at": now.isoformat(),
                "violation_count": len(violations),
                "violations": violations,
            }
            redis.set(KEY_1, json.dumps(payload))
            print(f" Finished Writing to Redis key '{KEY_1}'")

        except Exception as e:
            print(f"Error: {e}")

        cycle_time = time.time() - cycle_start
        print(f" The cycle took {cycle_time:.1f}s")

        if cycle_num < NUM_CYCLES:
            sleep_time = max(SLEEP_CYCLE - cycle_time, 1)
            print(f"{sleep_time:.0f}s until next cycle")
            time.sleep(sleep_time)

    print(f"\nCycles Finished: {NUM_CYCLES}, done with run")


if __name__ == "__main__":
    main()