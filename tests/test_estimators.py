"""Estimators on simulated panels where the truth is known."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.synth import fit, ascm, synth_control  # noqa: E402
from shutdowns.inference import estimate, conformal  # noqa: E402
from shutdowns.sensitivity import breakdown, robust_interval, backdate, leave_one_out  # noqa: E402


def factor_panel(n=40, T=24, seed=0, noise=0.01):
    rng = np.random.default_rng(seed)
    f = rng.normal(size=(2, T)).cumsum(axis=1) * 0.05
    load = rng.uniform(0.5, 1.5, size=(n, 2))
    level = rng.normal(12, 1, size=(n, 1))
    return level + load @ f + rng.normal(0, noise, size=(n, T))


@pytest.mark.parametrize("method", ["sc", "sdid", "ascm"])
@pytest.mark.parametrize("drop", [0.0, 0.25, 0.6])
def test_every_estimator_recovers_a_planted_drop(method, drop):
    Y = factor_panel(seed=4)
    y1, Y0 = Y[0].copy(), Y[1:]
    y1[20:] += np.log1p(-drop)
    f = fit(method, y1, Y0, list(range(20)), [20, 21])
    assert abs(np.expm1(f.effect) + drop) < 0.03


@pytest.mark.parametrize("method", ["sc", "sdid", "ascm"])
def test_a_planted_effect_moves_the_estimate_by_exactly_that_much(method):
    # the weights only look at the pre period, so this has to hold to machine precision.
    # the power simulations depend on it.
    Y = factor_panel(seed=5, noise=0.05)
    y1, Y0 = Y[0].copy(), Y[1:]
    pre, post = list(range(18)), [18]
    base = fit(method, y1, Y0, pre, post).effect
    for d in (-0.7, -0.2, 0.3):
        y = y1.copy()
        y[18] += d
        assert abs(fit(method, y, Y0, pre, post).effect - (base + d)) < 1e-9


def test_ascm_matches_sc_when_the_fit_is_perfect():
    Y0 = factor_panel(n=30, seed=6)
    w = np.zeros(30)
    w[[2, 5, 9]] = [0.5, 0.3, 0.2]
    y1 = w @ Y0
    y1[-1] -= 0.4
    pre, post = list(range(len(y1) - 1)), [len(y1) - 1]
    a, s = ascm(y1, Y0, pre, post), synth_control(y1, Y0, pre, post)
    assert abs(a.effect - s.effect) < 1e-3
    assert abs(a.effect + 0.4) < 1e-3


def test_ascm_fixes_a_bad_pre_fit_better_than_sc():
    # treated unit sits outside the donors' convex hull in shape, so SC can't match it
    rng = np.random.default_rng(7)
    T = 24
    trend = np.linspace(0, 1, T)
    Y0 = np.array([12 + a * trend + rng.normal(0, 0.01, T) for a in rng.uniform(0.2, 0.8, 40)])
    y1 = 11 + 1.3 * trend + rng.normal(0, 0.01, T)
    pre, post = list(range(20)), [20, 21, 22, 23]
    y1[post] -= 0.3
    sc, ac = synth_control(y1, Y0, pre, post), ascm(y1, Y0, pre, post)
    assert abs(ac.effect + 0.3) < abs(sc.effect + 0.3)


def test_placebo_test_has_the_right_size_under_the_null():
    # no effect anywhere: the share of normal-approximation rejections at 5% should be
    # near 5%, and certainly not double it
    rej = []
    for s in range(60):
        Y = factor_panel(n=25, T=16, seed=100 + s, noise=0.03)
        r = estimate("sdid", Y[0], Y[1:], list(range(14)), [14])
        rej.append(abs(r.effect) / r.se > 1.96)
    assert np.mean(rej) <= 0.12


def test_placebo_test_finds_a_big_drop():
    hits = 0
    for s in range(20):
        Y = factor_panel(n=25, T=16, seed=300 + s, noise=0.03)
        y1 = Y[0].copy()
        y1[14] += np.log(0.5)
        r = estimate("sdid", y1, Y[1:], list(range(14)), [14])
        hits += r.p_value <= 0.05 and abs(r.effect) / r.se > 1.96
    assert hits >= 18


def test_conformal_rejects_a_big_drop_and_covers_the_truth():
    Y = factor_panel(n=30, T=24, seed=8, noise=0.02)
    y1 = Y[0].copy()
    y1[23] += np.log(0.4)
    c = conformal(y1, Y[1:], list(range(23)), [23])
    assert c["p"] <= 1 / 24 + 1e-12            # can't go lower than one over the number of quarters
    assert c["lo"] <= np.log(0.4) <= c["hi"]


def test_conformal_p_is_never_below_its_floor_and_is_flat_under_the_null():
    ps = []
    for s in range(30):
        Y = factor_panel(n=20, T=20, seed=500 + s, noise=0.03)
        c = conformal(Y[0], Y[1:], list(range(19)), [19], grid=np.linspace(-1, 1, 21))
        assert c["p"] >= c["min_p"] - 1e-12
        ps.append(c["p"])
    assert np.mean(np.array(ps) <= 0.1) <= 0.25


def test_breakdown_math():
    b = breakdown(-0.8, 0.1, 0.2)
    assert abs(b["breakdown_m"] - (0.8 - 0.196) / 0.2) < 1e-12
    lo, hi = robust_interval(-0.8, 0.1, 0.2, b["breakdown_m"])
    assert abs(hi) < 1e-9                      # at the breakdown value the interval just touches zero
    assert breakdown(-0.1, 0.1, 0.2)["breakdown_m"] == 0.0


def test_backdate_and_leave_one_out_shapes():
    Y = factor_panel(seed=9)
    y1, Y0 = Y[0], Y[1:]
    b = backdate("sdid", y1, Y0, list(range(20)), [20])
    assert len(b["held_out"]) == 2 and max(abs(g) for g in b["held_out"]) < 0.1
    f = fit("sdid", y1, Y0, list(range(20)), [20])
    loo = leave_one_out("sdid", y1, Y0, list(range(20)), [20], f.omega, [str(i) for i in range(39)])
    assert len(loo) == int(np.sum(f.omega > 0.01))
    assert backdate("sdid", y1, Y0, list(range(5)), [5]) is None
