"""S&P 500 constituent tickers.

Fetched from Wikipedia's S&P 500 list page. Falls back to a bundled
snapshot so the tool works offline.
"""

import pandas as pd

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def get_sp500_tickers() -> list[str]:
    """Return current S&P 500 ticker symbols sorted alphabetically."""
    try:
        tables = pd.read_html(_WIKIPEDIA_URL)
        df = tables[0]
        tickers = sorted(df["Symbol"].str.replace(".", "-", regex=False).tolist())
        return tickers
    except Exception as exc:
        print(f"[warn] Could not fetch live S&P 500 list ({exc}), using bundled snapshot")
        return _SNAPSHOT


# Bundled fallback snapshot (as of early 2026, sorted). Dots replaced with
# hyphens to match Yahoo Finance convention (e.g. BRK.B -> BRK-B).
_SNAPSHOT = sorted([
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL",
    "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AAL", "AEP", "AXP",
    "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "ANSS",
    "AON", "APA", "AAPL", "AMAT", "APTV", "ACGL", "ADM", "ANET", "AJG",
    "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR",
    "BALL", "BAC", "BK", "BBWI", "BAX", "BDX", "BRK-B", "BBY", "BIO",
    "TECH", "BIIB", "BLK", "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR",
    "BG", "BXP", "BSX", "CHRW", "CDNS", "CZR", "CPB", "COF", "CAH",
    "KMX", "CCL", "CARR", "CTLT", "CAT", "CBOE", "CBRE", "CDW", "CE",
    "COR", "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG",
    "CB", "CHD", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME",
    "CMS", "KO", "CTSH", "CL", "CMCSA", "CAG", "COP", "ED", "STZ",
    "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CTRA",
    "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DVA", "DAY", "DECK",
    "DE", "DAL", "DVN", "DXCM", "FANG", "DLR", "DFS", "DG", "DLTR",
    "D", "DPZ", "DOV", "DOW", "DHI", "DTE", "DUK", "DD", "EMN", "ETN",
    "EBAY", "ECL", "EIX", "EW", "EA", "ELV", "EMR", "ENPH", "ETR",
    "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ESS", "EL", "ETSY",
    "EG", "EVRG", "ES", "EXC", "EXPE", "EXPD", "EXR", "XOM", "FFIV",
    "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE",
    "FI", "FMC", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX",
    "GRMN", "IT", "GEHC", "GEN", "GNRC", "GD", "GE", "GIS", "GM",
    "GPC", "GILD", "GPN", "GL", "GS", "HAL", "HIG", "HAS", "HCA",
    "PEAK", "HSIC", "HSY", "HES", "HPE", "HLT", "HOLX", "HD", "HON",
    "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM",
    "IEX", "IDXX", "ITW", "ILMN", "INCY", "IR", "PODD", "INTC", "ICE",
    "IFF", "IP", "IPG", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM",
    "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "JNPR", "K",
    "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KLAC", "KHC",
    "KR", "LHX", "LH", "LRCX", "LW", "LVS", "LDOS", "LEN", "LIN",
    "LLY", "LKQ", "LMT", "L", "LOW", "LULU", "LYB", "MTB", "MRO",
    "MPC", "MKTX", "MAR", "MMC", "MLM", "MAS", "MA", "MTCH", "MKC",
    "MCD", "MCK", "MDT", "MRK", "META", "MCHP", "MU", "MSFT", "MAA",
    "MRNA", "MHK", "MOH", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS",
    "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS",
    "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG",
    "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON",
    "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PANW", "PARA", "PH", "PAYX",
    "PAYC", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW",
    "PXD", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD",
    "PRU", "PEG", "PTC", "PSA", "PHM", "QRVO", "PWR", "QCOM", "DGX",
    "RL", "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY",
    "RHI", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SBAC",
    "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SNA",
    "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK",
    "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TRGP", "TGT", "TEL", "TDY",
    "TFX", "TER", "TSLA", "TXN", "TXT", "TMO", "TJX", "TSCO", "TT",
    "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR",
    "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VTR",
    "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VIAV", "V", "VMC", "WRB",
    "WAB", "WBA", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC",
    "WELL", "WST", "WDC", "WRK", "WY", "WMB", "WTW", "GWW", "WYNN",
    "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS",
])
