"""Desktop GUI for ProjectQuant using customtkinter."""

import threading
from tkinter import ttk

import customtkinter as ctk

from data.scanner import DatasetInfo, scan_cache, _format_size


# ── Design tokens ─────────────────────────────────────────────────────────────
_BG_APP       = "#13131f"
_BG_PANEL     = "#18182c"
_BG_NAV       = "#0f0f1e"
_BG_CARD      = "#1e1e34"
_BG_SEP       = "#2a2a48"
_BG_BTN_MUTED = "#252540"
_BG_BTN_HOVER = "#30305a"

_TEXT_PRIMARY  = "#dddde8"
_TEXT_LABEL    = "#9898b8"
_TEXT_SECTION  = "#5a5a80"
_TEXT_MUTED    = "#666680"

_ACCENT_TEAL   = "#26a69a"
_ACCENT_TEAL_H = "#1e8c82"
_ACCENT_AMBER  = "#ff9800"
_ACCENT_AMBER_H= "#c77800"
_ACCENT_PURPLE = "#9c27b0"
_ACCENT_PURPLE_H="#7b1fa2"
_ACCENT_NAV    = "#3a3a70"
_ACCENT_NAV_H  = "#4a4a80"

_FONT_TITLE  = ("Segoe UI", 22, "bold")
_FONT_CARD_H = ("Segoe UI",  9, "bold")
_FONT_LABEL  = ("Segoe UI", 11)
_FONT_LABEL_B= ("Segoe UI", 11, "bold")
_FONT_NAV    = ("Segoe UI", 12, "bold")
_FONT_NAV2   = ("Segoe UI", 12)


class ProjectQuantApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("ProjectQuant")
        self.geometry("1200x920")
        self.minsize(960, 660)
        self.configure(fg_color=_BG_APP)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._datasets: list[DatasetInfo] = []
        self._sort_col: str = "Ticker"
        self._sort_reverse: bool = False

        self._st: dict[str, dict] = {"sma": {}, "ema": {}}

        self._build_ui()
        self._style_treeview()
        self._load_data()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(18, 0))

        ctk.CTkLabel(
            header_frame, text="ProjectQuant",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            self, text="Cached datasets overview",
            font=ctk.CTkFont(size=12), text_color=_TEXT_MUTED,
        ).pack(padx=24, pady=(2, 10), anchor="w")

        # ── Filter bar ────────────────────────────────────────────────
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(filter_frame, text="Filter:", text_color=_TEXT_LABEL,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))

        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", self._apply_filter)
        ctk.CTkEntry(
            filter_frame, textvariable=self._filter_var,
            placeholder_text="Search ticker…", width=200,
        ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(filter_frame, text="Index:", text_color=_TEXT_LABEL,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))

        self._index_var = ctk.StringVar(value="All")
        ctk.CTkComboBox(
            filter_frame, values=["All", "S&P 500", "DAX 30", "Other"],
            variable=self._index_var, width=140, state="readonly",
            command=lambda _: self._apply_filter(),
        ).pack(side="left", padx=(0, 16))

        self._count_label = ctk.CTkLabel(
            filter_frame, text="", text_color=_TEXT_MUTED, font=ctk.CTkFont(size=12),
        )
        self._count_label.pack(side="left", padx=(16, 0))

        ctk.CTkButton(
            filter_frame, text="Refresh", width=90, command=self._load_data,
        ).pack(side="right")

        # ── Data table ────────────────────────────────────────────────
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        columns = ("Ticker", "Rows", "First Date", "Last Date", "Size", "Index")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse",
        )
        col_widths  = {"Ticker": 110, "Rows": 80, "First Date": 120,
                       "Last Date": 120, "Size": 90, "Index": 100}
        col_anchors = {"Rows": "e", "Size": "e"}
        for col in columns:
            self._tree.heading(col, text=col, command=lambda c=col: self._sort_column(c))
            self._tree.column(col, width=col_widths.get(col, 100),
                              anchor=col_anchors.get(col, "w"), minwidth=60)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # ── Strategy control panel ─────────────────────────────────────
        panel = ctk.CTkFrame(self, fg_color=_BG_PANEL, corner_radius=12)
        panel.pack(fill="x", padx=24, pady=(0, 18))

        # Navigation bar
        nav = ctk.CTkFrame(panel, fg_color=_BG_NAV, corner_radius=8)
        nav.pack(fill="x", padx=12, pady=(12, 10))

        self._strat_seg = ctk.CTkSegmentedButton(
            nav,
            values=["SMA Strategy", "EMA Strategy"],
            command=self._on_nav_change,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=_BG_PANEL,
            selected_color=_ACCENT_TEAL,
            selected_hover_color=_ACCENT_TEAL_H,
            unselected_color=_BG_PANEL,
            unselected_hover_color=_BG_BTN_HOVER,
            text_color=_TEXT_PRIMARY,
        )
        self._strat_seg.set("SMA Strategy")
        self._strat_seg.pack(side="left", padx=10, pady=8)

        self._test_seg = ctk.CTkSegmentedButton(
            nav,
            values=["Single Test", "Bulk Test", "Matrix Test"],
            command=self._on_nav_change,
            font=ctk.CTkFont(size=12),
            fg_color=_BG_PANEL,
            selected_color=_ACCENT_NAV,
            selected_hover_color=_ACCENT_NAV_H,
            unselected_color=_BG_PANEL,
            unselected_hover_color=_BG_BTN_HOVER,
            text_color=_TEXT_PRIMARY,
        )
        self._test_seg.set("Single Test")
        self._test_seg.pack(side="right", padx=10, pady=8)

        # Content area
        self._content_area = ctk.CTkFrame(panel, fg_color="transparent")
        self._content_area.pack(fill="x", padx=12, pady=(0, 12))

        # Build all 6 content frames (2 strategies × 3 test types)
        self._nav_frames: dict[tuple[str, str], ctk.CTkFrame] = {}
        for strat in ("sma", "ema"):
            for test_type, builder in [
                ("single", self._build_single_test_tab),
                ("bulk",   self._build_bulk_test_tab),
                ("matrix", self._build_matrix_test_tab),
            ]:
                f = ctk.CTkFrame(self._content_area, fg_color="transparent")
                self._nav_frames[(strat, test_type)] = f
                builder(f, strat)

        self._active_nav = ("sma", "single")
        self._nav_frames[self._active_nav].pack(fill="x")

    def _on_nav_change(self, _=None):
        strat_map = {"SMA Strategy": "sma", "EMA Strategy": "ema"}
        test_map  = {"Single Test": "single", "Bulk Test": "bulk", "Matrix Test": "matrix"}
        key = (strat_map[self._strat_seg.get()], test_map[self._test_seg.get()])
        if key == self._active_nav:
            return
        self._nav_frames[self._active_nav].pack_forget()
        self._active_nav = key
        self._nav_frames[key].pack(fill="x")

    # ── Layout helpers ────────────────────────────────────────────────

    def _make_section(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        """Create a labeled section card and return its inner content row frame."""
        card = ctk.CTkFrame(parent, fg_color=_BG_CARD, corner_radius=8)
        card.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=_TEXT_SECTION,
        ).pack(anchor="w", padx=12, pady=(8, 3))
        ctk.CTkFrame(card, fg_color=_BG_SEP, height=1, corner_radius=0).pack(fill="x", padx=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=(8, 10))
        return inner

    def _field(self, parent, label: str, key: str, value: str, width: int,
               store: dict, placeholder: bool = False):
        """Add label + entry pair to a horizontal row, store entry in `store[key]`."""
        ctk.CTkLabel(
            parent, text=label, font=ctk.CTkFont(size=11), text_color=_TEXT_LABEL,
        ).pack(side="left", padx=(0, 5))
        e = ctk.CTkEntry(parent, width=width, font=ctk.CTkFont(size=11))
        if placeholder:
            e.configure(placeholder_text=value)
        else:
            e.insert(0, value)
        e.pack(side="left", padx=(0, 16))
        store[key] = e

    # ── Treeview styling ─────────────────────────────────────────────

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1e1e34",
            foreground=_TEXT_PRIMARY,
            fieldbackground="#1e1e34",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#252540",
            foreground=_TEXT_LABEL,
            borderwidth=1,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview",
                  background=[("selected", "#32326a")],
                  foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading",
                  background=[("active", "#303058")])
        style.configure(
            "Horizontal.TProgressbar",
            background=_ACCENT_TEAL,
            troughcolor="#252540",
            borderwidth=0,
            thickness=6,
        )

    # ── Data loading ─────────────────────────────────────────────────

    def _load_data(self):
        self._count_label.configure(text="Scanning cache…")
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

        search       = self._filter_var.get().strip().upper()
        index_filter = self._index_var.get()

        filtered = self._datasets
        if search:
            filtered = [d for d in filtered if search in d.ticker.upper()]
        if index_filter != "All":
            filtered = [d for d in filtered if d.index == index_filter]

        key_map = {
            "Ticker":     lambda d: d.ticker,
            "Rows":       lambda d: d.rows,
            "First Date": lambda d: d.first_date,
            "Last Date":  lambda d: d.last_date,
            "Size":       lambda d: d.size_bytes,
            "Index":      lambda d: d.index,
        }
        key_fn = key_map.get(self._sort_col, lambda d: d.ticker)
        filtered.sort(key=key_fn, reverse=self._sort_reverse)

        for d in filtered:
            self._tree.insert("", "end", values=(
                d.ticker, f"{d.rows:,}", d.first_date, d.last_date,
                _format_size(d.size_bytes), d.index,
            ))

        self._count_label.configure(
            text=f"{len(filtered)} / {len(self._datasets)} datasets"
        )

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
        s["status_label"].configure(text="", text_color=_TEXT_MUTED)

    # ── Backtest execution ───────────────────────────────────────────

    def _run_backtest(self, strat: str):
        s = self._st[strat]
        ticker        = s["bt_entries"]["Ticker"].get().strip()
        start         = s["bt_entries"]["From"].get().strip()
        end           = s["bt_entries"]["To"].get().strip()
        capital_str   = s["bt_entries"]["Capital"].get().strip()
        short_str     = s["bt_entries"]["Short"].get().strip()
        long_str      = s["bt_entries"]["Long"].get().strip()
        allow_short   = s["allow_short_var"].get()
        short_rate_str= s["bt_entries"]["ShortRate"].get().strip()
        long_pct_str  = s["bt_entries"]["LongPct"].get().strip()
        short_pct_str = s["bt_entries"]["ShortPct"].get().strip()

        if not ticker or not start or not end:
            s["status_label"].configure(
                text="Ticker, From, and To are required.", text_color="#ef5350",
            )
            return

        try:
            capital      = float(capital_str)  if capital_str  else 10_000.0
            short_window = int(short_str)       if short_str    else 50
            long_window  = int(long_str)        if long_str     else 200
            short_rate   = float(short_rate_str)if short_rate_str else 2.0
            long_pct     = float(long_pct_str)  if long_pct_str else 100.0
            short_pct    = float(short_pct_str) if short_pct_str else 100.0
        except ValueError:
            s["status_label"].configure(text="Invalid numeric input.", text_color="#ef5350")
            return

        s["run_btn"].configure(state="disabled")
        s["status_label"].configure(
            text=f"Running backtest for {ticker}…", text_color=_TEXT_MUTED,
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

                df      = fetch_data(ticker, start, end)
                signals = strategy.generate_signals(df)
                bt      = Backtester(
                    initial_capital=capital, allow_short=allow_short,
                    short_interest_rate=short_rate, long_pct=long_pct, short_pct=short_pct,
                )
                result = bt.run(df, signals)
                self.after(0, lambda: self._on_backtest_done(
                    ticker, start, end, capital, result, df, short_window, long_window, strat,
                ))
            except Exception as exc:
                self.after(0, lambda: self._on_backtest_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_backtest_done(self, ticker, start, end, capital, result, df,
                          short_window, long_window, strat):
        s = self._st[strat]
        s["run_btn"].configure(state="normal")
        s["status_label"].configure(
            text=f"Complete — {len(result.trades)} trades. Opening results…",
            text_color=_ACCENT_TEAL,
        )

        def _build_and_open():
            from display.ui import launch_ui
            try:
                launch_ui(ticker=ticker, start=start, end=end, initial_capital=capital,
                          result=result, df=df, short_window=short_window,
                          long_window=long_window, strategy_type=strat)
                self.after(0, lambda: s["status_label"].configure(
                    text=f"Complete — {len(result.trades)} trades. Report opened in browser.",
                    text_color=_ACCENT_TEAL,
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
        s   = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"
        s["bt_entries"] = {}

        # Section: Instrument & Date Range
        instr = self._make_section(tab, "INSTRUMENT & DATE RANGE")
        for label, key, ph, w in [
            ("Ticker", "Ticker", "AAPL",       90),
            ("From",   "From",   "YYYY-MM-DD", 120),
            ("To",     "To",     "YYYY-MM-DD", 120),
        ]:
            self._field(instr, label, key, ph, w, s["bt_entries"], placeholder=True)

        s["full_range_btn"] = ctk.CTkButton(
            instr, text="Full Range", width=90,
            fg_color=_BG_BTN_MUTED, hover_color=_BG_BTN_HOVER,
            text_color=_TEXT_LABEL, font=ctk.CTkFont(size=11),
            command=lambda: self._use_full_date_range(strat),
        )
        s["full_range_btn"].pack(side="left", padx=(0, 0))

        # Section: Strategy Parameters
        params = self._make_section(tab, "STRATEGY PARAMETERS")
        for label, key, default, w in [
            (f"Short {ind}", "Short",   "50",    70),
            (f"Long {ind}",  "Long",    "200",   70),
            ("Capital",      "Capital", "10000", 100),
        ]:
            self._field(params, label, key, default, w, s["bt_entries"])

        # Section: Short Selling
        shorts = self._make_section(tab, "SHORT SELLING")
        ctk.CTkLabel(shorts, text="Allow Shorts", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 6))
        s["allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(shorts, text="", variable=s["allow_short_var"], width=46).pack(
            side="left", padx=(0, 20),
        )
        for label, key, default, w in [
            ("Interest Rate (% p.a.)", "ShortRate", "2.0", 60),
            ("Long % Capital",         "LongPct",   "100", 55),
            ("Short % Capital",        "ShortPct",  "100", 55),
        ]:
            self._field(shorts, label, key, default, w, s["bt_entries"])

        # Action row
        action = ctk.CTkFrame(tab, fg_color="transparent")
        action.pack(fill="x", pady=(4, 0))
        s["run_btn"] = ctk.CTkButton(
            action, text="Run Backtest", width=130,
            fg_color=_ACCENT_TEAL, hover_color=_ACCENT_TEAL_H,
            command=lambda: self._run_backtest(strat),
        )
        s["run_btn"].pack(side="left", padx=(0, 14))
        s["status_label"] = ctk.CTkLabel(
            action, text="", text_color=_TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=11),
        )
        s["status_label"].pack(side="left", fill="x", expand=True)

    def _build_bulk_test_tab(self, tab: ctk.CTkFrame, strat: str):
        s   = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"
        s["bulk_entries"] = {}

        # Section: Strategy Parameters
        params = self._make_section(tab, "STRATEGY PARAMETERS")
        for ui_label, key, default, width in [
            (f"Short {ind}", "Short",   "50",    70),
            (f"Long {ind}",  "Long",    "200",   70),
            ("Capital",      "Capital", "10000", 100),
        ]:
            self._field(params, ui_label, key, default, width, s["bulk_entries"])

        ctk.CTkLabel(params, text="Time period", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["bulk_mode_var"] = ctk.StringVar(value="Full history per ticker")
        ctk.CTkComboBox(
            params, values=["Custom date range", "Full history per ticker"],
            variable=s["bulk_mode_var"], width=200, state="readonly",
            command=lambda _: self._on_bulk_mode_change(strat),
        ).pack(side="left")

        # Section: Short Selling
        shorts = self._make_section(tab, "SHORT SELLING")
        ctk.CTkLabel(shorts, text="Allow Shorts", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 6))
        s["bulk_allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(shorts, text="", variable=s["bulk_allow_short_var"], width=46).pack(
            side="left", padx=(0, 20),
        )
        s["bulk_short_entries"] = {}
        for ui_label, key, default, width in [
            ("Interest Rate (% p.a.)", "ShortRate", "2.0", 60),
            ("Long % Capital",         "LongPct",   "100", 55),
            ("Short % Capital",        "ShortPct",  "100", 55),
        ]:
            self._field(shorts, ui_label, key, default, width, s["bulk_short_entries"])

        # Date row (hidden; shown for "Custom date range")
        s["bulk_date_row"] = ctk.CTkFrame(tab, fg_color=_BG_CARD, corner_radius=8)
        date_inner = ctk.CTkFrame(s["bulk_date_row"], fg_color="transparent")
        date_inner.pack(fill="x", padx=12, pady=(8, 10))
        ctk.CTkLabel(date_inner, text="CUSTOM DATE RANGE",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=_TEXT_SECTION).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(date_inner, text="From:", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["bulk_from_entry"] = ctk.CTkEntry(
            date_inner, width=130, placeholder_text="YYYY-MM-DD",
            font=ctk.CTkFont(size=11),
        )
        s["bulk_from_entry"].pack(side="left", padx=(0, 16))
        ctk.CTkLabel(date_inner, text="To:", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["bulk_to_entry"] = ctk.CTkEntry(
            date_inner, width=130, placeholder_text="YYYY-MM-DD",
            font=ctk.CTkFont(size=11),
        )
        s["bulk_to_entry"].pack(side="left")

        # Action row
        s["bulk_run_row"] = ctk.CTkFrame(tab, fg_color="transparent")
        s["bulk_run_row"].pack(fill="x", pady=(4, 0))
        s["bulk_run_btn"] = ctk.CTkButton(
            s["bulk_run_row"], text="Run All Tickers", width=150,
            fg_color=_ACCENT_AMBER, hover_color=_ACCENT_AMBER_H,
            command=lambda: self._run_bulk_backtest(strat),
        )
        s["bulk_run_btn"].pack(side="left", padx=(0, 14))
        s["bulk_progress_label"] = ctk.CTkLabel(
            s["bulk_run_row"], text="", text_color=_TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=11),
        )
        s["bulk_progress_label"].pack(side="left", padx=(4, 0))

        s["bulk_progress_bar"] = ttk.Progressbar(
            tab, orient="horizontal", mode="determinate",
        )
        s["bulk_progress_bar"].pack(fill="x", pady=(6, 2))

        s["bulk_status_label"] = ctk.CTkLabel(
            tab, text="", text_color=_TEXT_MUTED, font=ctk.CTkFont(size=11),
        )
        s["bulk_status_label"].pack(anchor="w", pady=(0, 2))

    # ── Bulk mode toggle ──────────────────────────────────────────────

    def _on_bulk_mode_change(self, strat: str):
        s = self._st[strat]
        if s["bulk_mode_var"].get() == "Full history per ticker":
            s["bulk_date_row"].pack_forget()
        else:
            s["bulk_date_row"].pack(
                fill="x", pady=(0, 6),
                before=s["bulk_run_row"],
            )

    # ── Bulk backtest execution ───────────────────────────────────────

    def _run_bulk_backtest(self, strat: str):
        s = self._st[strat]
        capital_str   = s["bulk_entries"]["Capital"].get().strip()
        short_str     = s["bulk_entries"]["Short"].get().strip()
        long_str      = s["bulk_entries"]["Long"].get().strip()
        mode          = s["bulk_mode_var"].get()
        allow_short   = s["bulk_allow_short_var"].get()
        short_rate_str= s["bulk_short_entries"]["ShortRate"].get().strip()
        long_pct_str  = s["bulk_short_entries"]["LongPct"].get().strip()
        short_pct_str = s["bulk_short_entries"]["ShortPct"].get().strip()

        try:
            capital      = float(capital_str)  if capital_str  else 10_000.0
            short_window = int(short_str)       if short_str    else 50
            long_window  = int(long_str)        if long_str     else 200
            short_rate   = float(short_rate_str)if short_rate_str else 2.0
            long_pct     = float(long_pct_str)  if long_pct_str else 100.0
            short_pct    = float(short_pct_str) if short_pct_str else 100.0
        except ValueError:
            s["bulk_status_label"].configure(
                text="Invalid numeric input.", text_color="#ef5350",
            )
            return

        start: str | None = None
        end:   str | None = None
        if mode == "Custom date range":
            start = s["bulk_from_entry"].get().strip()
            end   = s["bulk_to_entry"].get().strip()
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
            text=f"Running bulk backtest on {total} tickers…", text_color=_TEXT_MUTED,
        )

        datasets_snapshot = list(self._datasets)

        def _progress_cb(done: int, tot: int, ticker: str):
            self.after(0, lambda d=done, t=tot, tk=ticker: self._on_bulk_progress(d, t, tk, strat))

        def _execute():
            try:
                from engine.bulk_runner import run_bulk_backtest
                result = run_bulk_backtest(
                    datasets=datasets_snapshot, start=start, end=end,
                    capital=capital, short_sma=short_window, long_sma=long_window,
                    timeframe_mode=mode, strategy_type=strat,
                    allow_short=allow_short, short_interest_rate=short_rate,
                    long_pct=long_pct, short_pct=short_pct,
                    workers=8, progress_cb=_progress_cb,
                )
                self.after(0, lambda: self._on_bulk_done(result, strat))
            except Exception as exc:
                self.after(0, lambda: self._on_bulk_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_bulk_progress(self, done: int, total: int, ticker: str, strat: str):
        s = self._st[strat]
        s["bulk_progress_bar"].configure(value=done)
        s["bulk_progress_label"].configure(text=f"Running {ticker} — {done} / {total}")

    def _on_bulk_done(self, result, strat: str):
        s          = self._st[strat]
        successful = sum(1 for r in result.ticker_results if r.error is None)
        n          = len(result.ticker_results)
        s["bulk_run_btn"].configure(state="normal")
        s["bulk_progress_bar"].configure(value=n)
        s["bulk_progress_label"].configure(text=f"{n} / {n}")
        s["bulk_status_label"].configure(
            text=f"Complete — {successful}/{n} succeeded. Building report…",
            text_color=_ACCENT_TEAL,
        )

        def _build_and_open():
            from display.ui import launch_bulk_ui
            try:
                launch_bulk_ui(result)
                self.after(0, lambda: s["bulk_status_label"].configure(
                    text=f"Complete — {successful}/{n} succeeded. Report opened in browser.",
                    text_color=_ACCENT_TEAL,
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
        s   = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"
        s["matrix_entries"] = {}

        # Section: Window Range & Scope
        scope = self._make_section(tab, f"{ind} WINDOW RANGE & SCOPE")
        for ui_label, key, default, width in [
            (f"{ind} From",      "From",             "3",   55),
            (f"{ind} To",        "To",               "200", 55),
            ("Assets per Test",  "Assets per Test",  "30",  65),
            ("Max Combinations", "Max Combinations", "150", 65),
        ]:
            self._field(scope, ui_label, key, default, width, s["matrix_entries"])

        ctk.CTkLabel(scope, text="Time period", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["matrix_mode_var"] = ctk.StringVar(value="Full history per ticker")
        ctk.CTkComboBox(
            scope, values=["Custom date range", "Full history per ticker"],
            variable=s["matrix_mode_var"], width=200, state="readonly",
            command=lambda _: self._on_matrix_mode_change(strat),
        ).pack(side="left")

        # Section: Portfolio
        portfolio = self._make_section(tab, "PORTFOLIO")
        self._field(portfolio, "Capital", "Capital", "10000", 110, s["matrix_entries"])

        # Section: Short Selling
        shorts = self._make_section(tab, "SHORT SELLING")
        ctk.CTkLabel(shorts, text="Allow Shorts", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 6))
        s["matrix_allow_short_var"] = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(shorts, text="", variable=s["matrix_allow_short_var"], width=46).pack(
            side="left", padx=(0, 20),
        )
        s["matrix_short_entries"] = {}
        for ui_label, key, default, width in [
            ("Interest Rate (% p.a.)", "ShortRate", "2.0", 60),
            ("Long % Capital",         "LongPct",   "100", 55),
            ("Short % Capital",        "ShortPct",  "100", 55),
        ]:
            self._field(shorts, ui_label, key, default, width, s["matrix_short_entries"])

        # Date row (hidden; shown for "Custom date range")
        s["matrix_date_row"] = ctk.CTkFrame(tab, fg_color=_BG_CARD, corner_radius=8)
        mdate_inner = ctk.CTkFrame(s["matrix_date_row"], fg_color="transparent")
        mdate_inner.pack(fill="x", padx=12, pady=(8, 10))
        ctk.CTkLabel(mdate_inner, text="CUSTOM DATE RANGE",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=_TEXT_SECTION).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(mdate_inner, text="From:", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["matrix_from_entry"] = ctk.CTkEntry(
            mdate_inner, width=130, placeholder_text="YYYY-MM-DD",
            font=ctk.CTkFont(size=11),
        )
        s["matrix_from_entry"].pack(side="left", padx=(0, 16))
        ctk.CTkLabel(mdate_inner, text="To:", font=ctk.CTkFont(size=11),
                     text_color=_TEXT_LABEL).pack(side="left", padx=(0, 5))
        s["matrix_to_entry"] = ctk.CTkEntry(
            mdate_inner, width=130, placeholder_text="YYYY-MM-DD",
            font=ctk.CTkFont(size=11),
        )
        s["matrix_to_entry"].pack(side="left")

        # Action row
        s["matrix_run_row"] = ctk.CTkFrame(tab, fg_color="transparent")
        s["matrix_run_row"].pack(fill="x", pady=(4, 0))
        s["matrix_run_btn"] = ctk.CTkButton(
            s["matrix_run_row"], text="Run Matrix Test", width=150,
            fg_color=_ACCENT_PURPLE, hover_color=_ACCENT_PURPLE_H,
            command=lambda: self._run_matrix_test(strat),
        )
        s["matrix_run_btn"].pack(side="left", padx=(0, 14))
        s["matrix_progress_label"] = ctk.CTkLabel(
            s["matrix_run_row"], text="", text_color=_TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=11),
        )
        s["matrix_progress_label"].pack(side="left", padx=(4, 0))

        s["matrix_progress_bar"] = ttk.Progressbar(
            tab, orient="horizontal", mode="determinate",
        )
        s["matrix_progress_bar"].pack(fill="x", pady=(6, 2))

        s["matrix_status_label"] = ctk.CTkLabel(
            tab, text="", text_color=_TEXT_MUTED, font=ctk.CTkFont(size=11),
        )
        s["matrix_status_label"].pack(anchor="w", pady=(0, 2))

    def _on_matrix_mode_change(self, strat: str):
        s = self._st[strat]
        if s["matrix_mode_var"].get() == "Full history per ticker":
            s["matrix_date_row"].pack_forget()
        else:
            s["matrix_date_row"].pack(
                fill="x", pady=(0, 6),
                before=s["matrix_run_row"],
            )

    def _run_matrix_test(self, strat: str):
        s   = self._st[strat]
        ind = "EMA" if strat == "ema" else "SMA"
        try:
            assets_per_test = int(s["matrix_entries"]["Assets per Test"].get().strip())
            sma_from        = int(s["matrix_entries"]["From"].get().strip())
            sma_to          = int(s["matrix_entries"]["To"].get().strip())
            max_combos      = int(s["matrix_entries"]["Max Combinations"].get().strip())
            capital         = float(s["matrix_entries"]["Capital"].get().strip() or "10000")
            allow_short     = s["matrix_allow_short_var"].get()
            short_rate      = float(s["matrix_short_entries"]["ShortRate"].get().strip() or "2.0")
            long_pct        = float(s["matrix_short_entries"]["LongPct"].get().strip() or "100")
            short_pct       = float(s["matrix_short_entries"]["ShortPct"].get().strip() or "100")
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

        mode  = s["matrix_mode_var"].get()
        start: str | None = None
        end:   str | None = None
        if mode == "Custom date range":
            start = s["matrix_from_entry"].get().strip()
            end   = s["matrix_to_entry"].get().strip()
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
        sample_size  = min(assets_per_test, len(self._datasets))
        total_tasks  = len(pairs) * sample_size

        s["matrix_run_btn"].configure(state="disabled")
        s["matrix_progress_bar"].configure(maximum=total_tasks, value=0)
        s["matrix_progress_label"].configure(text=f"0 / {total_tasks}")
        s["matrix_status_label"].configure(
            text=f"Running matrix test: {len(pairs)} {ind} combos × {sample_size} assets = {total_tasks} backtests…",
            text_color=_TEXT_MUTED,
        )

        datasets_snapshot = list(self._datasets)

        def _progress_cb(done: int, tot: int, info: str):
            self.after(0, lambda d=done, t=tot, i=info: self._on_matrix_progress(d, t, i, strat))

        def _execute():
            try:
                from engine.matrix_runner import run_matrix_test
                result = run_matrix_test(
                    all_datasets=datasets_snapshot,
                    sma_from=sma_from, sma_to=sma_to,
                    max_combinations=max_combos, assets_per_test=assets_per_test,
                    capital=capital, timeframe_mode=mode, start=start, end=end,
                    strategy_type=strat, allow_short=allow_short,
                    short_interest_rate=short_rate, long_pct=long_pct, short_pct=short_pct,
                    workers=8, progress_cb=_progress_cb,
                )
                self.after(0, lambda: self._on_matrix_done(result, strat))
            except Exception as exc:
                self.after(0, lambda: self._on_matrix_error(str(exc), strat))

        threading.Thread(target=_execute, daemon=True).start()

    def _on_matrix_progress(self, done: int, total: int, info: str, strat: str):
        s = self._st[strat]
        s["matrix_progress_bar"].configure(value=done)
        s["matrix_progress_label"].configure(text=f"Running {info} — {done} / {total}")

    def _on_matrix_done(self, result, strat: str):
        s     = self._st[strat]
        valid = sum(1 for c in result.cells if c.num_tickers_succeeded > 0)
        s["matrix_run_btn"].configure(state="normal")
        s["matrix_progress_bar"].configure(value=result.total_backtests_run)
        s["matrix_progress_label"].configure(
            text=f"{result.total_backtests_run} / {result.total_backtests_run}",
        )
        s["matrix_status_label"].configure(
            text=f"Complete — {valid}/{len(result.cells)} combos with results. Building report…",
            text_color=_ACCENT_TEAL,
        )

        def _build_and_open():
            from display.ui import launch_matrix_ui
            try:
                launch_matrix_ui(result)
                self.after(0, lambda: s["matrix_status_label"].configure(
                    text=f"Complete — {valid}/{len(result.cells)} combos. Report opened in browser.",
                    text_color=_ACCENT_TEAL,
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
