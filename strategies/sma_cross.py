"""Simple Moving Average crossover strategy."""

import pandas as pd

from strategies.base import Strategy


class SMACrossStrategy(Strategy):
    """Go long when the short SMA crosses above the long SMA; flat otherwise."""

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]
        sma_short = close.rolling(window=self.short_window).mean()
        sma_long = close.rolling(window=self.long_window).mean()

        # 1 when short SMA > long SMA, else 0
        signal = (sma_short > sma_long).astype(int)

        # No position until both SMAs have enough data
        signal.iloc[: self.long_window] = 0

        return signal
