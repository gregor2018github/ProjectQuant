"""ProjectQuant — CLI & GUI entry point."""

import argparse

from data.fetcher import fetch_data, download_ticker, download_sp500
from strategies.sma_cross import SMACrossStrategy
from engine.backtester import Backtester
from display.report import print_report
from display.ui import launch_ui


def parse_args():
    parser = argparse.ArgumentParser(
        description="ProjectQuant — backtest trading strategies"
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

    # ── GUI control ─────────────────────────────────────────────────
    parser.add_argument(
        "--no-gui", action="store_true",
        help="Disable GUI; require CLI backtest flags instead"
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

    # ── backtest CLI mode ─────────────────────────────────────────
    if args.ticker or args.start or args.end:
        if not args.ticker or not args.start or not args.end:
            raise SystemExit(
                "Backtest mode requires --ticker, --from, and --to."
            )

        df = fetch_data(args.ticker, args.start, args.end)
        strategy = SMACrossStrategy(
            short_window=args.short_window,
            long_window=args.long_window,
        )
        signals = strategy.generate_signals(df)
        bt = Backtester(initial_capital=args.capital)
        result = bt.run(df, signals)

        print_report(args.ticker, args.start, args.end, args.capital, result)
        launch_ui(
            ticker=args.ticker,
            start=args.start,
            end=args.end,
            initial_capital=args.capital,
            result=result,
            df=df,
            short_window=args.short_window,
            long_window=args.long_window,
        )
        return

    # ── GUI mode (default) ────────────────────────────────────────
    if args.no_gui:
        raise SystemExit(
            "No action specified. Use --ticker/--from/--to for backtest,\n"
            "or --download to fetch data, or run without --no-gui for the GUI."
        )

    from display.desktop import launch_desktop
    launch_desktop()


if __name__ == "__main__":
    main()
