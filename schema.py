from pydantic import BaseModel, computed_field
from typing import Optional

class EventSchema(BaseModel):
    event_ticker: str
    mutually_exclusive: bool
    markets: list[MarketSchema]
    category: Optional[str] = None
    title: Optional[str] = None
class MarketSchema(BaseModel):
    ticker: str
    event_ticker: str
    yes_ask_dollars: Optional[float] = None
    yes_bid_dollars: Optional[float] = None
    no_ask_dollars: Optional[float] = None
    strike_type: Optional[str] = None
    floor_strike: Optional[float] = None
    cap_strike: Optional[float] = None
    status: Optional[str] = None

    @computed_field
    @property
    def market_structure(self) -> str:
        if self.floor_strike is not None and self.cap_strike is not None:
            return "between"
        if self.floor_strike is not None:
            return "greater"
        if self.cap_strike is not None:
            return "less"
        return "custom"