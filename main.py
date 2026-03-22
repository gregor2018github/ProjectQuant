"""ProjectQuant — CLI entry point."""

import argparse

from data.fetcher import fetch_data
from strategies.sma_cross import SMACrossStrategy
from engine.backtester import Backtester
from display.report import print_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="ProjectQuant — backtest trading strategies from the terminal"
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument(
        "--from", dest="start", required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", dest="end", required=True,
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
