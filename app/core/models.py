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
    level: Literal["bi", "segment"] = "segment"
    entry_seg_idx: Optional[int] = None
    leave_seg_idx: Optional[int] = None
    direction: Optional[Direction] = None


class Divergence(BaseModel):
    level: Literal["bi", "segment"] = "segment"
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
    pivot_level: Optional[Literal["bi", "segment"]] = None
    pivot_idx: Optional[int] = None
    entry_seg_idx: Optional[int] = None
    leave_seg_idx: Optional[int] = None
    macd_ratio: Optional[float] = None
    evidence: Optional[str] = None


class TdSummary(BaseModel):
    setup_up: int
    setup_down: int
    last_signal: Optional[Signal] = None


class ActionFocusPivotRef(BaseModel):
    """用于「当下关注点」的中枢引用（来自本级或映射后的上级中枢）。"""

    level: Literal["bi", "segment"]
    zd: float
    zg: float
    start_idx: int = Field(ge=0)
    end_idx: int = Field(ge=0)


class ActionFocusPivotSlot(BaseModel):
    """价格相对某一参考中枢的位置。"""

    relation: Literal["inside", "above", "below", "none"]
    pivot: Optional[ActionFocusPivotRef] = None


class ActionFocusActiveBi(BaseModel):
    direction: Direction
    start_price: float
    end_price: float


class ActionFocusRecentDivergence(BaseModel):
    level: Literal["bi", "segment"]
    direction: Direction
    idx: int = Field(ge=0)
    ratio: float


class ActionFocusRecentSignal(BaseModel):
    side: SignalSide
    kind: Literal["first", "second", "third", "td9"]
    idx: int = Field(ge=0)
    time: str


class ActionFocus(BaseModel):
    """当前 K 线末端的结构与证据语境（非交易建议）。"""

    last_bar_index: int = Field(ge=0)
    recent_window_bars: int = Field(ge=1)
    current_price: float
    primary_pivot: ActionFocusPivotSlot
    higher_pivot: ActionFocusPivotSlot
    active_bi: Optional[ActionFocusActiveBi] = None
    recent_divergence: Optional[ActionFocusRecentDivergence] = None
    recent_signal: Optional[ActionFocusRecentSignal] = None


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
    action_focus: ActionFocus
    warning: Optional[str] = None


class SymbolResponse(BaseModel):
    success: bool = True
    symbols: list[str]
