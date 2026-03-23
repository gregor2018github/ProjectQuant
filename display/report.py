"""Rich terminal output for backtest results."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from engine.backtester import BacktestResult

console = Console()


def print_report(
    ticker: str,
    start: str,
    end: str,
    initial_capital: float,
    result: BacktestResult,
) -> None:
    total_return = result.final_value - initial_capital
    pct_return = (total_return / initial_capital) * 100

    bh_return = result.buy_hold_final_value - initial_capital
    bh_pct = (bh_return / initial_capital) * 100
    vs_bh = result.final_value - result.buy_hold_final_value
    vs_bh_pct = (vs_bh / result.buy_hold_final_value) * 100 if result.buy_hold_final_value else 0

    # --- Summary panel ---
    summary = (
        f"[bold]{ticker}[/bold]  {start} -> {end}\n"
        f"Starting capital: [cyan]${initial_capital:,.2f}[/cyan]\n"
        f"Final value:      [cyan]${result.final_value:,.2f}[/cyan]\n"
        f"Return:           [{'green' if total_return >= 0 else 'red'}]"
        f"${total_return:,.2f} ({pct_return:+.2f}%)[/]\n"
        f"Buy & Hold:       [{'green' if bh_return >= 0 else 'red'}]"
        f"${bh_return:,.2f} ({bh_pct:+.2f}%)[/]\n"
        f"vs Buy & Hold:    [{'green' if vs_bh >= 0 else 'red'}]"
        f"${vs_bh:,.2f} ({vs_bh_pct:+.2f}%)[/]"
    )
    console.print(Panel(summary, title="Backtest Summary", border_style="blue"))

    # --- Trade log ---
    if not result.trades:
        console.print("[yellow]No trades were executed.[/yellow]")
        return

    table = Table(title=f"Trade Log ({len(result.trades)} trades)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Entry Date")
    table.add_column("Entry Price", justify="right")
    table.add_column("Exit Date")
    table.add_column("Exit Price", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("Capital Start", justify="right")
    table.add_column("Investment", justify="right")
    table.add_column("Capital End", justify="right")
    table.add_column("B&H Capital End", justify="right")
    table.add_column("P&L", justify="right")

    for i, t in enumerate(result.trades, 1):
        pnl_style = "green" if t.pnl >= 0 else "red"
        table.add_row(
            str(i),
            t.entry_date,
            f"${t.entry_price:,.2f}",
            t.exit_date,
            f"${t.exit_price:,.2f}",
            str(t.shares),
            f"${t.capital_start:,.2f}",
            f"${t.investment:,.2f}",
            f"${t.capital_end:,.2f}",
            f"${t.bh_capital_end:,.2f}",
            f"[{pnl_style}]${t.pnl:,.2f}[/{pnl_style}]",
        )

    console.print(table)
