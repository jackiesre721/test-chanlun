from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Chanlan"
    binance_base_url: str = "https://api.binance.com"
    request_timeout_seconds: float = Field(default=12.0, gt=0)
    max_klines_limit: int = Field(default=1000, ge=100, le=1000)
    # /analyze 允许请求的合并 K 数量上限（Binance 单次最多 max_klines_limit，仓储侧会自动分页）。
    analyze_max_bars: int = Field(default=5000, ge=500, le=15000)
    divergence_ratio: float = Field(default=0.8, gt=0, le=1)
    divergence_min_breakout_ratio: float = Field(default=0.05, ge=0)
    pivot_dedupe_overlap_ratio: float = Field(default=0.95, gt=0, le=1)

    backtest_max_bars: int = Field(default=30_000, ge=1000, le=500_000)
    paper_trading_enabled: bool = Field(default=True)
    live_trading_enabled: bool = Field(default=False)
    paper_orders_db_path: str = Field(default=".cache/chanlan/paper_orders.sqlite")
    paper_orders_max_rows: int = Field(default=5000, ge=0, le=500_000)

    # 24 课：用 MACD 判背驰时，中枢段 B 往往把黄白线（DIF）拉回 0 轴附近；默认关闭以免误杀信号。
    divergence_require_pivot_macd_zero_axis: bool = Field(default=False)
    divergence_macd_zero_axis_abs: float = Field(default=0.02, ge=0)

    # 线段：`legacy` 为早期三笔重叠延伸；`strict67` 为 67 课特征序列分型（情形一 + 情形二扫描，未命中则回退 legacy 延伸）。
    segment_engine: Literal["legacy", "strict67"] = Field(default="legacy")

    # 背驰：可选要求离开段相对进入段，MACD 柱与 DIF 的峰值同时收缩（chanlun-pro 多维度力度思路的简化版）。
    divergence_require_macd_extrema_shrink: bool = Field(default=False)
    divergence_macd_extrema_max_ratio: float = Field(default=0.95, gt=0, le=1.0)
    # 峰值闸门是否同时约束 DEA（黄线）。
    divergence_macd_extrema_require_dea: bool = Field(default=False)
    # MACD 背驰度量：area / hump / peak(|hist|最大) / slope(价变/根数)；either=面积或驼峰；both=二者同时；
    # either_loose=面积/驼峰/峰值/斜率任一满足；peak|slope 单用对应指标。
    divergence_macd_metric: Literal[
        "area", "hump", "peak", "slope", "either", "either_loose", "both"
    ] = Field(default="area")

    # 最后两根标准化 K 上检测「进行中」分型（不参与严格几何完成判定，仅供展示/辅助笔预处理）。
    fractal_include_tentative: bool = Field(default=True)
    # 合并夹在中间的浅反向笔（相对相邻同向笔幅度过小时折叠为一笔）。
    stroke_collapse_shallow_reversal: bool = Field(default=True)
    stroke_collapse_middle_max_ratio: float = Field(default=0.22, gt=0, lt=1.0)

    # 离开段内要求 DIF 相对零轴贴近或穿越（可与中枢零轴闸门同时开）。
    divergence_require_leave_segment_zero_cross: bool = Field(default=False)

    # 无笔中枢时：两段同向笔「不创新高/低 + 力度减弱」的盘整一类信号（T1P）。
    enable_t1p_pan_first_signals: bool = Field(default=True)

    # 67 课特征序列分型：第三元素须相对第二元素真正突破（过滤包含合并假分型）。
    segment_feature_require_actual_break: bool = Field(default=True)

    # 中枢：去重后再合并「笔序相邻且价带相交」的同级中枢为一段（ZD/ZG 取交集）。
    pivot_merge_adjacent_overlaps: bool = Field(default=True)

    # BSP / 程序买卖点细规则（与一类背驰、二/三类链配合）。
    bsp1_only_multibi_zs: bool = Field(default=False)
    # 中枢跨度：end_bi - start_bi ≥ 该值才允许将背驰计为一买/一卖类信号（0 表示关闭宽度闸门）。
    bsp1_min_stroke_span: int = Field(default=2, ge=0)

    # 二类「延伸」：同一中枢语境下，二买/二卖确认后再次抬高低点/压低高点的同类结构（T2S）。
    enable_t2s_second_extend: bool = Field(default=True)

    # MACD 序列缓存：多次 analyze 相同尾部窗口时减重复计算（0=关闭）。
    macd_cache_max_entries: int = Field(default=64, ge=0, le=10_000)

    # 智谱 GLM：`POST /ai/verdict`；`anthropic` 为 Claude API 兼容（推荐），`openai_compat` 为旧版 paas/v4/chat/completions。
    zhipu_api_key: str = ""
    zhipu_api_mode: Literal["anthropic", "openai_compat"] = "anthropic"
    zhipu_api_base: str = "https://open.bigmodel.cn/api/anthropic"
    zhipu_model: str = "glm-4.7"
    ai_verdict_timeout_seconds: float = Field(default=45.0, gt=2.0, le=120.0)

    analyze_disk_cache_enabled: bool = Field(default=True)
    analyze_disk_cache_dir: str = Field(default=".cache/analyze")
    analyze_disk_cache_max_files: int = Field(default=80, ge=0, le=10_000)

    model_config = SettingsConfigDict(env_prefix="CHANLAN_", env_file=".env", extra="ignore")


settings = Settings()
