"""Shutdowns my registry doesn't have, found by a fixed rule in the Access Now data.

Rule: nationwide, full network, fixed and mobile both cut, at least 5 days, in an economy
that's in the panel, starting in 2021 or later (so there are at least four pre quarters).
Every quarter the shutdown touches is a headline quarter.

Two uses. First, a check on the registry: the rule should find the full shutdowns already
in data/events.csv. Second, an out of sample test of the dose response: take the slope
fitted on the registry events and see whether it predicts these new ones. Exam shutdowns
(Iraq, Syria, Algeria) cut the internet for a few hours a day, not all day, so the day
count overstates them; they are reported apart.

Writes results/discovery.json.   python analysis/discover.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel, index  # noqa: E402
from shutdowns.design import run, registry_skip  # noqa: E402
from shutdowns.exposure import load_daily, exposure, quarter_dates  # noqa: E402

MIN_DAYS = 5


def candidates(panel):
    k = pd.read_csv(ROOT / "data" / "keepiton" / "shutdowns_2020_2025.csv",
                    parse_dates=["start_date", "end_date"])
    k["dur"] = pd.to_numeric(k.duration, errors="coerce")
    c = k[k.full_network & k.nationwide & (k.affected_network == "Broadband, Mobile") & (k.dur >= MIN_DAYS)
          & k.iso2.isin(set(panel.Y.index)) & (k.start_date >= "2021-01-01")]
    return c


def quarter_days(rows):
    """Days in each quarter covered by the union of the shutdown windows."""
    days = set()
    for r in rows.itertuples():
        end = r.end_date if pd.notna(r.end_date) else r.start_date
        days |= set(pd.date_range(r.start_date, end, freq="D"))
    out = {}
    for d in days:
        q = f"{d.year}Q{(d.month - 1) // 3 + 1}"
        out[q] = out.get(q, 0) + 1
    return out


def main():
    panel = Panel()
    reg = panel.events
    c = candidates(panel)
    ooni = load_daily("ooni")
    wm_path = ROOT / "data" / "wikimedia" / "daily_pageviews.csv"
    wiki = load_daily("wikimedia") if wm_path.exists() else None
    H = json.loads((ROOT / "results" / "heterogeneity.json").read_text())["dose_response"]
    beta = H["beta"]
    found, new = [], []
    for iso2, rows in c.groupby("iso2"):
        exam = bool((rows.actual_cause == "Exam cheating").all())
        # group windows into separate episodes by quarter
        qd = quarter_days(rows)
        for q, days in sorted(qd.items()):
            t = index(q)
            if t >= panel.T:
                continue
            reg_hit = reg[(reg.iso2 == iso2) & (reg.t == t)]
            if iso2 == "MM" and q in ("2021Q1", "2021Q2"):
                reg_hit = reg[reg.event == "MM-2021"]
            if len(reg_hit):
                found.append({"iso2": iso2, "quarter": q, "registry_event": reg_hit.event.iloc[0], "days": days})
                continue
            a, b = quarter_dates(q)
            here = rows[(rows.start_date <= pd.Timestamp(b)) &
                        (rows.end_date.fillna(rows.start_date) >= pd.Timestamp(a))]
            new.append({"iso2": iso2, "quarter": q, "days": int(days), "exam": exam,
                        "cause": ", ".join(sorted(set(here.actual_cause))),
                        "source": here.info_source_link.iloc[0],
                        "keepiton_start": str(here.start_date.min().date())})
    # estimate the new ones, one quarter at a time
    for n in new:
        t = index(n["quarter"])
        skip = registry_skip(panel, n["iso2"], [t]) | {index(m["quarter"]) for m in new
                                                       if m["iso2"] == n["iso2"] and m["quarter"] != n["quarter"]}
        pre = [s for s in range(t) if s not in skip]
        r = run(panel, n["iso2"], [t], pre=pre, path=[], methods=("sdid",), extras=False)
        a, b = quarter_dates(n["quarter"])
        share = n["days"] / ((b - a).days + 1)
        n.update({"pre_quarters": len(pre), "sdid_pct": r["sdid"]["pct"], "se": r["sdid"]["se"],
                  "p_normal": r["sdid"]["p_normal"], "share_of_quarter": share,
                  "predicted_pct_beta_fit": float(np.expm1(beta * np.log1p(-share))),
                  "predicted_pct_day_for_day": float(-share)})
        n["z_vs_prediction"] = float((np.log1p(n["sdid_pct"]) - beta * np.log1p(-share)) / n["se"])
        n["ooni"] = exposure(ooni, n["iso2"], [n["quarter"]])
        if wiki is not None:
            n["wikimedia"] = exposure(wiki, n["iso2"], [n["quarter"]], source="wikimedia",
                                      covered=(pd.Timestamp("2024-02-15"), pd.Timestamp("2026-10-19")),
                                      base_end=None)
        print(n["iso2"], n["quarter"], f"{n['days']}d share {share:.2f} exam={n['exam']}  "
              f"sdid {n['sdid_pct']:+.1%} (se {n['se']:.2f})  predicted {n['predicted_pct_beta_fit']:+.1%}  z {n['z_vs_prediction']:+.1f}")
    # registry events the rule should find (the full ones before 2026)
    expected = list(reg[(reg.kind == "full") & (reg.quarter < "2026Q1")].event)
    got = sorted({f["registry_event"] for f in found})
    nonexam = [n for n in new if not n["exam"]]
    chi = float(np.sum([n["z_vs_prediction"] ** 2 for n in nonexam]))
    out = {"rule": f"nationwide, full network, fixed and mobile, >= {MIN_DAYS} days, panel economy, from 2021",
           "registry_found": found, "registry_expected": expected,
           "registry_missed": sorted(set(expected) - set(got)),
           "new": new, "dose_beta_used": beta,
           "non_exam_chi2": chi, "non_exam_n": len(nonexam)}
    print("registry missed by the rule:", out["registry_missed"])
    (ROOT / "results" / "discovery.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
