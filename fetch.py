import requests
from models import EventSchema

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
CHUNK_SIZE = 200


def fetch_by_tickers(tickers: list[str]) -> list[EventSchema]:
    events = []
    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i : i + CHUNK_SIZE]

        ticker_str = ",".join(chunk)
        params = {
            "tickers": ticker_str,
            "with_nested_markets": "true",
            "limit": CHUNK_SIZE,
            "status": "open",
        }

        response = requests.get(f"{BASE_URL}/events", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for raw in data.get("events", []):
            try:
                events.append(EventSchema(**raw))
            except Exception as e:
                print(f"Skipped {raw.get('event_ticker', '?')}: {e}")

    return events