import asyncio
import json
import os
import time
from datetime import datetime, timezone

import aiohttp
from dotenv import load_dotenv
from upstash_redis import Redis

from models import EventSchema, SeriesFee
from detectors import classify_event_confidence, Structure, Exhaustiveness
from tracker import detect_violations, update_tracker, get_open_violations
from fees import DEFAULT_FEE_MULTIPLIER

load_dotenv()

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
PAGE_LIMIT = 200
CHUNK_SIZE = 200

HOT_INTERVAL = 480
COLD_INTERVAL = 1800
SWEEP_INTERVAL = 86400

VALID_STRUCTURES = {Structure.SINGLE_BINARY, Structure.BRACKET, Structure.CUMULATIVE}
VALID_EXHAUSTIVENESS = {Exhaustiveness.THEORETICAL, Exhaustiveness.EMPIRICAL}

HOT_SINGLE_MARKET_THRESHOLD = 10
HOT_SUM_THRESHOLD = 30

KEY_1 = "kalshi:live_violations"

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
)

watch_list = {
    "hot": [],
    "cold": [],
}

series_fee_store = {}


async def fetch_all_series(session: aiohttp.ClientSession) -> dict[str, SeriesFee]:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(f"{BASE_URL}/series", timeout=timeout) as response:
            if response.status != 200:
                print(f"[fees] Wrong status code fetching series list: {response.status}")
                return {}
            data = await response.json()
    except Exception as e:
        print(f"[fees] Failed to fetch series list: {e}")
        return {}

    store = {}
    for entry in data.get("series", []):
        ticker = entry.get("ticker")
        if ticker is None:
            continue
        store[ticker] = SeriesFee(
            ticker=ticker,
            fee_multiplier=entry.get("fee_multiplier", DEFAULT_FEE_MULTIPLIER),
            fee_type=entry.get("fee_type", "unknown"),
        )
    return store


async def fetch_by_tickers(session: aiohttp.ClientSession, tickers: list[str]) -> list[EventSchema]:
    events = []

    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i : i + CHUNK_SIZE]
        params = {
            "tickers": ",".join(chunk),
            "with_nested_markets": "true",
            "limit": CHUNK_SIZE,
            "status": "open",
        }

        timeout = aiohttp.ClientTimeout(total=30)
        async with session.get(f"{BASE_URL}/events", params=params, timeout=timeout) as response:
            response.raise_for_status()
            data = await response.json()

        for raw in data.get("events", []):
            try:
                events.append(EventSchema(**raw))
            except Exception as e:
                print(f"  [WARN] Skipped {raw.get('event_ticker', '?')}: {e}")

    return events


def classify_tier(event: EventSchema) -> str:
    volume_sum = 0
    for market in event.markets:
        volume = market.volume_24h_fp or 0
        volume_sum += volume
        if volume >= HOT_SINGLE_MARKET_THRESHOLD:
            return "hot"
        if volume_sum >= HOT_SUM_THRESHOLD:
            return "hot"
    return "cold"


async def daily_sweep(session: aiohttp.ClientSession) -> dict:
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

        timeout = aiohttp.ClientTimeout(total=30)
        async with session.get(f"{BASE_URL}/events", params=params, timeout=timeout) as response:
            response.raise_for_status()
            data = await response.json()

        events_raw = data.get("events", [])
        if not events_raw:
            break

        print(f"  [sweep] page {page_num}: {len(events_raw)} events")

        for raw in events_raw:
            try:
                event = EventSchema(**raw)
            except Exception as e:
                print(f"  [WARN] Skipped {raw.get('event_ticker', '?')}: {e}")
                continue

            classification = classify_event_confidence(event)
            if (classification["structure"] in VALID_STRUCTURES
                    and classification["exhaustiveness"] in VALID_EXHAUSTIVENESS):
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


def run_cycle(events: list[EventSchema], tier_label: str):
    all_violations = []
    for event in events:
        event_violations = detect_violations(event, series_fee_store)
        all_violations.extend(event_violations)

    summary = update_tracker(all_violations)
    print(f"[{tier_label}] Tracker: {summary['new']} new, {summary['continued']} continued, "
          f"{summary['closed']} closed, {summary['total_open']} open")

    snapshot = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "violation_count": summary["total_open"],
        "violations": get_open_violations(),
    }
    redis.set(KEY_1, json.dumps(snapshot))


async def hot_loop(session: aiohttp.ClientSession):
    while True:
        start = time.time()
        try:
            tickers = watch_list["hot"]
            if tickers:
                events = await fetch_by_tickers(session, tickers)
                print(f"[hot] Fetched {len(events)} events at {datetime.now(timezone.utc).isoformat()}")
                run_cycle(events, "hot")
            else:
                print("[hot] No hot tickers yet, waiting for first sweep")
        except Exception as e:
            print(f"[hot] Error: {e}")

        elapsed = time.time() - start
        await asyncio.sleep(max(0, HOT_INTERVAL - elapsed))


async def cold_loop(session: aiohttp.ClientSession):
    while True:
        start = time.time()
        try:
            tickers = watch_list["cold"]
            if tickers:
                events = await fetch_by_tickers(session, tickers)
                print(f"[cold] Fetched {len(events)} events at {datetime.now(timezone.utc).isoformat()}")
                run_cycle(events, "cold")
            else:
                print("[cold] No cold tickers yet, waiting for first sweep")
        except Exception as e:
            print(f"[cold] Error: {e}")

        elapsed = time.time() - start
        await asyncio.sleep(max(0, COLD_INTERVAL - elapsed))


async def sweep_loop(session: aiohttp.ClientSession):
    global series_fee_store
    while True:
        start = time.time()
        try:
            print(f"[sweep] Starting at {datetime.now(timezone.utc).isoformat()}")

            updated_fees = await fetch_all_series(session)
            if updated_fees:
                series_fee_store = updated_fees
                print(f"[sweep] Refreshed series fees: {len(series_fee_store)} series")

            result = await daily_sweep(session)
            watch_list["hot"] = result["hot"]
            watch_list["cold"] = result["cold"]
            print(f"[sweep] Done. Hot: {len(result['hot'])}, Cold: {len(result['cold'])}")
        except Exception as e:
            print(f"[sweep] Error: {e}")

        elapsed = time.time() - start
        await asyncio.sleep(max(0, SWEEP_INTERVAL - elapsed))


async def main():
    global series_fee_store
    async with aiohttp.ClientSession() as session:
        print("Fetching series fees...")
        series_fee_store = await fetch_all_series(session)
        print(f"Loaded {len(series_fee_store)} series fees")

        print("Running initial sweep...")
        result = await daily_sweep(session)
        watch_list["hot"] = result["hot"]
        watch_list["cold"] = result["cold"]
        print(f"Initial sweep done. Hot: {len(result['hot'])}, Cold: {len(result['cold'])}")

        await asyncio.gather(
            hot_loop(session),
            cold_loop(session),
            sweep_loop(session),
        )


if __name__ == "__main__":
    asyncio.run(main())