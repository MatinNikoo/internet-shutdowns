"""The full design for one event, in one call. Used by the analysis scripts, the CLI
and the report cards, so every event goes through exactly the same steps.

    synthetic DiD, synthetic control, augmented synthetic control
    placebos in space and time, conformal p value and interval
    backdating, breakdown value, leave one donor out
"""
import numpy as np

from .inference import estimate, conformal
from .panel import Panel, label, index
from .sensitivity import backdate, worst_miss, breakdown, leave_one_out

METHODS = ("sdid", "sc", "ascm")


def windows(panel, iso2, head, skip=(), horizon=8):
    """Pre quarters, headline quarters and recovery path for any economy.

    Quarters in `skip` (other shutdowns in the same country) are left out of the pre
    period, and the path stops at the next one."""
    head = sorted(head)
    pre = [t for t in range(head[0]) if t not in set(skip)]
    later = [t for t in skip if t > head[-1]]
    stop = min(later) if later else panel.T
    path = list(range(head[-1] + 1, min(stop, head[-1] + 1 + horizon, panel.T)))
    return pre, head, path


def registry_skip(panel, iso2, head):
    """Quarters of every registered event in this economy, other than the one asked for."""
    from .panel import EXTRA_AFFECTED, HEADLINE
    out = set()
    for _, r in panel.events[panel.events.iso2 == iso2].iterrows():
        qs = set(HEADLINE.get(r.event, [r.t])) | set(EXTRA_AFFECTED.get(r.event, []))
        if not qs & set(head):
            out |= qs
        else:
            # same event: quarters it touched outside the asked window still aren't clean
            out |= qs - set(head)
    return out


def summary(r):
    lo, hi = r.ci_pct
    return {"pct": r.pct, "lo": lo, "hi": hi, "log": r.effect, "se": r.se, "se_space": r.se_space,
            "se_time": r.se_time, "p_perm": r.p_value,
            "p_normal": float(2 * (1 - _phi(abs(r.effect) / r.se))) if r.se > 0 else float("nan"),
            "pre_rmse": r.fit.pre_rmse}


def _phi(x):
    from math import erf, sqrt
    return 0.5 * (1 + erf(x / sqrt(2)))


def run(panel, iso2, head, pre=None, path=None, donors=None, methods=METHODS, extras=True):
    """Everything for one economy and one set of headline quarters. Returns plain dicts."""
    if pre is None or path is None:
        p0, _, pa = windows(panel, iso2, head, registry_skip(panel, iso2, head))
        pre = p0 if pre is None else pre
        path = pa if path is None else path
    donors = [c for c in (panel.donors if donors is None else donors) if c != iso2 and c in panel.Y.index]
    Y0 = panel.Y.loc[donors].to_numpy()
    y1 = panel.series(iso2)
    out = {"iso2": iso2, "outcome": panel.outcome, "quarters": [label(t) for t in head],
           "pre_quarters": [label(t) for t in pre], "path_quarters": [label(t) for t in path],
           "n_donors": len(donors)}
    res = {}
    for m in methods:
        res[m] = estimate(m, y1, Y0, pre, head, path)
        out[m] = summary(res[m])
    main = res[methods[0]]
    f = main.fit
    out["series"] = {"labels": panel.labels, "actual": [float(v) for v in y1],
                     "twin": [float(v) for v in f.twin], "gap": [float(v) for v in f.gaps],
                     "band": [float(v) if np.isfinite(v) else None for v in 1.96 * main.path_se]}
    order = np.argsort(-f.omega)[:8]
    out["weights"] = [{"iso2": donors[i], "w": float(f.omega[i])} for i in order if f.omega[i] > 0.005]
    out["placebos"] = {"space": [float(v) for v in main.space], "time": [float(v) for v in main.time]}
    if not extras:
        return out
    out["conformal"] = conformal(y1, Y0, pre, head)
    bd = backdate(methods[0], y1, Y0, pre, head)
    if bd is not None:
        bd["inside_band"] = bool(all(abs(g) <= 1.96 * main.se for g in bd["held_out"]))
        bd["held_quarters"] = [label(t) for t in bd["held_quarters"]]
    out["backdate"] = bd
    miss, src = worst_miss(main)
    out["sensitivity"] = {"worst_miss_log": miss, "benchmark": src,
                          **breakdown(main.effect, main.se, miss)}
    loo = leave_one_out(methods[0], y1, Y0, pre, head, f.omega, donors)
    eff = [x["effect"] for x in loo]
    out["leave_one_out"] = {"n": len(loo), "min_pct": float(np.expm1(min(eff))) if eff else None,
                            "max_pct": float(np.expm1(max(eff))) if eff else None,
                            "max_move_se": float(max(abs(e - main.effect) for e in eff) / main.se) if eff else 0.0,
                            "sign_flips": int(sum(np.sign(e) != np.sign(main.effect) for e in eff)),
                            "drops": loo}
    return out


def quarters_from(start, end=None):
    a = index(start)
    b = index(end) if end else a
    return list(range(a, b + 1))


def for_event(panel, ev_row, **kw):
    from .panel import event_windows
    pre, head, path = event_windows(panel, ev_row)
    return run(panel, ev_row.iso2, head, pre=pre, path=path, **kw)


__all__ = ["run", "for_event", "windows", "quarters_from", "Panel"]
