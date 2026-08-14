import json
import requests
from schema import EventSchema

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

event_ticker = "KXGDPYEAR-34"
response = requests.get(
    f"{BASE_URL}/events/{event_ticker}",
    params={"with_nested_markets": "true"}
)

raw_data = response.json()
markets = raw_data["event"]["markets"]

print("Title:", raw_data["event"].get("title"))
print()

for m in markets:
    print(
        m.get("ticker"),
        "| strike_type:", m.get("strike_type"),
        "| floor_strike:", m.get("floor_strike"),
        "| cap_strike:", m.get("cap_strike"),
        "|", m.get("subtitle") or m.get("title")
    )

mid_index = len(markets) // 2

print()
print("--- FIRST market (likely open-ended bottom bucket) ---")
print(json.dumps(markets[0], indent=2))

print()
print(f"--- MIDDLE market (index {mid_index}, likely a bounded bucket) ---")
print(json.dumps(markets[mid_index], indent=2))

print()
print("--- LAST market (likely open-ended top bucket) ---")
print(json.dumps(markets[-1], indent=2))