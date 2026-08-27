import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

r = requests.get(f"{BASE_URL}/series")
print(r.status_code)
data = r.json()

series_list = data.get("series", [])
print(f"got {len(series_list)} series")

for s in series_list:
    print(s["ticker"], s.get("fee_multiplier"), s.get("fee_type"), s.get("category"))