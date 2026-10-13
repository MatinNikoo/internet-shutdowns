"""Estimate every shutdown, the dose response test, recovery paths and robustness checks.

Writes results/events.json and results/site.json (the data behind the web page).
Run from the repo root:  python analysis/run_events.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel, event_windows, label, index  # noqa: E402
from shutdowns.inference import estimate  # noqa: E402
from shutdowns.synth import fit  # noqa: E402

METHODS = ("sdid", "sc")


def quarter_days(t):
    y, q = 2020 + t // 4, t % 4 + 1
    start = date(y, 3 * q - 2, 1)
    end = date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
    return (end - start).days


def run(panel, ev, min_donor=None):
    pre, head, path = event_windows(panel, ev)
    _, Y0 = panel.donor_matrix()
    y1 = panel.series(ev.iso2)
    out = {}
    for m in METHODS:
        r = estimate(m, y1, Y0, pre, head, path)
        out[m] = r
    return pre, head, path, out


def summarize(r):
    lo, hi = r.ci_pct
    return {"pct": r.pct, "lo": lo, "hi": hi, "se": r.se, "se_space": r.se_space,
            "se_time": r.se_time, "p": r.p_value, "pre_rmse": r.fit.pre_rmse}


def dose_response(rows):
    """Does a day offline cost exactly a day of work?

    If coding simply stops while the internet is off and nothing is made up later,
    a quarter with share s of its days offline should land at (1 - s) of its twin,
    a log effect of log(1 - s). Fit measured = beta * predicted across the full
    shutdowns, weighting by precision. beta = 1 is "a day is a day", below 1 means
    people caught up or got around it, above 1 means the damage outlasted the outage."""
    x = np.array([np.log1p(-r["share_mid"]) for r in rows])
    y = np.array([np.log1p(r["sdid"]["pct"]) for r in rows])
    se = np.array([r["sdid"]["se"] for r in rows])
    w = 1 / se ** 2
    beta = np.sum(w * x * y) / np.sum(w * x ** 2)
    beta_se = np.sqrt(1 / np.sum(w * x ** 2))
    # sensitivity: the same fit with the low and high day counts
    sens = {}
    for k in ("share_low", "share_high"):
        xs = np.array([np.log1p(-r[k]) for r in rows])
        sens[k] = float(np.sum(w * xs * y) / np.sum(w * xs ** 2))
    # same fit without the one event that dominates the weights
    big = int(np.argmax(w * x ** 2))
    keep = np.arange(len(rows)) != big
    beta_wo = float(np.sum((w * x * y)[keep]) / np.sum((w * x ** 2)[keep]))
    beta_wo_se = float(np.sqrt(1 / np.sum((w * x ** 2)[keep])))
    return {"beta": float(beta), "se": float(beta_se),
            "lo": float(beta - 1.96 * beta_se), "hi": float(beta + 1.96 * beta_se),
            "beta_days_low": sens["share_low"], "beta_days_high": sens["share_high"],
            "without": rows[big]["event"], "beta_without": beta_wo, "se_without": beta_wo_se}


def robustness(panel, ev, pre, head):
    """Same estimate under different choices, for the events with a clear effect."""
    y1 = panel.series(ev.iso2)
    res = {}
    for thr in (10_000, 50_000, 200_000):
        ds = [c for c in panel.donors if panel.min_pushes[c] >= thr]
        Y0 = panel.Y.loc[ds].to_numpy()
        res[f"donors_over_{thr}"] = float(np.expm1(fit("sdid", y1, Y0, pre, head).effect))
    ds, Y0 = panel.donor_matrix()
    f = fit("sdid", y1, Y0, pre, head)
    top = int(np.argmax(f.omega))
    keep = [i for i in range(len(ds)) if i != top]
    res["drop_top_donor"] = float(np.expm1(fit("sdid", y1, Y0[keep], pre, head).effect))
    res["top_donor"] = ds[top]
    # only the last 8 pre quarters, in case the early pandemic years look different
    if len(pre) > 8:
        res["last_8_pre_quarters"] = float(np.expm1(fit("sdid", y1, Y0, pre[-8:], head).effect))
    return res


def main():
    panel = Panel()
    # stock counts by where accounts are seen; they barely ever fall, so a fall means
    # accounts started showing up somewhere else (a VPN, or people leaving)
    stocks = {"developers": Panel(outcome="log_devs"), "repositories": Panel(outcome="log_repos")}
    rows = []
    for _, ev in panel.events.iterrows():
        pre, head, path, est = run(panel, ev)
        days_in = sum(quarter_days(t) for t in head)
        row = {
            "event": ev.event, "iso2": ev.iso2, "country": ev.country, "kind": ev.kind,
            "quarters": [label(t) for t in head], "pre_quarters": len(pre),
            "path_quarters": [label(t) for t in path],
            "what": ev.what_happened, "source": ev.source,
            **{m: summarize(r) for m, r in est.items()},
        }
        if ev.kind == "full":
            row["days_low"], row["days_high"] = float(ev.days_low), float(ev.days_high)
            row["share_low"] = ev.days_low / days_in
            row["share_high"] = ev.days_high / days_in
            row["share_mid"] = (row["share_low"] + row["share_high"]) / 2
            row["full_stop_pct"] = -row["share_mid"]
        r = est["sdid"]
        quarters = list(head) + list(path)
        row["path"] = [{"q": label(t), "gap_pct": float(np.expm1(r.fit.gaps[t])),
                        "lo": float(np.expm1(r.fit.gaps[t] - 1.96 * r.path_se[t])),
                        "hi": float(np.expm1(r.fit.gaps[t] + 1.96 * r.path_se[t]))}
                       for t in quarters]
        row["series"] = {"actual": [float(v) for v in np.exp(panel.series(ev.iso2))],
                         "twin": [float(v) for v in np.exp(r.fit.twin)]}
        ds, _ = panel.donor_matrix()
        order = np.argsort(-r.fit.omega)[:6]
        row["twin_made_of"] = [{"iso2": ds[i], "weight": float(r.fit.omega[i])}
                               for i in order if r.fit.omega[i] > 0.005]
        a = np.exp(panel.series(ev.iso2))
        t0 = head[0]
        prev = max(t for t in range(t0) if t in pre)
        row["naive"] = {"vs_last_clean_quarter": float(a[t0] / a[prev] - 1),
                        "vs_same_quarter_last_year": float(a[t0] / a[t0 - 4] - 1)}
        row["location_drift"] = {}
        for name, sp in stocks.items():
            _, Ys = sp.donor_matrix()
            rs = estimate("sdid", sp.series(ev.iso2), Ys, pre, head)
            lo_, hi_ = rs.ci_pct
            row["location_drift"][name] = {"pct": rs.pct, "lo": lo_, "hi": hi_, "p": rs.p_value}
        if r.p_value < 0.1 or abs(r.pct) > 0.3:
            row["robustness"] = robustness(panel, ev, pre, head)
        rows.append(row)
        print(f"{ev.event:8} sdid {r.pct:+.1%} [{row['sdid']['lo']:+.1%}, {row['sdid']['hi']:+.1%}] "
              f"p={r.p_value:.3f}   sc {est['sc'].pct:+.1%}")

    full = [r for r in rows if r["kind"] == "full"]
    dr = dose_response(full)
    print("dose response beta", dr)

    out = {"labels": panel.labels, "n_donors": len(panel.donors), "events": rows, "dose_response": dr,
           "data_through": panel.labels[-1]}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "events.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
