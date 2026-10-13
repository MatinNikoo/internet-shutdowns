"""How sure can we be? Placebo tests in space and in time.

Space: pretend each donor country had the shutdown instead and see how big a
"effect" shows up by chance. Time: pretend the treated country had it in an
earlier quarter, which measures how noisy that particular country is.

Small countries are noisier than the big donors, so the space placebos alone can
be too optimistic for them. The standard error used is the larger of the two.
"""
from dataclasses import dataclass
import numpy as np
from .synth import fit


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
    return Result(method, f.effect, se, se_space, se_time, float(p), len(pe), f, path_se)
