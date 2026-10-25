"""Loads the country by quarter panel (built in SQL) and the list of shutdowns."""
from pathlib import Path
import duckdb
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


OUTCOMES = {"git_pushes": "log_pushes", "developers": "log_devs",
            "repositories": "log_repos", "organizations": "log_orgs"}


def load_meta():
    """Continent, UN region and 2020 World Bank income group for every economy in the panel."""
    return pd.read_csv(ROOT / "data" / "meta" / "economies.csv", keep_default_na=False,
                       na_values=[""]).set_index("iso2")


def country_name(iso2):
    """Short common name for an iso2 code, the code itself if pycountry doesn't know it."""
    import pycountry
    c = pycountry.countries.get(alpha_2=iso2)
    if c is None:
        return iso2
    return (getattr(c, "common_name", None) or c.name).split(",")[0].replace(" (Plurinational State of)", "")


def load_neighbors():
    nb = pd.read_csv(ROOT / "data" / "meta" / "neighbors.csv")
    return {r.iso2: r.neighbors.split() for r in nb.itertuples()}


def keepiton_full_network(since="2020-01-01", until="2025-12-31"):
    """Economies with any full network shutdown in the Access Now data (any scope)."""
    k = pd.read_csv(ROOT / "data" / "keepiton" / "shutdowns_2020_2025.csv", parse_dates=["start_date"])
    k = k[k.full_network & (k.start_date >= since) & (k.start_date <= until)]
    return set(k.iso2)


class Panel:
    """Log pushes as a matrix (countries x quarters), plus helpers to pick donors."""

    def __init__(self, df=None, min_donor_pushes=10_000, outcome="log_pushes"):
        df = load_panel() if df is None else df
        outcome = OUTCOMES.get(outcome, outcome)
        self.outcome = outcome
        self.df = df
        wide = df.pivot(index="iso2", columns="t", values=outcome).sort_index(axis=1)
        wide = wide.dropna()
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

    def donor_matrix(self, exclude=(), only=None):
        ds = [c for c in self.donors if c not in exclude and (only is None or c in only)]
        return ds, self.Y.loc[ds].to_numpy()

    def pool(self, kind, iso2):
        """Alternative donor pools for one treated economy."""
        if kind == "all":
            return list(self.donors)
        if kind == "no_keepiton_shutdown":
            bad = keepiton_full_network()
            return [c for c in self.donors if c not in bad]
        meta = load_meta()
        if kind == "same_continent":
            return [c for c in self.donors if meta.continent.get(c) == meta.continent[iso2]]
        if kind == "same_income":
            return [c for c in self.donors if meta.income_2020.get(c) == meta.income_2020[iso2]]
        if kind == "no_neighbors":
            nb = set(load_neighbors().get(iso2, []))
            return [c for c in self.donors if c not in nb]
        raise ValueError(kind)

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
