import time
import requests
from schema import EventSchema
from pydantic import ValidationError
from fees import compute_event_fees, determine_fee_multiplier
from detectors import (
    classify_event_confidence,
    compute_event_sum,
    classify_event_sum,
    check_monotonicity,
    compute_spread,
    evaluate_arbitrage_with_fees,
    report_overround_fees,
    MarketSumInefficiencies,
)

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


def fetch_all_events() -> list[EventSchema]:
    print("ENTERED fetch_all_events")
    events = []
    cursor = None
    fetch_time = 0.0
    parse_time = 0.0

    while True:
        print(f"LOOP ITER: cursor={cursor!r}, events_so_far={len(events)}")
        params = {"with_nested_markets": "true", "limit": 200, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        t0 = time.time()
        try:
            response = requests.get(f"{BASE_URL}/events", params=params)
            fetch_time += time.time() - t0
        except Exception as e:
            fetch_time += time.time() - t0
            print(e)
            break

        if response.status_code != 200:
            print(f"Wrong status code: {response.status_code}")
            break

        data = response.json()

        t0 = time.time()
        for event in data["events"]:
            try:
                events.append(EventSchema(**event))
            except ValidationError as e:
                print(f"Cannot parse event {event.get('event_ticker', 'unknown')}: {e}")
        parse_time += time.time() - t0

        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"Done. Parsed {len(events)} events. fetch_time={fetch_time:.2f}s parse_time={parse_time:.2f}s")
    return events


def process_events(events: list[EventSchema], series_fee_store: dict) -> list[dict]:
    results = []
    series_fee_time = 0.0
    detector_time = 0.0
    fee_computation_time = 0.0
    failed_time = 0.0

    for event in events:
        event_start = time.time()
        try:
            t0 = time.time()
            classification = classify_event_confidence(event)
            computation = compute_event_sum(event)
            classified_event_sum = classify_event_sum(computation, classification)
            monotonicity = check_monotonicity(event, classification)
            spreads = [compute_spread(market) for market in event.markets]
            detector_time += time.time() - t0

            t0 = time.time()
            fee_multiplier = determine_fee_multiplier(event, series_fee_store)
            series_fee_time += time.time() - t0

            t0 = time.time()
            event_fees = compute_event_fees(event, fee_multiplier)
            fee_computation_time += time.time() - t0

            t0 = time.time()
            if classified_event_sum["sum_inefficiency_type"] == MarketSumInefficiencies.ARBITRAGE_SUM:
                result_with_fees = evaluate_arbitrage_with_fees(classified_event_sum, event_fees)
            elif classified_event_sum["sum_inefficiency_type"] == MarketSumInefficiencies.OVERROUND:
                result_with_fees = report_overround_fees(classified_event_sum, event_fees)
            else:
                result_with_fees = None

            results.append({
                "event_ticker": event.event_ticker,
                "classification": classification,
                "sum": classified_event_sum,
                "monotonicity": monotonicity,
                "fees": event_fees,
                "fee_evaluation": result_with_fees,
                "spreads": spreads,
            })
            detector_time += time.time() - t0

        except Exception as e:
            failed_time += time.time() - event_start
            print(f"Error on event {event.event_ticker}: {e}")
            continue

    print(f"detector_time={detector_time:.2f}s series_fee_time={series_fee_time:.2f}s "
          f"fee_computation_time={fee_computation_time:.2f}s failed_time={failed_time:.2f}s")
    return results