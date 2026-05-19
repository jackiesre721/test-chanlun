import { useTradingStore } from "@/stores/trading-store";

const SYMBOLS = ["SOLUSDT"] as const;

function fmtPrice(symbol: string, price: number | undefined): string {
  if (price == null || price === 0) return "—";
  if (symbol === "DOGEUSDT") return price.toFixed(5);
  if (symbol === "XAUUSDT") return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (symbol === "SOLUSDT") return price.toFixed(2);
  if (symbol === "ETHUSDT") return price.toFixed(2);
  return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function PriceBar() {
  const prices = useTradingStore((s) => s.prices);

  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 rounded-lg border border-border-subtle bg-bg-card px-3 py-2">
      {SYMBOLS.map((sym) => {
        const price = prices[sym];
        return (
          <div key={sym} className="flex items-center gap-1 text-xs">
            <span className="font-medium text-text-muted">{sym.replace("USDT", "")}</span>
            <span className="tabular-nums text-text-primary">{fmtPrice(sym, price)}</span>
          </div>
        );
      })}
    </div>
  );
}
