import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

r = requests.get(f"{BASE_URL}/events/KXUSCPIYEAR-34FEB01", params={"with_nested_markets": "true"})
ev = r.json()["event"]

print("title:", ev.get("title"))
print("mutually_exclusive:", ev.get("mutually_exclusive"))
print("markets:", len(ev["markets"]))
print()

for m in ev["markets"]:
    print(
        m.get("ticker"),
        "| strike_type:", m.get("strike_type"),
        "| floor:", m.get("floor_strike"),
        "| cap:", m.get("cap_strike"),
        "| custom:", m.get("custom_strike"),
        "|", m.get("yes_sub_title"),
    )