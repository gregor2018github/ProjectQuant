# ProjectQuant

A command-line stock backtesting tool. Feed it a ticker and a date range, and it simulates an SMA crossover strategy against historical data, then prints a performance report.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run a backtest
python main.py --ticker AAPL --from 2023-01-01 --to 2024-01-01
```

## Usage

```
python main.py --ticker <SYMBOL> --from <START> --to <END> [options]
```

### Required

| Flag       | Description                          |
|------------|--------------------------------------|
| `--ticker` | Stock ticker symbol (e.g. `AAPL`)    |
| `--from`   | Start date (`YYYY-MM-DD`)            |
| `--to`     | End date (`YYYY-MM-DD`)              |

### Optional

| Flag             | Default  | Description                  |
|------------------|----------|------------------------------|
| `--capital`      | `10000`  | Starting capital in dollars  |
| `--short-window` | `50`     | Short (fast) SMA period      |
| `--long-window`  | `200`    | Long (slow) SMA period       |

### Examples

```bash
# Backtest Tesla for 2023 with default settings
python main.py --ticker TSLA --from 2023-01-01 --to 2024-01-01

# Use $50k capital and faster 20/100 SMA crossover
python main.py --ticker MSFT --from 2022-01-01 --to 2024-01-01 --capital 50000 --short-window 20 --long-window 100
```

## How It Works

The program runs an **SMA (Simple Moving Average) crossover** strategy:

1. **Fetch** — Downloads historical price data from Yahoo Finance (cached locally in `data/cache/` to avoid re-downloading).
2. **Signal** — Computes a short and long SMA. When the short SMA crosses above the long SMA, it generates a **buy** signal. When it crosses below, it generates a **sell** signal.
3. **Simulate** — Walks through each trading day, buying with all available capital on buy signals and selling the full position on sell signals.
4. **Report** — Prints a summary (return %, final value) and a detailed trade log to the terminal using Rich.

> **Note:** Make sure your date range covers enough trading days for the long SMA window. A 200-day SMA needs ~200 days of data before it can produce any signals.

## Project Structure

```
ProjectQuant/
├── main.py                # CLI entry point
├── requirements.txt       # Dependencies
├── data/
│   ├── fetcher.py         # Yahoo Finance download + CSV caching
│   └── cache/             # Cached price data (auto-created)
├── strategies/
│   ├── base.py            # Abstract Strategy base class
│   └── sma_cross.py       # SMA crossover implementation
├── engine/
│   ├── backtester.py      # Trade simulation engine
│   └── metrics.py         # Performance metrics (Phase 2)
└── display/
    └── report.py          # Rich terminal output
```

## Requirements

- Python 3.10+
- [yfinance](https://pypi.org/project/yfinance/) — historical market data
- [pandas](https://pypi.org/project/pandas/) — data manipulation
- [Rich](https://pypi.org/project/rich/) — terminal formatting
