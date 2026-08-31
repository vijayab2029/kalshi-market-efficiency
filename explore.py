import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


def explore():
    params = {}
    response = requests.get(f"{BASE_URL}/series", params=params, timeout=10)

    print("status:", response.status_code)

    data = response.json()

    print("top-level keys:", list(data.keys()))
    print("has cursor?:", "cursor" in data)

    series_list = data.get("series", [])
    print("number of series returned:", len(series_list))

    if series_list:
        print("\nsample entry:")
        print(series_list[0])

        print("\nunique fee_multiplier values seen:", set(s.get("fee_multiplier") for s in series_list))
        print("unique fee_type values seen:", set(s.get("fee_type") for s in series_list))


if __name__ == "__main__":
    explore()