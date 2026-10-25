"""How sure can we be? Placebo tests in space and in time.

Space: pretend each donor country had the shutdown instead and see how big a
"effect" shows up by chance. Time: pretend the treated country had it in an
earlier quarter, which measures how noisy that particular country is.

Small countries are noisier than the big donors, so the space placebos alone can
be too optimistic for them. The standard error used is the larger of the two.
"""
from dataclasses import dataclass
import numpy as np
from .synth import fit, simplex_weights


@dataclass
class Result:
    method: str
    effect: float            # log scale, average over headline quarters
    se: float
    se_space: float
    se_time: float
    p_value: float           # permutation p value from the space placebos
    n_placebos: int
    fit: object
    path_se: np.ndarray      # placebo standard error at each quarter (space)
    space: np.ndarray = None   # every in-space placebo effect
    time: np.ndarray = None    # every in-time placebo effect

    @property
    def pct(self):
        return float(np.expm1(self.effect))

    @property
    def ci_pct(self):
        return (float(np.expm1(self.effect - 1.96 * self.se)),
                float(np.expm1(self.effect + 1.96 * self.se)))


def space_placebos(method, Y0, pre, post):
    """Run the same design on every donor in turn, using the other donors as its pool."""
    effects, gaps = [], []
    n = Y0.shape[0]
    for j in range(n):
        others = np.delete(Y0, j, axis=0)
        f = fit(method, Y0[j], others, pre, post)
        effects.append(f.effect)
        gaps.append(f.gaps)
    return np.array(effects), np.array(gaps)


def time_placebos(method, y1, Y0, pre, n_post, min_pre=5):
    """Fake events at earlier quarters of the treated country, fit only on what came before."""
    out = []
    for k in range(min_pre, len(pre) - n_post + 1):
        p_pre, p_post = pre[:k], pre[k:k + n_post]
        out.append(fit(method, y1, Y0, p_pre, p_post).effect)
    return np.array(out)


def conformal(y1, Y0, pre, post, grid=None, alpha=0.05):
    """Conformal inference for synthetic control (Chernozhukov, Wuthrich and Zhu 2021).

    For a candidate effect theta, take theta out of the post quarters, fit the twin on
    pre and post together (that's the null being imposed), and ask whether the post
    residuals look unusually big next to every cyclic shift of the residuals in time.
    The p value is exact if the residuals are stationary, and the interval is every
    theta that isn't rejected. With n quarters in the fit the smallest possible p is 1/n."""
    y1 = np.asarray(y1, float)
    Y0 = np.asarray(Y0, float)
    used = sorted(set(pre) | set(post))
    pos = [used.index(t) for t in post]
    n = len(used)
    # with ~100 donors and ~20 quarters a plain synthetic control can fit the post
    # quarters too once the null is imposed, which makes every residual tiny. the same
    # ridge penalty synthetic DiD uses keeps it honest.
    sigma = np.std(np.diff(Y0[:, pre], axis=1), ddof=1)
    eta = n * ((len(post)) ** 0.25 * sigma) ** 2

    def pval(theta):
        y = y1.copy()
        y[list(post)] -= theta
        w = simplex_weights(Y0[:, used].T, y[used], eta=eta, intercept=True)
        u = y[used] - w @ Y0[:, used]
        u = u - u.mean()
        s = np.array([np.mean(np.abs(np.roll(u, j)[pos])) for j in range(n)])
        return float(np.mean(s >= s[0] - 1e-12))

    grid = np.linspace(-2.5, 1.0, 351) if grid is None else np.asarray(grid)
    ps = np.array([pval(th) for th in grid])
    keep = grid[ps > alpha]
    lo, hi = (float(keep.min()), float(keep.max())) if len(keep) else (np.nan, np.nan)
    return {"p": pval(0.0), "lo": lo, "hi": hi, "min_p": 1 / n, "n_periods": n,
            "lo_pct": float(np.expm1(lo)), "hi_pct": float(np.expm1(hi)),
            # interval hits the edge of the grid, so it's really open on that side
            "open_low": bool(len(keep) and keep.min() <= grid.min()),
            "open_high": bool(len(keep) and keep.max() >= grid.max())}


def estimate(method, y1, Y0, pre, post, path=(), min_pre=5):
    quarters = list(post) + list(path)
    f = fit(method, y1, Y0, pre, post)
    pe, pg = space_placebos(method, Y0, pre, post)
    se_space = float(np.sqrt(np.mean(pe ** 2)))
    te = time_placebos(method, y1, Y0, pre, len(post), min_pre)
    se_time = float(np.sqrt(np.mean(te ** 2))) if len(te) >= 3 else 0.0
    se = max(se_space, se_time)
    p = (1 + np.sum(np.abs(pe) >= abs(f.effect))) / (1 + len(pe))
    path_se = np.full(len(y1), np.nan)
    path_se[quarters] = np.sqrt(np.mean(pg[:, quarters] ** 2, axis=0))
    # the treated country's own noise also applies along the path
    path_se[quarters] = np.maximum(path_se[quarters], se_time)
    return Result(method, f.effect, se, se_space, se_time, float(p), len(pe), f, path_se, pe, te)
