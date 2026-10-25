"""Packs the clean analysis dataset into data/release/ so anyone can use it without
running the pipeline. One row per economy and quarter, plus the event table with my
estimates next to each event, plus a data card.

    python analysis/release.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))
from shutdowns.panel import Panel, load_meta, HEADLINE, label  # noqa: E402
from shutdowns.exposure import load_daily, quarterly_table  # noqa: E402
from exposure import kio_quarters  # noqa: E402

OUT = ROOT / "data" / "release"


def name(iso2):
    c = pycountry.countries.get(alpha_2=iso2)
    return (getattr(c, "common_name", None) or c.name) if c else iso2


def panel_table(panel):
    df = panel.df.copy()
    meta = load_meta()
    kio = kio_quarters()
    ooni = load_daily("ooni")
    q = ooni.assign(quarter=ooni.day.dt.year.astype(str) + "Q" + ((ooni.day.dt.month - 1) // 3 + 1).astype(str))
    q = q.groupby(["iso2", "quarter"])["count"].sum()
    ev = {}
    for _, e in panel.events.iterrows():
        for t in HEADLINE.get(e.event, [e.t]):
            ev[(e.iso2, label(t))] = e.event
    ex = quarterly_table(ooni, panel.labels[1:]).set_index(["iso2", "quarter"])["share"]
    rows = []
    for r in df.itertuples():
        share = ex.get((r.iso2, r.label), np.nan)
        rows.append({
            "iso2": r.iso2, "economy": name(r.iso2), "quarter": r.label,
            "git_pushes": int(r.git_pushes), "developers": int(r.developers), "repositories": int(r.repositories),
            "organizations": None if pd.isna(r.organizations) else int(r.organizations),
            "donor": r.iso2 in panel.donors, "registry_event": ev.get((r.iso2, r.label), ""),
            "keepiton_full_network": (r.iso2, r.label) in kio,
            "ooni_measurements": int(q.get((r.iso2, r.label), 0)),
            "ooni_share_disrupted": None if pd.isna(share) else float(share),
            "un_region": meta.un_region.get(r.iso2), "continent": meta.continent.get(r.iso2),
            "income_2020": meta.income_2020.get(r.iso2)})
    return pd.DataFrame(rows)


def event_table(panel):
    ev = panel.events.drop(columns=["t"]).copy()
    I = {e["event"]: e for e in json.loads((ROOT / "results" / "identification.json").read_text())["events"]}
    X = {e["event"]: e for e in json.loads((ROOT / "results" / "exposure.json").read_text())["events"]}
    for m in ("sdid", "sc", "ascm"):
        ev[f"{m}_pct"] = ev.event.map(lambda e: I[e][m]["pct"])
    ev["sdid_lo"] = ev.event.map(lambda e: I[e]["sdid"]["lo"])
    ev["sdid_hi"] = ev.event.map(lambda e: I[e]["sdid"]["hi"])
    ev["p_holm"] = ev.event.map(lambda e: I[e]["p_holm"])
    ev["conformal_p"] = ev.event.map(lambda e: I[e]["conformal"]["p"])
    ev["breakdown_m"] = ev.event.map(lambda e: I[e]["sensitivity"]["breakdown_m"])
    ev["passes_all_checks"] = ev.event.map(lambda e: I[e]["clear_drop"])
    ev["passes_all_runnable_checks"] = ev.event.map(lambda e: I[e]["passes_all_runnable"])
    ev["ooni_share_disrupted"] = ev.event.map(
        lambda e: X[e]["ooni"]["0.5"]["share"] if X[e]["ooni"]["0.5"]["usable"] else np.nan)
    return ev


CARD = """# Data card: internet shutdowns and GitHub activity

What's here. Two tables I built for this project, ready to use without running any code.

* `panel.csv` has one row per economy and quarter, 2020Q1 to 2026Q1, {n_econ} economies, {n_rows} rows. GitHub activity
  (git pushes, developers, repositories, organizations), whether the economy is in the donor pool, which registry
  shutdown (if any) hit that quarter, whether Access Now recorded any full network shutdown there that quarter, OONI
  measurement counts, the OONI share of disrupted days (blank when the baseline is too thin to trust), and region and
  income group.
* `events.csv` is the event registry (dates, full or partial, which networks, day counts, region, a public source for
  every row) with my estimates next to each event.

Where it comes from.

* GitHub Innovation Graph, commit {commit}, datasheet version {version}. CC0. GitHub places a developer in the
  economy their IP address shows on most days of the quarter, and carries the last location forward on days with no
  activity. So VPN users count wherever the VPN exits. Developers, repositories and organizations are end of quarter
  counts that include inactive accounts. Economies need 100 or more developers doing the activity to be published at
  all, and this panel keeps only economies with every quarter present.
* Access Now KeepItOn shutdown tracker, 2020 to 2025. The flag here is "any record coded as a full network shutdown in
  that quarter", of any scope, so it includes regional and short ones.
* OONI measurement counts (api.ooni.io aggregation endpoint). These are volunteer network tests. Counts swing a lot
  when a heavy volunteer starts or stops, so the disrupted day share is noisy outside very large countries. In quarters
  with no recorded shutdown and a baseline of 5,000 or more tests a day, the share is {p50:.0%} at the median and {p95:.0%}
  at the 95th percentile.
* Regions from country_converter, income groups from the World Bank classification via Our World in Data.

Licenses, source by source. The repo's MIT license covers the code only.

* GitHub Innovation Graph columns (git pushes, developers, repositories, organizations) are CC0.
* The Access Now flag (`keepiton_full_network`) is derived from Access Now's KeepItOn data, which they publish under
  CC BY 4.0. Credit Access Now if you reuse it. The 1,418 row extract of the whole tracker in
  `data/keepiton/shutdowns_2020_2025.csv` is the same data, with a few derived columns I added.
* The OONI columns (`ooni_measurements`, `ooni_share_disrupted`) and `data/ooni/daily_measurements.csv.gz` are OONI
  data, CC BY-NC-SA 4.0 (https://github.com/ooni/license/tree/master/data). That means attribution, no commercial
  use, and share alike.
* Wikimedia pageviews (`data/wikimedia/`) are CC0.
* Because `panel.csv` and `events.csv` both carry OONI derived columns, treat both files as CC BY-NC-SA 4.0. Drop the
  OONI columns and the rest is CC0 plus the Access Now flag under CC BY 4.0.

What it's good for. Comparing GitHub activity across economies and quarters, and lining that up with shutdown records.

What it's not good for. National output, productivity or employment. Anything finer than a quarter. Small economies,
where a few accounts move the numbers. Any claim that ignores VPN use.

Rebuild it with `python analysis/release.py` after `make all`.
"""


def main():
    panel = Panel()
    OUT.mkdir(parents=True, exist_ok=True)
    p = panel_table(panel)
    p.to_csv(OUT / "panel.csv", index=False)
    e = event_table(panel)
    e.to_csv(OUT / "events.csv", index=False)
    prov = json.loads((ROOT / "data" / "provenance_github.json").read_text())
    nf = json.loads((ROOT / "results" / "exposure.json").read_text())["noise_floor"]["baseline_5000_up"]
    (OUT / "DATACARD.md").write_text(CARD.format(n_econ=p.iso2.nunique(), n_rows=len(p), commit=prov["pinned_commit"][:7],
                                                 version=prov["datasheet_version"], p50=nf["p50"], p95=nf["p95"]))
    print("panel", p.shape, "events", e.shape)


if __name__ == "__main__":
    main()
