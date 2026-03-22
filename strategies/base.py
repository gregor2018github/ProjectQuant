"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """Every strategy must implement ``generate_signals``."""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series aligned with *df* index.

        Values:
            1  → long / buy
            0  → flat / no position
           -1  → sell (reserved for future short-selling support)
        """
        ...
