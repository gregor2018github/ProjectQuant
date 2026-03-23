"""Download OHLCV data via yfinance with local CSV storage.

Each ticker gets a single CSV file (e.g. ``AAPL.csv``) that holds *all*
available history.  Incremental refreshes only download what's missing,
with a configurable overlap (default 3 trading days) so late corrections
from the provider are captured.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from data.sp500 import get_sp500_tickers

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rate-limiting defaults (seconds between API calls)
_REQUEST_DELAY = 1.5
_OVERLAP_DAYS = 3


# ── public helpers ──────────────────────────────────────────────────────

def ticker_path(ticker: str) -> Path:
    """Return the local CSV path for *ticker*."""
    return CACHE_DIR / f"{ticker}.csv"


def load_local(ticker: str) -> pd.DataFrame | None:
    """Load locally stored data for *ticker*, or ``None`` if absent."""
    path = ticker_path(ticker)
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    df.sort_index(inplace=True)
    return df


def save_local(ticker: str, df: pd.DataFrame) -> None:
    """Persist *df* to the local CSV store."""
    df.sort_index(inplace=True)
    df.to_csv(ticker_path(ticker))


def fetch_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return OHLCV DataFrame for *ticker* between *start* and *end*.

    Reads from the local store — call :func:`download_ticker` first if
    the ticker hasn't been downloaded yet.
    """
    df = load_local(ticker)
    if df is None:
        # Convenience: download full history on the fly if not stored
        df = download_ticker(ticker)

    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
    subset = df.loc[mask]

    if subset.empty:
        raise SystemExit(
            f"No data for {ticker} in range {start} -> {end}. "
            "Try running  python main.py --download  to refresh."
        )
    return subset


# ── downloading ─────────────────────────────────────────────────────────

def _download_raw(ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
    """Low-level yfinance download. Returns empty DataFrame on failure."""
    kwargs = {"progress": False}
    if start:
        kwargs["start"] = start
    if end:
        kwargs["end"] = end
    if not start and not end:
        kwargs["period"] = "max"
    df = yf.download(ticker, **kwargs)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def download_ticker(
    ticker: str,
    overlap_days: int = _OVERLAP_DAYS,
) -> pd.DataFrame:
    """Download (or incrementally refresh) data for a single *ticker*.

    * If no local data exists the full available history is fetched.
    * If local data exists only the missing tail is fetched, starting
      *overlap_days* before the last stored date so that late corrections
      from the provider overwrite stale rows.

    Returns the merged DataFrame.
    """
    existing = load_local(ticker)

    if existing is not None and not existing.empty:
        last_date = existing.index.max()
        fetch_from = (last_date - timedelta(days=overlap_days)).strftime("%Y-%m-%d")
        tomorrow = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"[refresh] {ticker}: fetching from {fetch_from} …")
        new = _download_raw(ticker, start=fetch_from, end=tomorrow)

        if new.empty:
            print(f"[refresh] {ticker}: no new data returned, keeping existing")
            return existing

        # Merge: new data wins for overlapping dates
        combined = pd.concat([existing, new])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
    else:
        print(f"[download] {ticker}: fetching full history …")
        combined = _download_raw(ticker, start=None, end=None)
        if combined.empty:
            print(f"[warn] {ticker}: no data returned — skipping")
            return pd.DataFrame()

    save_local(ticker, combined)
    print(f"[stored] {ticker}: {len(combined)} rows -> {ticker_path(ticker).name}")
    return combined


def download_sp500(
    delay: float = _REQUEST_DELAY,
    overlap_days: int = _OVERLAP_DAYS,
) -> None:
    """Download / refresh data for every current S&P 500 constituent.

    Pauses *delay* seconds between API calls to avoid rate-limiting.
    """
    tickers = get_sp500_tickers()
    total = len(tickers)
    print(f"[sp500] Downloading {total} tickers (delay={delay}s) …\n")

    failed: list[str] = []
    for i, ticker in enumerate(tickers, 1):
        print(f"({i}/{total}) ", end="")
        try:
            download_ticker(ticker, overlap_days=overlap_days)
        except Exception as exc:
            print(f"[error] {ticker}: {exc}")
            failed.append(ticker)

        if i < total:
            time.sleep(delay)

    print(f"\n[sp500] Done. {total - len(failed)}/{total} succeeded.")
    if failed:
        print(f"[sp500] Failed: {', '.join(failed)}")
