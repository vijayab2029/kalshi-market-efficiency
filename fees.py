import requests

from schema import MarketSchema, EventSchema, SeriesFee
from statistics import mean
from enum import Enum
from decimal import Decimal, ROUND_UP, ROUND_FLOOR

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

TAKER_RATE = Decimal("0.07")
CENTICENT = Decimal("0.0001")
CENT = Decimal("0.01")
DEFAULT_FEE_MULTIPLIER = 1


def compute_taker_fee(price: Decimal, num_contracts: Decimal, fee_multiplier: float) -> Decimal:
    fee_multiplier_decimal = Decimal(str(fee_multiplier))
    raw_fee = fee_multiplier_decimal * TAKER_RATE * num_contracts * price * (1 - price)
    return raw_fee.quantize(CENTICENT, rounding=ROUND_UP)


def compute_rounding_fee(price: Decimal, num_contracts: Decimal, trading_fee: Decimal) -> Decimal:
    revenue = -price * num_contracts
    balance_change = revenue - trading_fee
    floored = balance_change.quantize(CENT, rounding=ROUND_FLOOR)
    return balance_change - floored


def apply_rebate(total_rounding_fee: Decimal) -> Decimal:
    cents = (total_rounding_fee / CENT).to_integral_value(rounding=ROUND_FLOOR)
    return cents * CENT


def compute_fees(fills: list[dict], fee_multiplier: int) -> dict:
    total_trading_fee = Decimal("0")
    total_rounding_fee = Decimal("0")

    for fill in fills:
        price = Decimal(str(fill["price"]))
        num_contracts = Decimal(str(fill["num_contracts"]))
        trading_fee = compute_taker_fee(price, num_contracts, fee_multiplier)
        rounding_fee = compute_rounding_fee(price, num_contracts, trading_fee)
        total_trading_fee += trading_fee
        total_rounding_fee += rounding_fee

    rebate = apply_rebate(total_rounding_fee)
    total_fee = total_trading_fee + total_rounding_fee - rebate

    return {
        "trading_fee": float(total_trading_fee),
        "rounding_fee": float(total_rounding_fee),
        "rebate": float(rebate),
        "total_fee": float(total_fee),
    }


#TODO: Consider changing this if adding more advanced depth

def get_best_market_fills(market: MarketSchema) -> dict:
    return {
        "price": market.yes_ask_dollars,
        "num_contracts": 1,
    }

def compute_event_fees(event: EventSchema, fee_multiplier: int) -> dict:
    total_trading_fee = 0.0
    total_rounding_fee = 0.0
    total_rebate = 0.0
    total_fee = 0.0

    for market in event.markets:
        fill = get_best_market_fills(market)
        fee_result = compute_fees([fill], fee_multiplier)
        total_trading_fee += fee_result["trading_fee"]
        total_rounding_fee += fee_result["rounding_fee"]
        total_rebate += fee_result["rebate"]
        total_fee += fee_result["total_fee"]

    return {
        "trading_fee": total_trading_fee,
        "rounding_fee": total_rounding_fee,
        "rebate": total_rebate,
        "total_fee": total_fee,
    }


def get_series_fee(series_ticker: str) -> SeriesFee:
    try:
        response = requests.get(f"{BASE_URL}/series/{series_ticker}")
    except Exception as e:
        print(f"Could not fetch series {series_ticker}: {e}")
        return SeriesFee(
            ticker=series_ticker,
            fee_multiplier=DEFAULT_FEE_MULTIPLIER,
            fee_type="unknown",
        )

    if response.status_code != 200:
        print(f"Incorrect status code for series {series_ticker}: {response.status_code}")
        return SeriesFee(
            ticker=series_ticker,
            fee_multiplier=DEFAULT_FEE_MULTIPLIER,
            fee_type="unknown",
        )

    data = response.json()["series"]
    return SeriesFee(
        ticker=series_ticker,
        fee_multiplier=data.get("fee_multiplier", DEFAULT_FEE_MULTIPLIER),
        fee_type=data.get("fee_type", "unknown"),
    )

def determine_fee_multiplier(event: EventSchema, series_fee_store: dict) -> int:
    if event.fee_multiplier_override is not None:
        return event.fee_multiplier_override

    series_ticker = event.series_ticker
    if series_ticker in series_fee_store:
        series_fee = series_fee_store[series_ticker]
    else:
        series_fee = get_series_fee(series_ticker)
        series_fee_store[series_ticker] = series_fee

    return series_fee.fee_multiplier

def fetch_all_series() -> dict[str, SeriesFee]:
    try:
        response = requests.get(f"{BASE_URL}/series", timeout=10)
    except Exception as e:
        print(f"Failed to fetch series list: {e}")
        return {}

    if response.status_code != 200:
        print(f"Wrong status code fetching series list: {response.status_code}")
        return {}

    data = response.json()
    series_fee_store = {}

    for entry in data.get("series", []):
        ticker = entry.get("ticker")
        if ticker is None:
            continue

        series_fee_store[ticker] = SeriesFee(
            ticker=ticker,
            fee_multiplier=entry.get("fee_multiplier", DEFAULT_FEE_MULTIPLIER),
            fee_type=entry.get("fee_type", "unknown"),
        )

    return series_fee_store