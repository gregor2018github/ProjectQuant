"""Exponential Moving Average crossover strategy."""

import pandas as pd

from strategies.base import Strategy


class EMACrossStrategy(Strategy):
    """Go long when the short EMA crosses above the long EMA; flat otherwise."""

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]
        ema_short = close.ewm(span=self.short_window, adjust=False).mean()
        ema_long = close.ewm(span=self.long_window, adjust=False).mean()

        # 1 when short EMA > long EMA, else 0
        signal = (ema_short > ema_long).astype(int)

        # No position until the long window has had enough data to warm up
        signal.iloc[: self.long_window] = 0

        return signal
