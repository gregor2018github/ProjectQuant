"""Bulk backtest runner — executes all cached tickers in parallel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pandas as pd

from data.fetcher import load_local
from data.scanner import DatasetInfo
from engine.backtester import Backtester
from strategies.sma_cross import SMACrossStrategy


def _compute_yearly_returns(equity_curve: pd.Series, initial: float) -> dict[str, float]:
    """Return per-calendar-year return % from an equity curve with a DatetimeIndex."""
    if equity_curve.empty:
        return {}
    yearly: dict[str, float] = {}
    for year, group in equity_curve.groupby(equity_curve.index.year):
        start_val = float(group.iloc[0])
        end_val = float(group.iloc[-1])
        yearly[str(year)] = round(((end_val - start_val) / start_val) * 100, 2) if start_val else 0.0
    return yearly


def _compute_bh_yearly_returns(df: pd.DataFrame, initial: float) -> dict[str, float]:
    """Return per-calendar-year buy-and-hold return % from a price DataFrame."""
    if df.empty:
        return {}
    first_close = float(df["Close"].iloc[0])
    if first_close <= 0:
        return {}
    bh_shares = int(initial // first_close)
    bh_cash = initial - bh_shares * first_close
    bh_equity = df["Close"] * bh_shares + bh_cash
    yearly: dict[str, float] = {}
    for year, group in bh_equity.groupby(bh_equity.index.year):
        start_val = float(group.iloc[0])
        end_val = float(group.iloc[-1])
        yearly[str(year)] = round(((end_val - start_val) / start_val) * 100, 2) if start_val else 0.0
    return yearly


@dataclass
class TickerResult:
    ticker: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float = 0.0
    buy_hold_final_value: float = 0.0
    strategy_return_pct: float = 0.0
    buy_hold_return_pct: float = 0.0
    num_trades: int = 0
    won_vs_bh: bool = False
    yearly_returns: dict[str, float] = field(default_factory=dict)
    bh_yearly_returns: dict[str, float] = field(default_factory=dict)
    error: str | None = None


@dataclass
class BulkBacktestResult:
    ticker_results: list[TickerResult] = field(default_factory=list)
    short_sma: int = 50
    long_sma: int = 200
    timeframe_mode: str = "Custom date range"
    custom_start: str = ""
    custom_end: str = ""
    initial_capital: float = 10_000.0
    timestamp: str = ""


def _run_one(
    dataset: DatasetInfo,
    start: str | None,
    end: str | None,
    capital: float,
    short_sma: int,
    long_sma: int,
    timeframe_mode: str,
) -> TickerResult:
    """Run a single backtest for *dataset*; captures any exception as an error field."""
    ticker = dataset.ticker
    try:
        if timeframe_mode == "Full history per ticker":
            actual_start = dataset.first_date
            actual_end = dataset.last_date
        else:
            actual_start = start or dataset.first_date
            actual_end = end or dataset.last_date

        df = load_local(ticker)
        if df is None:
            return TickerResult(
                ticker=ticker, start_date=actual_start, end_date=actual_end,
                initial_capital=capital, error="No local data file found",
            )

        mask = (df.index >= pd.Timestamp(actual_start)) & (df.index <= pd.Timestamp(actual_end))
        df = df.loc[mask].copy()
        df = df.dropna(subset=["Close"])

        min_rows = long_sma + 10
        if len(df) < min_rows:
            return TickerResult(
                ticker=ticker, start_date=actual_start, end_date=actual_end,
                initial_capital=capital,
                error=f"Insufficient data ({len(df)} rows, need \u2265 {min_rows})",
            )

        strategy = SMACrossStrategy(short_window=short_sma, long_window=long_sma)
        signals = strategy.generate_signals(df)
        bt = Backtester(initial_capital=capital)
        result = bt.run(df, signals)

        strat_return_pct = round(((result.final_value - capital) / capital) * 100, 2)
        bh_return_pct = round(((result.buy_hold_final_value - capital) / capital) * 100, 2)

        return TickerResult(
            ticker=ticker,
            start_date=actual_start,
            end_date=actual_end,
            initial_capital=capital,
            final_value=result.final_value,
            buy_hold_final_value=result.buy_hold_final_value,
            strategy_return_pct=strat_return_pct,
            buy_hold_return_pct=bh_return_pct,
            num_trades=len(result.trades),
            won_vs_bh=result.final_value >= result.buy_hold_final_value,
            yearly_returns=_compute_yearly_returns(result.equity_curve, capital),
            bh_yearly_returns=_compute_bh_yearly_returns(df, capital),
        )

    except Exception as exc:
        return TickerResult(
            ticker=ticker,
            start_date=start or dataset.first_date,
            end_date=end or dataset.last_date,
            initial_capital=capital,
            error=str(exc),
        )


def run_bulk_backtest(
    datasets: list[DatasetInfo],
    start: str | None,
    end: str | None,
    capital: float,
    short_sma: int,
    long_sma: int,
    timeframe_mode: str = "Custom date range",
    workers: int = 8,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> BulkBacktestResult:
    """Run backtests for all *datasets* in parallel, reporting progress via *progress_cb*.

    *progress_cb(done, total, ticker)* is called in the calling thread after each
    future completes — safe to schedule GUI updates via ``self.after(0, …)`` from there.
    """
    total = len(datasets)
    ticker_results: list[TickerResult | None] = [None] * total
    done_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_one, ds, start, end, capital, short_sma, long_sma, timeframe_mode
            ): i
            for i, ds in enumerate(datasets)
        }

        for future in as_completed(futures):
            idx = futures[future]
            ticker_result = future.result()
            ticker_results[idx] = ticker_result
            done_count += 1
            if progress_cb is not None:
                progress_cb(done_count, total, ticker_result.ticker)

    return BulkBacktestResult(
        ticker_results=[r for r in ticker_results if r is not None],
        short_sma=short_sma,
        long_sma=long_sma,
        timeframe_mode=timeframe_mode,
        custom_start=start or "",
        custom_end=end or "",
        initial_capital=capital,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
