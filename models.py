from pydantic import BaseModel, computed_field
from datetime import datetime, timezone
from typing import Optional

DATE_KEYS = ("Date", "Before")
DATE_FORMAT = "%b %d, %Y"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
BEFORE_PHRASES = ("before", "earlier", "sooner")
AFTER_PHRASES = ("after", "later")


class MarketSchema(BaseModel):
    ticker: str
    event_ticker: str
    yes_ask_dollars: Optional[float] = None
    yes_ask_size_fp: Optional[float] = None
    yes_bid_dollars: Optional[float] = None
    yes_bid_size_fp: Optional[float] = None
    no_ask_dollars: Optional[float] = None
    no_ask_size_fp: Optional[float] = None
    no_bid_dollars: Optional[float] = None
    volume_24h_fp: Optional[float] = None
    strike_type: Optional[str] = None
    floor_strike: Optional[float] = None
    cap_strike: Optional[float] = None
    status: Optional[str] = None
    custom_strike: Optional[dict] = None
    yes_sub_title: Optional[str] = None

    @computed_field
    @property
    def strike_date(self) -> Optional[datetime]:
        if not self.custom_strike:
            return None

        for key in DATE_KEYS:
            raw = self.custom_strike.get(key)
            if raw is None:
                continue
            try:
                parsed = datetime.strptime(raw, DATE_FORMAT)
                return parsed.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

        return None

    @computed_field
    @property
    def date_direction_unconfirmed(self) -> bool:
        if self.strike_date is None or not self.yes_sub_title:
            return True

        subtitle = self.yes_sub_title.lower()

        if any(token in subtitle for token in AFTER_PHRASES):
            return True

        return not any(token in subtitle for token in BEFORE_PHRASES)

    @computed_field
    @property
    def effective_cap(self) -> Optional[float]:
        if self.cap_strike is not None:
            return self.cap_strike
        if self.strike_date is not None and self.floor_strike is None:
            return float((self.strike_date - EPOCH).days)
        return None

    @computed_field
    @property
    def market_structure(self) -> str:
        cap = self.effective_cap

        if self.floor_strike is not None and cap is not None:
            return "between"
        if self.floor_strike is not None:
            return "greater"
        if cap is not None:
            return "less"
        return "custom"
class EventSchema(BaseModel):
    event_ticker: str
    series_ticker: str
    mutually_exclusive: bool
    markets: list[MarketSchema]
    category: Optional[str] = None
    title: Optional[str] = None
    fee_type_override: Optional[str] = None
    fee_multiplier_override: Optional[int] = None

class SeriesFee(BaseModel):
    ticker: str
    fee_multiplier: float
    fee_type: str