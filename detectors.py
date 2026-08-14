from schema import MarketSchema

def compute_overround(markets: list[MarketSchema]) -> dict:
    total_yes_ask = 0.0
    missing_count = 0

    for market in markets:
        if market.yes_ask_dollars is not None:
            total_yes_ask += market.yes_ask_dollars
        else:
            missing_count += 1

    return {
        "total": total_yes_ask,
        "missing_count": missing_count,
        "market_count": len(markets),
    }