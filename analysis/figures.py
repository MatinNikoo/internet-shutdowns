"""Draws every chart in figures/ from the json in results/."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
INK, MUTED, LINE, ACCENT, RED = "#0E1726", "#596476", "#DCE1E9", "#2F4BC4", "#C2410C"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": LINE, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#EEF1F5", "grid.linewidth": 0.8, "figure.dpi": 150,
    "savefig.bbox": "tight", "legend.frameon": False,
})

E = json.loads((ROOT / "results" / "events.json").read_text())
EV = {e["event"]: e for e in E["events"]}
LABELS = E["labels"]


def pct(x):
    return f"{x * 100:+.0f}%"


def iran():
    e = EV["IR-2026"]
    a = np.array(e["series"]["actual"]) / 1000
    w = np.array(e["series"]["twin"]) / 1000
    x = np.arange(len(a))
    top = max(a.max(), w.max())
    fig, ax = plt.subplots(figsize=(8.2, 4.1))
    for ev, txt in (("IR-2022", "2022 mobile\ncurfews"), ("IR-2025", "June 2025\nblackout"),
                    ("IR-2026", "2026\nblackouts")):
        for q in EV[ev]["quarters"]:
            t = LABELS.index(q)
            ax.axvspan(t - .5, t + .5, color="#F4E3DA", lw=0)
        t = LABELS.index(EV[ev]["quarters"][0])
        ax.text(t, top * 1.02, txt, ha="center", va="bottom", fontsize=8.5, color=RED)
    ax.plot(x, w, color=MUTED, lw=1.6, ls=(0, (4, 3)), label="Iran's twin, built from countries that stayed online")
    ax.plot(x, a, color=ACCENT, lw=2.2, label="Iran, actual")
    t = len(a) - 1
    ax.annotate("", xy=(t + .25, a[t]), xytext=(t + .25, w[t]),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.4))
    ax.text(t - .35, (a[t] + w[t]) / 2 - 60, f"{e['sdid']['pct'] * 100:.0f}%", color=RED, ha="right",
            va="center", fontsize=12, fontweight="bold")
    ax.text(t - .45, 300, "the twin follows the\njump most countries\nhad this quarter",
            ha="right", va="top", fontsize=8, color=MUTED)
    ax.set_xticks(x[::4], [LABELS[i][:4] for i in x[::4]])
    ax.set_ylabel("Git pushes per quarter (thousands)")
    ax.set_ylim(0, top * 1.17)
    ax.legend(loc="upper left", bbox_to_anchor=(0, .86), fontsize=9)
    ax.set_title("Iran's coding activity on GitHub vs its synthetic twin", loc="left", color=INK, fontsize=12)
    fig.savefig(FIG / "iran.png")
    plt.close(fig)


def forest():
    rows = sorted(E["events"], key=lambda e: e["sdid"]["pct"])
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    for i, e in enumerate(rows):
        s = e["sdid"]
        c = ACCENT if e["kind"] == "full" else MUTED
        ax.plot([s["lo"] * 100, s["hi"] * 100], [i, i], color=c, lw=2, alpha=.45, solid_capstyle="round")
        ax.plot(s["pct"] * 100, i, "o", color=c, ms=7)
        if "full_stop_pct" in e:
            ax.plot(e["full_stop_pct"] * 100, i, "D", mfc="white", mec=RED, ms=6.5, mew=1.5)
    ax.axvline(0, color=INK, lw=.8)
    names = [f"{e['country']} {e['event'][-4:]}" + ("" if e["kind"] == "full" else "  (partial)") for e in rows]
    ax.set_yticks(range(len(rows)), names)
    ax.set_xlabel("Change in git pushes vs synthetic twin, with 95% interval (%)")
    ax.plot([], [], "o", color=ACCENT, label="Full shutdown")
    ax.plot([], [], "o", color=MUTED, label="Partial (mobile only or curfews)")
    ax.plot([], [], "D", mfc="white", mec=RED, mew=1.5, label="If a day offline cost exactly a day")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG / "events.png")
    plt.close(fig)


def dose():
    dr = E["dose_response"]
    full = [e for e in E["events"] if e["kind"] == "full"]
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    s = np.linspace(0, .66, 100)
    ax.plot(s * 100, -s * 100, color=RED, lw=1.4, ls=(0, (4, 3)), label="A day offline costs a day")
    fitted = np.expm1(dr["beta"] * np.log1p(-s))
    ax.plot(s * 100, fitted * 100, color=ACCENT, lw=2,
            label=f"Best fit: each day costs {dr['beta']:.2f} days")
    for e in full:
        x0, x1 = e["share_low"] * 100, e["share_high"] * 100
        xm = e["share_mid"] * 100
        sd = e["sdid"]
        ax.plot([xm, xm], [sd["lo"] * 100, sd["hi"] * 100], color=ACCENT, alpha=.35, lw=2)
        ax.plot([x0, x1], [sd["pct"] * 100] * 2, color=ACCENT, alpha=.35, lw=2)
        ax.plot(xm, sd["pct"] * 100, "o", color=ACCENT, ms=7)
        ax.annotate(f"{e['country']} {e['event'][-4:]}", (xm, sd["pct"] * 100), xytext=(6, 6),
                    textcoords="offset points", fontsize=8.5, color=INK)
    ax.axhline(0, color=INK, lw=.8)
    ax.set_xlabel("Share of the quarter the internet was off (%)")
    ax.set_ylabel("Change in git pushes vs twin (%)")
    ax.set_xlim(-2, 68)
    ax.legend(loc="lower left", fontsize=8.5)
    ax.set_title("Lost days aren't made up later", loc="left", fontsize=12, color=INK)
    fig.savefig(FIG / "dose.png")
    plt.close(fig)


def recovery():
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, k, title in ((axes[0], "IR-2022", "Iran 2022 (mobile curfews)"),
                         (axes[1], "MM-2021", "Myanmar 2021 (coup, months of cuts)")):
        p = EV[k]["path"]
        x = np.arange(len(p))
        g = np.array([q["gap_pct"] for q in p]) * 100
        lo = np.array([q["lo"] for q in p]) * 100
        hi = np.array([q["hi"] for q in p]) * 100
        ax.fill_between(x, lo, hi, color=ACCENT, alpha=.12, lw=0)
        ax.plot(x, g, "o-", color=ACCENT, ms=4.5, lw=1.8)
        ax.axhline(0, color=INK, lw=.8)
        nh = len(EV[k]["quarters"])
        ax.axvspan(-.4, nh - .6, color="#F4E3DA", lw=0)
        ax.set_xticks(x, [q["q"].replace("20", "'", 1) for q in p], rotation=45, fontsize=8)
        ax.set_title(title, loc="left", fontsize=10.5, color=INK)
    axes[0].set_ylabel("Pushes vs twin (%)")
    axes[0].set_ylim(-90, 130)
    fig.savefig(FIG / "recovery.png")
    plt.close(fig)


def drift():
    keys = ["MM-2021", "IR-2026", "SD-2021", "IR-2022", "IR-2025", "BD-2024", "TZ-2025", "KZ-2022", "PK-2023"]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    y = np.arange(len(keys))
    for off, name, col in ((-.18, "developers", ACCENT), (.18, "repositories", "#7C8CD9")):
        v = [EV[k]["location_drift"][name] for k in keys]
        ax.barh(y + off, [d["pct"] * 100 for d in v], height=.34, color=col, label=f"{name.capitalize()} located there")
        for i, d in enumerate(v):
            ax.plot([d["lo"] * 100, d["hi"] * 100], [y[i] + off] * 2, color=INK, lw=.9, alpha=.6)
    ax.set_yticks(y, [f"{EV[k]['country']} {k[-4:]}" for k in keys])
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    ax.set_xlabel("Change vs twin (%). These counts almost never fall on their own")
    ax.legend(fontsize=8.5, loc="lower left")
    ax.grid(axis="y", visible=False)
    ax.set_title("Accounts that 'left' the country on GitHub's map", loc="left", fontsize=12, color=INK)
    fig.savefig(FIG / "drift.png")
    plt.close(fig)


def power():
    p = ROOT / "results" / "simulations.json"
    if not p.exists():
        return
    S = json.loads(p.read_text())
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for m, col, name in (("sdid", ACCENT, "Synthetic DiD"), ("sc", MUTED, "Synthetic control")):
        rows = S["summary"][m]
        days = [r["drop"] * 91 for r in rows]
        ax.plot(days, [r["power"] * 100 for r in rows], "o-", color=col, lw=2, ms=5, label=name)
    ax.axhline(80, color=RED, lw=1, ls=(0, (4, 3)))
    ax.text(1, 82, "80% chance of catching it", color=RED, fontsize=8.5)
    ax.axhline(5, color=MUTED, lw=.8, ls=":")
    ax.set_xlabel("Days offline in a quarter (planted, as a share of 91 days)")
    ax.set_ylabel("Fake shutdowns flagged (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("How long a shutdown has to be before quarterly data can see it", loc="left",
                 fontsize=11, color=INK)
    fig.savefig(FIG / "power.png")
    plt.close(fig)


if __name__ == "__main__":
    iran()
    forest()
    dose()
    recovery()
    drift()
    power()
    print("figures written")
