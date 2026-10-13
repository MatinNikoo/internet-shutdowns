"""Check the methods on fake shutdowns where the true answer is known.

Pick a country that never had a shutdown, pick a quarter, knock a known share off
its pushes in that quarter, then see what each method reports. Repeated many times
for each size, this gives the bias, how often the 95% interval covers the truth,
and how often a real drop gets flagged (power). Power by size turns into the
shortest shutdown quarterly data can reliably see.

Run from the repo root:  python analysis/simulations.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel  # noqa: E402
from shutdowns.inference import estimate  # noqa: E402

DROPS = [0.0, 0.05, 0.10, 0.20, 0.35, 0.50]
SIMS = 250
MIN_PRE = 8


def main(seed=7):
    rng = np.random.default_rng(seed)
    panel = Panel()
    ds, Y = panel.donor_matrix()
    size = panel.min_pushes[ds].to_numpy()
    T = Y.shape[1]
    results = {m: {str(d): [] for d in DROPS} for m in ("sdid", "sc")}
    for d in DROPS:
        for s in range(SIMS):
            j = int(rng.integers(len(ds)))
            t = int(rng.integers(MIN_PRE, T))
            y1 = Y[j].copy()
            y1[t] += np.log1p(-d)                      # the planted shutdown
            Y0 = np.delete(Y, j, axis=0)
            pre = list(range(t))
            for m in ("sdid", "sc"):
                r = estimate(m, y1, Y0, pre, [t])
                truth = np.log1p(-d)
                results[m][str(d)].append({
                    "est": r.effect, "se": r.se, "p": r.p_value,
                    "cover": abs(r.effect - truth) <= 1.96 * r.se,
                    "flag": abs(r.effect) / r.se > 1.96,
                    "big": bool(size[j] >= np.median(size)),
                })
        print("done", d)

    summary = {}
    for m, by in results.items():
        summary[m] = []
        for d, sims in by.items():
            truth = np.log1p(-float(d))
            est = np.array([x["est"] for x in sims])
            big = np.array([x["big"] for x in sims])
            flag = np.array([x["flag"] for x in sims])
            summary[m].append({
                "drop": float(d),
                "bias_pct_points": float(np.mean(np.expm1(est)) - (-float(d))) * 100,
                "rmse_log": float(np.sqrt(np.mean((est - truth) ** 2))),
                "coverage": float(np.mean([x["cover"] for x in sims])),
                "power": float(np.mean(flag)),
                "power_big": float(np.mean(flag[big])),
                "power_small": float(np.mean(flag[~big])),
                "perm_reject": float(np.mean([x["p"] <= 0.05 for x in sims])),
            })
    out = {"sims_per_size": SIMS, "drops": DROPS, "summary": summary,
           "median_donor_min_pushes": float(np.median(size))}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "simulations.json").write_text(json.dumps(out, indent=1))
    for m in summary:
        for row in summary[m]:
            print(m, {k: round(v, 3) for k, v in row.items()})


if __name__ == "__main__":
    main()
