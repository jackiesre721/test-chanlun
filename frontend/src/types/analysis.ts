// ── API response types (matching FastAPI backend actual field names) ──

export interface KlineBar {
  time: string | number;
  open_time?: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Fractal {
  idx: number;
  norm_idx?: number;
  type: "TOP" | "BOTTOM";
  confirmed: boolean;
  price: number;
  strength_hint?: number;
  open_time?: number;
}

export interface Stroke {
  start_idx: number;
  end_idx: number;
  norm_start_idx?: number;
  norm_end_idx?: number;
  direction: "up" | "down" | "UP" | "DOWN";
  start_price: number;
  end_price: number;
  pause_after_end?: boolean;
  is_active?: boolean;
  open_time?: number;
  is_fake?: boolean;
  start_bi?: number;
  end_bi?: number;
}

export interface Segment {
  start_idx: number;
  end_idx: number;
  direction: "up" | "down";
  start_price: number;
  end_price: number;
  open_time?: number;
}

export interface Pivot {
  zd: number;
  zg: number;
  start_idx: number;
  end_idx: number;
  level: "bi" | "segment";
  direction?: string;
}

export interface Divergence {
  idx: number;
  price: number;
  direction: "DOWN" | "UP" | "down" | "up";
  structure_kind?: string;
  description?: string;
  level?: string;
  macd_ratio?: number;
  open_time?: number;
}

export interface Signal {
  idx: number;
  side: "BUY" | "SELL";
  kind: string;
  price: number;
  level?: "bi" | "segment" | "higher_bi";
  pivot_level?: "bi" | "segment" | null;
  description?: string;
  evidence?: string;
  open_time?: number;
  stop_loss?: number;
  take_profit?: number;
  risk_reward_ratio?: number;
}

export interface MacdBar {
  hist: number;
  dif: number;
  dea: number;
}

export interface BollingerBar {
  upper: number;
  mid: number;
  lower: number;
}

export interface LinesForm {
  primary: string;
  detail_zh?: string;
  abc_hint?: string;
}

/** 与后端 `ActionFocusPivotRef` / `ActionFocusPivotSlot` 一致：ZD/ZG 在嵌套 `pivot` 上 */
export interface ActionFocusPivotRef {
  level?: string;
  zd?: number;
  zg?: number;
  start_idx?: number;
  end_idx?: number;
}

export interface ActionFocusPivotSlot {
  relation: string;
  pivot?: ActionFocusPivotRef | null;
}

export interface ActionFocus {
  last_bar_index?: number;
  recent_window_bars?: number;
  /** 后端字段名为 current_price；旧前端可能用 price */
  current_price?: number;
  price?: number;
  active_bi?: { direction: string; start_price?: number; end_price?: number } | null;
  primary_pivot?: ActionFocusPivotSlot | null;
  higher_pivot?: ActionFocusPivotSlot | null;
  recent_divergence?: {
    level: string;
    direction: string;
    idx?: number;
    ratio?: number;
    macd_ratio?: number;
    structure_kind?: string;
  } | null;
  recent_signal?: { kind: string; side: string; idx: number; time: string; price?: number; stop_loss?: number; stop_loss_2?: number; take_profit_1?: number; take_profit_2?: number } | null;
}

export interface AdvancedContext {
  nested_interval?: unknown[];
  aAbBc?: unknown[];
  segment_trend_runs?: unknown[];
  trend_recursion?: unknown;
  zn?: unknown[];
  bi_pauses?: unknown[];
  gaps?: unknown[];
  lines_form?: string;
  detail_zh?: string;
  abc_hint?: string;
  higher_interval?: string;
  rules_version?: string;
  segment_engine?: string;
  fake_bi_count?: number;
  zhongshu_symmetry?: Record<string, number>;
  __clientAdvancedFallback?: boolean;
}

export interface AnalyzeResult {
  success?: boolean;
  error?: { message: string };
  kline_data: KlineBar[];
  bis: Stroke[];
  active_bi?: Stroke;
  segments: Segment[];
  fractals: Fractal[];
  buy_signals: Signal[];
  sell_signals: Signal[];
  zhongshus: Pivot[];
  segment_zhongshus?: Pivot[];
  zhongshus_lv2?: Pivot[];
  divergences: Divergence[];
  bi_pauses?: unknown[];
  fake_bis?: Stroke[];
  bis_lv2?: Stroke[];
  macd_data: MacdBar[];
  bollinger?: BollingerBar[];
  rsi14?: number[];
  current_price: number;
  data_source?: string;
  warning?: string;
  lines_form?: LinesForm;
  detail_zh?: string;
  abc_hint?: string;
  action_focus?: ActionFocus;
  advanced_context?: AdvancedContext;
  rules_version?: string;
  segment_engine?: string;
  meta?: {
    source?: string;
    rules_version?: string;
    segment_engine?: string;
    bar_count?: number;
    symbol?: string;
    interval?: number;
  };
}

// ── Other API types ──

export interface PositionSizeRequest {
  equity: number;
  risk_fraction: number;
  entry_price: number;
  stop_price: number;
  leverage?: number;
  maint_margin_rate?: number;
}

export interface PositionSizeResponse {
  quantity: number;
  notional: number;
  risk_amount: number;
  leverage: number;
  required_margin?: number;
  liquidation_price?: number;
  effective_risk_pct?: number;
  warnings?: string[];
}

export interface PaperTradeRequest {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  note?: string;
}

export interface PaperTradeRecord {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  note?: string;
  created_at: string;
}

export interface BacktestRequest {
  symbol: string;
  interval: string;
  strategy: "long_only_flip" | "long_short_flip";
  initial_equity_usdt: number;
  fee_bps: number;
  leverage?: number;
  trade_amount_usdt?: number;
  start_time_ms?: number;
  end_time_ms?: number;
}

export interface BacktestTrade {
  bar_idx: number;
  time: string;
  action: "BUY" | "SELL";
  price: number;
  equity_after: number;
  exit_reason: "signal" | "stop_loss" | "liquidation";
  quantity: number;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
}

export type BacktestExecTrade = BacktestTrade;

export interface BacktestMetrics {
  bars_used: number;
  trades: number;
  final_equity_usdt: number;
  total_return_fraction: number;
  max_drawdown_fraction: number;
  sharpe_naive?: number | null;
  win_rate?: number | null;
  profit_factor?: number | null;
  stop_loss_hits: number;
}

export interface BacktestRoundTrip {
  entry_bar_idx: number;
  exit_bar_idx: number;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  side: "LONG" | "SHORT";
  pnl_usdt: number;
  pnl_pct: number;
  bars_held: number;
  signal_kind_at_entry: string;
}

export interface BacktestResult {
  success: boolean;
  disclaimer: string;
  metrics: BacktestMetrics;
  trade_log: BacktestTrade[];
  closed_trades?: BacktestRoundTrip[];
  stats_by_signal_kind?: Record<string, { count: number; wins: number; losses: number; win_rate: number; avg_pnl_usdt: number }>;
}

export interface SymbolOption {
  symbol: string;
  name?: string;
}

export interface GlmVerdict {
  headline?: string;
  sub?: string;
  bias?: string;
  confidence?: string;
  price_hints?: string;
  reasoning?: string;
  raw?: string;
}
