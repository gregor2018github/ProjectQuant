"""Browser-based interactive UI for backtest results."""

import html
import tempfile
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine.backtester import BacktestResult


def _build_chart(
    df: pd.DataFrame,
    trades: list,
    equity_curve: pd.Series,
    short_window: int,
    long_window: int,
) -> str:
    """Build an interactive Plotly candlestick chart and return its HTML div."""

    close = df["Close"]
    sma_short = close.rolling(window=short_window).mean()
    sma_long = close.rolling(window=long_window).mean()

    # Build equity series aligned to all dates (forward-fill for days without trades)
    equity_by_date = equity_curve.reindex(df.index).ffill()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
    )

    # --- Candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            customdata=equity_by_date.values,
            hovertext=[
                f"Equity: ${eq:,.2f}" if pd.notna(eq) else ""
                for eq in equity_by_date.values
            ],
        ),
        row=1, col=1,
    )

    # --- SMA lines ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=sma_short,
            name=f"SMA {short_window}",
            line=dict(color="#ff9800", width=1.5),
            hovertemplate=f"SMA {short_window}: " + "%{y:$.2f}<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=sma_long,
            name=f"SMA {long_window}",
            line=dict(color="#2196f3", width=1.5),
            hovertemplate=f"SMA {long_window}: " + "%{y:$.2f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- Entry / Exit markers ---
    buy_dates, buy_prices, buy_texts = [], [], []
    sell_dates, sell_prices, sell_texts = [], [], []

    for t in trades:
        buy_dates.append(pd.Timestamp(t.entry_date))
        buy_prices.append(t.entry_price)
        buy_texts.append(
            f"BUY {t.shares} shares @ ${t.entry_price:,.2f}<br>"
            f"Capital: ${t.capital_start:,.2f}<br>"
            f"Investment: ${t.investment:,.2f}"
        )

        sell_dates.append(pd.Timestamp(t.exit_date))
        sell_prices.append(t.exit_price)
        pnl_color = "#26a69a" if t.pnl >= 0 else "#ef5350"
        sell_texts.append(
            f"SELL {t.shares} shares @ ${t.exit_price:,.2f}<br>"
            f"P&L: <span style='color:{pnl_color}'>${t.pnl:,.2f}</span><br>"
            f"Capital: ${t.capital_end:,.2f}"
        )

    fig.add_trace(
        go.Scatter(
            x=buy_dates, y=buy_prices,
            mode="markers",
            name="Buy",
            marker=dict(
                symbol="triangle-up", size=14, color="#26a69a",
                line=dict(width=1, color="#fff"),
            ),
            hovertemplate="%{text}<extra></extra>",
            text=buy_texts,
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=sell_dates, y=sell_prices,
            mode="markers",
            name="Sell",
            marker=dict(
                symbol="triangle-down", size=14, color="#ef5350",
                line=dict(width=1, color="#fff"),
            ),
            hovertemplate="%{text}<extra></extra>",
            text=sell_texts,
        ),
        row=1, col=1,
    )

    # --- Volume bars ---
    colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"],
            name="Volume",
            marker_color=colors,
            opacity=0.5,
            hovertemplate="Vol: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # --- Layout ---
    fig.update_layout(
        height=700,
        margin=dict(l=60, r=30, t=30, b=30),
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        font=dict(color="#d4d4d4", size=12),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(
        gridcolor="#333", showgrid=True,
        type="date",
    )
    fig.update_yaxes(gridcolor="#333", showgrid=True)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig.to_html(full_html=False, include_plotlyjs=False)


def _build_html(
    ticker: str,
    start: str,
    end: str,
    initial_capital: float,
    result: BacktestResult,
    chart_div: str,
) -> str:
    """Assemble the full HTML page."""

    total_return = result.final_value - initial_capital
    pct_return = (total_return / initial_capital) * 100
    ret_color = "#26a69a" if total_return >= 0 else "#ef5350"

    bh_return = result.buy_hold_final_value - initial_capital
    bh_pct = (bh_return / initial_capital) * 100
    bh_color = "#26a69a" if bh_return >= 0 else "#ef5350"

    vs_bh = result.final_value - result.buy_hold_final_value
    vs_bh_pct = (vs_bh / result.buy_hold_final_value) * 100 if result.buy_hold_final_value else 0
    vs_bh_color = "#26a69a" if vs_bh >= 0 else "#ef5350"

    # Build trade table rows
    trade_rows = ""
    for i, t in enumerate(result.trades, 1):
        pnl_color = "#26a69a" if t.pnl >= 0 else "#ef5350"
        trade_rows += f"""
        <tr>
            <td>{i}</td>
            <td>{html.escape(t.entry_date)}</td>
            <td>${t.entry_price:,.2f}</td>
            <td>{html.escape(t.exit_date)}</td>
            <td>${t.exit_price:,.2f}</td>
            <td>{t.shares}</td>
            <td>${t.capital_start:,.2f}</td>
            <td>${t.investment:,.2f}</td>
            <td>${t.capital_end:,.2f}</td>
            <td>${t.bh_capital_end:,.2f}</td>
            <td style="color:{pnl_color};font-weight:600">${t.pnl:,.2f}</td>
        </tr>"""

    no_trades_msg = ""
    if not result.trades:
        no_trades_msg = '<p style="color:#ff9800;padding:12px;">No trades were executed.</p>'

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ProjectQuant — {html.escape(ticker)} Backtest</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    background: #1e1e1e; color: #d4d4d4;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 14px;
  }}
  .summary {{
    display: flex; flex-wrap: wrap; gap: 16px;
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 20px 24px; margin-bottom: 16px;
  }}
  .summary h2 {{
    width: 100%; margin: 0 0 8px; font-size: 18px; color: #fff;
  }}
  .summary .stat {{
    min-width: 180px;
  }}
  .summary .stat .label {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.05em; color: #888; margin-bottom: 2px;
  }}
  .summary .stat .value {{
    font-size: 20px; font-weight: 600; color: #fff;
  }}
  .table-wrap {{
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 16px; margin-bottom: 16px;
    overflow-x: auto;
  }}
  .table-wrap h3 {{
    margin: 0 0 12px; font-size: 15px; color: #fff;
  }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 13px;
  }}
  th {{
    text-align: left; padding: 8px 12px;
    border-bottom: 2px solid #444; color: #aaa;
    font-weight: 600; text-transform: uppercase; font-size: 11px;
    letter-spacing: 0.03em; white-space: nowrap;
  }}
  th:first-child, td:first-child {{ text-align: right; }}
  td {{
    padding: 7px 12px; border-bottom: 1px solid #333;
    white-space: nowrap;
  }}
  tr:hover td {{ background: #2a2d2e; }}
  .chart-wrap {{
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 16px;
  }}
  .chart-wrap h3 {{
    margin: 0 0 8px; font-size: 15px; color: #fff;
  }}
</style>
</head>
<body>

<!-- Summary -->
<div class="summary">
  <h2>Backtest — {html.escape(ticker)}</h2>
  <div class="stat">
    <div class="label">Period</div>
    <div class="value" style="font-size:15px">{html.escape(start)} &rarr; {html.escape(end)}</div>
  </div>
  <div class="stat">
    <div class="label">Starting Capital</div>
    <div class="value">${initial_capital:,.2f}</div>
  </div>
  <div class="stat">
    <div class="label">Final Value</div>
    <div class="value">${result.final_value:,.2f}</div>
  </div>
  <div class="stat">
    <div class="label">Return</div>
    <div class="value" style="color:{ret_color}">${total_return:,.2f} ({pct_return:+.2f}%)</div>
  </div>
  <div class="stat">
    <div class="label">Trades</div>
    <div class="value">{len(result.trades)}</div>
  </div>
  <div class="stat">
    <div class="label">Buy &amp; Hold Return</div>
    <div class="value" style="color:{bh_color}">${bh_return:,.2f} ({bh_pct:+.2f}%)</div>
  </div>
  <div class="stat">
    <div class="label">Strategy vs Buy &amp; Hold</div>
    <div class="value" style="color:{vs_bh_color}">${vs_bh:,.2f} ({vs_bh_pct:+.2f}%)</div>
  </div>
</div>

<!-- Trade Log -->
<div class="table-wrap">
  <h3>Trade Log</h3>
  {no_trades_msg}
  {"" if not result.trades else f'''<table>
    <thead>
      <tr>
        <th>#</th><th>Entry Date</th><th>Entry Price</th>
        <th>Exit Date</th><th>Exit Price</th><th>Shares</th>
        <th>Capital Start</th><th>Investment</th><th>Capital End</th><th>B&amp;H Capital End</th><th>P&amp;L</th>
      </tr>
    </thead>
    <tbody>{trade_rows}</tbody>
  </table>'''}
</div>

<!-- Chart -->
<div class="chart-wrap">
  <h3>Price Chart</h3>
  {chart_div}
</div>

</body>
</html>"""
    return page


def launch_ui(
    ticker: str,
    start: str,
    end: str,
    initial_capital: float,
    result: BacktestResult,
    df: pd.DataFrame,
    short_window: int,
    long_window: int,
) -> None:
    """Build the interactive report and open it in the default browser."""

    chart_div = _build_chart(
        df=df,
        trades=result.trades,
        equity_curve=result.equity_curve,
        short_window=short_window,
        long_window=long_window,
    )

    page_html = _build_html(
        ticker=ticker,
        start=start,
        end=end,
        initial_capital=initial_capital,
        result=result,
        chart_div=chart_div,
    )

    # Write to a temp file and open in browser
    tmp = Path(tempfile.mktemp(suffix=".html", prefix=f"pq_{ticker}_"))
    tmp.write_text(page_html, encoding="utf-8")
    webbrowser.open(tmp.as_uri())
