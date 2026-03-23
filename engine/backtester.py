"""Core backtest simulation engine."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    pnl: float
    capital_start: float
    capital_end: float
    investment: float


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    final_value: float = 0.0


class Backtester:
    """Simulate a long-only strategy on daily OHLCV data."""

    def __init__(self, initial_capital: float = 10_000.0):
        self.initial_capital = initial_capital

    def run(self, df: pd.DataFrame, signals: pd.Series) -> BacktestResult:
        cash = self.initial_capital
        shares = 0
        entry_price = 0.0
        entry_date = ""
        capital_at_entry = 0.0

        trades: list[Trade] = []
        equity: dict[str, float] = {}

        for date, row in df.iterrows():
            price = float(row["Close"])
            sig = int(signals.loc[date])
            date_str = str(date.date()) if hasattr(date, "date") else str(date)

            # --- entry ---
            if sig == 1 and shares == 0:
                shares = int(cash // price)
                if shares > 0:
                    capital_at_entry = cash
                    entry_price = price
                    entry_date = date_str
                    cash -= shares * price

            # --- exit ---
            elif sig == 0 and shares > 0:
                pnl = (price - entry_price) * shares
                investment = shares * entry_price
                cash += shares * price
                capital_at_exit = cash
                trades.append(Trade(
                    entry_date=entry_date,
                    entry_price=round(entry_price, 2),
                    exit_date=date_str,
                    exit_price=round(price, 2),
                    shares=shares,
                    pnl=round(pnl, 2),
                    capital_start=round(capital_at_entry, 2),
                    capital_end=round(capital_at_exit, 2),
                    investment=round(investment, 2),
                ))
                shares = 0

            equity[date_str] = cash + shares * price

        # Close any open position at the last price
        if shares > 0:
            last_price = float(df["Close"].iloc[-1])
            last_date = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])
            pnl = (last_price - entry_price) * shares
            investment = shares * entry_price
            cash += shares * last_price
            capital_at_exit = cash
            trades.append(Trade(
                entry_date=entry_date,
                entry_price=round(entry_price, 2),
                exit_date=last_date,
                exit_price=round(last_price, 2),
                shares=shares,
                pnl=round(pnl, 2),
                capital_start=round(capital_at_entry, 2),
                capital_end=round(capital_at_exit, 2),
                investment=round(investment, 2),
            ))
            equity[last_date] = cash

        equity_series = pd.Series(equity, dtype=float)
        equity_series.index = pd.to_datetime(equity_series.index)

        return BacktestResult(
            trades=trades,
            equity_curve=equity_series,
            final_value=round(equity_series.iloc[-1], 2) if len(equity_series) else self.initial_capital,
        )
