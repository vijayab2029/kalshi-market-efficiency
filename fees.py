
from schema import MarketSchema, EventSchema, SeriesFee
from statistics import mean
from enum import Enum
from decimal import Decimal, ROUND_UP, ROUND_FLOOR

TAKER_RATE = Decimal("0.07")
CENTICENT = Decimal("0.0001")
CENT = Decimal("0.01")


def compute_taker_fee(price: Decimal, num_contracts: Decimal, fee_multiplier: int) -> Decimal:
    raw_fee = fee_multiplier * TAKER_RATE * num_contracts * price * (1 - price)
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

def get_best_market_fills(market: MarketSchema) -> dict:
    return {
        "price": market.yes_ask_dollars,
        "num_contracts": market.yes_ask_size_fp,
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