import { create } from "zustand";
import { getAccountSummary, getPositions } from "@/lib/api";

export interface Position {
  position_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  quantity: number;
  stop_loss: number;
  take_profit_1: number | null;
  take_profit_2: number | null;
  trailing_stop: number | null;
  peak_price: number | null;
  trough_price: number | null;
  margin_used: number;
  leverage: number;
  status: string;
  opened_at: string;
  realized_pnl: number;
  signal_kind: string | null;
  reductions_done: string;
}

export interface AccountSummary {
  initial_equity: number;
  current_equity: number;
  available_balance: number;
  unrealized_pnl: number;
  open_positions: number;
  total_realized_pnl: number;
  daily_pnl: number;
  daily_trades: number;
}

interface WsMessage {
  type: string;
  symbol?: string;
  price?: number;
  positions?: Position[];
  account?: AccountSummary;
}

interface TradingState {
  connected: boolean;
  account: AccountSummary | null;
  positions: Position[];
  prices: Record<string, number>;
  ws: WebSocket | null;

  connect: () => void;
  disconnect: () => void;
  _setConnected: (v: boolean) => void;
  _setAccount: (a: AccountSummary) => void;
  _setPositions: (p: Position[]) => void;
  _updatePrice: (symbol: string, price: number) => void;
}

export const useTradingStore = create<TradingState>()((set, get) => ({
  connected: false,
  account: null,
  positions: [],
  prices: {},
  ws: null,

  _setConnected: (v) => set({ connected: v }),
  _setAccount: (a) => set({ account: a }),
  _setPositions: (p) => set({ positions: p }),
  _updatePrice: (symbol, price) =>
    set((s) => ({ prices: { ...s.prices, [symbol]: price } })),

  connect: () => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/trading`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      get()._setConnected(true);
      // Fetch initial state via REST
      getPositions().then((res) => {
        const all = (res as { positions?: Position[] }).positions ?? [];
        const active = all.filter((p) => p.status === "open" || p.status === "partial_closed");
        get()._setPositions(active);
      }).catch(() => {});
      getAccountSummary().then((res) => {
        get()._setAccount(res as unknown as AccountSummary);
      }).catch(() => {});
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        switch (msg.type) {
          case "price_tick":
            if (msg.symbol && msg.price != null) {
              get()._updatePrice(msg.symbol, msg.price);
            }
            break;
          case "position_update":
            if (msg.positions) get()._setPositions(msg.positions);
            if (msg.account) get()._setAccount(msg.account);
            break;
          case "trade_closed":
          case "trade_reduced":
          case "signal_detected":
            console.log(`[trading] ${msg.type}`, msg);
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      get()._setConnected(false);
      set({ ws: null });
      setTimeout(() => {
        if (!get().ws) get().connect();
      }, 3000);
    };

    ws.onerror = () => {
      get()._setConnected(false);
    };

    set({ ws });
  },

  disconnect: () => {
    const ws = get().ws;
    if (ws) {
      ws.onclose = null;
      ws.close();
      set({ ws: null, connected: false });
    }
  },
}));
