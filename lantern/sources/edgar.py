"""SEC EDGAR company-facts: quarterly flows and instant balances keyed by filing date."""

import json
from datetime import date

import pandas as pd

from lantern import config
from lantern.sources.base import SourceError, fetch_raw
from lantern.store import Store

FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "6-K"}
# series -> candidate (taxonomy, tag, preferred unit); the candidate with the latest period wins
TAGS = {
    "net_income": [
        ("us-gaap", "NetIncomeLoss", "USD"),
        ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic", "USD"),
        ("us-gaap", "ProfitLoss", "USD"),
        ("ifrs-full", "ProfitLoss", None),
    ],
    "shares": [
        ("dei", "EntityCommonStockSharesOutstanding", "shares"),
        ("us-gaap", "CommonStockSharesOutstanding", "shares"),
        ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding", "shares"),
    ],
    "capex": [
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD"),
        ("ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", None),
    ],
    "ocf": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "USD"),
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities", None),
    ],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue", "USD"),
        ("ifrs-full", "CashAndCashEquivalents", None),
    ],
    "debt": [("us-gaap", "LongTermDebt", "USD"), ("us-gaap", "LongTermDebtNoncurrent", "USD")],
}
FLOWS = {"net_income", "capex", "ocf"}
COLUMNS = ["date", "period_end", "value", "kind"]


def facts_url(cik: int) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def _empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c in ("date", "period_end") else object) for c in COLUMNS})


def _frame(rows: list[dict], need_start: bool) -> pd.DataFrame:
    recs = [r for r in rows if r.get("form") in FORMS and (("start" in r) == need_start)]
    if not recs:
        return pd.DataFrame(columns=["start", "end", "filed", "val"]) if need_start else pd.DataFrame(columns=["end", "filed", "val"])
    df = pd.DataFrame(recs)
    cols = ["start", "end", "filed", "val"] if need_start else ["end", "filed", "val"]
    df = df[cols].copy()
    for c in cols[:-1]:
        df[c] = pd.to_datetime(df[c])
    df["val"] = df["val"].astype(float)
    key = ["start", "end"] if need_start else ["end"]
    return df.sort_values("filed").drop_duplicates(key, keep="first").reset_index(drop=True)


def _flows(rows: list[dict]) -> pd.DataFrame:
    """Standalone quarters as reported; Q4 derived from the annual figure minus its three quarters."""
    df = _frame(rows, need_start=True)
    if df.empty:
        return _empty()
    df["days"] = (df["end"] - df["start"]).dt.days
    quarters = df[df["days"].between(80, 100)]
    out = [pd.DataFrame({"date": quarters["filed"], "period_end": quarters["end"], "value": quarters["val"], "kind": "quarter"})]
    for _, a in df[df["days"].between(350, 380)].iterrows():
        inside = quarters[(quarters["start"] >= a["start"]) & (quarters["end"] <= a["end"])]
        ytd9 = df[(df["start"] == a["start"]) & df["days"].between(260, 290)]
        if len(inside) == 3:
            q4 = a["val"] - inside["val"].sum()
        elif len(ytd9) == 1:
            q4 = a["val"] - float(ytd9["val"].iloc[0])
        elif len(inside) == 0:
            out.append(pd.DataFrame({"date": [a["filed"]], "period_end": [a["end"]], "value": [a["val"]], "kind": ["annual"]}))
            continue
        else:
            continue
        out.append(pd.DataFrame({"date": [a["filed"]], "period_end": [a["end"]], "value": [q4], "kind": ["quarter"]}))
    res = pd.concat(out, ignore_index=True)
    res = res.sort_values(["period_end", "date"]).drop_duplicates(["period_end", "kind"], keep="first")
    return res[COLUMNS].reset_index(drop=True)


def _instants(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows, need_start=False)
    if df.empty:  # a duration fact (a weighted average share count) stands in as the instant at its period end
        df = _frame(rows, need_start=True)
        if df.empty:
            return _empty()
        df = df[(df["end"] - df["start"]).dt.days.between(80, 100)]
        if df.empty:
            return _empty()
    res = pd.DataFrame({"date": df["filed"], "period_end": df["end"], "value": df["val"], "kind": "instant"})
    return res.sort_values("period_end").drop_duplicates("period_end", keep="first").reset_index(drop=True)[COLUMNS]


def _series_frame(facts: dict, series: str) -> tuple[pd.DataFrame, str | None]:
    """Build every candidate tag's frame and keep the one whose data reaches furthest in time."""
    best, best_unit, best_end = _empty(), None, None
    for tax, tag, pref in TAGS[series]:
        node = facts.get(tax, {}).get(tag)
        if not node or not node.get("units"):
            continue
        units = node["units"]
        unit = pref if pref in units else next(iter(units))
        df = _flows(units[unit]) if series in FLOWS else _instants(units[unit])
        if df.empty:
            continue
        end = df["period_end"].max()
        if best_end is None or end > best_end:
            best, best_unit, best_end = df, unit, end
    return best, best_unit


def pull_edgar(store: Store, tickers: list[str] = config.BASKET) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            raw = fetch_raw(store, f"edgar.{t}", facts_url(config.CIK[t]), headers={"User-Agent": config.SEC_USER_AGENT})
        except SourceError:
            continue
        facts = json.loads(raw.content).get("facts", {})
        notes = []
        for series in TAGS:
            df, unit = _series_frame(facts, series)
            name = f"edgar.{t}.{series}"
            store.save_series(name, df)
            out[name] = df
            if series in FLOWS and unit and unit != "USD":
                store.set_meta(f"edgar.{t}.unit", unit)
                notes.append(f"{series} reported in {unit}, converted with FRED DEXTAUS")
            if df.empty:
                notes.append(f"no {series} tag in the company facts")
        if notes:
            store.set_meta(f"edgar.{t}.note", "; ".join(dict.fromkeys(notes)))
    return out


def shares_history(store: Store, ticker: str) -> pd.DataFrame | None:
    """Filed share counts in today's share units: later splits applied to earlier counts, scale errors dropped."""
    sh = store.load_series(f"edgar.{ticker}.shares")
    if sh is None or sh.empty:
        return None
    sh = sh.sort_values("period_end").reset_index(drop=True)
    splits = store.load_series(f"yahoo.splits.{ticker}")
    if splits is not None and not splits.empty:
        split_dates = pd.to_datetime(splits["date"])
        sh["value"] = sh["value"] * [float(splits.loc[split_dates > d, "value"].prod()) for d in pd.to_datetime(sh["period_end"])]
    # ponytail: rolling-median screen catches the 10^6x cover-page scale errors; blind for a series of two rows
    ratio = sh["value"] / sh["value"].rolling(5, center=True, min_periods=1).median()
    return sh[(ratio > 0.1) & (ratio < 10)].reset_index(drop=True)[COLUMNS]


def trailing_4q(df: pd.DataFrame, as_of: date) -> float | None:
    """Sum of the four latest quarters filed by `as_of`; the latest annual figure when only annuals exist."""
    known = df[df["date"] <= pd.Timestamp(as_of)]
    if known.empty:
        return None
    q = known[known["kind"] == "quarter"].sort_values("period_end").drop_duplicates("period_end", keep="last")
    if len(q) >= 4:
        return float(q["value"].tail(4).sum())
    annual = known[known["kind"] == "annual"].sort_values("period_end")
    return float(annual["value"].iloc[-1]) if not annual.empty else None


def latest_value(df: pd.DataFrame, as_of: date) -> float | None:
    known = df[df["date"] <= pd.Timestamp(as_of)]
    if known.empty:
        return None
    return float(known.sort_values("period_end")["value"].iloc[-1])
