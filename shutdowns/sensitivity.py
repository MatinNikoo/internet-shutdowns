"""How much would have to go wrong to erase a result?

backdate      refit with the last pre quarters held out, so they become real out of sample checks
breakdown     how big a break from the twin's path is needed to wipe out the effect
              (relative magnitudes, in the spirit of Rambachan and Roth 2023)
leave_one_out drop each donor that matters and refit
"""
import numpy as np
from .synth import fit


def backdate(method, y1, Y0, pre, post, hold=2):
    """Fit on pre[:-hold] only. Returns the held out gaps and the effect under that fit."""
    if len(pre) - hold < 4:
        return None
    early, held = pre[:-hold], pre[-hold:]
    f = fit(method, y1, Y0, early, post)
    return {"held_out": [float(f.gaps[t]) for t in held], "effect": float(f.effect),
            "held_quarters": list(held)}


def worst_miss(res):
    """Benchmark size of a parallel trends violation for this country.

    First choice is the worst out of sample miss of the twin in the country's own past
    (the in-time placebos). Myanmar and Sudan have too little history for that, so they
    fall back to the worst in-sample pre period gap, which is smaller and so makes the
    breakdown value look better than it is. The source is returned so it can be flagged."""
    if res.time is not None and len(res.time) >= 3:
        return float(np.max(np.abs(res.time))), "country's own past (fake events in earlier quarters)"
    f = res.fit
    g = f.gaps[f.pre] - f.lam @ f.gaps[f.pre]
    return float(np.max(np.abs(g))), "pre period fit (a weaker benchmark, there is too little history for fake events)"


def breakdown(effect, se, miss, z=1.96):
    """Relative magnitudes bound: allow the post period to drift off the twin by up to
    M times the benchmark miss. The robust interval is effect -/+ (M * miss + z * se).
    Breakdown M is the largest M that still keeps zero out of that interval."""
    room = abs(effect) - z * se
    m = room / miss if miss > 0 else np.inf
    return {"breakdown_m": float(max(m, 0.0)),
            "bias_to_erase_log": float(max(room, 0.0)),
            # the same thing as a ratio: how many times too high the twin would have to be
            "bias_to_erase_factor": float(np.exp(max(room, 0.0)))}


def robust_interval(effect, se, miss, m, z=1.96):
    return float(effect - m * miss - z * se), float(effect + m * miss + z * se)


def leave_one_out(method, y1, Y0, pre, post, omega, names, min_weight=0.01):
    out = []
    for j in np.where(omega > min_weight)[0]:
        keep = np.arange(Y0.shape[0]) != j
        f = fit(method, y1, Y0[keep], pre, post)
        out.append({"dropped": names[j], "weight": float(omega[j]), "effect": float(f.effect)})
    return out
