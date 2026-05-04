from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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

# App-internal interval codes → Binance mapping lives in BinanceRepository.
ALLOWED_ANALYSIS_INTERVALS = frozenset({"1", "15", "30", "60", "240", "1440"})


def normalize_supported_symbol(value: str) -> str:
    value = value.strip().upper()
    if not value or len(value) > 30:
        raise ValueError("symbol must be a non-empty trading pair")
    if not value.replace("-", "").replace("_", "").isalnum():
        raise ValueError("symbol contains unsupported characters")
    if value not in SUPPORTED_SYMBOLS:
        raise ValueError("symbol must be BTCUSDT or ETHUSDT")
    return value


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
    # 合并后的缠论 K 线由哪些原始 K（source_idx）组成，顺序与合并过程一致；未合并时与单根 source 一致。
    merged_from: Optional[list[int]] = None


class Fractal(BaseModel):
    idx: int
    norm_idx: int
    type: PointType
    price: float
    time: str
    confirmed: bool = True
    # 0~1 粗力度，仅基于三根标准化 K 几何与收盘行为，供过滤弱分型（非 chanlun 同款公式）。
    strength_hint: Optional[float] = None


class Stroke(BaseModel):
    start_idx: int
    end_idx: int
    norm_start_idx: Optional[int] = None
    norm_end_idx: Optional[int] = None
    start_price: float
    end_price: float
    direction: Direction
    # bis_lv2：在映射到本级标准化 K 线索引之前，上级（经包含处理）K 线窗口（供区间套时间对齐与审计）。
    higher_origin_bar_lo: Optional[int] = None
    higher_origin_bar_hi: Optional[int] = None
    higher_origin_open_time_lo: Optional[int] = None
    higher_origin_open_time_hi: Optional[int] = None
    # 笔端点之后是否出现收盘价突破端点价（类似「笔停顿」的量化定义）。
    pause_after_end: Optional[bool] = None
    # --- 几何/力度（`stroke_metrics.hydrate_stroke_metrics`，与 czsc BI 量纲类似，公式自研）---
    length_bars: Optional[int] = None
    price_change: Optional[float] = None
    slope_per_bar: Optional[float] = None
    angle_deg: Optional[float] = None
    hypotenuse: Optional[float] = None
    power_price: Optional[float] = None
    power_volume: Optional[float] = None
    rsq_close: Optional[float] = None
    acceleration: Optional[float] = None
    power_snr: Optional[float] = None


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
    # 收盘价相对 [ZD,ZG] 中轴上下侧根数平衡度（0~1），及是否达到对称启发式阈值。
    symmetry_balance: Optional[float] = Field(default=None, ge=0, le=1)
    symmetry_zs: Optional[bool] = None


class FakeBiStroke(BaseModel):
    """笔内部的虚拟笔（次级别结构近似）。"""

    parent_bi_index: int = Field(ge=0)
    start_idx: int
    end_idx: int
    norm_start_idx: Optional[int] = None
    norm_end_idx: Optional[int] = None
    start_price: float
    end_price: float
    direction: Direction


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
    # 趋势背驰：至少两个「堆叠」中枢；否则视为盘整类背驰（单中枢或重叠震荡）。
    structure_kind: Literal["trend", "zpan_like"] = "zpan_like"


class MacdPoint(BaseModel):
    dif: float
    dea: float
    hist: float


class BollingerPoint(BaseModel):
    mid: float
    upper: float
    lower: float


class Signal(BaseModel):
    side: SignalSide
    kind: Literal["first", "second", "second_extend", "third", "second_class", "third_class", "td9"]
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
    structure_kind: Literal["trend", "zpan_like"] = "zpan_like"


class ActionFocusRecentSignal(BaseModel):
    side: SignalSide
    kind: Literal["first", "second", "second_extend", "third", "second_class", "third_class", "td9"]
    idx: int = Field(ge=0)
    time: str


class LinesFormSummary(BaseModel):
    """本级笔走势形态粗分类（见 `lines_form.analyze_lines_form`）。"""

    primary: str
    detail_zh: str = ""
    has_three_stroke_overlap: bool = False
    bi_pivot_count: int = 0
    abc_hint: Optional[str] = None


class IntervalNestSlice(BaseModel):
    """多周期区间套：一根上级笔在蜡烛 index 上覆盖的本级子窗口及本级形态摘要。"""

    higher_stroke_index: int = Field(ge=0)
    higher_direction: Literal["UP", "DOWN"]
    candle_index_lo: int = Field(ge=0)
    candle_index_hi: int = Field(ge=0)
    # 本级为「经包含处理后的 K 线」序列上的索引，与 `bis` / `segments` 一致。
    base_open_time_lo: Optional[int] = None
    base_open_time_hi: Optional[int] = None
    # 上级笔在「经包含处理后的上级 K 线」上的 bar 下标与 open_time（Binance 毫秒开盘时间）。
    higher_bar_index_lo: Optional[int] = None
    higher_bar_index_hi: Optional[int] = None
    higher_open_time_lo: Optional[int] = None
    higher_open_time_hi: Optional[int] = None
    sub_stroke_count: int = Field(default=0, ge=0)
    lines_form_primary: str
    lines_form_detail_zh: str = ""
    bi_pivot_count: int = Field(default=0, ge=0)
    hint_zh: str = ""


class NestedIntervalAnalysis(BaseModel):
    """上级周期笔 → 本级 K 区间对齐 + 本级 `lines_form` 子分析（P0 #1）。"""

    higher_interval: str
    base_interval: str
    slices: list[IntervalNestSlice] = Field(default_factory=list)
    summary_zh: str = ""
    # 时间对齐：上级标准化 K 的 [open_time, next_open_time) 半开区间映射到本级标准化 K 线索引。
    alignment_rule_id: str = "higher_norm_half_open_to_base_norm_index_v1"
    time_axis: Literal["open_time_ms"] = "open_time_ms"


class AbcPart(BaseModel):
    label: Literal["a", "A", "b", "B", "c"]
    from_bi: int = Field(ge=0)
    to_bi: int = Field(ge=0)


class AbcDecomposition(BaseModel):
    """最近两个价域分离的笔中枢上粗分 a+A+b+B+c（算法近似，P0 #2）。"""

    parts: list[AbcPart] = Field(default_factory=list)
    note_zh: str = ""


SegmentTrendTypeCode = Literal[
    "uptrend_zs_stacked",
    "downtrend_zs_stacked",
    "consolidation_zs_overlap",
    "trend_extension_in_zs",
    "directional_extension",
    "neutral_single_segment",
    "mixed_counterstack",
    "mixed_bidirectional_zs",
]


class SegmentTrendRun(BaseModel):
    """线段级同向合并 + 线段中枢（走势中枢代理）上的走势类型可审计判定。"""

    start_seg_index: int = Field(ge=0)
    end_seg_index: int = Field(ge=0)
    direction: Literal["UP", "DOWN"]
    segment_count: int = Field(ge=1)
    run_high: float
    run_low: float
    level: Literal["segment"] = "segment"
    merge_rule: str = "contiguous_same_direction_segments_v1"
    schema_version: str = "chanlan-seg-trend-run-2"
    trend_type_code: SegmentTrendTypeCode = "neutral_single_segment"
    trend_type_note_zh: str = ""
    trend_rule_table_id: str = "seg-zs-stack-overlap-v1"
    segment_engine: str = "legacy"


class TrendRecursionSummary(BaseModel):
    """本级线段走势类型与上级区间套末片形态的递归对照（规则表可版本化）。"""

    composite: Literal[
        "aligned_uptrend",
        "aligned_downtrend",
        "aligned_consolidation",
        "cross_level_divergent",
        "partially_aligned",
        "insufficient_higher_data",
    ]
    note_zh: str = ""
    higher_lines_form_primary: Optional[str] = None
    base_last_run_trend_code: Optional[str] = None
    rule_table_version: str = "cross-level-lines-form-vs-seg-run-v1"


class GapStat(BaseModel):
    """指定蜡烛窗口内向上/向下笔内缺口（相邻 K 不重叠）计数。"""

    stroke_bi_index: int = Field(ge=0)
    candle_lo: int = Field(ge=0)
    candle_hi: int = Field(ge=0)
    up_gaps: int = Field(ge=0)
    down_gaps: int = Field(ge=0)


class ChanAdvancedContext(BaseModel):
    """进阶结构 API：区间套、a+A+b+B+c、Zn、笔停顿、缺口、线段走势段、跨级别走势递归等。"""

    higher_interval: Optional[str] = None
    nested_interval: Optional[NestedIntervalAnalysis] = None
    abc_decomposition: Optional[AbcDecomposition] = None
    segment_trend_runs: list[SegmentTrendRun] = Field(default_factory=list)
    trend_recursion: Optional[TrendRecursionSummary] = None
    zn_last_bi_mid: Optional[float] = None
    zn_note_zh: Optional[str] = None
    bi_pause_hint: Optional[str] = None
    gap_last_bi: Optional[GapStat] = None


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


class KlineParentRef(BaseModel):
    """本级合并 K ↔ 上级标准化 K 的父子对应（按上级 open_time 半开区间落点）。"""

    base_idx: int = Field(ge=0)
    parent_interval: str
    parent_open_time: int
    parent_norm_idx: int = Field(ge=0)


class GlmVerdictInlineOptions(BaseModel):
    """嵌套在 AnalyzeRequest 内；字段与 /ai/verdict 请求体顶层 glm_* 一致。"""

    glm_api_key: Optional[str] = None
    glm_model: Optional[str] = None
    glm_full_context: bool = True


class AnalyzeRequest(BaseModel):
    market: Market = Market.CRYPTO
    symbol: str = "BTCUSDT"
    interval: str = "1"
    limit: int = Field(default=2500, ge=100, le=15000)
    # 若设置，则在同一次 /analyze 内调用智谱并写入响应的 glm_verdict（适合网关不转发 /analyze/verdict 时）。
    glm_verdict: Optional[GlmVerdictInlineOptions] = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_supported_symbol(value)

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: str) -> str:
        if value not in ALLOWED_ANALYSIS_INTERVALS:
            raise ValueError(f"interval must be one of {sorted(ALLOWED_ANALYSIS_INTERVALS)}")
        return value


class AnalyzeResponse(BaseModel):
    success: bool = True
    market: Market
    symbol: str
    interval: str
    current_price: float
    data_source: str
    rules_version: str
    # 与 `CHANLAN_SEGMENT_ENGINE` 一致；`strict67` 为 67 课特征序列线段划分。
    segment_engine: Literal["legacy", "strict67"] = "legacy"
    lines_form: LinesFormSummary
    kline_data: list[Candle]
    macd_data: list[MacdPoint]
    bollinger: list[BollingerPoint] = Field(default_factory=list)
    rsi14: list[Optional[float]] = Field(default_factory=list)
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
    # 始终序列化（避免网关/客户端把 null 字段丢掉后前端读不到）；缺省为空对象而非 null。
    advanced_context: ChanAdvancedContext = Field(default_factory=ChanAdvancedContext)
    kline_parent_refs: list[KlineParentRef] = Field(default_factory=list)
    fake_bis: list[FakeBiStroke] = Field(default_factory=list)
    glm_verdict: Optional["AiVerdictResponse"] = None


class BarAggregateRequest(BaseModel):
    """将传入 K 线按目标分钟周期分桶合成（开盘时间对齐）。"""

    candles: list[Candle]
    target_interval_minutes: int = Field(15, ge=1, le=1440)


class BarAggregateResponse(BaseModel):
    success: bool = True
    candles: list[Candle]
    rule_id: str = "ohlcv_bucket_open_time_ms_v1"


class MultiAnalyzeRequest(BaseModel):
    """并行请求多个周期分析（每个周期单独拉行情；超过 Binance 单次条数时仓储分页）。"""

    market: Market = Market.CRYPTO
    symbol: str = "BTCUSDT"
    intervals: list[str] = Field(default_factory=lambda: ["60", "240", "1440"])
    limit: int = Field(default=2500, ge=100, le=15000)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol_ma(cls, value: str) -> str:
        return normalize_supported_symbol(value)

    @field_validator("intervals")
    @classmethod
    def validate_intervals_ma(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("intervals must be non-empty")
        for interval in values:
            if interval not in ALLOWED_ANALYSIS_INTERVALS:
                raise ValueError(f"unsupported interval: {interval}")
        return values


class MultiAnalyzeResultRow(BaseModel):
    interval: str
    result: AnalyzeResponse


class MultiAnalyzeResponse(BaseModel):
    success: bool = True
    market: Market
    symbol: str
    results: list[MultiAnalyzeResultRow]


class CompactOHLC(BaseModel):
    high: float
    low: float
    close: float


class PositionSizingRequest(BaseModel):
    """给定单笔风险比例与止损价，估算名义头寸规模（现货口径简化模型）。"""

    equity_usdt: float = Field(gt=0)
    risk_fraction: float = Field(gt=0, le=0.2)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)

    @model_validator(mode="after")
    def stop_must_differ(self) -> "PositionSizingRequest":
        if abs(self.entry_price - self.stop_price) < 1e-12:
            raise ValueError("stop_price must differ from entry_price")
        return self


class PositionSizingResponse(BaseModel):
    risk_usdt: float
    suggested_quantity: float
    notional_usdt: float


class TrailingStopRequest(BaseModel):
    direction: Literal["LONG", "SHORT"]
    entry_price: float = Field(gt=0)
    peak_price: Optional[float] = Field(default=None, gt=0)
    trough_price: Optional[float] = Field(default=None, gt=0)
    atr_period: int = Field(default=14, ge=2, le=200)
    atr_multiplier: float = Field(default=2.0, gt=0)
    ohlc_tail: list[CompactOHLC] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tail_length(self) -> "TrailingStopRequest":
        need = self.atr_period + 2
        if len(self.ohlc_tail) < need:
            raise ValueError(f"ohlc_tail must contain at least {need} bars for atr_period={self.atr_period}")
        return self


class TrailingStopResponse(BaseModel):
    atr: float
    stop_price: float
    mode: Literal["atr_trailing"]


class QuickBacktestRequest(BaseModel):
    market: Market = Market.CRYPTO
    symbol: str = "BTCUSDT"
    interval: str = "240"
    max_bars: int = Field(default=8000, ge=500, le=50000)
    strategy: Literal["long_only_flip", "long_short_flip"] = "long_only_flip"
    initial_equity_usdt: float = Field(default=10_000.0, gt=0)
    fee_bps: float = Field(default=10.0, ge=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol_bt(cls, value: str) -> str:
        return normalize_supported_symbol(value)

    @field_validator("interval")
    @classmethod
    def validate_interval_bt(cls, value: str) -> str:
        if value not in ALLOWED_ANALYSIS_INTERVALS:
            raise ValueError(f"interval must be one of {sorted(ALLOWED_ANALYSIS_INTERVALS)}")
        return value


class QuickBacktestTrade(BaseModel):
    bar_idx: int
    time: str
    action: Literal["BUY", "SELL"]
    price: float
    equity_after: float


class QuickBacktestMetrics(BaseModel):
    bars_used: int
    trades: int
    final_equity_usdt: float
    total_return_fraction: float
    max_drawdown_fraction: float
    sharpe_naive: Optional[float] = None


class QuickBacktestResponse(BaseModel):
    success: bool = True
    disclaimer: str = (
        "演示级回测：简化成交价模型与手续费假设；不构成业绩承诺。"
    )
    metrics: QuickBacktestMetrics
    trade_log: list[QuickBacktestTrade]


class PaperOrderRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0)
    note: str = ""

    @field_validator("symbol")
    @classmethod
    def normalize_symbol_po(cls, value: str) -> str:
        return normalize_supported_symbol(value)


class PaperOrderResponse(BaseModel):
    accepted: bool
    reason: str
    order_id: Optional[str] = None


class AiStructureHintRequest(BaseModel):
    """占位：结构语境打分（启发式，非训练模型）。"""

    pivot_count: int = Field(ge=0)
    divergence_count: int = Field(ge=0)
    buy_signal_count: int = Field(ge=0)
    sell_signal_count: int = Field(ge=0)


class AiStructureHintResponse(BaseModel):
    score_0_100: float
    notes: list[str]
    disclaimer: str = "启发式占位接口；非深度学习模型输出。"


class AiVerdictPriceHints(BaseModel):
    """模型给出的结构推演参考价（非成交保证、非投资建议）。"""

    buy_focus_price: Optional[float] = None
    sell_focus_price: Optional[float] = None
    stop_loss_buy: Optional[float] = None
    stop_loss_sell: Optional[float] = None
    note_zh: str = ""


class AiVerdictResponse(BaseModel):
    """GLM / 规则降级的语境裁决（结构披露，非投资建议）。"""

    success: bool = True
    source: Literal["glm", "heuristic_fallback", "disabled"] = "heuristic_fallback"
    bias: Literal["long", "short", "neutral"] = "neutral"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    summary_zh: str = ""
    reasons_zh: list[str] = Field(default_factory=list)
    price_hints: Optional[AiVerdictPriceHints] = None
    model_name: Optional[str] = None
    error_detail: Optional[str] = None
    disclaimer: str = (
        "本结论包含由模型推演的参考价位，仅为缠论结构语境下的数值归纳，不构成证券投资建议，不保证成交与盈亏；须自行承担风险。"
    )


AnalyzeResponse.model_rebuild()


class SymbolResponse(BaseModel):
    success: bool = True
    symbols: list[str]
