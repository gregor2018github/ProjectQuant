"""Download OHLCV data via yfinance with local CSV caching."""

import os
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def _cache_path(ticker: str, start: str, end: str) -> Path:
    return CACHE_DIR / f"{ticker}_{start}_{end}.csv"


def fetch_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return OHLCV DataFrame for *ticker* between *start* and *end*.

    Results are cached as CSV so repeated runs don't re-download.
    """
    path = _cache_path(ticker, start, end)

    if path.exists():
        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        print(f"[cache] Loaded {ticker} data from {path.name}")
        return df

    print(f"[download] Fetching {ticker} from {start} to {end} …")
    df = yf.download(ticker, start=start, end=end, progress=False)

    if df.empty:
        raise SystemExit(f"No data returned for {ticker} ({start} -> {end}). Check the ticker/dates.")

    # Flatten multi-level columns if present (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    print(f"[cache] Saved to {path.name}")
    return df
