import { useEffect, useState, useCallback } from "react";
import { getTradeJournal, updateTradeReview } from "@/lib/api";

interface JournalEntry {
  position_id: string;
  symbol: string;
  side: string;
  signal_kind: string | null;
  signal_strength: number | null;
  signal_idx: number | null;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number | null;
  take_profit_2: number | null;
  risk_reward_ratio: number | null;
  quantity: number;
  analysis_snapshot: string;
  exit_price: number | null;
  exit_reason: string | null;
  realized_pnl: number | null;
  r_multiple: number | null;
  hold_seconds: number | null;
  opened_at: string;
  closed_at: string | null;
  review_tags: string;
  review_notes: string;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h${m}m`;
  return `${m}m`;
}

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
}

function SnapshotViewer({ raw }: { raw: string }) {
  const [expanded, setExpanded] = useState(false);
  let data: Record<string, unknown> | null = null;
  try {
    data = JSON.parse(raw);
  } catch {
    return <span className="text-text-muted text-xs">无效数据</span>;
  }
  if (!data || !Object.keys(data).length) {
    return <span className="text-text-muted text-xs">无分析快照</span>;
  }

  const signal = data.signal as Record<string, unknown> | undefined;
  const structure = data.structure as Record<string, unknown> | undefined;
  const market = data.market as Record<string, unknown> | undefined;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-accent hover:underline"
        >
          {expanded ? "收起" : "查看依据"}
        </button>
        {signal && (
          <span className="text-xs text-text-muted">
            {String(signal.kind || "")} #{String(signal.idx ?? "")}
          </span>
        )}
        {structure && (
          <span className="text-xs text-text-muted">
            {String(structure.zhongshu_count ?? 0)}中枢 {String(structure.divergence_count ?? 0)}背驰
          </span>
        )}
      </div>
      {expanded && (
        <pre className="rounded bg-bg-deep/80 p-2 text-xs text-text-muted overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ReviewEditor({
  entry,
  onSaved,
}: {
  entry: JournalEntry;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [tags, setTags] = useState(entry.review_tags);
  const [notes, setNotes] = useState(entry.review_notes);
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await updateTradeReview(entry.position_id, tags, notes);
      setEditing(false);
      onSaved();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  }, [entry.position_id, tags, notes, onSaved]);

  if (!editing) {
    return (
      <div className="space-y-1">
        {entry.review_tags && (
          <div className="text-xs text-text-muted">标签: {entry.review_tags}</div>
        )}
        {entry.review_notes && (
          <div className="text-xs text-text-muted whitespace-pre-wrap">
            复盘: {entry.review_notes}
          </div>
        )}
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-accent hover:underline"
        >
          {entry.review_tags || entry.review_notes ? "编辑复盘" : "添加复盘"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <input
        type="text"
        value={tags}
        onChange={(e) => setTags(e.target.value)}
        placeholder="标签 (逗号分隔)"
        className="w-full rounded border border-border-subtle bg-bg-deep px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
      />
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="复盘笔记..."
        rows={2}
        className="w-full rounded border border-border-subtle bg-bg-deep px-2 py-1 text-xs text-text-primary outline-none focus:border-accent resize-none"
      />
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-accent/20 px-2 py-0.5 text-xs text-accent hover:bg-accent/30 disabled:opacity-50"
        >
          {saving ? "保存中..." : "保存"}
        </button>
        <button
          onClick={() => setEditing(false)}
          className="text-xs text-text-muted hover:text-text-primary"
        >
          取消
        </button>
      </div>
    </div>
  );
}

function JournalCard({ entry, onSaved }: { entry: JournalEntry; onSaved: () => void }) {
  const isClosed = entry.closed_at != null;
  const pnl = entry.realized_pnl ?? 0;
  const isLong = entry.side === "LONG";

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-card/50 p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">{entry.symbol}</span>
          <span
            className={`rounded px-1.5 py-0.5 text-xs font-medium ${
              isLong ? "bg-positive/15 text-positive" : "bg-negative/15 text-negative"
            }`}
          >
            {entry.side}
          </span>
          {entry.signal_kind && (
            <span className="text-xs text-text-muted">{entry.signal_kind}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isClosed && (
            <span className={`text-xs font-medium ${pnl >= 0 ? "text-positive" : "text-negative"}`}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
            </span>
          )}
          <span
            className={`h-1.5 w-1.5 rounded-full ${isClosed ? "bg-text-muted" : "bg-positive"}`}
          />
        </div>
      </div>

      {/* Price grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-text-muted">入场</span>
          <span className="text-text-primary">{formatPrice(entry.entry_price)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">止损</span>
          <span className="text-text-primary">{formatPrice(entry.stop_loss)}</span>
        </div>
        {entry.exit_price != null && (
          <div className="flex justify-between">
            <span className="text-text-muted">出场</span>
            <span className="text-text-primary">{formatPrice(entry.exit_price)}</span>
          </div>
        )}
        {entry.risk_reward_ratio != null && (
          <div className="flex justify-between">
            <span className="text-text-muted">R:R</span>
            <span className="text-text-primary">{entry.risk_reward_ratio.toFixed(1)}</span>
          </div>
        )}
        {entry.r_multiple != null && (
          <div className="flex justify-between">
            <span className="text-text-muted">实际R</span>
            <span className={entry.r_multiple >= 0 ? "text-positive" : "text-negative"}>
              {entry.r_multiple.toFixed(2)}R
            </span>
          </div>
        )}
        {entry.hold_seconds != null && (
          <div className="flex justify-between">
            <span className="text-text-muted">持仓</span>
            <span className="text-text-primary">{formatDuration(entry.hold_seconds)}</span>
          </div>
        )}
      </div>

      {/* Exit reason */}
      {entry.exit_reason && (
        <div className="text-xs text-text-muted">
          出场原因: <span className="text-text-primary">{entry.exit_reason}</span>
        </div>
      )}

      {/* Analysis snapshot */}
      <SnapshotViewer raw={entry.analysis_snapshot} />

      {/* Review */}
      {isClosed && <ReviewEditor entry={entry} onSaved={onSaved} />}
    </div>
  );
}

export function TradeJournal() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSymbol, setFilterSymbol] = useState<string>("");

  const fetchJournal = useCallback(async () => {
    try {
      const data = await getTradeJournal(100, filterSymbol || undefined);
      const list = (data as { journal?: JournalEntry[] }).journal ?? [];
      setEntries(list);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [filterSymbol]);

  useEffect(() => {
    fetchJournal();
  }, [fetchJournal]);

  const symbols = ["", "SOLUSDT"];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="section-label">交易日志</div>
        <select
          value={filterSymbol}
          onChange={(e) => {
            setFilterSymbol(e.target.value);
            setLoading(true);
          }}
          className="rounded border border-border-subtle bg-bg-deep px-2 py-1 text-xs text-text-primary outline-none"
        >
          {symbols.map((s) => (
            <option key={s} value={s}>
              {s || "全部标的"}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="py-4 text-center text-sm text-text-muted">加载中...</div>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-border-subtle bg-bg-card/50 p-4 text-center text-sm text-text-muted">
          暂无交易记录
        </div>
      ) : (
        <div className="space-y-2.5">
          {entries.map((e) => (
            <JournalCard key={e.position_id} entry={e} onSaved={fetchJournal} />
          ))}
        </div>
      )}
    </div>
  );
}
