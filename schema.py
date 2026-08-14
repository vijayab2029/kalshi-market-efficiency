from pydantic import BaseModel
from typing import Optional

class MarketSchema(BaseModel):
    ticker: str
    event_ticker: str
    yes_ask_dollars: Optional[float] = None
    yes_bid_dollars: Optional[float] = None

class EventSchema(BaseModel):
    event_ticker: str
    mutually_exclusive: bool
    markets: list[MarketSchema]