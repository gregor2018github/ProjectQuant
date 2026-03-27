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
    direction: str = "long"   # "long" or "short"
    bh_capital_end: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    final_value: float = 0.0
    buy_hold_final_value: float = 0.0


class Backtester:
    """Simulate a strategy on daily OHLCV data, with optional short selling.

    Parameters
    ----------
    initial_capital : float
        Starting cash.
    allow_short : bool
        When True, a -1 signal opens a short position (and closes any open long).
        When False, -1 is treated the same as 0 (exit / stay flat).
    short_interest_rate : float
        Annual interest rate (%) charged on short positions, deducted daily.
        E.g. 2.0 means 2 % per year.
    long_pct : float
        Percentage of available cash to deploy on a long entry (0–100).
    short_pct : float
        Percentage of available cash to deploy on a short entry (0–100).
    """

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        allow_short: bool = False,
        short_interest_rate: float = 0.0,
        long_pct: float = 100.0,
        short_pct: float = 100.0,
    ):
        self.initial_capital = initial_capital
        self.allow_short = allow_short
        self.short_interest_rate = short_interest_rate
        self.long_pct = long_pct
        self.short_pct = short_pct

    def run(self, df: pd.DataFrame, signals: pd.Series) -> BacktestResult:
        cash = self.initial_capital

        # Long position state
        long_shares = 0
        long_entry_price = 0.0
        long_entry_date = ""
        long_capital_at_entry = 0.0

        # Short position state
        short_shares = 0
        short_entry_price = 0.0
        short_entry_date = ""
        short_capital_at_entry = 0.0

        # Buy-and-hold baseline: buy at first close, hold until end
        first_close = float(df["Close"].iloc[0])
        bh_shares = int(self.initial_capital // first_close)
        bh_cash = self.initial_capital - bh_shares * first_close

        daily_short_rate = self.short_interest_rate / 100.0 / 365.0

        trades: list[Trade] = []
        equity: dict[str, float] = {}

        for date, row in df.iterrows():
            price = float(row["Close"])
            sig = int(signals.loc[date])
            date_str = str(date.date()) if hasattr(date, "date") else str(date)

            # --- daily short interest (charged before any trade on this bar) ---
            if short_shares > 0:
                cash -= daily_short_rate * short_shares * price

            bh_value = bh_shares * price + bh_cash

            if self.allow_short:
                # ── Bullish signal: close short, open long ──────────────────
                if sig > 0:
                    if short_shares > 0:
                        # Cover the short position
                        pnl = (short_entry_price - price) * short_shares
                        cash -= short_shares * price
                        capital_at_exit = cash  # all settled to cash
                        trades.append(Trade(
                            entry_date=short_entry_date,
                            entry_price=round(short_entry_price, 2),
                            exit_date=date_str,
                            exit_price=round(price, 2),
                            shares=short_shares,
                            pnl=round(pnl, 2),
                            capital_start=round(short_capital_at_entry, 2),
                            capital_end=round(capital_at_exit, 2),
                            investment=round(short_shares * short_entry_price, 2),
                            direction="short",
                            bh_capital_end=round(bh_value, 2),
                        ))
                        short_shares = 0

                    if long_shares == 0:
                        invest = cash * (self.long_pct / 100.0)
                        shares_to_buy = int(invest // price)
                        if shares_to_buy > 0:
                            long_capital_at_entry = cash
                            long_entry_price = price
                            long_entry_date = date_str
                            long_shares = shares_to_buy
                            cash -= long_shares * price

                # ── Bearish signal: close long, open short ──────────────────
                elif sig < 0:
                    if long_shares > 0:
                        # Close the long position
                        pnl = (price - long_entry_price) * long_shares
                        cash += long_shares * price
                        capital_at_exit = cash
                        trades.append(Trade(
                            entry_date=long_entry_date,
                            entry_price=round(long_entry_price, 2),
                            exit_date=date_str,
                            exit_price=round(price, 2),
                            shares=long_shares,
                            pnl=round(pnl, 2),
                            capital_start=round(long_capital_at_entry, 2),
                            capital_end=round(capital_at_exit, 2),
                            investment=round(long_shares * long_entry_price, 2),
                            direction="long",
                            bh_capital_end=round(bh_value, 2),
                        ))
                        long_shares = 0

                    if short_shares == 0:
                        invest = cash * (self.short_pct / 100.0)
                        shares_to_short = int(invest // price)
                        if shares_to_short > 0:
                            short_capital_at_entry = cash
                            short_entry_price = price
                            short_entry_date = date_str
                            short_shares = shares_to_short
                            cash += short_shares * price  # receive short-sale proceeds

            else:
                # ── Long-only mode ──────────────────────────────────────────
                if sig > 0 and long_shares == 0:
                    invest = cash * (self.long_pct / 100.0)
                    shares_to_buy = int(invest // price)
                    if shares_to_buy > 0:
                        long_capital_at_entry = cash
                        long_entry_price = price
                        long_entry_date = date_str
                        long_shares = shares_to_buy
                        cash -= long_shares * price

                elif sig <= 0 and long_shares > 0:
                    pnl = (price - long_entry_price) * long_shares
                    cash += long_shares * price
                    capital_at_exit = cash
                    trades.append(Trade(
                        entry_date=long_entry_date,
                        entry_price=round(long_entry_price, 2),
                        exit_date=date_str,
                        exit_price=round(price, 2),
                        shares=long_shares,
                        pnl=round(pnl, 2),
                        capital_start=round(long_capital_at_entry, 2),
                        capital_end=round(capital_at_exit, 2),
                        investment=round(long_shares * long_entry_price, 2),
                        direction="long",
                        bh_capital_end=round(bh_value, 2),
                    ))
                    long_shares = 0

            # Net equity: cash + long value − short liability
            equity[date_str] = cash + long_shares * price - short_shares * price

        # ── Close any open position at the last price ───────────────────────
        last_price = float(df["Close"].iloc[-1])
        last_date = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])
        bh_value = bh_shares * last_price + bh_cash

        if long_shares > 0:
            pnl = (last_price - long_entry_price) * long_shares
            cash += long_shares * last_price
            trades.append(Trade(
                entry_date=long_entry_date,
                entry_price=round(long_entry_price, 2),
                exit_date=last_date,
                exit_price=round(last_price, 2),
                shares=long_shares,
                pnl=round(pnl, 2),
                capital_start=round(long_capital_at_entry, 2),
                capital_end=round(cash, 2),
                investment=round(long_shares * long_entry_price, 2),
                direction="long",
                bh_capital_end=round(bh_value, 2),
            ))
            equity[last_date] = cash

        if short_shares > 0:
            pnl = (short_entry_price - last_price) * short_shares
            cash -= short_shares * last_price
            trades.append(Trade(
                entry_date=short_entry_date,
                entry_price=round(short_entry_price, 2),
                exit_date=last_date,
                exit_price=round(last_price, 2),
                shares=short_shares,
                pnl=round(pnl, 2),
                capital_start=round(short_capital_at_entry, 2),
                capital_end=round(cash, 2),
                investment=round(short_shares * short_entry_price, 2),
                direction="short",
                bh_capital_end=round(bh_value, 2),
            ))
            equity[last_date] = cash

        equity_series = pd.Series(equity, dtype=float)
        equity_series.index = pd.to_datetime(equity_series.index)

        last_close = float(df["Close"].iloc[-1])
        bh_final = round(bh_shares * last_close + bh_cash, 2)

        return BacktestResult(
            trades=trades,
            equity_curve=equity_series,
            final_value=round(equity_series.iloc[-1], 2) if len(equity_series) else self.initial_capital,
            buy_hold_final_value=bh_final,
        )
