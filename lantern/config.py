"""Constants shared across the package. Values pinned by the design spec are commented."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

MODEL_VERSION = "0.3"

# Equal-weighted AI capex basket, indexed to 100 at the start of the 24-month window.
BASKET = ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "TSM", "ORCL"]
# Hyperscalers whose capex and operating cash flow feed the capex driver.
HYPERSCALERS = ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]
# Other large caps used only to reconstruct the top-10 concentration history.
LARGE_CAPS = [
    "AAPL", "BRK-B", "JPM", "LLY", "V", "UNH", "XOM", "MA", "JNJ", "PG",
    "COST", "HD", "ABBV", "WMT", "BAC", "NFLX", "KO", "CRM", "CVX", "MRK",
]
INDICES = ["^NDX", "^GSPC"]

# SEC central index keys.
CIK = {
    "NVDA": 1045810, "MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724,
    "META": 1326801, "AVGO": 1730168, "TSM": 1046179, "ORCL": 1341439,
    "AAPL": 320193, "BRK-B": 1067983, "JPM": 19617, "LLY": 59478, "V": 1403161,
    "UNH": 731766, "XOM": 34088, "MA": 1141391, "JNJ": 200406, "PG": 80424,
    "COST": 909832, "HD": 354950, "ABBV": 1551152, "WMT": 104169, "BAC": 70858,
    "NFLX": 1065280, "KO": 21344, "CRM": 1108524, "CVX": 93410, "MRK": 310158,
}

FRED = {
    "real_yield": "DFII10",
    "fed_funds": "DFF",
    "hy_spread": "BAMLH0A0HYM2",
    "fed_assets": "WALCL",
}

# Fixed, disclosed composite weights (spec: The model, item 2).
WEIGHTS = {
    "valuation": 0.25,
    "capex": 0.20,
    "concentration": 0.15,
    "leverage": 0.15,
    "positioning": 0.10,
    "revisions": 0.10,
    "rates": 0.05,
}

DRAWDOWN = 0.25            # de-rating event: a 25% or larger drawdown ...
MELTUP = 0.20              # melt-up event: a 20% or larger gain ...
HORIZON_MONTHS = 12        # ... within 12 months
Z_WINDOW_MONTHS = 120      # z-scores against the driver's own trailing 10-year history
Z_MIN_MONTHS = 24          # expanding window until the full window fills
FV_BAND = 0.07             # fair-value band, plus or minus 7%
REAL_YIELD_PE_SENSITIVITY = 0.10  # P/E falls 10% per percentage point of real yield above its median
CALIBRATION_START = "2003-01"     # every driver has a free history from here
STATUS_BANDS = [(0.25, "calm"), (0.50, "elevated"), (1.0, "high")]
PROB_CLAMP = (0.01, 0.99)
SLOPE_PRIOR = (1.0, 1.0)   # weak normal prior (mean, sd) on the logistic slope; the slope is floored at 0
CONDITIONAL_BAND = 1.0     # composite points either side of today for the conditional window
CONDITIONAL_MIN_OBS = 24
TOP10_PEAK_2000 = 0.27     # context on the concentration tile
SP500_DIVISOR_SHARES = 8.4e9  # approximate S&P 500 index shares, used for the concentration history
NOT_IN_SP500 = ["TSM"]          # in the basket but not an index constituent: out of the concentration history
PE_EXCLUDED = ["TSM"]           # files annual 20-F facts only, in TWD: out of the basket P/E, disclosed on the panel
SHARES_MAX_AGE_DAYS = 730       # a filed share count older than this no longer stands in for a month
CONCENTRATION_MIN_NAMES = 20    # months with fewer names carrying a market cap have no reconstructed reading

DATA_DIR = Path(os.environ.get("LANTERN_DATA", "./data"))
SGT = ZoneInfo("Asia/Singapore")
SEC_USER_AGENT = os.environ.get("LANTERN_SEC_UA", "Lantern research (abhay@example.com)")
