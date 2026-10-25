"""Measure each shutdown with data that has nothing to do with GitHub.

1. OONI daily measurement counts: when did each country actually go dark, and for how
   many days of the quarter? Checked against the dates in data/events.csv.
2. How noisy is that measure in quarters with no shutdown? (every donor economy-quarter
   with a usable baseline and no full network shutdown in the Access Now data)
3. Wikimedia daily pageviews as a second, independent check where they exist.
4. C3 from the analysis plan: does the drop in attributed pushes scale with the OONI
   measured share of the quarter offline?

Writes results/exposure.json.   python analysis/exposure.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.exposure import load_daily, exposure, disrupted_runs, quarter_dates  # noqa: E402
from shutdowns.panel import Panel, HEADLINE, label  # noqa: E402
from shutdowns.power import wls_origin  # noqa: E402

THRESHOLDS = (0.25, 0.5, 0.75)
QUIET = []   # (baseline, daily disrupted flags) for every quiet donor quarter, filled by calibration()


def run_mask(flags, k=3):
    """True on days that sit in a run of at least k disrupted days."""
    f = np.asarray(flags, bool)
    out = np.zeros(len(f), bool)
    i = 0
    while i < len(f):
        if f[i]:
            j = i
            while j < len(f) and f[j]:
                j += 1
            if j - i >= k:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def timing(daily, ev, base, threshold=0.5, min_base=1000):
    """Does OONI show a run of 3+ disrupted days inside the registry window? And how often
    would a quiet quarter show one in a window of the same length and position by chance?"""
    q0, q1 = quarter_dates(ev.quarter)
    a = pd.Timestamp(ev.start_date)
    b = pd.Timestamp(ev.end_date) if isinstance(ev.end_date, str) and ev.end_date else pd.Timestamp(q1)
    lo = max(a, pd.Timestamp(q0)) - pd.Timestamp(q0)
    hi = min(b, pd.Timestamp(q1)) - pd.Timestamp(q0)
    i, j = lo.days, hi.days + 1
    from shutdowns.exposure import series
    flags = (series(daily, ev.iso2, q0, q1) / base < threshold).values
    hit = bool(run_mask(flags)[i:j].any())
    chance = [run_mask(f)[i:j].any() for bb, f in QUIET if bb >= min_base and len(f) >= j]
    # exploratory, not the plan's rule: only count disrupted days near the registry dates
    # (3 days either side), so volunteer noise elsewhere in the quarter doesn't count as exposure
    wi, wj = max(i - 3, 0), min(j + 3, len(flags))
    return {"window": [str(a.date()), str(b.date())], "ooni_run_in_window": hit,
            "chance_rate": float(np.mean(chance)), "n_quiet": len(chance),
            "window_disrupted_days": int(flags[wi:wj].sum()), "window_share": float(flags[wi:wj].sum() / len(flags))}
WM_COVER = (pd.Timestamp("2024-02-15"), pd.Timestamp("2026-10-19"))


def event_quarters(ev):
    return [label(t) for t in HEADLINE.get(ev.event, [ev.t])]


def kio_quarters():
    k = pd.read_csv(ROOT / "data" / "keepiton" / "shutdowns_2020_2025.csv",
                    parse_dates=["start_date", "end_date"])
    k = k[k.full_network]
    hit = set()
    for r in k.itertuples():
        end = r.end_date if pd.notna(r.end_date) else r.start_date
        for d in pd.date_range(r.start_date, end, freq="MS").union([r.start_date, end]):
            hit.add((r.iso2, f"{d.year}Q{(d.month - 1) // 3 + 1}"))
    return hit


def calibration(daily, panel, threshold=0.5):
    """Exposure in quarters where nothing happened, the noise floor. Reported by how big
    the country's baseline is, since a country with a few hundred tests a day swings far
    more than one with ten thousand."""
    bad = kio_quarters()
    vals = []
    for c in panel.donors:
        s = daily[daily.iso2 == c].set_index("day")["count"]
        s = s.reindex(pd.date_range("2019-10-01", "2026-03-31", freq="D"), fill_value=0).astype(float)
        for t in range(2, panel.T):
            q = label(t)
            if (c, q) in bad:
                continue
            a, b = quarter_dates(q)
            base = float(np.median(s[pd.Timestamp(a) - pd.Timedelta(days=91):pd.Timestamp(a) - pd.Timedelta(days=1)]))
            if base < 100:
                continue
            flags = (s[pd.Timestamp(a):pd.Timestamp(b)] / base < threshold).values
            vals.append((base, float(flags.mean())))
            QUIET.append((base, flags))
    v = np.array(vals)
    out = {}
    for lo, hi in ((100, 1000), (1000, 5000), (5000, np.inf)):
        x = v[(v[:, 0] >= lo) & (v[:, 0] < hi), 1]
        out[f"baseline_{lo}_{'up' if hi == np.inf else int(hi)}"] = {
            "n": int(len(x)), "mean": float(x.mean()), "p50": float(np.median(x)),
            "p95": float(np.quantile(x, 0.95)), "p99": float(np.quantile(x, 0.99))}
    x = v[:, 1]
    out["all"] = {"n": int(len(x)), "mean": float(x.mean()), "p50": float(np.median(x)),
                  "p95": float(np.quantile(x, 0.95)), "p99": float(np.quantile(x, 0.99))}
    return out


def main():
    panel = Panel()
    ooni = load_daily("ooni")
    wm_path = ROOT / "data" / "wikimedia" / "daily_pageviews.csv"
    wiki = load_daily("wikimedia") if wm_path.exists() else None
    ide = {e["event"]: e for e in json.loads((ROOT / "results" / "identification.json").read_text())["events"]}
    calib = calibration(ooni, panel)
    print("noise floor", calib)
    rows = []
    for _, ev in panel.events.iterrows():
        qs = event_quarters(ev)
        row = {"event": ev.event, "kind": ev.kind, "quarters": qs,
               "registry_days": [ev.days_low, ev.days_high] if ev.kind == "full" else None,
               "ooni": {}, "wikimedia": None}
        for th in THRESHOLDS:
            row["ooni"][str(th)] = exposure(ooni, ev.iso2, qs, threshold=th)
        x = row["ooni"]["0.5"]
        if x["usable"]:
            s, e = quarter_dates(qs[0])[0], quarter_dates(qs[-1])[1]
            row["ooni_runs"] = [r for r in disrupted_runs(ooni, ev.iso2, s, e, x["baseline"]) if r[2] >= 2]
            row["timing"] = timing(ooni, ev, x["baseline"])
        if wiki is not None:
            w = exposure(wiki, ev.iso2, qs, source="wikimedia", covered=WM_COVER)
            row["wikimedia"] = w
            if w.get("usable"):
                s, e = quarter_dates(qs[0])[0], quarter_dates(qs[-1])[1]
                row["wikimedia_runs"] = [r for r in disrupted_runs(wiki, ev.iso2, s, e, w["baseline"]) if r[2] >= 2]
        row["sdid"] = {k: ide[ev.event]["sdid"][k] for k in ("log", "se", "pct")}
        rows.append(row)
        print(ev.event, qs, "ooni", {k: (round(v["share"], 3) if v["usable"] else None) for k, v in row["ooni"].items()},
              "wiki", row["wikimedia"] and row["wikimedia"].get("share"))

    # wikimedia noise floor: 2024Q3 is the one quarter whose whole baseline window was downloaded
    wiki_floor = None
    if wiki is not None:
        from shutdowns.exposure import quarterly_table
        t = quarterly_table(wiki, ["2024Q3"], source="wikimedia")
        bad = kio_quarters()
        t = t[t.iso2.isin(panel.donors) & ~t.apply(lambda r: (r.iso2, r.quarter) in bad, axis=1)].dropna()
        wiki_floor = {"quarter": "2024Q3", "n": int(len(t)), "p50": float(t.share.median()),
                      "p95": float(t.share.quantile(.95)), "max": float(t.share.max())}
        print("wikimedia noise floor", wiki_floor)

    # C3: slope of the log effect on log(1 - exposure), events with usable OONI exposure
    use = [r for r in rows if r["ooni"]["0.5"]["usable"]]
    x = np.array([np.log1p(-r["ooni"]["0.5"]["share"]) for r in use])
    y = np.array([r["sdid"]["log"] for r in use])
    se = np.array([r["sdid"]["se"] for r in use])
    b, sb = wls_origin(x, y, se)
    c3 = {"events": [r["event"] for r in use], "beta": b, "se": sb, "lo": b - 1.96 * sb, "hi": b + 1.96 * sb,
          "p_one_sided": float(1 - norm.cdf(b / sb)), "interval_width": 3.92 * sb,
          "slope_one_question_allowed": bool(3.92 * sb < 0.5)}
    # the same with depth instead of a yes/no day count, and with only full shutdowns
    xd = np.array([np.log1p(-r["ooni"]["0.5"]["mean_depth"]) for r in use])
    bd, sbd = wls_origin(xd, y, se)
    c3["depth_version"] = {"beta": bd, "se": sbd}
    full = [i for i, r in enumerate(use) if r["kind"] == "full"]
    bf, sbf = wls_origin(x[full], y[full], se[full])
    c3["full_only"] = {"events": [use[i]["event"] for i in full], "beta": bf, "se": sbf}
    no_ir26 = [i for i, r in enumerate(use) if r["event"] != "IR-2026"]
    bn, sbn = wls_origin(x[no_ir26], y[no_ir26], se[no_ir26])
    c3["without_IR-2026"] = {"beta": bn, "se": sbn}
    # PK-2023's 14% is volunteer noise in April, a month before the 9 to 12 May cut, and
    # IR-2022's 2 days miss evening mobile curfews. two exploratory versions that deal with that
    use_w = [r for r in use if r.get("timing")]
    xw = np.array([np.log1p(-r["timing"]["window_share"]) for r in use_w])
    yw = np.array([r["sdid"]["log"] for r in use_w])
    sw = np.array([r["sdid"]["se"] for r in use_w])
    ok = xw < 0
    bw, sbw = wls_origin(xw[ok], yw[ok], sw[ok])
    c3["event_window_version"] = {"events": [r["event"] for r, k in zip(use_w, ok) if k],
                                  "dropped_no_exposure": [r["event"] for r, k in zip(use_w, ok) if not k],
                                  "beta": bw, "se": sbw, "lo": bw - 1.96 * sbw, "hi": bw + 1.96 * sbw}
    c3["full_only"]["lo"] = bf - 1.96 * sbf
    c3["full_only"]["hi"] = bf + 1.96 * sbf
    c3["without_IR-2026"]["lo"] = bn - 1.96 * sbn
    c3["without_IR-2026"]["hi"] = bn + 1.96 * sbn
    c3["exposure_used"] = {r["event"]: r["ooni"]["0.5"]["share"] for r in use}
    print("C3", json.dumps(c3, indent=1))
    tm = [r["timing"] for r in rows if r.get("timing") and r["kind"] == "full"]
    timing_summary = {"full_events_checked": len(tm), "hits": sum(t["ooni_run_in_window"] for t in tm),
                      # chance that every one of them lines up if OONI were just noise
                      "joint_chance": float(np.prod([t["chance_rate"] for t in tm]))}
    print("timing", timing_summary)
    out = {"events": rows, "noise_floor": calib, "wikimedia_noise_floor": wiki_floor, "C3": c3, "timing": timing_summary,
           "sources": {"ooni": "https://api.ooni.io (aggregation endpoint, measurement_start_day)",
                       "wikimedia": "https://analytics.wikimedia.org/published/datasets/country_project_page/"}}
    (ROOT / "results" / "exposure.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
