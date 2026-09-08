import time
from datetime import datetime, timezone

import requests
from models import EventSchema
from detectors import classify_event_confidence, Structure, Exhaustiveness

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
PAGE_LIMIT = 200

VALID_STRUCTURES = {Structure.SINGLE_BINARY, Structure.BRACKET, Structure.CUMULATIVE}
VALID_EXHAUSTIVENESS = {Exhaustiveness.THEORETICAL, Exhaustiveness.EMPIRICAL}

HOT_SINGLE_MARKET_THRESHOLD = 10
HOT_SUM_THRESHOLD = 30


def classify_tier(event: EventSchema) -> str:
    volume_sum = 0
    for market in event.markets:
        volume = market.volume_24h_fp
        if volume:
            volume_sum += market.volume_24h_fp
            if volume >= HOT_SINGLE_MARKET_THRESHOLD:
                return "hot"
            if volume_sum >= HOT_SUM_THRESHOLD:
                return "hot"
    return "cold"


def daily_sweep():
    hot_tickers = []
    cold_tickers = []

    cursor = None
    page_num = 0

    while True:
        page_num += 1
        params = {
            "with_nested_markets": "true",
            "limit": PAGE_LIMIT,
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

        print(f"  page {page_num}: {len(events_raw)} events")

        for raw in events_raw:
            try:
                event = EventSchema(**raw)
            except Exception as e:
                print(f"Skipped {raw.get('event_ticker', '?')}: {e}")
                continue

            classification = classify_event_confidence(event)
            if classification["structure"] in VALID_STRUCTURES and classification["exhaustiveness"] in VALID_EXHAUSTIVENESS:
                if classify_tier(event) == "hot":
                    hot_tickers.append(event.event_ticker)
                else:
                    cold_tickers.append(event.event_ticker)

        cursor = data.get("cursor")
        if not cursor:
            break

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hot": hot_tickers,
        "cold": cold_tickers,
    }


if __name__ == "__main__":
    start = time.time()
    watch_list = daily_sweep()
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Hot: {len(watch_list['hot'])}, Cold: {len(watch_list['cold'])}")