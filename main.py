from worker import fetch_all_events, process_events


def main():
    events = fetch_all_events()
    series_fee_cache = {}
    results = process_events(events, series_fee_cache)

    for result in results:
        print(result)


if __name__ == "__main__":
    main()