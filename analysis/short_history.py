"""Are the intervals still honest with very little history?

The main simulations (simulations.py) use at least 8 pre quarters. Myanmar has 4 and
Sudan 7, and both are small. This runs the same design with no effect planted, in
Myanmar's setting (4 pre quarters, 2 headline quarters) and Sudan's (7 and 1), on random
donors and random start quarters, and counts how often the interval misses zero. Since a
planted effect moves the estimate by exactly its size, the miss rate under no effect is
also how often the interval would miss the truth for any effect.

Writes results/short_history.json.   python analysis/short_history.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel  # noqa: E402
from shutdowns.inference import estimate  # noqa: E402

SETTINGS = {"myanmar_like": (4, 2), "sudan_like": (7, 1)}
SIMS = 200


def main(seed=21):
    rng = np.random.default_rng(seed)
    panel = Panel()
    ds, Y = panel.donor_matrix()
    size = panel.min_pushes[ds].to_numpy()
    small = size < np.median(size)
    out = {"sims": SIMS, "settings": {}}
    for name, (npre, npost) in SETTINGS.items():
        rows = []
        for _ in range(SIMS):
            j = int(rng.integers(len(ds)))
            t = int(rng.integers(npre, panel.T - npost + 1))
            pre, post = list(range(t - npre, t)), list(range(t, t + npost))
            r = estimate("sdid", Y[j], np.delete(Y, j, axis=0), pre, post)
            rows.append((abs(r.effect) / r.se > 1.96, r.p_value <= 0.05, bool(small[j]), r.se_time == 0))
        a = np.array(rows, bool)
        out["settings"][name] = {
            "pre_quarters": npre, "post_quarters": npost,
            "false_alarm_normal": float(a[:, 0].mean()), "false_alarm_permutation": float(a[:, 1].mean()),
            "false_alarm_normal_small_donors": float(a[a[:, 2], 0].mean()),
            "share_without_time_placebos": float(a[:, 3].mean())}
        print(name, out["settings"][name])
    (ROOT / "results" / "short_history.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
