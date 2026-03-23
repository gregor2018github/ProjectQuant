"""ProjectQuant — CLI entry point."""

import argparse

from data.fetcher import fetch_data, download_ticker, download_sp500
from strategies.sma_cross import SMACrossStrategy
from engine.backtester import Backtester
from display.report import print_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="ProjectQuant — backtest trading strategies from the terminal"
    )

    # ── data management ─────────────────────────────────────────────
    parser.add_argument(
        "--download", action="store_true",
        help="Download / refresh S&P 500 data and exit"
    )
    parser.add_argument(
        "--download-ticker",
        help="Download / refresh a single ticker and exit"
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="Seconds between API calls during bulk download (default: 1.5)"
    )
    parser.add_argument(
        "--overlap", type=int, default=3,
        help="Days of overlap when refreshing existing data (default: 3)"
    )

    # ── backtest parameters ─────────────────────────────────────────
    parser.add_argument("--ticker", help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument(
        "--from", dest="start",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", dest="end",
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--capital", type=float, default=10_000.0,
        help="Starting capital (default: 10000)"
    )
    parser.add_argument(
        "--short-window", type=int, default=50,
        help="Short SMA window (default: 50)"
    )
    parser.add_argument(
        "--long-window", type=int, default=200,
        help="Long SMA window (default: 200)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── download mode ───────────────────────────────────────────────
    if args.download:
        download_sp500(delay=args.delay, overlap_days=args.overlap)
        return

    if args.download_ticker:
        download_ticker(args.download_ticker, overlap_days=args.overlap)
        return

    # ── backtest mode ───────────────────────────────────────────────
    if not args.ticker or not args.start or not args.end:
        raise SystemExit(
            "Backtest mode requires --ticker, --from, and --to.\n"
            "Run with --download to fetch S&P 500 data first."
        )

    # 1. Fetch data
    df = fetch_data(args.ticker, args.start, args.end)

    # 2. Build strategy & generate signals
    strategy = SMACrossStrategy(
        short_window=args.short_window,
        long_window=args.long_window,
    )
    signals = strategy.generate_signals(df)

    # 3. Run backtest
    bt = Backtester(initial_capital=args.capital)
    result = bt.run(df, signals)

    # 4. Display results
    print_report(args.ticker, args.start, args.end, args.capital, result)


if __name__ == "__main__":
    main()
