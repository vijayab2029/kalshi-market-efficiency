import requests
r = requests.get(
    "https://external-api.kalshi.com/trade-api/v2/events",
    params={"with_nested_markets": True},
    timeout=10,
)
print(r.status_code)