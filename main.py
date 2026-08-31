from worker import fetch_all_events, process_events
from fees import fetch_all_series


def main():
    events = fetch_all_events()
    series_fee_store = fetch_all_series()
    results = process_events(events, series_fee_store)

    for result in results:
        print(result)


if __name__ == "__main__":
    main()