import { useState, useEffect } from "react";
import { Card, CardContent, Input, Button } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { postPaperTrade, getPaperRecent } from "@/lib/api";
import { fmtOpenTime } from "@/lib/format";
import type { PaperTradeRecord } from "@/types/analysis";

export function PaperTradingCard() {
  const symbol = useSettingsStore((s) => s.symbol);
  const [qty, setQty] = useState("");
  const [note, setNote] = useState("");
  const [records, setRecords] = useState<PaperTradeRecord[]>([]);
  const [status, setStatus] = useState("");

  const loadRecent = async () => {
    try {
      const recs = await getPaperRecent();
      setRecords(recs.slice(0, 10));
    } catch { /* ignore */ }
  };

  const trade = async (side: "BUY" | "SELL") => {
    const q = Number(qty);
    if (!q || q <= 0) { setStatus("请输入有效数量"); return; }
    try {
      await postPaperTrade({ symbol, side, quantity: q, note: note || undefined });
      setStatus(`${side} ${q} ${symbol} 成功`);
      setQty("");
      setNote("");
      loadRecent();
    } catch (e: any) {
      setStatus(e.message);
    }
  };

  useEffect(() => { loadRecent(); }, []);

  return (
    <Disclosure defaultOpen={false}>
      <Card className="card-glow bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="section-label cursor-pointer hover:text-accent transition-colors" style={{ padding: "10px 12px 8px" }}>
            纸盘记账（本地）
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              写入服务端 SQLite，非交易所实盘；用于演练流程与复盘。
            </p>
            <Input aria-label="纸盘交易数量" placeholder="数量 (如 0.01)" type="number" value={qty} onChange={(e) => setQty(e.target.value)} className="text-sm" />
            <Input aria-label="纸盘备注" placeholder="备注（可选）" value={note} onChange={(e) => setNote(e.target.value)} className="text-sm" />
            <div className="flex gap-2">
              <Button size="sm" variant="bordered" className="text-success border-success/30" onPress={() => trade("BUY")}>模拟买入</Button>
              <Button size="sm" variant="bordered" className="text-danger border-danger/30" onPress={() => trade("SELL")}>模拟卖出</Button>
              <Button size="sm" variant="light" onPress={loadRecent}>刷新</Button>
            </div>
            {status && <div className="text-xs text-text-muted">{status}</div>}
            {records.length > 0 && (
              <div className="space-y-1 mt-2">
                {records.map((r) => (
                  <div key={r.id} className="text-[10px] text-text-muted flex gap-2">
                    <span className={r.side === "BUY" ? "text-success" : "text-danger"}>{r.side}</span>
                    <span>{r.quantity} @ {Number(r.price).toFixed(2)}</span>
                    <span className="ml-auto">{fmtOpenTime(new Date(r.created_at).getTime())}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
