import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))
from shutdowns.synth import simplex_weights, synth_control, sdid  # noqa: E402
from shutdowns.inference import estimate  # noqa: E402
from shutdowns.panel import Panel, event_windows, index, label  # noqa: E402
import run_events  # noqa: E402


def factor_panel(n=40, T=24, seed=0):
    """Countries driven by two shared trends plus noise, like the real data."""
    rng = np.random.default_rng(seed)
    f = rng.normal(size=(2, T)).cumsum(axis=1) * 0.05
    load = rng.uniform(0.5, 1.5, size=(n, 2))
    level = rng.normal(12, 1, size=(n, 1))
    return level + load @ f + rng.normal(0, 0.01, size=(n, T))


def test_weights_live_on_the_simplex():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(10, 30))
    w = simplex_weights(A, rng.normal(size=10), eta=0.1)
    assert w.min() >= 0 and abs(w.sum() - 1) < 1e-9


def test_weights_recover_an_exact_mix():
    rng = np.random.default_rng(2)
    A = rng.normal(size=(20, 8))
    true = np.array([0.6, 0.4, 0, 0, 0, 0, 0, 0])
    w = simplex_weights(A, A @ true, intercept=False)
    assert np.allclose(w, true, atol=1e-4)


@pytest.mark.parametrize("method", [synth_control, sdid])
@pytest.mark.parametrize("drop", [0.0, 0.3, 0.6])
def test_methods_recover_a_planted_drop(method, drop):
    Y = factor_panel()
    y1, Y0 = Y[0].copy(), Y[1:]
    y1[20:] += np.log1p(-drop)
    f = method(y1, Y0, list(range(20)), [20, 21])
    assert abs(np.expm1(f.effect) - (-drop)) < 0.03


def test_sdid_is_exact_when_trends_are_parallel():
    T = 12
    time = np.linspace(0, 1, T)
    Y0 = np.array([c + time for c in np.linspace(10, 14, 15)])
    y1 = 9 + time
    y1[-2:] -= 0.5
    f = sdid(y1, Y0, list(range(10)), [10, 11])
    assert abs(f.effect + 0.5) < 1e-6


def test_no_effect_gives_no_signal():
    Y = factor_panel(seed=3)
    r = estimate("sdid", Y[0], Y[1:], list(range(18)), [18])
    assert r.p_value > 0.05
    assert 1 / (Y.shape[0]) <= r.p_value <= 1


def test_quarter_labels_round_trip():
    for t in range(30):
        assert index(label(t)) == t
    assert label(0) == "2020Q1" and index("2026Q1") == 24


def test_quarter_lengths():
    assert run_events.quarter_days(index("2024Q1")) == 91   # leap year
    assert run_events.quarter_days(index("2023Q1")) == 90
    assert run_events.quarter_days(index("2023Q3")) == 92


def test_dose_response_slope_is_one_when_a_day_costs_a_day():
    rows = []
    for share in (0.05, 0.2, 0.5):
        rows.append({"event": str(share), "share_mid": share, "share_low": share, "share_high": share,
                     "sdid": {"pct": -share, "se": 0.1}})
    assert abs(run_events.dose_response(rows)["beta"] - 1) < 1e-9


@pytest.fixture(scope="module")
def panel():
    return Panel()


def test_panel_is_complete(panel):
    assert not panel.Y.isna().any().any()
    assert len(panel.donors) > 50
    assert not set(panel.donors) & set(panel.events.iso2)


def test_other_shutdowns_stay_out_of_the_pre_period(panel):
    ev = panel.events[panel.events.event == "IR-2026"].iloc[0]
    pre, head, path = event_windows(panel, ev)
    for q in ("2022Q3", "2022Q4", "2025Q2"):
        assert index(q) not in pre
    assert head == [index("2026Q1")]


def test_recovery_path_stops_before_the_next_event(panel):
    ev = panel.events[panel.events.event == "IR-2022"].iloc[0]
    _, _, path = event_windows(panel, ev)
    assert max(path) < index("2025Q2")
