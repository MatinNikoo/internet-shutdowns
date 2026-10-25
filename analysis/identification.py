"""Can anything other than the shutdown explain the drops? Every check fixed in
paper/analysis_plan.tex, run on the nine events.

  F2 backdating, F3 donor pools and leave one out, breakdown values, conformal p values,
  three estimators, Holm across the nine events (C1), F1 negative controls,
  F4 VPN reassignment, and the 2026 jump that Iran's twin assumes.

Writes results/identification.json.   python analysis/identification.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel, event_windows, index, label  # noqa: E402
from shutdowns.design import for_event, run  # noqa: E402
from shutdowns.inference import estimate  # noqa: E402

POOLS = ["no_keepiton_shutdown", "same_continent", "same_income", "no_neighbors"]
# fixed in the analysis plan before running this check (version 1 had already shown Iran 2026)
EXITS = ["US", "DE", "NL", "GB", "FR", "FI", "SE", "CA", "SG", "TR", "AE"]
SANCTIONED = ["RU", "BY", "CU", "VE"]
VPN_EVENTS = ["IR-2026", "IR-2025", "IR-2022", "MM-2021", "SD-2021"]


def holm(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    run_max = 0.0
    for k, i in enumerate(order):
        run_max = max(run_max, (len(p) - k) * p[i])
        adj[i] = min(1.0, run_max)
    return adj


def pools(panel, ev, pre, head, base):
    y1 = panel.series(ev.iso2)
    out = {}
    for kind in POOLS:
        ds = [c for c in panel.pool(kind, ev.iso2) if c != ev.iso2]
        Y0 = panel.Y.loc[ds].to_numpy()
        r = estimate("sdid", y1, Y0, pre, head)
        lo, hi = r.ci_pct
        out[kind] = {"n_donors": len(ds), "pct": r.pct, "se": r.se, "lo": lo, "hi": hi, "p_perm": r.p_value,
                     "move_se": abs(r.effect - base["log"]) / base["se"],
                     "same_sign": bool(np.sign(r.effect) == np.sign(base["log"]))}
    return out


def placebo_extremes(e, names, k=3):
    """The donors whose fake events come out biggest in this event's window. Ethiopia had a
    38 day nationwide shutdown in mid 2020 that isn't in my registry, so it shows up here."""
    sp = np.array(e["placebos"]["space"])
    order = np.argsort(-np.abs(sp))[:k]
    beats = [names[i] for i in range(len(sp)) if abs(sp[i]) >= abs(e["sdid"]["log"])]
    return {"top": [{"iso2": names[i], "pct": float(np.expm1(sp[i]))} for i in order],
            "donors_at_least_as_big": beats}


def negative_controls(panel):
    nc = pd.read_csv(ROOT / "data" / "negative_controls.csv")
    rows = []
    for c in nc.itertuples():
        t = index(c.quarter)
        r = run(panel, c.iso2, [t], pre=list(range(t)), path=[], methods=("sdid",), extras=False)
        s = r["sdid"]
        rows.append({"control": c.control, "iso2": c.iso2, "country": c.country, "quarter": c.quarter,
                     "kind": c.kind, "source": c.source, "pct": s["pct"], "lo": s["lo"], "hi": s["hi"],
                     "p_normal": s["p_normal"], "p_perm": s["p_perm"]})
    n = len(rows)
    hits = sum(r["p_normal"] < 0.05 for r in rows)
    allowed = int(binom.ppf(0.95, n, 0.05))
    return {"controls": rows, "n": n, "rejections": hits, "allowed": allowed, "pass": hits <= allowed}


def vpn_check(panel, ev):
    """Does activity show up in likely VPN exit economies when a country goes dark?"""
    pre, head, _ = event_windows(panel, ev)
    donors = [c for c in panel.donors if c not in EXITS]
    Y0 = panel.Y.loc[donors].to_numpy()
    tr = run(panel, ev.iso2, head, pre=pre, path=[], methods=("sdid",), extras=False)
    raw = panel.df.pivot(index="iso2", columns="t", values="git_pushes")
    missing = float(sum(raw.loc[ev.iso2, t] * (np.exp(-tr["sdid"]["log"]) - 1) for t in head))
    rows, excess, var = [], 0.0, 0.0
    for e in EXITS:
        r = estimate("sdid", panel.series(e), Y0, pre, head)
        level = float(sum(raw.loc[e, t] for t in head))
        twin = level / np.exp(r.effect)
        ex = level - twin
        se_level = twin * r.se
        rows.append({"iso2": e, "pct": r.pct, "se": r.se, "excess_pushes": ex, "se_pushes": se_level})
        excess += ex
        var += se_level ** 2
    se = float(np.sqrt(var))
    return {"event": ev.event, "missing_pushes": missing, "exit_excess": excess, "exit_se": se,
            "z": excess / se, "mde_pushes": 2.8 * se, "mde_share_of_missing": 2.8 * se / missing,
            "exits": rows}


def stock_falls(panel):
    """Repositories and organizations are placed by where their members are seen. Both
    counts include dead projects, so they almost never fall. An outright fall means
    projects got placed somewhere else (or deleted), which is what VPN use would do."""
    out = {"base_rates": {}, "events": {}}
    for col in ("repositories", "organizations", "developers"):
        w = panel.df.pivot(index="iso2", columns="t", values=col).dropna()
        pc = w.pct_change(axis=1).iloc[:, 1:]
        out["base_rates"][col] = {"share_any_fall": float((pc < 0).values.mean()),
                                  "share_fall_over_2pct": float((pc < -0.02).values.mean()),
                                  "n": int(pc.size)}
        for _, ev in panel.events.iterrows():
            from shutdowns.panel import HEADLINE
            for t in HEADLINE.get(ev.event, [ev.t]):
                v = float(pc.loc[ev.iso2, t])
                rank = float((pc.values < v).mean())
                out["events"].setdefault(ev.event, {})[f"{col}_{label(t)}"] = {"pct_change": v, "share_of_all_lower": rank}
    return out


def jump_2026(panel, iran):
    """Iran's twin rises with the ~30% jump most economies had in 2026Q1. Did economies
    under broad sanctions get that jump too?"""
    t = index("2026Q1")
    donors = iran["donor_names"]
    space = np.array(iran["placebos"]["space"])
    out = {"donor_quarter_effects": {}}
    for c in SANCTIONED:
        if c in donors:
            v = space[donors.index(c)]
            out["donor_quarter_effects"][c] = {"pct": float(np.expm1(v)),
                                               "rank_from_bottom": int(np.sum(space <= v)),
                                               "of": len(space)}
    raw = panel.df.pivot(index="iso2", columns="t", values="git_pushes")
    dev = panel.df.pivot(index="iso2", columns="t", values="developers")
    D = panel.donors
    ppd = raw / dev
    out["what_jumped"] = {
        "median_donor_pushes": float((raw[t] / raw[t - 1] - 1)[D].median()),
        "median_donor_developers": float((dev[t] / dev[t - 1] - 1)[D].median()),
        "median_donor_pushes_per_developer": float((ppd[t] / ppd[t - 1] - 1)[D].median()),
        "share_donors_over_20pct": float(((raw[t] / raw[t - 1] - 1)[D] > 0.2).mean()),
        # the same first quarter growth in earlier years, for scale
        "earlier_q1_median_pushes": {f"{2020 + q // 4}Q1": float((raw[q] / raw[q - 1] - 1)[D].median())
                                     for q in (4, 8, 12, 16, 20)}}
    g = raw[t] / raw[t - 1] - 1
    out["growth_25q4_to_26q1"] = {"median_donor": float(g[panel.donors].median()),
                                  "iran": float(g["IR"]),
                                  **{c: float(g[c]) for c in SANCTIONED}}
    # bound 1: Iran stays flat from 2025Q4 instead of jumping
    out["flat_counterfactual_pct"] = float(raw.loc["IR", t] / raw.loc["IR", t - 1] - 1)
    # bound 2: Iran grows like the sanctioned economies did that quarter
    sg = float(np.mean([g[c] for c in SANCTIONED]))
    out["sanctioned_growth_mean"] = sg
    out["sanctioned_growth_counterfactual_pct"] = float(raw.loc["IR", t] / (raw.loc["IR", t - 1] * (1 + sg)) - 1)
    # bound 3: a twin built only from the sanctioned economies
    ev = panel.events[panel.events.event == "IR-2026"].iloc[0]
    pre, head, _ = event_windows(panel, ev)
    from shutdowns.synth import fit
    f = fit("sc", panel.series("IR"), panel.Y.loc[SANCTIONED].to_numpy(), pre, head)
    out["sanctioned_twin_pct"] = float(np.expm1(f.effect))
    out["sanctioned_twin_pre_rmse"] = f.pre_rmse
    return out


def main():
    panel = Panel()
    events = []
    for _, ev in panel.events.iterrows():
        r = for_event(panel, ev)
        pre, head, _ = event_windows(panel, ev)
        r["event"], r["country"], r["kind"] = ev.event, ev.country, ev.kind
        r["pools"] = pools(panel, ev, pre, head, r["sdid"])
        r["donor_names"] = [c for c in panel.donors if c != ev.iso2]
        events.append(r)
        print(ev.event, f"sdid {r['sdid']['pct']:+.1%} sc {r['sc']['pct']:+.1%} ascm {r['ascm']['pct']:+.1%}"
              f"  conformal p {r['conformal']['p']:.3f}  breakdown {r['sensitivity']['breakdown_m']:.2f}")
    adj = holm([e["sdid"]["p_normal"] for e in events])
    # the same correction on the exact permutation p values, which don't lean on a normal tail
    adj_perm = holm([e["sdid"]["p_perm"] for e in events])
    for e, a, ap in zip(events, adj, adj_perm):
        e["p_holm"] = float(a)
        e["p_holm_perm"] = float(ap)
        e["placebo_extremes"] = placebo_extremes(e, e["donor_names"])
        f2 = e["backdate"]["inside_band"] if e["backdate"] else None
        f3 = all(v["same_sign"] and v["move_se"] <= 1 for v in e["pools"].values()) and \
            e["leave_one_out"]["sign_flips"] == 0 and e["leave_one_out"]["max_move_se"] <= 1
        agree = all(e[m]["p_normal"] < 0.05 and np.sign(e[m]["log"]) == np.sign(e["sdid"]["log"])
                    for m in ("sc", "ascm"))
        e["checks"] = {"C1_holm": bool(a < 0.05), "F2_backdate": f2, "F3_donors": bool(f3),
                       "estimators_agree": bool(agree),
                       "breakdown_above_1": bool(e["sensitivity"]["breakdown_m"] > 1)}
        rest = bool(e["checks"]["C1_holm"] and f3 and agree and e["checks"]["breakdown_above_1"] and e["sdid"]["log"] < 0)
        # the plan asks for a backdating pass, so an event that can't be backdated isn't "clear",
        # it only passes every check that can be run on it
        e["clear_drop"] = bool(rest and f2 is True)
        e["passes_all_runnable"] = bool(rest and f2 is not False)
        e["checks"]["F2_note"] = "not testable, too few pre quarters" if f2 is None else ""
    nc = negative_controls(panel)
    print("negative controls", nc["rejections"], "of", nc["n"], "allowed", nc["allowed"])
    vpn = [vpn_check(panel, panel.events[panel.events.event == k].iloc[0]) for k in VPN_EVENTS]
    for v in vpn:
        print(v["event"], f"missing {v['missing_pushes']:,.0f}  exit excess {v['exit_excess']:,.0f} "
              f"(se {v['exit_se']:,.0f})  mde/missing {v['mde_share_of_missing']:.2f}")
    iran = next(e for e in events if e["event"] == "IR-2026")
    jump = jump_2026(panel, iran)
    print("2026 jump", json.dumps(jump, indent=1))
    for e in events:
        e.pop("donor_names", None)
    falls = stock_falls(panel)
    out = {"events": events, "negative_controls": nc, "vpn": vpn, "jump_2026": jump, "stock_falls": falls,
           "exit_economies": EXITS, "sanctioned": SANCTIONED,
           "sanctions_source": "https://ofac.treasury.gov/sanctions-programs-and-country-information"}
    (ROOT / "results" / "identification.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
