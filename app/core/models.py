from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Market(str, Enum):
    CRYPTO = "crypto"


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class PointType(str, Enum):
    TOP = "TOP"
    BOTTOM = "BOTTOM"


class SignalSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


SUPPORTED_SYMBOLS = {"BTCUSDT", "ETHUSDT"}


class Candle(BaseModel):
    open_time: int
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_idx: Optional[int] = None
    high_idx: Optional[int] = None
    low_idx: Optional[int] = None


class Fractal(BaseModel):
    idx: int
    norm_idx: int
    type: PointType
    price: float
    time: str


class Stroke(BaseModel):
    start_idx: int
    end_idx: int
    norm_start_idx: Optional[int] = None
    norm_end_idx: Optional[int] = None
    start_price: float
    end_price: float
    direction: Direction


class Segment(BaseModel):
    start_bi: int
    end_bi: int
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    direction: Direction
    confirmed: bool = True


class Pivot(BaseModel):
    start_bi: int
    end_bi: int
    start_idx: int
    end_idx: int
    zg: float
    zd: float
    entry_seg_idx: Optional[int] = None
    leave_seg_idx: Optional[int] = None
    direction: Optional[Direction] = None


class Divergence(BaseModel):
    direction: Direction
    pivot_idx: int
    entry_seg_idx: int
    leave_seg_idx: int
    idx: int
    price: float
    entry_area: float
    leave_area: float
    ratio: float
    description: str


class MacdPoint(BaseModel):
    dif: float
    dea: float
    hist: float


class Signal(BaseModel):
    side: SignalSide
    kind: Literal["first", "second", "third", "td9"]
    idx: int
    time: str
    price: float
    description: str
    strength: float = Field(ge=0)
    pivot_idx: Optional[int] = None
    entry_seg_idx: Optional[int] = None
    leave_seg_idx: Optional[int] = None
    macd_ratio: Optional[float] = None
    evidence: Optional[str] = None


class TdSummary(BaseModel):
    setup_up: int
    setup_down: int
    last_signal: Optional[Signal] = None


class AnalyzeRequest(BaseModel):
    market: Market = Market.CRYPTO
    symbol: str = "BTCUSDT"
    interval: str = "1"
    limit: int = Field(default=1000, ge=100, le=1000)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 30:
            raise ValueError("symbol must be a non-empty trading pair")
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("symbol contains unsupported characters")
        if value not in SUPPORTED_SYMBOLS:
            raise ValueError("symbol must be BTCUSDT or ETHUSDT")
        return value

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: str) -> str:
        allowed = {"1", "15", "30"}
        if value not in allowed:
            raise ValueError(f"interval must be one of {sorted(allowed)}")
        return value


class AnalyzeResponse(BaseModel):
    success: bool = True
    market: Market
    symbol: str
    interval: str
    current_price: float
    data_source: str
    rules_version: str
    kline_data: list[Candle]
    macd_data: list[MacdPoint]
    fractals: list[Fractal]
    bis: list[Stroke]
    active_bi: Optional[Stroke] = None
    segments: list[Segment]
    divergences: list[Divergence]
    bis_lv2: list[Stroke]
    zhongshus: list[Pivot]
    zhongshus_lv2: list[Pivot]
    buy_signals: list[Signal]
    sell_signals: list[Signal]
    td_summary: TdSummary
    warning: Optional[str] = None


class SymbolResponse(BaseModel):
    success: bool = True
    symbols: list[str]
