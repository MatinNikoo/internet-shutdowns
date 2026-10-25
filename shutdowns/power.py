"""Can quarterly data tell events apart? Power and minimum detectable differences.

The trick that makes this cheap: in synthetic control and synthetic DiD the weights only
use the pre period, so planting an effect of size d in the post quarter moves the
estimate by exactly d (tests check this). So the estimate for event i is truth_i + e_i,
where e_i is a draw from that event's own placebo distribution. Simulating a contrast
between groups of events only needs those error draws, no refitting.
"""
import numpy as np


def error_pool(space, se):
    """The event's in-space placebo effects, scaled up if the country's own history
    (in-time placebos) says it's noisier than the donors."""
    space = np.asarray(space, float)
    rms = np.sqrt(np.mean(space ** 2))
    return space * (se / rms) if rms > 0 else space


def wmean(y, se):
    w = 1 / np.asarray(se) ** 2
    return float(np.sum(w * y) / np.sum(w)), float(np.sqrt(1 / np.sum(w)))


def wls_origin(x, y, se):
    """y = beta x, weighted by 1/se^2. Returns beta and its standard error."""
    x, y, w = np.asarray(x, float), np.asarray(y, float), 1 / np.asarray(se, float) ** 2
    beta = np.sum(w * x * y) / np.sum(w * x ** 2)
    return float(beta), float(np.sqrt(1 / np.sum(w * x ** 2)))


def wls(x, y, se):
    """y = a + b x, weighted. Returns (a, b, se_a, se_b)."""
    x, y, w = np.asarray(x, float), np.asarray(y, float), 1 / np.asarray(se, float) ** 2
    X = np.column_stack([np.ones_like(x), x])
    V = np.linalg.inv(X.T @ (w[:, None] * X))
    a, b = V @ X.T @ (w * y)
    return float(a), float(b), float(np.sqrt(V[0, 0])), float(np.sqrt(V[1, 1]))


def draw(pools, rng, n):
    return np.column_stack([rng.choice(p, size=n, replace=True) for p in pools])


def contrast_power(group, se, pools, deltas, sims=4000, seed=0):
    """Power to detect a difference delta (log scale) between group 1 and group 0,
    using the precision weighted means and a z test at 5%."""
    rng = np.random.default_rng(seed)
    group = np.asarray(group, bool)
    se = np.asarray(se, float)
    w = 1 / se ** 2
    se_d = np.sqrt(1 / w[group].sum() + 1 / w[~group].sum())
    E = draw(pools, rng, sims)
    base = (E[:, group] @ w[group]) / w[group].sum() - (E[:, ~group] @ w[~group]) / w[~group].sum()
    out = []
    for d in deltas:
        z = (d + base) / se_d
        out.append({"delta": float(d), "power": float(np.mean(np.abs(z) > 1.96))})
    return {"se_diff": float(se_d), "curve": out, "mdd": mdd(out)}


def slope_power(x, se, pools, slopes, center=0.0, sims=4000, seed=0, origin=False):
    """Power to detect a slope (log effect per unit of x) different from `center`."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    se = np.asarray(se, float)
    E = draw(pools, rng, sims)
    out = []
    for b in slopes:
        Y = b * x + E if origin else b * (x - x.mean()) + E
        z = []
        for y in Y:
            if origin:
                bh, sb = wls_origin(x, y, se)
            else:
                _, bh, _, sb = wls(x, y, se)
            z.append((bh - center) / sb)
        out.append({"slope": float(b), "power": float(np.mean(np.abs(np.array(z)) > 1.96))})
    return {"curve": out, "mdd": mdd(out, key="slope", ref=center)}


def mdd(curve, key="delta", ref=0.0, target=0.8):
    """Smallest distance from ref (on the positive side) where power reaches target."""
    pts = sorted((c[key] - ref, c["power"]) for c in curve if c[key] - ref > 0)
    for k, (d, p) in enumerate(pts):
        if p >= target:
            if k == 0:
                return float(d)
            d0, p0 = pts[k - 1]
            return float(d0 + (target - p0) * (d - d0) / (p - p0))
    return None


def jackknife(x, y, se, names):
    out = []
    for i in range(len(x)):
        keep = np.arange(len(x)) != i
        b, s = wls_origin(np.asarray(x)[keep], np.asarray(y)[keep], np.asarray(se)[keep])
        out.append({"dropped": names[i], "beta": b, "se": s})
    return out


def influence_share(x, se):
    w = 1 / np.asarray(se, float) ** 2
    x = np.asarray(x, float)
    return (w * x ** 2) / np.sum(w * x ** 2)
