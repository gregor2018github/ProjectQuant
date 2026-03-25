"""Lightweight CSV metadata scanning for the data cache."""

from dataclasses import dataclass
from pathlib import Path

from data.fetcher import CACHE_DIR
from data.sp500 import get_sp500_tickers
from data.dax30 import get_dax30_tickers


@dataclass
class DatasetInfo:
    ticker: str
    rows: int
    first_date: str
    last_date: str
    size_bytes: int
    index: str


def _format_size(size_bytes: int) -> str:
    """Return human-readable file size string."""
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def scan_cache() -> list[DatasetInfo]:
    """Scan all CSVs in the cache directory and return metadata.

    Reads only the first/last lines of each file for dates, counts rows
    by streaming, and uses stat() for file size.  No full DataFrame is
    loaded.
    """
    sp500_set = set(get_sp500_tickers())
    dax30_set = set(get_dax30_tickers())
    results: list[DatasetInfo] = []

    for csv_path in sorted(CACHE_DIR.glob("*.csv")):
        ticker = csv_path.stem
        size = csv_path.stat().st_size

        try:
            with open(csv_path, "rb") as f:
                _header = f.readline()          # skip header
                first_line = f.readline()
                if not first_line.strip():
                    continue  # empty file
                first_date = first_line.split(b",")[0].decode().strip()

                # seek backwards from end for last line
                f.seek(0, 2)
                pos = f.tell() - 2
                while pos > 0:
                    f.seek(pos)
                    if f.read(1) == b"\n":
                        break
                    pos -= 1
                last_line = f.readline()
                last_date = last_line.split(b",")[0].decode().strip()

            # count rows (minus header)
            row_count = sum(1 for _ in open(csv_path, "rb")) - 1
        except Exception:
            continue

        if ticker in sp500_set:
            index_name = "S&P 500"
        elif ticker in dax30_set:
            index_name = "DAX 30"
        else:
            index_name = "Other"
        results.append(DatasetInfo(
            ticker=ticker,
            rows=row_count,
            first_date=first_date,
            last_date=last_date,
            size_bytes=size,
            index=index_name,
        ))

    return results
