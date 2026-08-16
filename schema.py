from pydantic import BaseModel
from typing import Optional

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

class EventSchema(BaseModel):
    event_ticker: str
    mutually_exclusive: bool
    markets: list[MarketSchema]
    category: Optional[str] = None
    title: Optional[str] = None