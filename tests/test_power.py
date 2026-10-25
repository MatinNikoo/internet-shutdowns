import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns import power  # noqa: E402
sys.path.insert(0, str(ROOT / "analysis"))
from identification import holm  # noqa: E402


def normal_pools(se, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    return [rng.normal(0, s, n) for s in se]


def test_contrast_power_is_about_five_percent_at_zero_and_grows():
    se = np.array([0.1, 0.12, 0.15, 0.1, 0.2, 0.1])
    g = np.array([1, 1, 1, 0, 0, 0], bool)
    r = power.contrast_power(g, se, normal_pools(se), [0.0, 0.2, 0.4, 0.8], sims=3000)
    p = [c["power"] for c in r["curve"]]
    assert 0.03 < p[0] < 0.08
    assert p == sorted(p) and p[-1] > 0.95
    # the normal theory answer: 2.8 standard errors
    assert abs(r["mdd"] - 2.8 * r["se_diff"]) < 0.05


def test_wls_origin_recovers_a_slope_and_jackknife_drops_each_row():
    x = np.log1p(-np.array([0.05, 0.1, 0.3, 0.6]))
    se = np.array([0.1, 0.1, 0.1, 0.1])
    b, s = power.wls_origin(x, 1.5 * x, se)
    assert abs(b - 1.5) < 1e-12 and s > 0
    jk = power.jackknife(x, 1.5 * x, se, list("abcd"))
    assert [j["dropped"] for j in jk] == list("abcd")
    assert all(abs(j["beta"] - 1.5) < 1e-12 for j in jk)
    assert abs(power.influence_share(x, se).sum() - 1) < 1e-12


def test_error_pool_rescales_to_the_event_se():
    p = power.error_pool(np.array([-0.1, 0.1, 0.05, -0.05]), 0.3)
    assert abs(np.sqrt(np.mean(p ** 2)) - 0.3) < 1e-12


def test_mdd_interpolates():
    curve = [{"delta": 0.0, "power": 0.05}, {"delta": 0.2, "power": 0.6}, {"delta": 0.4, "power": 1.0}]
    assert abs(power.mdd(curve) - 0.3) < 1e-12
    assert power.mdd([{"delta": 0.1, "power": 0.2}]) is None


def test_holm():
    adj = holm([0.01, 0.04, 0.03, 0.5])
    assert np.allclose(adj, [0.04, 0.09, 0.09, 0.5])
