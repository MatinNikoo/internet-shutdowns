"""Can quarterly data tell shutdowns apart? Check power first, then interpret.

For three questions (full vs partial, longer vs shorter, big vs small developer bases)
this simulates the minimum detectable difference using each event's own placebo errors.
Only if that's smaller than a plausible difference does it report the estimate as an
answer. Then it takes the old dose response result (beta 1.31) apart: who drives it,
how much the day counts matter, and what happens if Iran's twin is too optimistic.

Writes results/heterogeneity.json.   python analysis/heterogeneity.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel  # noqa: E402
from shutdowns import power  # noqa: E402

# a plausible difference to compare the detectable one against: the drop a full month
# offline would give if a day offline cost exactly a day (about 30 of 91 days)
PLAUSIBLE = float(-np.log1p(-30 / 91))
SIMS = 4000


def main():
    panel = Panel()
    E = json.loads((ROOT / "results" / "events.json").read_text())
    I = {e["event"]: e for e in json.loads((ROOT / "results" / "identification.json").read_text())["events"]}
    J = json.loads((ROOT / "results" / "identification.json").read_text())["jump_2026"]
    ev = E["events"]
    names = [e["event"] for e in ev]
    y = np.array([I[n]["sdid"]["log"] for n in names])
    se = np.array([I[n]["sdid"]["se"] for n in names])
    pools = [power.error_pool(I[n]["placebos"]["space"], I[n]["sdid"]["se"]) for n in names]
    full = np.array([e["kind"] == "full" for e in ev])
    raw = panel.df.pivot(index="iso2", columns="t", values="git_pushes")
    size = np.array([np.log10(raw.loc[e["iso2"], [panel.labels.index(q) for q in I[e["event"]]["pre_quarters"]]].mean())
                     for e in ev])
    out = {"plausible_difference_log": PLAUSIBLE, "sims": SIMS}

    # full vs partial
    deltas = np.round(np.arange(0.0, 1.61, 0.05), 2)
    a = power.contrast_power(full, se, pools, deltas, sims=SIMS, seed=1)
    m_f, s_f = power.wmean(y[full], se[full])
    m_p, s_p = power.wmean(y[~full], se[~full])
    a["estimate"] = {"full_mean_log": m_f, "partial_mean_log": m_p, "diff_log": m_f - m_p,
                     "se": float(np.sqrt(s_f ** 2 + s_p ** 2))}
    a["answerable"] = bool(a["mdd"] is not None and a["mdd"] < PLAUSIBLE)
    out["full_vs_partial"] = a

    # duration, full shutdowns only: slope of the log effect on log(1 - share offline)
    fi = np.where(full)[0]
    x = np.array([np.log1p(-ev[i]["share_mid"]) for i in fi])
    fp = [pools[i] for i in fi]
    slopes = np.round(np.arange(0.0, 3.01, 0.1), 2)
    d0 = power.slope_power(x, se[fi], fp, slopes, center=0.0, sims=SIMS, seed=2, origin=True)
    d1 = power.slope_power(x, se[fi], fp, np.round(np.arange(1.0, 3.01, 0.05), 2), center=1.0,
                           sims=SIMS, seed=3, origin=True)
    out["duration"] = {"mdd_slope_vs_0": d0["mdd"], "mdd_slope_vs_1": d1["mdd"],
                       "curve_vs_0": d0["curve"], "curve_vs_1": d1["curve"],
                       # a slope of 1.31 vs 1 is a gap of 0.31: can the data see that?
                       "power_at_1_31": next(c["power"] for c in d1["curve"] if abs(c["slope"] - 1.3) < 1e-9)}
    # the same question without Iran 2026, the one event that carries the weight
    keep = [k for k, i in enumerate(fi) if names[i] != "IR-2026"]
    d1n = power.slope_power(x[keep], se[fi][keep], [fp[k] for k in keep], np.round(np.arange(1.0, 6.01, 0.25), 2),
                            center=1.0, sims=SIMS, seed=4, origin=True)
    out["duration"]["mdd_slope_vs_1_without_IR-2026"] = d1n["mdd"]

    # developer base: slope of the effect on log10 of pre period pushes, all nine events
    s3 = power.slope_power(size, se, pools, np.round(np.arange(0.0, 1.01, 0.05), 2), sims=SIMS, seed=5)
    a3, b3, _, sb3 = power.wls(size, y, se)
    out["baseline_size"] = {"mdd_per_10x": s3["mdd"], "curve": s3["curve"],
                            "estimate_per_10x": b3, "se": sb3,
                            # a slope per tenfold isn't on the same scale as a difference, so compare
                            # the detectable slope times the size range the events actually span
                            "size_range_decades": float(size.max() - size.min()),
                            "mdd_across_range": float(s3["mdd"] * (size.max() - size.min())) if s3["mdd"] else None,
                            "answerable": bool(s3["mdd"] is not None and s3["mdd"] * (size.max() - size.min()) < PLAUSIBLE),
                            "log10_pre_pushes": dict(zip(names, size.tolist()))}

    # the old dose response, taken apart
    yf, sf = y[fi], se[fi]
    nf = [names[i] for i in fi]
    b, sb = power.wls_origin(x, yf, sf)
    dr = {"beta": b, "se": sb, "lo": b - 1.96 * sb, "hi": b + 1.96 * sb,
          "influence_share": dict(zip(nf, power.influence_share(x, sf).tolist())),
          "jackknife": power.jackknife(x, yf, sf, nf)}
    # day counts are ranges: draw them uniformly and refit
    rng = np.random.default_rng(6)
    days_in = [ev[i]["days_low"] / ev[i]["share_low"] for i in fi]
    draws = []
    for _ in range(SIMS):
        dd = np.array([rng.uniform(ev[i]["days_low"], ev[i]["days_high"]) for i in fi])
        draws.append(power.wls_origin(np.log1p(-dd / np.array(days_in)), yf, sf)[0])
    dr["days_uncertainty"] = {"p2_5": float(np.quantile(draws, .025)), "p97_5": float(np.quantile(draws, .975))}
    # estimation error drawn from each event's own placebo distribution
    E_ = power.draw(fp, rng, SIMS)
    boot = [power.wls_origin(x, b * x + e, sf)[0] for e in E_]
    dr["placebo_bootstrap"] = {"p2_5": float(np.quantile(boot, .025)), "p97_5": float(np.quantile(boot, .975))}
    # with an intercept: does a zero-day shutdown predict zero effect?
    a0, b0, sa0, sb0 = power.wls(x, yf, sf)
    dr["with_intercept"] = {"a": a0, "b": b0, "se_a": sa0, "se_b": sb0}
    # if Iran's 2026 twin is too optimistic (no global jump for Iran)
    k = nf.index("IR-2026")
    alt = {}
    for lab, pct in (("flat", J["flat_counterfactual_pct"]),
                     ("sanctioned_growth", J["sanctioned_growth_counterfactual_pct"]),
                     ("sanctioned_twin", J["sanctioned_twin_pct"])):
        yy = yf.copy()
        yy[k] = np.log1p(pct)
        alt[lab] = {"iran_pct": pct, "beta": power.wls_origin(x, yy, sf)[0]}
    dr["iran_2026_alternatives"] = alt
    out["dose_response"] = dr
    print(json.dumps({k: v for k, v in out.items() if k != "dose_response"}, indent=1, default=float)[:1500])
    print(json.dumps(dr, indent=1)[:3000])
    (ROOT / "results" / "heterogeneity.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
