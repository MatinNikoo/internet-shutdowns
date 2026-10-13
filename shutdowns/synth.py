"""Synthetic control and synthetic difference in differences.

Both build a "twin" for the treated country out of countries that stayed online,
then read the effect as the gap between the country and its twin after the event.

Conventions: Y0 is the donor matrix (donors x quarters), y1 is the treated series,
pre and post are lists of quarter indices. Outcomes are on the log scale, so a gap
of g means the country did exp(g) - 1 relative to its twin.
"""
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import nnls


def simplex_weights(A, b, eta=0.0, intercept=True, penalty=1e4):
    """Minimize ||A w - b||^2 + eta ||w||^2 over the simplex (w >= 0, sum w = 1).

    Same objective as the Frank Wolfe solver in Arkhangelsky et al. (2021), solved
    exactly as a nonnegative least squares problem: the ridge term becomes extra
    rows, and sum(w) = 1 is enforced by one heavily weighted row.
    With intercept, A and b are centered first, which lets the twin sit at a
    different level and only match the shape.
    """
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    if intercept:
        A = A - A.mean(axis=0)
        b = b - b.mean()
    k = A.shape[1]
    scale = max(1.0, np.sqrt(np.mean(A ** 2)) * np.sqrt(A.shape[0]))
    rows = [A, penalty * scale * np.ones((1, k))]
    rhs = [b, [penalty * scale]]
    if eta > 0:
        rows.append(np.sqrt(eta) * np.eye(k))
        rhs.append(np.zeros(k))
    w, _ = nnls(np.vstack(rows), np.concatenate(rhs), maxiter=50 * k)
    s = w.sum()
    return w / s if s > 0 else np.full(k, 1.0 / k)


@dataclass
class Fit:
    method: str
    gaps: np.ndarray          # treated minus twin, every quarter (log scale)
    twin: np.ndarray          # the twin's series, on the treated unit's scale
    omega: np.ndarray         # donor weights
    lam: np.ndarray           # pre period weights (uniform for SC)
    pre: list
    post: list
    pre_rmse: float
    effect: float = field(init=False)   # average gap over post quarters

    def __post_init__(self):
        self.effect = float(np.mean(self.gaps[self.post]))


def _gaps(y1, Y0, omega, lam, pre):
    diff = y1 - omega @ Y0                       # treated minus weighted donors, every quarter
    base = lam @ diff[pre]                       # what that difference was before
    return diff - base, omega @ Y0 + base


def synth_control(y1, Y0, pre, post, intercept=True):
    """Abadie style synthetic control. With intercept=True this is the demeaned
    version (Ferman and Pinto 2021): the twin matches the shape of the pre period,
    not necessarily its level, which matters when the country is unusually big or small."""
    y1 = np.asarray(y1, float)
    Y0 = np.asarray(Y0, float)
    omega = simplex_weights(Y0[:, pre].T, y1[pre], eta=1e-8, intercept=intercept)
    lam = np.full(len(pre), 1.0 / len(pre))
    if intercept:
        gaps, twin = _gaps(y1, Y0, omega, lam, pre)
    else:
        twin = omega @ Y0
        gaps = y1 - twin
    return Fit("sc", gaps, twin, omega, lam, list(pre), list(post),
               float(np.sqrt(np.mean(gaps[pre] ** 2))))


def sdid(y1, Y0, pre, post):
    """Synthetic difference in differences (Arkhangelsky, Athey, Hirshberg, Imbens, Wager 2021).

    Unit weights make the donors move like the country before the event.
    Time weights pick the pre quarters that look most like the post period.
    The regularization follows the paper: zeta = (N_treated * T_post)^(1/4) * sigma,
    where sigma is the spread of quarter to quarter changes among donors.
    """
    y1 = np.asarray(y1, float)
    Y0 = np.asarray(Y0, float)
    n0 = Y0.shape[0]
    sigma = np.std(np.diff(Y0[:, pre], axis=1), ddof=1)
    zeta = (1 * len(post)) ** 0.25 * sigma
    omega = simplex_weights(Y0[:, pre].T, y1[pre], eta=len(pre) * zeta ** 2, intercept=True)
    # time weights: which pre quarters best predict the donors' post average
    lam = simplex_weights(Y0[:, pre], Y0[:, post].mean(axis=1), eta=n0 * (1e-6 * sigma) ** 2,
                          intercept=True)
    gaps, twin = _gaps(y1, Y0, omega, lam, pre)
    return Fit("sdid", gaps, twin, omega, lam, list(pre), list(post),
               float(np.sqrt(np.mean((gaps[pre] - lam @ gaps[pre]) ** 2))))


def fit(method, y1, Y0, pre, post):
    if method == "sc":
        return synth_control(y1, Y0, pre, post)
    if method == "sdid":
        return sdid(y1, Y0, pre, post)
    raise ValueError(method)
