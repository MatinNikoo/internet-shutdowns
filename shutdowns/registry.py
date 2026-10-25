"""The event registry (data/events.csv) and the checks every row has to pass.

Every event has an id, the country, the headline quarter, full or partial, the day count
range for full shutdowns, start and end dates, scope, which networks were cut, the UN
region, and a public source. validate() returns a list of problems (empty means fine).
"""
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["event", "iso2", "country", "quarter", "kind", "days_low", "days_high", "what_happened", "source",
            "start_date", "end_date", "ongoing_at_quarter_end", "scope", "networks", "un_region"]
KINDS = {"full", "partial"}
NETWORKS = {"fixed and mobile", "mobile"}
SCOPES = {"nationwide", "regional"}


def load(path=None):
    return pd.read_csv(path or ROOT / "data" / "events.csv", keep_default_na=False, na_values=[""])


def _quarter_bounds(q):
    y, n = int(q[:4]), int(q[-1])
    a = date(y, 3 * n - 2, 1)
    b = date(y + (n == 4), 1 if n == 4 else 3 * n + 1, 1)
    return a, b  # b is exclusive


def validate(ev=None, keepiton=True, max_quarter=None):
    import pycountry
    ev = load() if ev is None else ev
    bad = []
    miss = [c for c in REQUIRED if c not in ev.columns]
    if miss:
        return [f"missing columns {miss}"]
    if ev.event.duplicated().any():
        bad.append("duplicate event ids")
    for r in ev.itertuples():
        tag = r.event
        if pycountry.countries.get(alpha_2=r.iso2) is None:
            bad.append(f"{tag}: unknown iso2 {r.iso2}")
        if not r.event.startswith(r.iso2 + "-"):
            bad.append(f"{tag}: id should start with the iso2 code")
        try:
            a, b = _quarter_bounds(r.quarter)
        except (ValueError, IndexError):
            bad.append(f"{tag}: bad quarter {r.quarter}")
            continue
        if max_quarter and r.quarter > max_quarter:
            bad.append(f"{tag}: quarter {r.quarter} is past the data ({max_quarter})")
        if r.kind not in KINDS:
            bad.append(f"{tag}: kind must be full or partial")
        if r.networks not in NETWORKS:
            bad.append(f"{tag}: networks must be one of {sorted(NETWORKS)}")
        if r.scope not in SCOPES:
            bad.append(f"{tag}: scope must be one of {sorted(SCOPES)}")
        if not str(r.source).startswith("https://"):
            bad.append(f"{tag}: source must be an https link")
        start = date.fromisoformat(r.start_date)
        # the start can sit in the quarter before the headline one (Iran 2022 began 21 Sep)
        prev_a = _quarter_bounds(f"{a.year - (a.month == 1)}Q{(a.month - 2) // 3 % 4 + 1 if a.month > 1 else 4}")[0]
        if not (prev_a <= start < b):
            bad.append(f"{tag}: start date {start} is not in or just before {r.quarter}")
        if isinstance(r.end_date, str) and r.end_date:
            end = date.fromisoformat(r.end_date)
            if end < start:
                bad.append(f"{tag}: ends before it starts")
            span = (end - start).days + 1
        else:
            if r.ongoing_at_quarter_end != "yes":
                bad.append(f"{tag}: no end date but not marked ongoing")
            span = (b - start).days
        if r.kind == "full":
            if pd.isna(r.days_low) or pd.isna(r.days_high):
                bad.append(f"{tag}: full shutdowns need a day count range")
            elif not (0 < r.days_low <= r.days_high <= span + 1):
                bad.append(f"{tag}: day counts {r.days_low} to {r.days_high} don't fit the {span} day window")
    if keepiton:
        bad += crosscheck_keepiton(ev)
    return bad


def crosscheck_keepiton(ev, tol_days=7):
    """Every event that falls inside the Access Now data (2020 to 2025) should have a
    record there in the same country starting within a week of our start date."""
    k = pd.read_csv(ROOT / "data" / "keepiton" / "shutdowns_2020_2025.csv", parse_dates=["start_date"])
    k = k[k.multi_region | k.nationwide]
    bad = []
    for r in ev.itertuples():
        s = pd.Timestamp(r.start_date)
        if s > pd.Timestamp("2025-12-31"):
            continue
        near = k[(k.iso2 == r.iso2) & ((k.start_date - s).abs() <= pd.Timedelta(days=tol_days))]
        if near.empty:
            bad.append(f"{r.event}: no Access Now record within {tol_days} days of {r.start_date}")
    return bad
