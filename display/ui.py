"""Browser-based interactive UI for backtest results."""

import html
import math
import statistics
import tempfile
import webbrowser
from collections import defaultdict
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine.backtester import BacktestResult
from engine.bulk_runner import BulkBacktestResult


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
        vs_bh_diff = t.capital_end - t.bh_capital_end
        vs_bh_color = "#26a69a" if vs_bh_diff >= 0 else "#ef5350"
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
            <td style="color:{vs_bh_color};font-weight:600">${vs_bh_diff:+,.2f}</td>
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

<!-- Chart -->
<div class="chart-wrap">
  <h3>Price Chart</h3>
  {chart_div}
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
        <th>Capital Start</th><th>Investment</th><th>Capital End</th><th>B&amp;H Capital End</th><th>vs B&amp;H</th><th>P&amp;L</th>
      </tr>
    </thead>
    <tbody>{trade_rows}</tbody>
  </table>'''}
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


# ── Bulk backtest report ──────────────────────────────────────────────────────

def _pct_color(val: float) -> str:
    return "#26a69a" if val >= 0 else "#ef5350"


def _stat_card(label: str, value: str, color: str = "#fff") -> str:
    return (
        f'<div class="stat">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value" style="color:{color}">{value}</div>'
        f'</div>'
    )


def _dark_fig_layout(title: str, height: int = 450, **extra) -> dict:
    base = dict(
        title=dict(text=title, font=dict(color="#d4d4d4", size=15)),
        height=height,
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        font=dict(color="#d4d4d4", size=12),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=60, r=30, t=60, b=50),
    )
    base.update(extra)
    return base


def _heatmap_color_value(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    if value <= 0:
        return -math.log1p(abs(max(value, -100.0)))
    return math.log1p(value)


def _heatmap_colorbar(max_positive_return: float) -> dict:
    tick_candidates = [-100, -50, -20, -10, 0, 10, 20, 50, 100, 200, 500, 1000]
    tick_values = []
    tick_text = []
    for value in tick_candidates:
        if value < -100:
            continue
        if value > 0 and value > max_positive_return:
            continue
        tick_values.append(_heatmap_color_value(float(value)))
        tick_text.append(f"{value:g}%")
    return dict(title="Return %", tickvals=tick_values, ticktext=tick_text)


def _build_bulk_html(result: BulkBacktestResult) -> str:
    """Assemble the full bulk backtest HTML report."""
    successful = [r for r in result.ticker_results if r.error is None]
    failed = [r for r in result.ticker_results if r.error is not None]
    total = len(result.ticker_results)

    # ── Summary stats ────────────────────────────────────────────────
    if successful:
        strat_rets = [r.strategy_return_pct for r in successful]
        bh_rets = [r.buy_hold_return_pct for r in successful]
        avg_strat = statistics.mean(strat_rets)
        med_strat = statistics.median(strat_rets)
        avg_bh = statistics.mean(bh_rets)
        med_bh = statistics.median(bh_rets)
        beat_count = sum(1 for r in successful if r.won_vs_bh)
        pct_beat = beat_count / len(successful) * 100
        best = max(successful, key=lambda r: r.strategy_return_pct)
        worst = min(successful, key=lambda r: r.strategy_return_pct)
        avg_trades = statistics.mean(r.num_trades for r in successful)
    else:
        avg_strat = med_strat = avg_bh = med_bh = pct_beat = avg_trades = 0.0
        beat_count = 0
        best = worst = None

    best_str = (f"{html.escape(best.ticker)} ({best.strategy_return_pct:+.2f}%)"
                if best else "&mdash;")
    worst_str = (f"{html.escape(worst.ticker)} ({worst.strategy_return_pct:+.2f}%)"
                 if worst else "&mdash;")

    summary_html = (
        _stat_card("Tickers Run", str(total)) +
        _stat_card("Successful", str(len(successful)), "#26a69a") +
        _stat_card("Failed / Skipped", str(len(failed)),
                   "#ef5350" if failed else "#888") +
        _stat_card("Avg Strategy Return", f"{avg_strat:+.2f}%", _pct_color(avg_strat)) +
        _stat_card("Median Strategy Return", f"{med_strat:+.2f}%", _pct_color(med_strat)) +
        _stat_card("Avg B&H Return", f"{avg_bh:+.2f}%", _pct_color(avg_bh)) +
        _stat_card("Median B&H Return", f"{med_bh:+.2f}%", _pct_color(med_bh)) +
        _stat_card("Beat B&H", f"{pct_beat:.1f}%  ({beat_count} / {len(successful)})",
                   "#26a69a" if pct_beat >= 50 else "#ef5350") +
        _stat_card("Best Performer", best_str, "#26a69a") +
        _stat_card("Worst Performer", worst_str, "#ef5350") +
        _stat_card("Avg # Trades", f"{avg_trades:.1f}")
    )

    # ── Per-ticker table rows ─────────────────────────────────────────
    ticker_rows = ""
    for r in sorted(result.ticker_results, key=lambda r: r.ticker):
        if r.error:
            ticker_rows += (
                f'<tr class="row-error">'
                f'<td>{html.escape(r.ticker)}</td>'
                f'<td colspan="6" style="color:#888">{html.escape(r.error)}</td>'
                f'</tr>\n'
            )
        else:
            row_cls = "row-win" if r.won_vs_bh else "row-loss"
            beat_icon = "&#10003;" if r.won_vs_bh else "&#10007;"
            beat_color = "#26a69a" if r.won_vs_bh else "#ef5350"
            vs_bh_diff = r.final_value - r.buy_hold_final_value
            vs_bh_diff_color = "#26a69a" if vs_bh_diff >= 0 else "#ef5350"
            ticker_rows += (
                f'<tr class="{row_cls}">'
                f'<td>{html.escape(r.ticker)}</td>'
                f'<td style="font-size:11px;color:#888">'
                f'{html.escape(r.start_date)} &rarr; {html.escape(r.end_date)}</td>'
                f'<td style="text-align:right">{r.num_trades}</td>'
                f'<td style="text-align:right;color:{_pct_color(r.strategy_return_pct)};'
                f'font-weight:600">{r.strategy_return_pct:+.2f}%</td>'
                f'<td style="text-align:right;color:{_pct_color(r.buy_hold_return_pct)}">'
                f'{r.buy_hold_return_pct:+.2f}%</td>'
                f'<td style="text-align:right">${r.final_value:,.2f}</td>'
                f'<td style="text-align:right;color:{vs_bh_diff_color};font-weight:600">'
                f'${vs_bh_diff:+,.2f}</td>'
                f'<td style="text-align:center;color:{beat_color};font-weight:700">'
                f'{beat_icon}</td>'
                f'</tr>\n'
            )

    # ── By Year chart ─────────────────────────────────────────────────
    year_strat_d: defaultdict[str, list[float]] = defaultdict(list)
    year_bh_d: defaultdict[str, list[float]] = defaultdict(list)
    for r in successful:
        for yr, ret in r.yearly_returns.items():
            year_strat_d[yr].append(ret)
        for yr, ret in r.bh_yearly_returns.items():
            year_bh_d[yr].append(ret)

    years = sorted(set(year_strat_d) | set(year_bh_d))
    avg_strat_yr = [
        statistics.mean(year_strat_d[y]) if year_strat_d[y] else 0.0 for y in years
    ]
    avg_bh_yr = [
        statistics.mean(year_bh_d[y]) if year_bh_d[y] else 0.0 for y in years
    ]

    year_fig = go.Figure()
    year_fig.add_trace(go.Bar(
        x=years, y=avg_strat_yr,
        name=f"Strategy (SMA {result.short_sma}/{result.long_sma})",
        marker_color="#26a69a",
        hovertemplate="<b>%{x}</b><br>Avg Strategy: %{y:+.2f}%<extra></extra>",
    ))
    year_fig.add_trace(go.Bar(
        x=years, y=avg_bh_yr,
        name="Buy &amp; Hold",
        marker_color="#2196f3",
        hovertemplate="<b>%{x}</b><br>Avg B&H: %{y:+.2f}%<extra></extra>",
    ))
    year_fig.update_layout(
        barmode="group",
        **_dark_fig_layout("Average Annual Return by Calendar Year", height=420),
    )
    year_fig.update_xaxes(gridcolor="#333", showgrid=True)
    year_fig.update_yaxes(gridcolor="#333", showgrid=True, ticksuffix="%")
    year_div = year_fig.to_html(full_html=False, include_plotlyjs=False)

    # ── Scatter chart ─────────────────────────────────────────────────
    scatter_fig = go.Figure()
    if successful:
        all_vals = (
            [r.buy_hold_return_pct for r in successful] +
            [r.strategy_return_pct for r in successful]
        )
        v_min, v_max = min(all_vals), max(all_vals)
        pad = (v_max - v_min) * 0.05 or 1.0
        scatter_fig.add_trace(go.Scatter(
            x=[v_min - pad, v_max + pad],
            y=[v_min - pad, v_max + pad],
            mode="lines", name="Break-even (Y=X)",
            line=dict(color="#555", dash="dash", width=1),
            hoverinfo="skip",
        ))
        scatter_fig.add_trace(go.Scatter(
            x=[r.buy_hold_return_pct for r in successful],
            y=[r.strategy_return_pct for r in successful],
            mode="markers", name="Ticker",
            marker=dict(
                color=[r.strategy_return_pct - r.buy_hold_return_pct for r in successful],
                colorscale="RdYlGn", size=8, cmid=0,
                showscale=True,
                colorbar=dict(title="Strategy vs B&H %", ticksuffix="%"),
                line=dict(width=0.5, color="#333"),
            ),
            text=[r.ticker for r in successful],
            hovertemplate=(
                "<b>%{text}</b><br>B&H: %{x:+.2f}%<br>"
                "Strategy: %{y:+.2f}%<extra></extra>"
            ),
        ))
    scatter_fig.update_layout(
        xaxis_title="Buy &amp; Hold Return %",
        yaxis_title="Strategy Return %",
        **_dark_fig_layout("Strategy Return vs Buy &amp; Hold (per ticker)", height=500),
    )
    scatter_fig.update_xaxes(gridcolor="#333", showgrid=True, ticksuffix="%")
    scatter_fig.update_yaxes(gridcolor="#333", showgrid=True, ticksuffix="%")
    scatter_div = scatter_fig.to_html(full_html=False, include_plotlyjs=False)

    # ── Heatmap chart ─────────────────────────────────────────────────
    _HEATMAP_MAX = 100
    heatmap_note = ""
    if successful and years:
        # Sort by strategy return descending, cap at _HEATMAP_MAX for performance
        heatmap_pool = sorted(successful, key=lambda r: r.strategy_return_pct, reverse=True)
        if len(heatmap_pool) > _HEATMAP_MAX:
            heatmap_pool = heatmap_pool[:_HEATMAP_MAX]
            heatmap_note = (
                f'<p style="color:#888;font-size:12px;margin:0 0 8px">'
                f'Showing top {_HEATMAP_MAX} tickers by strategy return '
                f'(out of {len(successful)} successful).</p>'
            )
        tickers_heatmap = sorted(r.ticker for r in heatmap_pool)
        ticker_yearly = {r.ticker: r.yearly_returns for r in heatmap_pool}
        raw_z_data = [
            [ticker_yearly[t].get(y) for y in years]
            for t in tickers_heatmap
        ]
        z_data = [
          [_heatmap_color_value(value) for value in row]
          for row in raw_z_data
        ]
        max_positive_return = max(
          (value for row in raw_z_data for value in row if value is not None and value > 0),
          default=100.0,
        )
        heatmap_height = max(400, min(20 * len(tickers_heatmap) + 130, 2400))
        heatmap_fig = go.Figure(go.Heatmap(
          z=z_data, x=years, y=tickers_heatmap,
          customdata=raw_z_data,
            colorscale=[[0, "#ef5350"], [0.5, "#ffffff"], [1, "#26a69a"]],
          zmin=_heatmap_color_value(-100.0),
          zmax=_heatmap_color_value(max_positive_return),
          zmid=0,
            hovertemplate=(
            "<b>%{y}</b><br>Year: %{x}<br>Return: %{customdata:.2f}%<extra></extra>"
            ),
          colorbar=_heatmap_colorbar(max_positive_return),
        ))
        heatmap_fig.update_layout(
            **_dark_fig_layout(
                "Annual Strategy Returns Heatmap", height=heatmap_height,
                margin=dict(l=80, r=30, t=60, b=60),
            ),
        )
        heatmap_div = heatmap_fig.to_html(full_html=False, include_plotlyjs=False)
    else:
        heatmap_div = (
            "<p style='color:#888;padding:20px;'>Not enough data for heatmap.</p>"
        )
        heatmap_note = ""

    # ── Histogram: strategy return distribution ────────────────────────
    if successful:
        import math
        import numpy as np

        def _auto_bin_size(values: list, target_bins: int = 40) -> float:
            """Round bin size to a 'nice' number targeting ~target_bins buckets."""
            spread = max(values) - min(values)
            if spread == 0:
                return 1.0
            raw = spread / target_bins
            magnitude = 10 ** math.floor(math.log10(abs(raw)))
            for nice in (1, 2, 2.5, 5, 10):
                if nice * magnitude >= raw:
                    return nice * magnitude
            return 10 * magnitude

        def _clip_tails(values: list, pct: float = 5.0):
            """Clip bottom/top pct% into the edge bins. Returns clipped list + cutoffs + counts."""
            lo = float(np.percentile(values, pct))
            hi = float(np.percentile(values, 100 - pct))
            clipped = [max(lo, min(hi, v)) for v in values]
            n_lo = sum(1 for v in values if v < lo)
            n_hi = sum(1 for v in values if v > hi)
            return clipped, lo, hi, n_lo, n_hi

        def _tail_annotations(lo, hi, n_lo, n_hi) -> list:
            """Build Plotly annotation dicts for the overflow edge bins."""
            anns = []
            fmt = lambda v: f"${v:,.0f}"
            if n_lo > 0:
                anns.append(dict(
                    x=lo, y=0, xref="x", yref="paper",
                    text=f"≤ {fmt(lo)}<br>({n_lo})",
                    showarrow=False, yanchor="bottom",
                    font=dict(size=10, color="#aaa"),
                    xanchor="right",
                ))
            if n_hi > 0:
                anns.append(dict(
                    x=hi, y=0, xref="x", yref="paper",
                    text=f"≥ {fmt(hi)}<br>({n_hi})",
                    showarrow=False, yanchor="bottom",
                    font=dict(size=10, color="#aaa"),
                    xanchor="left",
                ))
            return anns

        strat_pnl = [r.final_value - r.initial_capital for r in successful]
        strat_clipped, s_lo, s_hi, s_n_lo, s_n_hi = _clip_tails(strat_pnl)
        bin_size_strat = _auto_bin_size(strat_clipped)
        hist_strat_fig = go.Figure(go.Histogram(
            x=strat_clipped,
            xbins=dict(size=bin_size_strat),
            marker=dict(
                color=["#26a69a" if v >= 0 else "#ef5350" for v in strat_clipped],
                line=dict(width=0.5, color="#1e1e1e"),
            ),
            hovertemplate="P&L: $%{x:,.0f}<br>Count: %{y}<extra></extra>",
        ))
        hist_strat_fig.add_vline(x=0, line=dict(color="#888", dash="dash", width=1))
        hist_strat_fig.update_layout(
            xaxis_title="Strategy P&L (USD)",
            yaxis_title="Number of Tickers",
            bargap=0.05,
            annotations=_tail_annotations(s_lo, s_hi, s_n_lo, s_n_hi),
            **_dark_fig_layout("Strategy P&L Distribution", height=420),
        )
        hist_strat_fig.update_xaxes(gridcolor="#333", showgrid=True, tickprefix="$", tickformat=",.0f")
        hist_strat_fig.update_yaxes(gridcolor="#333", showgrid=True)
        hist_strat_div = hist_strat_fig.to_html(full_html=False, include_plotlyjs=False)

        vs_bh_pnl = [r.final_value - r.buy_hold_final_value for r in successful]
        vsbh_clipped, v_lo, v_hi, v_n_lo, v_n_hi = _clip_tails(vs_bh_pnl)
        bin_size_vsbh = _auto_bin_size(vsbh_clipped)
        # Build bins aligned to 0 so negative/positive never share a bin
        _bin_start = math.floor(min(vsbh_clipped) / bin_size_vsbh) * bin_size_vsbh
        _bin_end = math.ceil(max(vsbh_clipped) / bin_size_vsbh) * bin_size_vsbh
        _bins = np.arange(_bin_start, _bin_end + bin_size_vsbh * 0.5, bin_size_vsbh)
        _centers = (_bins[:-1] + _bins[1:]) / 2
        vsbh_neg = [v for v in vsbh_clipped if v < 0]
        vsbh_pos = [v for v in vsbh_clipped if v >= 0]
        hist_vsbh_fig = go.Figure()
        for _vals, _color, _name in [
            (vsbh_neg, "#ef5350", "Underperforms B&H"),
            (vsbh_pos, "#26a69a", "Outperforms B&H"),
        ]:
            _counts, _ = np.histogram(_vals, bins=_bins)
            _hover = [
                f"${_lo:,.0f} – ${_hi:,.0f}<br>Count: {_c}"
                for _lo, _hi, _c in zip(_bins[:-1], _bins[1:], _counts)
            ]
            hist_vsbh_fig.add_trace(go.Bar(
                x=_centers,
                y=_counts,
                width=bin_size_vsbh,
                marker=dict(color=_color, line=dict(width=0.5, color="#1e1e1e")),
                name=_name,
                hovertext=_hover,
                hovertemplate="%{hovertext}<extra></extra>",
            ))
        hist_vsbh_fig.add_vline(x=0, line=dict(color="#888", dash="dash", width=1))
        hist_vsbh_fig.update_layout(
            xaxis_title="Strategy P&L − B&H P&L (USD)",
            yaxis_title="Number of Tickers",
            barmode="overlay",
            annotations=_tail_annotations(v_lo, v_hi, v_n_lo, v_n_hi),
            **_dark_fig_layout("Strategy vs Buy &amp; Hold P&L Distribution", height=420),
        )
        hist_vsbh_fig.update_xaxes(gridcolor="#333", showgrid=True, tickprefix="$", tickformat=",.0f")
        hist_vsbh_fig.update_yaxes(gridcolor="#333", showgrid=True)
        hist_vsbh_div = hist_vsbh_fig.to_html(full_html=False, include_plotlyjs=False)
    else:
        _no_data = "<p style='color:#888;padding:20px;'>Not enough data.</p>"
        hist_strat_div = _no_data
        hist_vsbh_div = _no_data

    # ── Timeframe description ─────────────────────────────────────────
    if result.timeframe_mode == "Full history per ticker":
        tf_desc = "Full history per ticker"
    else:
        tf_desc = (
            f"{html.escape(result.custom_start)} &rarr; {html.escape(result.custom_end)}"
        )

    # ── Assemble page ─────────────────────────────────────────────────
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ProjectQuant &mdash; Bulk Backtest Results</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    background: #1e1e1e; color: #d4d4d4;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 14px;
  }}
  h1 {{ margin: 0 0 4px; font-size: 24px; color: #fff; }}
  .run-meta {{ color: #888; font-size: 12px; margin-bottom: 20px; }}
  .summary {{
    display: flex; flex-wrap: wrap; gap: 16px;
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 20px 24px; margin-bottom: 16px;
  }}
  .stat {{ min-width: 160px; }}
  .stat .label {{
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.05em; color: #888; margin-bottom: 2px;
  }}
  .stat .value {{ font-size: 18px; font-weight: 600; color: #fff; }}
  .table-wrap {{
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 16px; margin-bottom: 16px;
    overflow-x: auto;
  }}
  .table-wrap h3 {{ margin: 0 0 12px; font-size: 15px; color: #fff; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    text-align: left; padding: 8px 12px;
    border-bottom: 2px solid #444; color: #aaa;
    font-weight: 600; text-transform: uppercase; font-size: 11px;
    letter-spacing: 0.03em; white-space: nowrap;
    cursor: pointer; user-select: none;
  }}
  th:hover {{ color: #fff; }}
  th.sort-asc::after {{ content: " \u25b2"; font-size: 9px; }}
  th.sort-desc::after {{ content: " \u25bc"; font-size: 9px; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #2e2e2e; white-space: nowrap; }}
  tr:hover td {{ background: #2a2d2e; }}
  .row-win {{ border-left: 3px solid #26a69a; }}
  .row-loss {{ border-left: 3px solid #ef5350; }}
  .row-error td {{ color: #555; font-style: italic; border-left: 3px solid #444; }}
  .chart-section {{
    background: #252526; border: 1px solid #333;
    border-radius: 8px; padding: 16px;
  }}
  .chart-section h3 {{ margin: 0 0 12px; font-size: 15px; color: #fff; }}
  .chart-tab-btns {{ display: flex; gap: 8px; margin-bottom: 12px; }}
  .chart-tab-btn {{
    background: #333; color: #aaa; border: 1px solid #444;
    border-radius: 4px; padding: 6px 18px; cursor: pointer; font-size: 13px;
    transition: background 0.15s;
  }}
  .chart-tab-btn:hover {{ background: #3a3a3a; color: #fff; }}
  .chart-tab-btn.active {{ background: #26a69a; color: #fff; border-color: #26a69a; }}
</style>
</head>
<body>

<h1>Bulk Backtest Results</h1>
<div class="run-meta">
  Capital: ${result.initial_capital:,.2f} &nbsp;|&nbsp;
  SMA {result.short_sma}/{result.long_sma} &nbsp;|&nbsp;
  Timeframe: {tf_desc} &nbsp;|&nbsp;
  Run at: {html.escape(result.timestamp)}
</div>

<!-- Summary -->
<div class="summary">
  {summary_html}
</div>

<!-- Charts -->
<div class="chart-section">
  <h3>Analysis Charts</h3>
  <div class="chart-tab-btns">
    <button class="chart-tab-btn active" onclick="switchChart('year', this)">By Year</button>
    <button class="chart-tab-btn" onclick="switchChart('scatter', this)">Scatter</button>
    <button class="chart-tab-btn" onclick="switchChart('heatmap', this)">Heatmap</button>
    <button class="chart-tab-btn" onclick="switchChart('hist-strat', this)">Return Distribution</button>
    <button class="chart-tab-btn" onclick="switchChart('hist-vsbh', this)">vs B&amp;H Distribution</button>
  </div>
  <div id="chart-year">{year_div}</div>
  <div id="chart-scatter" style="display:none">{scatter_div}</div>
  <div id="chart-heatmap" style="display:none">{heatmap_note}{heatmap_div}</div>
  <div id="chart-hist-strat" style="display:none">{hist_strat_div}</div>
  <div id="chart-hist-vsbh" style="display:none">{hist_vsbh_div}</div>
</div>

<!-- Per-ticker table -->
<div class="table-wrap" style="margin-top:16px">
  <h3>Results per Ticker <span style="color:#888;font-size:12px;font-weight:400">(click column header to sort)</span></h3>
  <table id="tickerTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Ticker</th>
        <th onclick="sortTable(1)">Period</th>
        <th onclick="sortTable(2)" style="text-align:right"># Trades</th>
        <th onclick="sortTable(3)" style="text-align:right">Strategy Return</th>
        <th onclick="sortTable(4)" style="text-align:right">B&amp;H Return</th>
        <th onclick="sortTable(5)" style="text-align:right">Final Value</th>
        <th onclick="sortTable(6)" style="text-align:right">vs B&amp;H ($)</th>
        <th onclick="sortTable(7)" style="text-align:center">Beat B&amp;H</th>
      </tr>
    </thead>
    <tbody>
{ticker_rows}    </tbody>
  </table>
</div>

<script>
function switchChart(name, btn) {{
  ['year', 'scatter', 'heatmap', 'hist-strat', 'hist-vsbh'].forEach(function(n) {{
    document.getElementById('chart-' + n).style.display = (n === name) ? 'block' : 'none';
  }});
  document.querySelectorAll('.chart-tab-btn').forEach(function(b) {{
    b.classList.remove('active');
  }});
  btn.classList.add('active');
}}

var _sortState = {{col: -1, asc: true}};
function sortTable(col) {{
  var table = document.getElementById('tickerTable');
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var asc = (_sortState.col === col) ? !_sortState.asc : true;
  _sortState = {{col: col, asc: asc}};
  table.querySelectorAll('th').forEach(function(th, i) {{
    th.classList.remove('sort-asc', 'sort-desc');
    if (i === col) th.classList.add(asc ? 'sort-asc' : 'sort-desc');
  }});
  rows.sort(function(a, b) {{
    var aCell = a.cells[col] ? a.cells[col].innerText.trim() : '';
    var bCell = b.cells[col] ? b.cells[col].innerText.trim() : '';
    var aNum = parseFloat(aCell.replace(/[$%+,\u2713\u2717]/g, ''));
    var bNum = parseFloat(bCell.replace(/[$%+,\u2713\u2717]/g, ''));
    var cmp = (!isNaN(aNum) && !isNaN(bNum)) ? aNum - bNum : aCell.localeCompare(bCell);
    return asc ? cmp : -cmp;
  }});
  rows.forEach(function(r) {{ tbody.appendChild(r); }});
}}
</script>

</body>
</html>"""
    return page


def launch_bulk_ui(result: BulkBacktestResult) -> None:
    """Build the bulk results interactive report and open it in the default browser."""
    page_html = _build_bulk_html(result)
    tmp = Path(tempfile.mktemp(suffix=".html", prefix="pq_bulk_"))
    tmp.write_text(page_html, encoding="utf-8")
    webbrowser.open(tmp.as_uri())
