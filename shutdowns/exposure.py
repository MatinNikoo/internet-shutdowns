"""How much of a quarter was a country actually offline? Measured from daily data that
has nothing to do with GitHub.

OONI: volunteers run network tests from their phones and computers, and every test is
uploaded with the day it ran. When a country goes dark the daily count falls toward
zero. Wikimedia: daily pageviews by country (privacy noised), only from Feb 2023 and only
for some countries.

The rule is fixed in the analysis plan: baseline is the median daily count over the 91
days before the quarter, a day is disrupted when its count is under half the baseline,
exposure is the share of disrupted days. Countries with a baseline under 100 a day are
too noisy to use.
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MIN_BASE = {"ooni": 100, "wikimedia": 1000}


def quarter_dates(lbl):
    y, q = int(lbl[:4]), int(lbl[-1])
    start = date(y, 3 * q - 2, 1)
    end = date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1) - timedelta(days=1)
    return start, end


def load_daily(source="ooni"):
    if source == "ooni":
        d = pd.read_csv(ROOT / "data" / "ooni" / "daily_measurements.csv.gz", parse_dates=["day"])
        return d.rename(columns={"measurements": "count"})
    d = pd.read_csv(ROOT / "data" / "wikimedia" / "daily_pageviews.csv", parse_dates=["day"])
    return d.rename(columns={"pageviews": "count"})[["iso2", "day", "count"]]


def series(daily, iso2, start, end):
    """Daily counts with missing days filled as zero (no measurement uploaded that day)."""
    s = daily[daily.iso2 == iso2].set_index("day")["count"]
    idx = pd.date_range(start, end, freq="D")
    return s.reindex(idx, fill_value=0).astype(float)


def exposure(daily, iso2, quarters, base_end=None, threshold=0.5, base_days=91, source="ooni",
             covered=None):
    """Share of days disrupted and average depth over the given quarters.

    base_end is the last day of the baseline window. By default it's the day before the
    first quarter starts. Returns None fields when the baseline is too thin to trust or
    the source doesn't cover the dates."""
    q0 = quarter_dates(quarters[0])[0]
    q1 = quarter_dates(quarters[-1])[1]
    base_end = pd.Timestamp(base_end or (q0 - timedelta(days=1)))
    base_start = base_end - pd.Timedelta(days=base_days - 1)
    if covered is not None and (base_start < covered[0] or pd.Timestamp(q1) > covered[1]):
        return {"usable": False, "reason": "outside data coverage"}
    b = series(daily, iso2, base_start, base_end)
    if source == "wikimedia":
        # wikimedia is only downloaded around events, so a day nobody has isn't a zero
        b = b[b.index.isin(daily.day.unique())]
    base = float(np.median(b)) if len(b) else 0.0
    if base < MIN_BASE[source]:
        return {"usable": False, "reason": f"baseline {base:.0f} a day is under {MIN_BASE[source]}",
                "baseline": base}
    s = series(daily, iso2, q0, q1)
    ratio = s / base
    disrupted = ratio < threshold
    depth = np.clip(1 - ratio, 0, 1)
    return {"usable": True, "baseline": base, "days": int(len(s)),
            "disrupted_days": int(disrupted.sum()), "share": float(disrupted.mean()),
            "mean_depth": float(depth.mean()), "threshold": threshold,
            "first_disrupted": str(s.index[disrupted.values][0].date()) if disrupted.any() else None,
            "last_disrupted": str(s.index[disrupted.values][-1].date()) if disrupted.any() else None}


def disrupted_runs(daily, iso2, start, end, base, threshold=0.5):
    """Runs of consecutive disrupted days, for checking dates against the event registry."""
    s = series(daily, iso2, start, end) / base < threshold
    runs, cur = [], None
    for d, v in s.items():
        if v and cur is None:
            cur = [d, d]
        elif v:
            cur[1] = d
        elif cur is not None:
            runs.append(cur)
            cur = None
    if cur is not None:
        runs.append(cur)
    return [(str(a.date()), str(b.date()), int((b - a).days) + 1) for a, b in runs]


def quarterly_table(daily, quarters, threshold=0.5, base_days=91, source="ooni"):
    """exposure() for every country and quarter at once (same rule, much faster).
    Returns a frame with iso2, quarter, baseline, share (NaN when the baseline is too thin)."""
    out = []
    lo = pd.Timestamp(quarter_dates(quarters[0])[0]) - pd.Timedelta(days=base_days)
    hi = pd.Timestamp(quarter_dates(quarters[-1])[1])
    idx = pd.date_range(lo, hi, freq="D")
    wide = daily.pivot_table(index="day", columns="iso2", values="count", aggfunc="sum").reindex(idx).fillna(0.0)
    for q in quarters:
        a, b = (pd.Timestamp(d) for d in quarter_dates(q))
        base = wide.loc[a - pd.Timedelta(days=base_days):a - pd.Timedelta(days=1)].median()
        cur = wide.loc[a:b]
        share = (cur.div(base.where(base > 0)) < threshold).mean()
        for c in wide.columns:
            ok = base[c] >= MIN_BASE[source]
            out.append((c, q, float(base[c]), float(share[c]) if ok else np.nan))
    return pd.DataFrame(out, columns=["iso2", "quarter", "baseline", "share"])
