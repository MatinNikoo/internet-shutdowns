"""Loads the country by quarter panel (built in SQL) and the list of shutdowns."""
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def label(t):
    return f"{2020 + t // 4}Q{t % 4 + 1}"


def index(lbl):
    y, q = lbl.split("Q")
    return (int(y) - 2020) * 4 + int(q) - 1


def load_panel():
    con = duckdb.connect()
    con.execute(f"SET file_search_path='{ROOT}'")
    con.execute((ROOT / "sql" / "panel.sql").read_text())
    df = con.execute("SELECT * FROM panel_eligible").df()
    con.close()
    return df


def load_events():
    ev = pd.read_csv(ROOT / "data" / "events.csv")
    ev["t"] = ev["quarter"].map(index)
    return ev


class Panel:
    """Log pushes as a matrix (countries x quarters), plus helpers to pick donors."""

    def __init__(self, df=None, min_donor_pushes=10_000, outcome="log_pushes"):
        df = load_panel() if df is None else df
        self.df = df
        wide = df.pivot(index="iso2", columns="t", values=outcome).sort_index(axis=1)
        self.Y = wide
        self.T = wide.shape[1]
        self.labels = [label(t) for t in wide.columns]
        self.min_pushes = df.groupby("iso2")["min_pushes"].first()
        self.events = load_events()
        hit = set(self.events["iso2"])
        self.donors = [c for c in wide.index
                       if c not in hit and self.min_pushes[c] >= min_donor_pushes]

    def series(self, iso2):
        return self.Y.loc[iso2].to_numpy()

    def donor_matrix(self, exclude=()):
        ds = [c for c in self.donors if c not in exclude]
        return ds, self.Y.loc[ds].to_numpy()

    def raw(self, iso2, col="git_pushes"):
        d = self.df[self.df.iso2 == iso2].sort_values("t")
        return d[col].to_numpy()


def event_windows(panel, ev_row, horizon=8):
    """Pre quarters, headline quarters and the recovery path for one event.

    Quarters hit by any other listed event in the same country are left out of the
    pre period, and the recovery path stops before the country's next event."""
    same = panel.events[panel.events.iso2 == ev_row.iso2]
    affected = set()
    for _, r in same.iterrows():
        affected |= set(EXTRA_AFFECTED.get(r.event, [])) | {r.t}
    start = ev_row.t
    headline = HEADLINE.get(ev_row.event, [start])
    first = min(headline + EXTRA_AFFECTED.get(ev_row.event, []))
    pre = [t for t in range(first) if t not in affected]
    later = sorted(r.t for _, r in same.iterrows() if r.t > max(headline))
    stop = min(later) if later else panel.T
    path = list(range(max(headline) + 1, min(stop, max(headline) + 1 + horizon, panel.T)))
    return pre, headline, path


# quarters partly touched by an event besides its main quarter
EXTRA_AFFECTED = {
    "IR-2022": [index("2022Q3")],          # curfews began 21 Sep
}
# events whose headline effect spans more than one quarter
HEADLINE = {
    "IR-2022": [index("2022Q4")],
    "MM-2021": [index("2021Q1"), index("2021Q2")],
}
