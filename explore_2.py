import requests, json

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

for ticker in ["KXRAMPBREX-40", "KXWCHOST-2038"]:
    r = requests.get(f"{BASE_URL}/events/{ticker}", params={"with_nested_markets": "true"})
    ev = r.json()["event"]

    print(f"=== {ticker} ===")
    print("title:", ev.get("title"))
    print("mutually_exclusive:", ev.get("mutually_exclusive"))
    print("markets:", len(ev["markets"]))
    print()
    for m in ev["markets"][:3]:
        print(" ", m.get("yes_sub_title"))
        print("   rules:", m.get("rules_primary"))
        print()