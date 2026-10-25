"""Downloads every outside dataset and writes the small files the analysis reads.

The analysis itself never touches the network. It reads what this script leaves in
data/ (all small, all committed), so a clean checkout reruns without downloading.
Raw downloads go to data/external/ (gitignored), or to the folder in SHUTDOWNS_EXTERNAL if that is set.

    python analysis/fetch_data.py all            # everything below
    python analysis/fetch_data.py github         # GitHub Innovation Graph, pinned commit
    python analysis/fetch_data.py github --latest   # check for newer quarters
    python analysis/fetch_data.py keepiton       # Access Now shutdown tracker
    python analysis/fetch_data.py ooni           # OONI daily measurement counts
    python analysis/fetch_data.py wikimedia      # Wikimedia daily pageviews (event windows only)
    python analysis/fetch_data.py meta           # regions and income groups
"""
import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = Path(os.environ.get("SHUTDOWNS_EXTERNAL") or ROOT / "data" / "external")
DATA = ROOT / "data"

IG_REPO = "https://github.com/github/innovationgraph"
IG_COMMIT = "078fb62ee4395d321bec9f4f06694cca68f6b6cb"     # 31 Aug 2026, datasheet v1.0.10
IG_FILES = ["git_pushes", "developers", "repositories", "organizations"]
KIO_SHEET = ("https://docs.google.com/spreadsheets/d/1DvPAuHNLp5BXGb0nnZDGNoiIwEeu2ogdXEIDvT4Hyfk/"
             "export?format=xlsx")
OONI_API = "https://api.ooni.io/api/v1/aggregation?probe_cc={cc}&since={a}&until={b}&axis_x=measurement_start_day"
WM_URL = "https://analytics.wikimedia.org/published/datasets/country_project_page/{d}.tsv"
OWID_INCOME = ("https://ourworldindata.org/grapher/world-bank-income-groups.csv"
               "?v=1&csvType=full&useColumnShortNames=true")
# windows around shutdowns that fall inside the Wikimedia data (it starts 6 Feb 2023,
# and only covers "medium/higher risk" countries from 15 Feb 2024)
WM_WINDOWS = [("2024-05-01", "2024-09-30"),   # Bangladesh 2024
              ("2025-08-01", "2025-12-31"),   # Tanzania 2025
              ("2024-02-15", "2024-04-30")]   # Sudan 2024 (found in the tracker, see analysis/discover.py)


def get(url, tries=8):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}),
                                        timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            print("retry", url, e)
            time.sleep(10 * (k + 1))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def github(latest=False, write=True):
    dst = EXT / "innovationgraph"
    if not dst.exists():
        subprocess.run(["git", "clone", "--quiet", IG_REPO, str(dst)], check=True)
    subprocess.run(["git", "-C", str(dst), "fetch", "--quiet", "origin"], check=True)
    head = subprocess.run(["git", "-C", str(dst), "rev-parse", "origin/HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    ref = head if latest else IG_COMMIT
    subprocess.run(["git", "-C", str(dst), "checkout", "--quiet", ref], check=True)
    out = {"repo": IG_REPO, "pinned_commit": IG_COMMIT, "upstream_head": head, "checked_out": ref,
           "checked_on": date.today().isoformat(), "files": {}}
    for f in IG_FILES:
        src = dst / "data" / f"{f}.csv"
        rows = list(csv.DictReader(src.open()))
        last = max((int(r["year"]), int(r["quarter"])) for r in rows)
        mine = DATA / "raw" / f"{f}.csv"
        out["files"][f] = {"sha256_upstream": sha(src), "sha256_repo": sha(mine),
                           "same_as_repo": sha(src) == sha(mine), "last_quarter": f"{last[0]}Q{last[1]}"}
    ds = (dst / "docs" / "datasheet.md").read_text()
    out["datasheet_version"] = ds.split("Version:")[1].split("\n")[0].strip()
    out["datasheet_updated"] = ds.split("Last updated:")[1].split("\n")[0].strip()
    if not write:
        # dry run (shutdowns refresh without --apply): report, touch nothing in the repo
        return out
    sup = dst / "supplementary_data" / "git_pushes_weighted_by_profile_economy"
    (DATA / "raw" / "supplementary").mkdir(parents=True, exist_ok=True)
    for f in ("git_pushes_weighted_by_profile_economy.csv", "README.md"):
        (DATA / "raw" / "supplementary" / f).write_bytes((sup / f).read_bytes())
    (DATA / "provenance_github.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


# Access Now lists Somaliland on its own. GitHub has no separate code for it, so it goes
# under Somalia (SO). Somalia isn't in the panel, so this changes no estimate.
KIO_FIX = {"Iran (Islamic Republic of)": "IR", "Turkey": "TR", "Venezuela (Bolivarian Republic of)": "VE",
           "Congo (Democratic Republic of the)": "CD", "Somaliland": "SO"}


def _iso(name):
    import pycountry
    name = name.strip()
    if name in KIO_FIX:
        return KIO_FIX[name]
    try:
        return pycountry.countries.lookup(name).alpha_2
    except LookupError:
        return pycountry.countries.search_fuzzy(name)[0].alpha_2


def keepiton():
    import pandas as pd
    raw = EXT / "keepiton.xlsx"
    if not raw.exists():
        raw.write_bytes(get(KIO_SHEET))
    v = pd.read_excel(raw, sheet_name="Combined (2016-2025)")
    v["start_date"] = pd.to_datetime(v.start_date, errors="coerce")
    v["end_date"] = pd.to_datetime(v.end_date, errors="coerce")
    v = v[v.start_date >= "2020-01-01"].copy()
    v["iso2"] = v.country.astype(str).str.split(";")
    v = v.explode("iso2")
    v["iso2"] = v.iso2.map(_iso)
    v["multi_region"] = v.geo_scope.astype(str).str.startswith("It affected locations in more than one")
    v["nationwide"] = v.area_name.astype(str).str.contains("ation|ountr|ntire|ear country", regex=True)
    v["full_network"] = v.shutdown_extent.astype(str).str.contains("Full network")
    keep = ["iso2", "start_date", "end_date", "duration", "area_name", "affected_network", "shutdown_extent",
            "actual_cause", "multi_region", "nationwide", "full_network", "info_source_link"]
    out = v[keep].sort_values(["iso2", "start_date"])
    out["start_date"] = out.start_date.dt.date
    out["end_date"] = out.end_date.dt.date
    out["area_name"] = out.area_name.astype(str).str.slice(0, 120)
    out["info_source_link"] = out.info_source_link.astype(str).str.split(r"[;\s]").str[0]
    (DATA / "keepiton").mkdir(exist_ok=True)
    out.to_csv(DATA / "keepiton" / "shutdowns_2020_2025.csv", index=False)
    print("keepiton rows", len(out), "countries", out.iso2.nunique())


def panel_iso2():
    sys.path.insert(0, str(ROOT))
    from shutdowns.panel import load_panel
    return sorted(load_panel().iso2.unique())


def ooni(since="2020-01-01", until="2026-04-01"):
    rows = []
    for cc in panel_iso2():
        r = json.loads(get(OONI_API.format(cc=cc, a=since, b=until)))
        for x in r["result"]:
            rows.append((cc, x["measurement_start_day"][:10], x["measurement_count"]))
        time.sleep(0.4)
        print(cc, len(r["result"]))
    (DATA / "ooni").mkdir(exist_ok=True)
    import gzip
    with gzip.open(DATA / "ooni" / "daily_measurements.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iso2", "day", "measurements"])
        w.writerows(rows)


def wikimedia():
    path = DATA / "wikimedia" / "daily_pageviews.csv"
    path.parent.mkdir(exist_ok=True)
    have = set()
    if path.exists():
        have = {r["day"] for r in csv.DictReader(path.open())}
    days = []
    for a, b in WM_WINDOWS:
        d, end = date.fromisoformat(a), date.fromisoformat(b)
        while d <= end:
            if d.isoformat() not in have:
                days.append(d.isoformat())
            d += timedelta(days=1)
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["iso2", "day", "pageviews", "pages"])
        for d in sorted(set(days)):
            tot, n = {}, {}
            for line in io.TextIOWrapper(io.BytesIO(get(WM_URL.format(d=d))), encoding="utf-8"):
                p = line.rstrip("\n").split("\t")
                if len(p) < 7:
                    continue
                cc = p[1]
                tot[cc] = tot.get(cc, 0) + float(p[-1])
                n[cc] = n.get(cc, 0) + 1
            for cc in sorted(tot):
                w.writerow([cc, d, round(tot[cc]), n[cc]])
            f.flush()
            print("wikimedia", d, len(tot))


def meta():
    import country_converter as coco
    import pandas as pd
    iso = panel_iso2()
    cc = coco.CountryConverter()
    reg = pd.DataFrame({"iso2": iso,
                        "un_region": cc.convert(iso, src="ISO2", to="UNregion", not_found=None),
                        "continent": cc.convert(iso, src="ISO2", to="continent", not_found=None),
                        "iso3": cc.convert(iso, src="ISO2", to="ISO3", not_found=None)})
    inc = pd.read_csv(io.BytesIO(get(OWID_INCOME)))
    inc = inc[inc.year == 2020].set_index("code")["classification"]
    reg["income_2020"] = reg.iso3.map(inc)
    (DATA / "meta").mkdir(exist_ok=True)
    reg.to_csv(DATA / "meta" / "economies.csv", index=False)
    print(reg.income_2020.value_counts(dropna=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["all", "github", "keepiton", "ooni", "wikimedia", "meta"])
    ap.add_argument("--latest", action="store_true")
    a = ap.parse_args()
    EXT.mkdir(parents=True, exist_ok=True)
    steps = ["github", "keepiton", "ooni", "meta", "wikimedia"] if a.what == "all" else [a.what]
    for s in steps:
        github(a.latest) if s == "github" else globals()[s]()
