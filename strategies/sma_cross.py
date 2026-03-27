"""Simple Moving Average crossover strategy."""

import numpy as np
import pandas as pd

from strategies.base import Strategy


class SMACrossStrategy(Strategy):
    """Long when short SMA > long SMA (+1), short when short SMA < long SMA (-1)."""

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]
        sma_short = close.rolling(window=self.short_window).mean()
        sma_long = close.rolling(window=self.long_window).mean()

        # +1 when short SMA > long SMA (long), -1 otherwise (short)
        signal = pd.Series(
            np.where(sma_short > sma_long, 1, -1), index=close.index, dtype=int
        )

        # No position until both SMAs have enough data
        signal.iloc[: self.long_window] = 0

        return signal
