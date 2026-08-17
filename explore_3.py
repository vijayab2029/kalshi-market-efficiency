import requests, json

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

r = requests.get(f"{BASE_URL}/events/KXWCCAREERGOALS-KMBAPPE", params={"with_nested_markets": "true"})
ev = r.json()["event"]

print("mutually_exclusive:", ev.get("mutually_exclusive"))
for m in ev["markets"]:
    print(m.get("ticker"), "|", m.get("strike_type"), "| floor:", m.get("floor_strike"),
          "| cap:", m.get("cap_strike"), "| custom:", m.get("custom_strike"), "|", m.get("yes_sub_title"))