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

        # Per-strategy UI state keyed by "sma" or "ema"
        self._st: dict[str, dict] = {"sma": {}, "ema": {}}

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
            filter_frame, values=["All", "S&P 500", "DAX 30", "Other"],
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

        # ── Outer strategy tabs: SMA Strategy / EMA Strategy ─────────
        self._strategy_tabs = ctk.CTkTabview(self)
        self._strategy_tabs.pack(fill="x", padx=20, pady=(0, 16))

        for strat, label in [("sma", "SMA Strategy"), ("ema", "EMA Strategy")]:
            outer_tab = self._strategy_tabs.add(label)
            inner_tabs = ctk.CTkTabview(outer_tab)
            inner_tabs.pack(fill="both", expand=True, padx=0, pady=0)
            self._build_single_test_tab(inner_tabs.add("Single Test"), strat)
            self._build_bulk_test_tab(inner_tabs.add("Bulk Test"), strat)
            self._build_matrix_test_tab(inner_tabs.add("Matrix Test"), strat)

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
        self._count_label.configure(text="Scanning cache...")
        self._tree.delete(*self._tree.get_children())

        def _scan():
            datasets = scan_cache()
            self.after(0, lambda: self._on_scan_done(datasets))

        threading.Thread(target=_scan, daemon=True).start()

    def _on_scan_done(self, datasets: list[DatasetInfo]):
        self._datasets = datasets
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

        # Populate both strategies' Single Test entries
        for strat in ("sma", "ema"):
            entries = self._st[strat]["bt_entries"]
            entries["Ticker"].delete(0, "end")
            entries["Ticker"].insert(0, ticker)
            entries["From"].delete(0, "end")
            entries["From"].insert(0, first_date)
            entries["To"].delete(0, "end")
            entries["To"].insert(0, last_date)

    # ── Full date range ──────────────────────────────────────────────

    def _use_full_date_range(self, strat: str):
        s = self._st[strat]
        ticker = s["bt_entries"]["Ticker"].get().strip().upper()
        if not ticker:
            s["status_label"].configure(text="Enter a ticker first.", text_color="#ef5350")
            return
        match = next((d for d in self._datasets if d.ticker.upper() == ticker), None)
        if match is None:
            s["status_label"].configure(
                text=f"Ticker '{ticker}' not found in loaded datasets.", text_color="#ef5350",
            )
            return
        s["bt_entries"]["From"].delete(0, "end")
        s["bt_entries"]["From"].insert(0, match.first_date)
        s["bt_entries"]["To"].delete(0, "end")
        s["bt_entries"]["To"].insert(0, match.last_date)
        s["status_label"].configure(text="", text_color="#888888")

    # ── Backtest execution ───────────────────────────────────────────

    def _run_backtest(self, strat: str):
        s = self._st[strat]
        ticker = s["bt_entries"]["Ticker"].get().strip()
        start = s["bt_entries"]["From"].get().strip()
        end = s["bt_entries"]["To"].get().strip()
        capital_str = s["bt_entries"]["Capital"].get().strip()
        short_str = s["bt_entries"]["Short"].get().strip()
        long_str = s["bt_entries"]["Long"].get().strip()
        allow_short = s["allow_short_var"].get()
        short_rate_str = s["bt_entries"]["ShortRate"].get().strip()
        long_pct_str = s["bt_entries"]["LongPct"].get().strip()
        short_pct_str = s["bt_entries"]["ShortPct"].get().strip()

        if not ticker or not start or not end:
            s["status_label"].configure(
                text="Ticker, From, and To are required.", text_color="#ef5350",
            )
            return

        try:
            capital = float(capital_str) if capital_str else 10_000.0
            short_window = int(short_str) if short_str else 50
            long_window = int(long_str) if long_str else 200
            short_rate = float(short_rate_str) if short_rate_str else 2.0
            long_pct = float(long_pct_str) if long_pct_str else 100.0
            short_pct = float(short_pct_str) if short_pct_str else 100.0
        except ValueError:
            s["status_label"].configure(text="Invalid numeric input.", text_color="#ef5350")
            return

        s["run_btn"].configure(state="disabled")
        s["status_label"].configure(
            text=f"Running backtest for {ticker}...", text_color="#888888",
        )

        def _execute():
            try:
                from data.fetcher import fetch_data
                from engine.backtester import Backtester

                if strat == "ema":
                    from strategies.ema_cross import EMACrossStrategy
                    strategy = EMACrossStrategy(short_window=short_window, long_window=long_window)
                else:
                    from strategies.sma_cross import SMACrossStrategy
                    strategy = SMACrossStrategy(short_window=short_window, long_window=long_window)

                df = fetch_data(ticker, start, end)
                signals = strategy.generate_signals(df)
                bt = Backtester(
                    initial_capital=capital,
                    allow_short=allow_short,
                    short_interest_rate=short_rate,
                    long_pct=long_pct,
                    short_pct=short_pct,
                )
                result = bt.run(df, signals)

                self.after(0, lambda: self._on_backtest_done(
                    ticker, start, end, capital, result, df, short_window, long_window, strat,
                ))
            except Exception as exc:
                self.after(0, lambda: self._on_backtest_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_backtest_done(self, ticker, start, end, capital, result, df, short_window, long_window, strat):
        s = self._st[strat]
        s["run_btn"].configure(state="normal")
        s["status_label"].configure(
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
                    strategy_type=strat,
                )
                self.after(0, lambda: s["status_label"].configure(
                    text=f"Backtest complete \u2014 {len(result.trades)} trades. Report opened in browser.",
                    text_color="#26a69a",
                ))
            except Exception as exc:
                self.after(0, lambda msg=str(exc): s["status_label"].configure(
                    text=f"Report error: {msg}", text_color="#ef5350",
                ))

        threading.Thread(target=_build_and_open, daemon=True).start()

    def _on_backtest_error(self, message: str, strat: str):
        s = self._st[strat]
        s["run_btn"].configure(state="normal")
        s["status_label"].configure(text=f"Error: {message}", text_color="#ef5350")

    # ── Tab builders ─────────────────────────────────────────────────

    def _build_single_test_tab(self, tab: ctk.CTkFrame, strat: str):
        s = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"

        ctk.CTkLabel(
            tab, text="Run Backtest",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=14, padx=12, pady=(12, 8), sticky="w")

        # (internal key, display label, default, placeholder, width)
        fields = [
            ("Ticker",  "Ticker",          "",      "AAPL",       100),
            ("From",    "From",            "",      "YYYY-MM-DD", 130),
            ("To",      "To",              "",      "YYYY-MM-DD", 130),
            ("Capital", "Capital",         "10000", "10000",      100),
            ("Short",   f"Short {ind}",    "50",    "50",          80),
            ("Long",    f"Long {ind}",     "200",   "200",         80),
        ]
        s["bt_entries"] = {}

        for i, (key, ui_label, default, ph, w) in enumerate(fields):
            ctk.CTkLabel(tab, text=ui_label + ":").grid(
                row=1, column=i * 2, padx=(12 if i == 0 else 4, 2), pady=(0, 12), sticky="e",
            )
            entry = ctk.CTkEntry(tab, width=w, placeholder_text=ph)
            if default:
                entry.insert(0, default)
            entry.grid(row=1, column=i * 2 + 1, padx=(0, 8), pady=(0, 12))
            s["bt_entries"][key] = entry

        s["run_btn"] = ctk.CTkButton(
            tab, text="Run Backtest", width=130,
            fg_color="#26a69a", hover_color="#1e8c82",
            command=lambda: self._run_backtest(strat),
        )
        s["run_btn"].grid(row=1, column=len(fields) * 2, padx=(8, 4), pady=(0, 12))

        s["full_range_btn"] = ctk.CTkButton(
            tab, text="Full Range", width=100,
            fg_color="#555", hover_color="#444",
            command=lambda: self._use_full_date_range(strat),
        )
        s["full_range_btn"].grid(row=1, column=len(fields) * 2 + 1, padx=(0, 12), pady=(0, 12))

        # ── Row 2: short-selling settings ────────────────────────────
        ctk.CTkLabel(tab, text="Allow Shorts:").grid(
            row=2, column=0, padx=(12, 2), pady=(0, 10), sticky="e",
        )
        s["allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(tab, text="", variable=s["allow_short_var"], width=46).grid(
            row=2, column=1, padx=(0, 8), pady=(0, 10), sticky="w",
        )

        short_fields = [
            ("ShortRate", "Interest Rate (% p.a.)", "2.0", 70),
            ("LongPct",   "Long % Capital",         "100", 70),
            ("ShortPct",  "Short % Capital",        "100", 70),
        ]
        for col_offset, (key, ui_label, default, w) in enumerate(short_fields):
            ctk.CTkLabel(tab, text=ui_label + ":").grid(
                row=2, column=2 + col_offset * 2, padx=(4, 2), pady=(0, 10), sticky="e",
            )
            entry = ctk.CTkEntry(tab, width=w)
            entry.insert(0, default)
            entry.grid(row=2, column=3 + col_offset * 2, padx=(0, 8), pady=(0, 10))
            s["bt_entries"][key] = entry

        s["status_label"] = ctk.CTkLabel(tab, text="", text_color="#888888")
        s["status_label"].grid(
            row=3, column=0, columnspan=len(fields) * 2 + 2,
            padx=12, pady=(0, 8), sticky="w",
        )

    def _build_bulk_test_tab(self, tab: ctk.CTkFrame, strat: str):
        s = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"

        ctk.CTkLabel(
            tab, text="Run Bulk Backtest",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 8))

        # ── Param row ────────────────────────────────────────────────
        param_row = ctk.CTkFrame(tab, fg_color="transparent")
        param_row.pack(fill="x", padx=12, pady=(0, 4))

        s["bulk_entries"] = {}
        for ui_label, key, default, width in [
            ("Capital",       "Capital", "10000", 100),
            (f"Short {ind}",  "Short",   "50",     80),
            (f"Long {ind}",   "Long",    "200",    80),
        ]:
            ctk.CTkLabel(param_row, text=ui_label + ":").pack(side="left", padx=(0, 2))
            entry = ctk.CTkEntry(param_row, width=width)
            entry.insert(0, default)
            entry.pack(side="left", padx=(0, 14))
            s["bulk_entries"][key] = entry

        ctk.CTkLabel(param_row, text="Mode:").pack(side="left", padx=(0, 2))
        s["bulk_mode_var"] = ctk.StringVar(value="Custom date range")
        ctk.CTkComboBox(
            param_row,
            values=["Custom date range", "Full history per ticker"],
            variable=s["bulk_mode_var"],
            width=210,
            state="readonly",
            command=lambda _: self._on_bulk_mode_change(strat),
        ).pack(side="left", padx=(0, 8))

        # ── Short-selling settings row ────────────────────────────────
        short_row = ctk.CTkFrame(tab, fg_color="transparent")
        short_row.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(short_row, text="Allow Shorts:").pack(side="left", padx=(0, 2))
        s["bulk_allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(short_row, text="", variable=s["bulk_allow_short_var"], width=46).pack(
            side="left", padx=(0, 14),
        )
        s["bulk_short_entries"] = {}
        for ui_label, key, default, width in [
            ("Interest Rate (% p.a.)", "ShortRate", "2.0",  70),
            ("Long % Capital",         "LongPct",   "100",  70),
            ("Short % Capital",        "ShortPct",  "100",  70),
        ]:
            ctk.CTkLabel(short_row, text=ui_label + ":").pack(side="left", padx=(0, 2))
            entry = ctk.CTkEntry(short_row, width=width)
            entry.insert(0, default)
            entry.pack(side="left", padx=(0, 14))
            s["bulk_short_entries"][key] = entry

        # ── Date row (toggled by mode selection) ─────────────────────
        s["bulk_date_row"] = ctk.CTkFrame(tab, fg_color="transparent")
        s["bulk_date_row"].pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(s["bulk_date_row"], text="From:").pack(side="left", padx=(0, 2))
        s["bulk_from_entry"] = ctk.CTkEntry(
            s["bulk_date_row"], width=130, placeholder_text="YYYY-MM-DD",
        )
        s["bulk_from_entry"].pack(side="left", padx=(0, 14))

        ctk.CTkLabel(s["bulk_date_row"], text="To:").pack(side="left", padx=(0, 2))
        s["bulk_to_entry"] = ctk.CTkEntry(
            s["bulk_date_row"], width=130, placeholder_text="YYYY-MM-DD",
        )
        s["bulk_to_entry"].pack(side="left")

        # ── Run row ──────────────────────────────────────────────────
        s["bulk_run_row"] = ctk.CTkFrame(tab, fg_color="transparent")
        s["bulk_run_row"].pack(fill="x", padx=12, pady=(4, 4))

        s["bulk_run_btn"] = ctk.CTkButton(
            s["bulk_run_row"], text="Run All Tickers", width=150,
            fg_color="#ff9800", hover_color="#c77800",
            command=lambda: self._run_bulk_backtest(strat),
        )
        s["bulk_run_btn"].pack(side="left", padx=(0, 14))

        s["bulk_progress_label"] = ctk.CTkLabel(
            s["bulk_run_row"], text="", text_color="#888888", anchor="w",
        )
        s["bulk_progress_label"].pack(side="left", padx=(4, 0))

        # ── Progress bar ─────────────────────────────────────────────
        s["bulk_progress_bar"] = ttk.Progressbar(
            tab, orient="horizontal", mode="determinate",
        )
        s["bulk_progress_bar"].pack(fill="x", padx=12, pady=(2, 4))

        # ── Status ───────────────────────────────────────────────────
        s["bulk_status_label"] = ctk.CTkLabel(tab, text="", text_color="#888888")
        s["bulk_status_label"].pack(anchor="w", padx=12, pady=(0, 8))

    # ── Bulk mode toggle ──────────────────────────────────────────────

    def _on_bulk_mode_change(self, strat: str):
        s = self._st[strat]
        if s["bulk_mode_var"].get() == "Full history per ticker":
            s["bulk_date_row"].pack_forget()
        else:
            s["bulk_date_row"].pack(
                fill="x", padx=12, pady=(0, 4),
                before=s["bulk_run_row"],
            )

    # ── Bulk backtest execution ───────────────────────────────────────

    def _run_bulk_backtest(self, strat: str):
        s = self._st[strat]
        capital_str = s["bulk_entries"]["Capital"].get().strip()
        short_str = s["bulk_entries"]["Short"].get().strip()
        long_str = s["bulk_entries"]["Long"].get().strip()
        mode = s["bulk_mode_var"].get()
        allow_short = s["bulk_allow_short_var"].get()
        short_rate_str = s["bulk_short_entries"]["ShortRate"].get().strip()
        long_pct_str = s["bulk_short_entries"]["LongPct"].get().strip()
        short_pct_str = s["bulk_short_entries"]["ShortPct"].get().strip()

        try:
            capital = float(capital_str) if capital_str else 10_000.0
            short_window = int(short_str) if short_str else 50
            long_window = int(long_str) if long_str else 200
            short_rate = float(short_rate_str) if short_rate_str else 2.0
            long_pct = float(long_pct_str) if long_pct_str else 100.0
            short_pct = float(short_pct_str) if short_pct_str else 100.0
        except ValueError:
            s["bulk_status_label"].configure(
                text="Invalid numeric input.", text_color="#ef5350",
            )
            return

        start: str | None = None
        end: str | None = None
        if mode == "Custom date range":
            start = s["bulk_from_entry"].get().strip()
            end = s["bulk_to_entry"].get().strip()
            if not start or not end:
                s["bulk_status_label"].configure(
                    text="From and To dates are required for Custom date range.",
                    text_color="#ef5350",
                )
                return

        if not self._datasets:
            s["bulk_status_label"].configure(
                text="No datasets loaded. Click Refresh first.", text_color="#ef5350",
            )
            return

        total = len(self._datasets)
        s["bulk_run_btn"].configure(state="disabled")
        s["bulk_progress_bar"].configure(maximum=total, value=0)
        s["bulk_progress_label"].configure(text=f"0 / {total}")
        s["bulk_status_label"].configure(
            text=f"Running bulk backtest on {total} tickers...", text_color="#888888",
        )

        datasets_snapshot = list(self._datasets)

        def _progress_cb(done: int, tot: int, ticker: str):
            self.after(0, lambda d=done, t=tot, tk=ticker: self._on_bulk_progress(d, t, tk, strat))

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
                    strategy_type=strat,
                    allow_short=allow_short,
                    short_interest_rate=short_rate,
                    long_pct=long_pct,
                    short_pct=short_pct,
                    workers=8,
                    progress_cb=_progress_cb,
                )
                self.after(0, lambda: self._on_bulk_done(result, strat))
            except Exception as exc:
                self.after(0, lambda: self._on_bulk_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_bulk_progress(self, done: int, total: int, ticker: str, strat: str):
        s = self._st[strat]
        s["bulk_progress_bar"].configure(value=done)
        s["bulk_progress_label"].configure(text=f"Running {ticker} \u2014 {done} / {total}")

    def _on_bulk_done(self, result, strat: str):
        s = self._st[strat]
        s["bulk_run_btn"].configure(state="normal")
        successful = sum(1 for r in result.ticker_results if r.error is None)
        n = len(result.ticker_results)
        s["bulk_progress_bar"].configure(value=n)
        s["bulk_progress_label"].configure(text=f"{n} / {n}")
        s["bulk_status_label"].configure(
            text=f"Complete \u2014 {successful}/{n} succeeded. Building report...",
            text_color="#26a69a",
        )

        def _build_and_open():
            from display.ui import launch_bulk_ui
            try:
                launch_bulk_ui(result)
                self.after(0, lambda: s["bulk_status_label"].configure(
                    text=f"Complete \u2014 {successful}/{n} succeeded. Report opened in browser.",
                    text_color="#26a69a",
                ))
            except Exception as exc:
                self.after(0, lambda msg=str(exc): s["bulk_status_label"].configure(
                    text=f"Report error: {msg}", text_color="#ef5350",
                ))

        threading.Thread(target=_build_and_open, daemon=True).start()

    def _on_bulk_error(self, message: str, strat: str):
        s = self._st[strat]
        s["bulk_run_btn"].configure(state="normal")
        s["bulk_status_label"].configure(text=f"Error: {message}", text_color="#ef5350")

    # ── Matrix Test tab ───────────────────────────────────────────────

    def _build_matrix_test_tab(self, tab: ctk.CTkFrame, strat: str):
        s = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"

        ctk.CTkLabel(
            tab, text="Run Matrix Test",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 8))

        # ── Param row ────────────────────────────────────────────────
        param_row = ctk.CTkFrame(tab, fg_color="transparent")
        param_row.pack(fill="x", padx=12, pady=(0, 4))

        s["matrix_entries"] = {}
        for ui_label, key, default, width in [
            ("Assets per Test",  "Assets per Test",  "30",  70),
            (f"{ind} From",      "From",             "3",   60),
            (f"{ind} To",        "To",               "200", 60),
            ("Max Combinations", "Max Combinations", "150", 70),
            ("Capital",          "Capital",          "10000", 100),
        ]:
            ctk.CTkLabel(param_row, text=ui_label + ":").pack(side="left", padx=(0, 2))
            entry = ctk.CTkEntry(param_row, width=width)
            entry.insert(0, default)
            entry.pack(side="left", padx=(0, 14))
            s["matrix_entries"][key] = entry

        ctk.CTkLabel(param_row, text="Mode:").pack(side="left", padx=(0, 2))
        s["matrix_mode_var"] = ctk.StringVar(value="Full history per ticker")
        ctk.CTkComboBox(
            param_row,
            values=["Custom date range", "Full history per ticker"],
            variable=s["matrix_mode_var"],
            width=210,
            state="readonly",
            command=lambda _: self._on_matrix_mode_change(strat),
        ).pack(side="left", padx=(0, 8))

        # ── Short-selling settings row ────────────────────────────────
        matrix_short_row = ctk.CTkFrame(tab, fg_color="transparent")
        matrix_short_row.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(matrix_short_row, text="Allow Shorts:").pack(side="left", padx=(0, 2))
        s["matrix_allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(matrix_short_row, text="", variable=s["matrix_allow_short_var"], width=46).pack(
            side="left", padx=(0, 14),
        )
        s["matrix_short_entries"] = {}
        for ui_label, key, default, width in [
            ("Interest Rate (% p.a.)", "ShortRate", "2.0",  70),
            ("Long % Capital",         "LongPct",   "100",  70),
            ("Short % Capital",        "ShortPct",  "100",  70),
        ]:
            ctk.CTkLabel(matrix_short_row, text=ui_label + ":").pack(side="left", padx=(0, 2))
            entry = ctk.CTkEntry(matrix_short_row, width=width)
            entry.insert(0, default)
            entry.pack(side="left", padx=(0, 14))
            s["matrix_short_entries"][key] = entry

        # ── Date row (toggled by mode selection) ─────────────────────
        s["matrix_date_row"] = ctk.CTkFrame(tab, fg_color="transparent")

        ctk.CTkLabel(s["matrix_date_row"], text="From:").pack(side="left", padx=(0, 2))
        s["matrix_from_entry"] = ctk.CTkEntry(
            s["matrix_date_row"], width=130, placeholder_text="YYYY-MM-DD",
        )
        s["matrix_from_entry"].pack(side="left", padx=(0, 14))

        ctk.CTkLabel(s["matrix_date_row"], text="To:").pack(side="left", padx=(0, 2))
        s["matrix_to_entry"] = ctk.CTkEntry(
            s["matrix_date_row"], width=130, placeholder_text="YYYY-MM-DD",
        )
        s["matrix_to_entry"].pack(side="left")

        # ── Run row ──────────────────────────────────────────────────
        s["matrix_run_row"] = ctk.CTkFrame(tab, fg_color="transparent")
        s["matrix_run_row"].pack(fill="x", padx=12, pady=(4, 4))

        s["matrix_run_btn"] = ctk.CTkButton(
            s["matrix_run_row"], text="Run Matrix Test", width=150,
            fg_color="#9c27b0", hover_color="#7b1fa2",
            command=lambda: self._run_matrix_test(strat),
        )
        s["matrix_run_btn"].pack(side="left", padx=(0, 14))

        s["matrix_progress_label"] = ctk.CTkLabel(
            s["matrix_run_row"], text="", text_color="#888888", anchor="w",
        )
        s["matrix_progress_label"].pack(side="left", padx=(4, 0))

        # ── Progress bar ─────────────────────────────────────────────
        s["matrix_progress_bar"] = ttk.Progressbar(
            tab, orient="horizontal", mode="determinate",
        )
        s["matrix_progress_bar"].pack(fill="x", padx=12, pady=(2, 4))

        # ── Status ───────────────────────────────────────────────────
        s["matrix_status_label"] = ctk.CTkLabel(tab, text="", text_color="#888888")
        s["matrix_status_label"].pack(anchor="w", padx=12, pady=(0, 8))

    def _on_matrix_mode_change(self, strat: str):
        s = self._st[strat]
        if s["matrix_mode_var"].get() == "Full history per ticker":
            s["matrix_date_row"].pack_forget()
        else:
            s["matrix_date_row"].pack(
                fill="x", padx=12, pady=(0, 4),
                before=s["matrix_run_row"],
            )

    def _run_matrix_test(self, strat: str):
        s = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"
        try:
            assets_per_test = int(s["matrix_entries"]["Assets per Test"].get().strip())
            sma_from = int(s["matrix_entries"]["From"].get().strip())
            sma_to = int(s["matrix_entries"]["To"].get().strip())
            max_combos = int(s["matrix_entries"]["Max Combinations"].get().strip())
            capital = float(s["matrix_entries"]["Capital"].get().strip() or "10000")
            allow_short = s["matrix_allow_short_var"].get()
            short_rate = float(s["matrix_short_entries"]["ShortRate"].get().strip() or "2.0")
            long_pct = float(s["matrix_short_entries"]["LongPct"].get().strip() or "100")
            short_pct = float(s["matrix_short_entries"]["ShortPct"].get().strip() or "100")
        except ValueError:
            s["matrix_status_label"].configure(
                text="Invalid numeric input.", text_color="#ef5350",
            )
            return

        if sma_from >= sma_to:
            s["matrix_status_label"].configure(
                text=f"{ind} From must be less than {ind} To.", text_color="#ef5350",
            )
            return
        if sma_from < 2:
            s["matrix_status_label"].configure(
                text=f"{ind} From must be at least 2.", text_color="#ef5350",
            )
            return
        if assets_per_test < 1 or max_combos < 1:
            s["matrix_status_label"].configure(
                text="Assets per Test and Max Combinations must be positive.",
                text_color="#ef5350",
            )
            return

        mode = s["matrix_mode_var"].get()
        start: str | None = None
        end: str | None = None
        if mode == "Custom date range":
            start = s["matrix_from_entry"].get().strip()
            end = s["matrix_to_entry"].get().strip()
            if not start or not end:
                s["matrix_status_label"].configure(
                    text="From and To dates are required for Custom date range.",
                    text_color="#ef5350",
                )
                return

        if not self._datasets:
            s["matrix_status_label"].configure(
                text="No datasets loaded. Click Refresh first.", text_color="#ef5350",
            )
            return

        from engine.matrix_runner import generate_sma_grid
        sma_values, pairs = generate_sma_grid(sma_from, sma_to, max_combos)
        sample_size = min(assets_per_test, len(self._datasets))
        total_tasks = len(pairs) * sample_size

        s["matrix_run_btn"].configure(state="disabled")
        s["matrix_progress_bar"].configure(maximum=total_tasks, value=0)
        s["matrix_progress_label"].configure(text=f"0 / {total_tasks}")
        s["matrix_status_label"].configure(
            text=f"Running matrix test: {len(pairs)} {ind} combos × {sample_size} assets = {total_tasks} backtests...",
            text_color="#888888",
        )

        datasets_snapshot = list(self._datasets)

        def _progress_cb(done: int, tot: int, info: str):
            self.after(0, lambda d=done, t=tot, i=info: self._on_matrix_progress(d, t, i, strat))

        def _execute():
            try:
                from engine.matrix_runner import run_matrix_test
                result = run_matrix_test(
                    all_datasets=datasets_snapshot,
                    sma_from=sma_from,
                    sma_to=sma_to,
                    max_combinations=max_combos,
                    assets_per_test=assets_per_test,
                    capital=capital,
                    timeframe_mode=mode,
                    start=start,
                    end=end,
                    strategy_type=strat,
                    allow_short=allow_short,
                    short_interest_rate=short_rate,
                    long_pct=long_pct,
                    short_pct=short_pct,
                    workers=8,
                    progress_cb=_progress_cb,
                )
                self.after(0, lambda: self._on_matrix_done(result, strat))
            except Exception as exc:
                self.after(0, lambda: self._on_matrix_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_matrix_progress(self, done: int, total: int, info: str, strat: str):
        s = self._st[strat]
        s["matrix_progress_bar"].configure(value=done)
        s["matrix_progress_label"].configure(text=f"Running {info} \u2014 {done} / {total}")

    def _on_matrix_done(self, result, strat: str):
        s = self._st[strat]
        s["matrix_run_btn"].configure(state="normal")
        valid = sum(1 for c in result.cells if c.num_tickers_succeeded > 0)
        s["matrix_progress_bar"].configure(value=result.total_backtests_run)
        s["matrix_progress_label"].configure(
            text=f"{result.total_backtests_run} / {result.total_backtests_run}",
        )
        s["matrix_status_label"].configure(
            text=f"Complete \u2014 {valid}/{len(result.cells)} combos with results. Building report...",
            text_color="#26a69a",
        )

        def _build_and_open():
            from display.ui import launch_matrix_ui
            try:
                launch_matrix_ui(result)
                self.after(0, lambda: s["matrix_status_label"].configure(
                    text=f"Complete \u2014 {valid}/{len(result.cells)} combos. Report opened in browser.",
                    text_color="#26a69a",
                ))
            except Exception as exc:
                self.after(0, lambda msg=str(exc): s["matrix_status_label"].configure(
                    text=f"Report error: {msg}", text_color="#ef5350",
                ))

        threading.Thread(target=_build_and_open, daemon=True).start()

    def _on_matrix_error(self, message: str, strat: str):
        s = self._st[strat]
        s["matrix_run_btn"].configure(state="normal")
        s["matrix_status_label"].configure(text=f"Error: {message}", text_color="#ef5350")


def launch_desktop():
    """Create and run the desktop application."""
    app = ProjectQuantApp()
    app.mainloop()
