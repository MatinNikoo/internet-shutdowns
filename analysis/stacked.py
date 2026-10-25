"""Pool the events: a stacked event study and the pooled effect (C2 in the plan).

Event study. Every event gets a twin fit with its last two pre quarters held out, so
quarters -2 and -1 are real out of sample checks (in a normal synthetic control they are
fitted and sit near zero by construction). Quarter 0 is the first shutdown quarter.
The stacked line is the plain average across events at each quarter. Its uncertainty
comes from doing the exact same thing to donor countries: pick one donor per event at
random, run the same design on it, average, and repeat.

Pooled effect. Precision weighted average of the headline effect over the six full
shutdowns, with each event's error redrawn from its own placebo distribution.

Writes results/stacked.json.   python analysis/stacked.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel, event_windows  # noqa: E402
from shutdowns.synth import fit  # noqa: E402
from shutdowns import power  # noqa: E402

K = list(range(-2, 5))
HOLD = 2
B = 4000


def rel_gaps(y1, Y0, pre, head, path, hold):
    early = pre[:-hold] if hold else pre
    f = fit("sdid", y1, Y0, early, head)
    t0 = head[0]
    out = {}
    for k in K:
        t = t0 + k
        ok = (k < 0 and hold and t in pre[-hold:]) or (k >= 0 and (t in head or t in path))
        out[k] = float(f.gaps[t]) if ok else np.nan
    return out


def main():
    panel = Panel()
    I = {e["event"]: e for e in json.loads((ROOT / "results" / "identification.json").read_text())["events"]}
    obs, null = [], []
    names = []
    for _, ev in panel.events.iterrows():
        pre, head, path = event_windows(panel, ev)
        path = path[:4]
        hold = HOLD if len(pre) - HOLD >= 5 else 0
        ds, Y0 = panel.donor_matrix()
        g = rel_gaps(panel.series(ev.iso2), Y0, pre, head, path, hold)
        obs.append([g[k] for k in K])
        pl = []
        for j in range(len(ds)):
            others = np.delete(Y0, j, axis=0)
            gj = rel_gaps(Y0[j], others, pre, head, path, hold)
            pl.append([gj[k] for k in K])
        null.append(np.array(pl))
        names.append(ev.event)
        print(ev.event, "held out" if hold else "no hold out", np.round(obs[-1], 3))
    obs = np.array(obs)
    rng = np.random.default_rng(11)
    draws = np.empty((B, len(K)))
    for b in range(B):
        draws[b] = np.nanmean(np.array([n[rng.integers(len(n))] for n in null]), axis=0)
    mean = np.nanmean(obs, axis=0)
    sd = np.nanstd(draws, axis=0)
    study = []
    for i, k in enumerate(K):
        p = float(np.mean(np.abs(draws[:, i]) >= abs(mean[i])))
        study.append({"k": k, "mean_log": float(mean[i]), "mean_pct": float(np.expm1(mean[i])),
                      "se": float(sd[i]), "p": p, "n_events": int(np.sum(~np.isnan(obs[:, i])))})
        print(k, f"{np.expm1(mean[i]):+.1%}  se {sd[i]:.3f}  p {p:.3f}  n {study[-1]['n_events']}")

    # C2: pooled effect over the full shutdowns
    full = [n for n in names if I[n]["kind"] == "full"]
    y = np.array([I[n]["sdid"]["log"] for n in full])
    se = np.array([I[n]["sdid"]["se"] for n in full])
    pools = [power.error_pool(I[n]["placebos"]["space"], I[n]["sdid"]["se"]) for n in full]
    w = 1 / se ** 2
    est = float(np.sum(w * y) / w.sum())
    E = power.draw(pools, rng, B)
    nd = (E @ w) / w.sum()
    c2 = {"events": full, "pooled_log": est, "pooled_pct": float(np.expm1(est)),
          "se": float(nd.std()), "p": float(np.mean(np.abs(nd) >= abs(est))),
          "lo_pct": float(np.expm1(est - 1.96 * nd.std())), "hi_pct": float(np.expm1(est + 1.96 * nd.std())),
          "weight_share": dict(zip(full, (w / w.sum()).tolist()))}
    eq = float(y.mean())
    nde = E.mean(axis=1)
    c2["equal_weight"] = {"pooled_pct": float(np.expm1(eq)), "se": float(nde.std()),
                          "p": float(np.mean(np.abs(nde) >= abs(eq)))}
    keep = [i for i, n in enumerate(full) if n != "IR-2026"]
    wk = w[keep]
    est2 = float(np.sum(wk * y[keep]) / wk.sum())
    nd2 = (E[:, keep] @ wk) / wk.sum()
    c2["without_IR-2026"] = {"pooled_pct": float(np.expm1(est2)), "se": float(nd2.std()),
                             "p": float(np.mean(np.abs(nd2) >= abs(est2)))}
    # exploratory: only the short ones, two weeks or less offline. Sudan 2021 (about 24 days)
    # and Iran 2026 are out, so this is what quarterly data says about short shutdowns
    days = dict(zip(panel.events.event, panel.events.days_high))
    short = [i for i, n in enumerate(full) if days[n] <= 14]
    ws = w[short]
    est3 = float(np.sum(ws * y[short]) / ws.sum())
    nd3 = (E[:, short] @ ws) / ws.sum()
    c2["short_only"] = {"events": [full[i] for i in short], "max_days": 14,
                        "pooled_pct": float(np.expm1(est3)), "se": float(nd3.std()),
                        "p": float(np.mean(np.abs(nd3) >= abs(est3))),
                        "lo_pct": float(np.expm1(est3 - 1.96 * nd3.std())),
                        "hi_pct": float(np.expm1(est3 + 1.96 * nd3.std()))}
    print("C2", json.dumps(c2, indent=1))
    out = {"k": K, "events": names, "gaps": [[None if np.isnan(v) else float(v) for v in r] for r in obs],
           "study": study, "C2": c2, "draws": B}
    (ROOT / "results" / "stacked.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
