"""Desktop GUI for ProjectQuant using customtkinter."""

import threading
from tkinter import ttk

import customtkinter as ctk

from data.scanner import DatasetInfo, scan_cache, _format_size


class ProjectQuantApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("ProjectQuant")
        self.geometry("1200x800")
        self.minsize(900, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._datasets: list[DatasetInfo] = []
        self._sort_col: str = "Ticker"
        self._sort_reverse: bool = False

        self._build_ui()
        self._style_treeview()
        self._load_data()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = ctk.CTkLabel(
            self, text="ProjectQuant", font=ctk.CTkFont(size=22, weight="bold"),
        )
        header.pack(padx=20, pady=(16, 4), anchor="w")

        subtitle = ctk.CTkLabel(
            self, text="Cached datasets overview",
            font=ctk.CTkFont(size=13), text_color="#888888",
        )
        subtitle.pack(padx=20, pady=(0, 8), anchor="w")

        # Filter bar
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(filter_frame, text="Filter:").pack(side="left", padx=(0, 6))

        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", self._apply_filter)
        filter_entry = ctk.CTkEntry(
            filter_frame, textvariable=self._filter_var,
            placeholder_text="Search ticker...", width=200,
        )
        filter_entry.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(filter_frame, text="Index:").pack(side="left", padx=(0, 6))

        self._index_var = ctk.StringVar(value="All")
        index_combo = ctk.CTkComboBox(
            filter_frame, values=["All", "S&P 500", "Other"],
            variable=self._index_var, width=140, state="readonly",
            command=lambda _: self._apply_filter(),
        )
        index_combo.pack(side="left", padx=(0, 16))

        self._count_label = ctk.CTkLabel(
            filter_frame, text="", text_color="#888888",
        )
        self._count_label.pack(side="left", padx=(16, 0))

        refresh_btn = ctk.CTkButton(
            filter_frame, text="Refresh", width=90, command=self._load_data,
        )
        refresh_btn.pack(side="right")

        # Data table
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        columns = ("Ticker", "Rows", "First Date", "Last Date", "Size", "Index")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse",
        )

        col_widths = {"Ticker": 100, "Rows": 80, "First Date": 120,
                      "Last Date": 120, "Size": 90, "Index": 100}
        col_anchors = {"Rows": "e", "Size": "e"}

        for col in columns:
            self._tree.heading(
                col, text=col,
                command=lambda c=col: self._sort_column(c),
            )
            self._tree.column(
                col,
                width=col_widths.get(col, 100),
                anchor=col_anchors.get(col, "w"),
                minwidth=60,
            )

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # ── Tab view: Single Test / Bulk Test ──────────────────────
        self._ctrl_tabs = ctk.CTkTabview(self)
        self._ctrl_tabs.pack(fill="x", padx=20, pady=(0, 16))

        self._build_single_test_tab(self._ctrl_tabs.add("Single Test"))
        self._build_bulk_test_tab(self._ctrl_tabs.add("Bulk Test"))

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="#d4d4d4",
            fieldbackground="#2b2b2b",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#333333",
            foreground="#d4d4d4",
            borderwidth=1,
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", "#3a3a5c")],
            foreground=[("selected", "#ffffff")],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#444444")],
        )
        style.configure(
            "Horizontal.TProgressbar",
            background="#26a69a",
            troughcolor="#333333",
            borderwidth=0,
            thickness=8,
        )

    # ── Data loading ─────────────────────────────────────────────────

    def _load_data(self):
        self._status_label.configure(text="Scanning cache...")
        self._tree.delete(*self._tree.get_children())

        def _scan():
            datasets = scan_cache()
            self.after(0, lambda: self._on_scan_done(datasets))

        threading.Thread(target=_scan, daemon=True).start()

    def _on_scan_done(self, datasets: list[DatasetInfo]):
        self._datasets = datasets
        self._status_label.configure(text="")
        self._populate_table()

    # ── Table population & filtering ─────────────────────────────────

    def _populate_table(self):
        self._tree.delete(*self._tree.get_children())

        search = self._filter_var.get().strip().upper()
        index_filter = self._index_var.get()

        filtered = self._datasets
        if search:
            filtered = [d for d in filtered if search in d.ticker.upper()]
        if index_filter != "All":
            filtered = [d for d in filtered if d.index == index_filter]

        # Sort
        key_map = {
            "Ticker": lambda d: d.ticker,
            "Rows": lambda d: d.rows,
            "First Date": lambda d: d.first_date,
            "Last Date": lambda d: d.last_date,
            "Size": lambda d: d.size_bytes,
            "Index": lambda d: d.index,
        }
        key_fn = key_map.get(self._sort_col, lambda d: d.ticker)
        filtered.sort(key=key_fn, reverse=self._sort_reverse)

        for d in filtered:
            self._tree.insert("", "end", values=(
                d.ticker,
                f"{d.rows:,}",
                d.first_date,
                d.last_date,
                _format_size(d.size_bytes),
                d.index,
            ))

        self._count_label.configure(text=f"{len(filtered)} / {len(self._datasets)} datasets")

    def _apply_filter(self, *_args):
        self._populate_table()

    def _sort_column(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._populate_table()

    # ── Row selection ────────────────────────────────────────────────

    def _on_row_select(self, _event):
        selection = self._tree.selection()
        if not selection:
            return
        values = self._tree.item(selection[0], "values")
        if not values:
            return

        ticker, _, first_date, last_date = values[0], values[1], values[2], values[3]

        self._bt_entries["Ticker"].delete(0, "end")
        self._bt_entries["Ticker"].insert(0, ticker)
        self._bt_entries["From"].delete(0, "end")
        self._bt_entries["From"].insert(0, first_date)
        self._bt_entries["To"].delete(0, "end")
        self._bt_entries["To"].insert(0, last_date)

    # ── Backtest execution ───────────────────────────────────────────

    def _use_full_date_range(self):
        ticker = self._bt_entries["Ticker"].get().strip().upper()
        if not ticker:
            self._status_label.configure(text="Enter a ticker first.", text_color="#ef5350")
            return
        match = next((d for d in self._datasets if d.ticker.upper() == ticker), None)
        if match is None:
            self._status_label.configure(
                text=f"Ticker '{ticker}' not found in loaded datasets.", text_color="#ef5350",
            )
            return
        self._bt_entries["From"].delete(0, "end")
        self._bt_entries["From"].insert(0, match.first_date)
        self._bt_entries["To"].delete(0, "end")
        self._bt_entries["To"].insert(0, match.last_date)
        self._status_label.configure(text="", text_color="#888888")

    def _run_backtest(self):
        ticker = self._bt_entries["Ticker"].get().strip()
        start = self._bt_entries["From"].get().strip()
        end = self._bt_entries["To"].get().strip()
        capital_str = self._bt_entries["Capital"].get().strip()
        short_str = self._bt_entries["Short SMA"].get().strip()
        long_str = self._bt_entries["Long SMA"].get().strip()

        if not ticker or not start or not end:
            self._status_label.configure(text="Ticker, From, and To are required.", text_color="#ef5350")
            return

        try:
            capital = float(capital_str) if capital_str else 10_000.0
            short_window = int(short_str) if short_str else 50
            long_window = int(long_str) if long_str else 200
        except ValueError:
            self._status_label.configure(text="Invalid numeric input.", text_color="#ef5350")
            return

        self._run_btn.configure(state="disabled")
        self._status_label.configure(
            text=f"Running backtest for {ticker}...", text_color="#888888",
        )

        def _execute():
            try:
                from data.fetcher import fetch_data
                from strategies.sma_cross import SMACrossStrategy
                from engine.backtester import Backtester
                from display.ui import launch_ui

                df = fetch_data(ticker, start, end)
                strategy = SMACrossStrategy(short_window=short_window, long_window=long_window)
                signals = strategy.generate_signals(df)
                bt = Backtester(initial_capital=capital)
                result = bt.run(df, signals)

                self.after(0, lambda: self._on_backtest_done(
                    ticker, start, end, capital, result, df, short_window, long_window,
                ))
            except Exception as exc:
                self.after(0, lambda: self._on_backtest_error(str(exc)))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_backtest_done(self, ticker, start, end, capital, result, df, short_window, long_window):
        self._run_btn.configure(state="normal")
        self._status_label.configure(
            text=f"Backtest complete \u2014 {len(result.trades)} trades. Opening results...",
            text_color="#26a69a",
        )

        def _build_and_open():
            from display.ui import launch_ui
            try:
                launch_ui(
                    ticker=ticker,
                    start=start,
                    end=end,
                    initial_capital=capital,
                    result=result,
                    df=df,
                    short_window=short_window,
                    long_window=long_window,
                )
                self.after(0, lambda: self._status_label.configure(
                    text=f"Backtest complete \u2014 {len(result.trades)} trades. Report opened in browser.",
                    text_color="#26a69a",
                ))
            except Exception as exc:
                self.after(0, lambda msg=str(exc): self._status_label.configure(
                    text=f"Report error: {msg}", text_color="#ef5350",
                ))

        threading.Thread(target=_build_and_open, daemon=True).start()

    def _on_backtest_error(self, message: str):
        self._run_btn.configure(state="normal")
        self._status_label.configure(text=f"Error: {message}", text_color="#ef5350")

    # ── Tab builders ─────────────────────────────────────────────────

    def _build_single_test_tab(self, tab: ctk.CTkFrame):
        """Recreate the single-ticker backtest controls inside *tab*."""
        ctk.CTkLabel(
            tab, text="Run Backtest",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=14, padx=12, pady=(12, 8), sticky="w")

        labels = ["Ticker", "From", "To", "Capital", "Short SMA", "Long SMA"]
        defaults = ["", "", "", "10000", "50", "200"]
        placeholders = ["AAPL", "YYYY-MM-DD", "YYYY-MM-DD", "10000", "50", "200"]
        widths = [100, 130, 130, 100, 80, 80]
        self._bt_entries: dict[str, ctk.CTkEntry] = {}

        for i, (label, default, ph, w) in enumerate(zip(labels, defaults, placeholders, widths)):
            ctk.CTkLabel(tab, text=label + ":").grid(
                row=1, column=i * 2, padx=(12 if i == 0 else 4, 2), pady=(0, 12), sticky="e",
            )
            entry = ctk.CTkEntry(tab, width=w, placeholder_text=ph)
            if default:
                entry.insert(0, default)
            entry.grid(row=1, column=i * 2 + 1, padx=(0, 8), pady=(0, 12))
            self._bt_entries[label] = entry

        self._run_btn = ctk.CTkButton(
            tab, text="Run Backtest", width=130,
            fg_color="#26a69a", hover_color="#1e8c82",
            command=self._run_backtest,
        )
        self._run_btn.grid(row=1, column=len(labels) * 2, padx=(8, 4), pady=(0, 12))

        self._full_range_btn = ctk.CTkButton(
            tab, text="Full Range", width=100,
            fg_color="#555", hover_color="#444",
            command=self._use_full_date_range,
        )
        self._full_range_btn.grid(row=1, column=len(labels) * 2 + 1, padx=(0, 12), pady=(0, 12))

        self._status_label = ctk.CTkLabel(tab, text="", text_color="#888888")
        self._status_label.grid(
            row=2, column=0, columnspan=len(labels) * 2 + 2,
            padx=12, pady=(0, 8), sticky="w",
        )

    def _build_bulk_test_tab(self, tab: ctk.CTkFrame):
        """Build bulk backtest controls inside *tab*."""
        ctk.CTkLabel(
            tab, text="Run Bulk Backtest",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 8))

        # ── Param row ────────────────────────────────────────────────
        param_row = ctk.CTkFrame(tab, fg_color="transparent")
        param_row.pack(fill="x", padx=12, pady=(0, 4))

        self._bulk_entries: dict[str, ctk.CTkEntry] = {}
        for label, default, width in [
            ("Capital", "10000", 100),
            ("Short SMA", "50", 80),
            ("Long SMA", "200", 80),
        ]:
            ctk.CTkLabel(param_row, text=label + ":").pack(side="left", padx=(0, 2))
            entry = ctk.CTkEntry(param_row, width=width)
            entry.insert(0, default)
            entry.pack(side="left", padx=(0, 14))
            self._bulk_entries[label] = entry

        ctk.CTkLabel(param_row, text="Mode:").pack(side="left", padx=(0, 2))
        self._bulk_mode_var = ctk.StringVar(value="Custom date range")
        ctk.CTkComboBox(
            param_row,
            values=["Custom date range", "Full history per ticker"],
            variable=self._bulk_mode_var,
            width=210,
            state="readonly",
            command=self._on_bulk_mode_change,
        ).pack(side="left", padx=(0, 8))

        # ── Date row (toggled by mode selection) ─────────────────────
        self._bulk_date_row = ctk.CTkFrame(tab, fg_color="transparent")
        self._bulk_date_row.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(self._bulk_date_row, text="From:").pack(side="left", padx=(0, 2))
        self._bulk_from_entry = ctk.CTkEntry(
            self._bulk_date_row, width=130, placeholder_text="YYYY-MM-DD",
        )
        self._bulk_from_entry.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(self._bulk_date_row, text="To:").pack(side="left", padx=(0, 2))
        self._bulk_to_entry = ctk.CTkEntry(
            self._bulk_date_row, width=130, placeholder_text="YYYY-MM-DD",
        )
        self._bulk_to_entry.pack(side="left")

        # ── Run row ──────────────────────────────────────────────────
        self._bulk_run_row = ctk.CTkFrame(tab, fg_color="transparent")
        self._bulk_run_row.pack(fill="x", padx=12, pady=(4, 4))

        self._bulk_run_btn = ctk.CTkButton(
            self._bulk_run_row, text="Run All Tickers", width=150,
            fg_color="#ff9800", hover_color="#c77800",
            command=self._run_bulk_backtest,
        )
        self._bulk_run_btn.pack(side="left", padx=(0, 14))

        self._bulk_progress_label = ctk.CTkLabel(
            self._bulk_run_row, text="", text_color="#888888", anchor="w",
        )
        self._bulk_progress_label.pack(side="left", padx=(4, 0))

        # ── Progress bar ─────────────────────────────────────────────
        self._bulk_progress_bar = ttk.Progressbar(
            tab, orient="horizontal", mode="determinate",
        )
        self._bulk_progress_bar.pack(fill="x", padx=12, pady=(2, 4))

        # ── Status ───────────────────────────────────────────────────
        self._bulk_status_label = ctk.CTkLabel(tab, text="", text_color="#888888")
        self._bulk_status_label.pack(anchor="w", padx=12, pady=(0, 8))

    # ── Bulk mode toggle ──────────────────────────────────────────────

    def _on_bulk_mode_change(self, _=None):
        if self._bulk_mode_var.get() == "Full history per ticker":
            self._bulk_date_row.pack_forget()
        else:
            self._bulk_date_row.pack(
                fill="x", padx=12, pady=(0, 4),
                before=self._bulk_run_row,
            )

    # ── Bulk backtest execution ───────────────────────────────────────

    def _run_bulk_backtest(self):
        capital_str = self._bulk_entries["Capital"].get().strip()
        short_str = self._bulk_entries["Short SMA"].get().strip()
        long_str = self._bulk_entries["Long SMA"].get().strip()
        mode = self._bulk_mode_var.get()

        try:
            capital = float(capital_str) if capital_str else 10_000.0
            short_window = int(short_str) if short_str else 50
            long_window = int(long_str) if long_str else 200
        except ValueError:
            self._bulk_status_label.configure(
                text="Invalid numeric input.", text_color="#ef5350",
            )
            return

        start: str | None = None
        end: str | None = None
        if mode == "Custom date range":
            start = self._bulk_from_entry.get().strip()
            end = self._bulk_to_entry.get().strip()
            if not start or not end:
                self._bulk_status_label.configure(
                    text="From and To dates are required for Custom date range.",
                    text_color="#ef5350",
                )
                return

        if not self._datasets:
            self._bulk_status_label.configure(
                text="No datasets loaded. Click Refresh first.", text_color="#ef5350",
            )
            return

        total = len(self._datasets)
        self._bulk_run_btn.configure(state="disabled")
        self._bulk_progress_bar.configure(maximum=total, value=0)
        self._bulk_progress_label.configure(text=f"0 / {total}")
        self._bulk_status_label.configure(
            text=f"Running bulk backtest on {total} tickers...", text_color="#888888",
        )

        datasets_snapshot = list(self._datasets)

        def _progress_cb(done: int, tot: int, ticker: str):
            self.after(0, lambda d=done, t=tot, tk=ticker: self._on_bulk_progress(d, t, tk))

        def _execute():
            try:
                from engine.bulk_runner import run_bulk_backtest
                result = run_bulk_backtest(
                    datasets=datasets_snapshot,
                    start=start,
                    end=end,
                    capital=capital,
                    short_sma=short_window,
                    long_sma=long_window,
                    timeframe_mode=mode,
                    workers=8,
                    progress_cb=_progress_cb,
                )
                self.after(0, lambda: self._on_bulk_done(result))
            except Exception as exc:
                self.after(0, lambda: self._on_bulk_error(str(exc)))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_bulk_progress(self, done: int, total: int, ticker: str):
        self._bulk_progress_bar.configure(value=done)
        self._bulk_progress_label.configure(text=f"Running {ticker} \u2014 {done} / {total}")

    def _on_bulk_done(self, result):
        self._bulk_run_btn.configure(state="normal")
        successful = sum(1 for r in result.ticker_results if r.error is None)
        n = len(result.ticker_results)
        self._bulk_progress_bar.configure(value=n)
        self._bulk_progress_label.configure(text=f"{n} / {n}")
        self._bulk_status_label.configure(
            text=f"Complete \u2014 {successful}/{n} succeeded. Building report...",
            text_color="#26a69a",
        )

        def _build_and_open():
            from display.ui import launch_bulk_ui
            try:
                launch_bulk_ui(result)
                self.after(0, lambda: self._bulk_status_label.configure(
                    text=f"Complete \u2014 {successful}/{n} succeeded. Report opened in browser.",
                    text_color="#26a69a",
                ))
            except Exception as exc:
                self.after(0, lambda msg=str(exc): self._bulk_status_label.configure(
                    text=f"Report error: {msg}", text_color="#ef5350",
                ))

        threading.Thread(target=_build_and_open, daemon=True).start()

    def _on_bulk_error(self, message: str):
        self._bulk_run_btn.configure(state="normal")
        self._bulk_status_label.configure(text=f"Error: {message}", text_color="#ef5350")


def launch_desktop():
    """Create and run the desktop application."""
    app = ProjectQuantApp()
    app.mainloop()
