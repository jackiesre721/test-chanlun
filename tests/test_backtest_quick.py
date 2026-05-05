"""backtest_quick：闭环回合统计与多空开仓配对。"""

from app.core.models import Candle, Signal, SignalSide
from app.services.backtest_quick import _aggregate_round_trips, _simulate


def _candles(n: int, close_start: float = 100.0, step: float = 0.5) -> list[Candle]:
    out: list[Candle] = []
    c = close_start
    for i in range(n):
        out.append(
            Candle(
                open_time=i,
                time=f"t{i}",
                open=c,
                high=c + 1,
                low=c - 1,
                close=c,
                volume=1.0,
            )
        )
        c += step
    return out


def test_long_only_round_trip_records_closed_trade_and_kind():
    candles = _candles(30)
    buys = [
        Signal(
            side=SignalSide.BUY,
            kind="first",
            idx=2,
            time="t2",
            price=candles[2].close,
            description="",
            strength=1.0,
        ),
    ]
    sells = [
        Signal(
            side=SignalSide.SELL,
            kind="third",
            idx=10,
            time="t10",
            price=candles[10].close,
            description="",
            strength=1.0,
        ),
    ]
    trades, rounds, _, _ = _simulate(
        candles,
        strategy="long_only_flip",
        fee_bps=0.0,
        initial_equity_usdt=10_000.0,
        buy_signals=buys,
        sell_signals=sells,
    )
    assert len(trades) == 2
    assert len(rounds) == 1
    assert rounds[0].signal_kind_at_entry == "first"
    assert rounds[0].side == "LONG"
    assert rounds[0].pnl_usdt > 0


def test_aggregate_round_trips_stats_by_kind():
    from app.core.models import QuickBacktestRoundTrip

    rounds = [
        QuickBacktestRoundTrip(
            entry_bar_idx=0,
            exit_bar_idx=5,
            entry_time="a",
            exit_time="b",
            entry_price=100.0,
            exit_price=110.0,
            side="LONG",
            pnl_usdt=50.0,
            pnl_pct=5.0,
            bars_held=5,
            signal_kind_at_entry="first",
        ),
        QuickBacktestRoundTrip(
            entry_bar_idx=6,
            exit_bar_idx=9,
            entry_time="a",
            exit_time="b",
            entry_price=110.0,
            exit_price=105.0,
            side="LONG",
            pnl_usdt=-30.0,
            pnl_pct=-2.0,
            bars_held=3,
            signal_kind_at_entry="first",
        ),
        QuickBacktestRoundTrip(
            entry_bar_idx=10,
            exit_bar_idx=15,
            entry_time="a",
            exit_time="b",
            entry_price=105.0,
            exit_price=108.0,
            side="LONG",
            pnl_usdt=-10.0,
            pnl_pct=-1.0,
            bars_held=5,
            signal_kind_at_entry="third",
        ),
    ]
    stats, wr, pf, exp, mx, _, _ = _aggregate_round_trips(rounds)
    assert stats["first"].count == 2
    assert stats["third"].count == 1
    assert wr == 1 / 3
    assert mx >= 2  # two consecutive losses in sequence - third trade is loss after win then loss - actually sequence +50,-30,-10 max_cons = 2
    assert pf is not None and pf > 0
    assert exp is not None
