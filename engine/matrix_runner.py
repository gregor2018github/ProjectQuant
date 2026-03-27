"""Matrix test runner — tests many SMA (short, long) combinations in parallel."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import numpy as np

from data.scanner import DatasetInfo
from engine.bulk_runner import _run_one


@dataclass
class MatrixCellResult:
    short_sma: int
    long_sma: int
    avg_diff_vs_bh: float
    num_tickers_tested: int
    num_tickers_succeeded: int
    avg_strategy_return: float
    avg_bh_return: float
    beat_bh_count: int


@dataclass
class MatrixTestResult:
    cells: list[MatrixCellResult] = field(default_factory=list)
    sma_values: list[int] = field(default_factory=list)
    sma_from: int = 3
    sma_to: int = 200
    max_combinations: int = 150
    assets_per_test: int = 30
    initial_capital: float = 10_000.0
    timeframe_mode: str = "Full history per ticker"
    custom_start: str = ""
    custom_end: str = ""
    total_backtests_run: int = 0
    timestamp: str = ""
    strategy_type: str = "sma"


def generate_sma_grid(
    sma_from: int, sma_to: int, max_combinations: int
) -> tuple[list[int], list[tuple[int, int]]]:
    """Return (sma_values, pairs) where pairs are all (short, long) with short < long.

    The number of unique SMA values N is chosen so that N*(N-1)/2 ≈ max_combinations.
    Values are evenly spaced integers in [sma_from, sma_to].
    """
    max_n = sma_to - sma_from + 1
    n = int(math.floor((1 + math.sqrt(1 + 8 * max_combinations)) / 2))
    n = max(2, min(n, max_n))

    raw = np.linspace(sma_from, sma_to, n)
    sma_values = sorted(set(int(round(v)) for v in raw))

    pairs = [
        (s, l)
        for i, s in enumerate(sma_values)
        for l in sma_values[i + 1 :]
    ]
    return sma_values, pairs


def run_matrix_test(
    all_datasets: list[DatasetInfo],
    sma_from: int,
    sma_to: int,
    max_combinations: int,
    assets_per_test: int,
    capital: float,
    timeframe_mode: str,
    start: str | None,
    end: str | None,
    strategy_type: str = "sma",
    workers: int = 8,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> MatrixTestResult:
    """Run backtests for many SMA combinations, each on a random sample of tickers."""

    sma_values, pairs = generate_sma_grid(sma_from, sma_to, max_combinations)
    sample_size = min(assets_per_test, len(all_datasets))

    # Build flat task list: (dataset, short_sma, long_sma)
    tasks: list[tuple[DatasetInfo, int, int]] = []
    for short_sma, long_sma in pairs:
        sampled = random.sample(all_datasets, sample_size)
        for ds in sampled:
            tasks.append((ds, short_sma, long_sma))

    total = len(tasks)
    done_count = 0

    # key: (short_sma, long_sma) -> list of TickerResult
    grouped: dict[tuple[int, int], list] = defaultdict(list)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_one, ds, start, end, capital, short_sma, long_sma, timeframe_mode, strategy_type
            ): (short_sma, long_sma)
            for ds, short_sma, long_sma in tasks
        }

        ind = strategy_type.upper()
        for future in as_completed(futures):
            key = futures[future]
            result = future.result()
            grouped[key].append(result)
            done_count += 1
            if progress_cb is not None:
                progress_cb(done_count, total, f"{result.ticker} ({ind} {key[0]}/{key[1]})")

    # Aggregate per-cell
    cells: list[MatrixCellResult] = []
    for (short_sma, long_sma), results in grouped.items():
        succeeded = [r for r in results if r.error is None]
        if not succeeded:
            cells.append(MatrixCellResult(
                short_sma=short_sma,
                long_sma=long_sma,
                avg_diff_vs_bh=float("nan"),
                num_tickers_tested=len(results),
                num_tickers_succeeded=0,
                avg_strategy_return=float("nan"),
                avg_bh_return=float("nan"),
                beat_bh_count=0,
            ))
            continue

        diffs = [r.strategy_return_pct - r.buy_hold_return_pct for r in succeeded]
        strat_rets = [r.strategy_return_pct for r in succeeded]
        bh_rets = [r.buy_hold_return_pct for r in succeeded]
        beat_count = sum(1 for r in succeeded if r.won_vs_bh)

        cells.append(MatrixCellResult(
            short_sma=short_sma,
            long_sma=long_sma,
            avg_diff_vs_bh=round(sum(diffs) / len(diffs), 2),
            num_tickers_tested=len(results),
            num_tickers_succeeded=len(succeeded),
            avg_strategy_return=round(sum(strat_rets) / len(strat_rets), 2),
            avg_bh_return=round(sum(bh_rets) / len(bh_rets), 2),
            beat_bh_count=beat_count,
        ))

    return MatrixTestResult(
        cells=cells,
        sma_values=sma_values,
        sma_from=sma_from,
        sma_to=sma_to,
        max_combinations=max_combinations,
        assets_per_test=assets_per_test,
        initial_capital=capital,
        timeframe_mode=timeframe_mode,
        custom_start=start or "",
        custom_end=end or "",
        total_backtests_run=total,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        strategy_type=strategy_type,
    )
