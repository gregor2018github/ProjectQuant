"""DAX 30 constituent tickers.

Fetched from Wikipedia's DAX page. Falls back to a bundled snapshot so
the tool works offline.

Yahoo Finance uses the `TICKER.DE` format for Frankfurt-listed stocks
(e.g. SAP.DE, ALV.DE).
"""

import pandas as pd

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/DAX"


def get_dax30_tickers() -> list[str]:
    """Return DAX 30 ticker symbols sorted alphabetically."""
    try:
        tables = pd.read_html(_WIKIPEDIA_URL)
        # The constituents table contains a 'Ticker symbol' column
        for df in tables:
            if "Ticker symbol" in df.columns:
                tickers = sorted(df["Ticker symbol"].dropna().tolist())
                if tickers:
                    return tickers
        raise ValueError("Constituents table not found")
    except Exception as exc:
        print(f"[warn] Could not fetch live DAX list ({exc}), using bundled snapshot")
        return _SNAPSHOT


# Bundled fallback snapshot (classic DAX 30 constituents, sorted).
# Yahoo Finance format: TICKER.DE
_SNAPSHOT = sorted([
    "ADS.DE",   # Adidas
    "AIR.DE",   # Airbus
    "ALV.DE",   # Allianz
    "BAS.DE",   # BASF
    "BAYN.DE",  # Bayer
    "BEI.DE",   # Beiersdorf
    "BMW.DE",   # BMW
    "CON.DE",   # Continental
    "1COV.DE",  # Covestro
    "DB1.DE",   # Deutsche Börse
    "DBK.DE",   # Deutsche Bank
    "DHL.DE",   # Deutsche Post DHL
    "DTE.DE",   # Deutsche Telekom
    "EOAN.DE",  # E.ON
    "FME.DE",   # Fresenius Medical Care
    "FRE.DE",   # Fresenius SE
    "HEI.DE",   # HeidelbergCement
    "HEN3.DE",  # Henkel
    "IFX.DE",   # Infineon
    "LIN",      # Linde (NYSE-listed, no .DE)
    "MBG.DE",   # Mercedes-Benz
    "MRK.DE",   # Merck KGaA
    "MTX.DE",   # MTU Aero Engines
    "MUV2.DE",  # Munich Re
    "RWE.DE",   # RWE
    "SAP.DE",   # SAP
    "SIE.DE",   # Siemens
    "VNA.DE",   # Vonovia
    "VOW3.DE",  # Volkswagen
    "ZAL.DE",   # Zalando
])
