"""Exponential Moving Average crossover strategy."""

import numpy as np
import pandas as pd

from strategies.base import Strategy


class EMACrossStrategy(Strategy):
    """Long when short EMA > long EMA (+1), short when short EMA < long EMA (-1)."""

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"]
        ema_short = close.ewm(span=self.short_window, adjust=False).mean()
        ema_long = close.ewm(span=self.long_window, adjust=False).mean()

        # +1 when short EMA > long EMA (long), -1 otherwise (short)
        signal = pd.Series(
            np.where(ema_short > ema_long, 1, -1), index=close.index, dtype=int
        )

        # No position until the long window has had enough data to warm up
        signal.iloc[: self.long_window] = 0

        return signal
