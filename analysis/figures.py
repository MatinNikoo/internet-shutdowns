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


def load(name):
    p = ROOT / "results" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


ID = load("identification")
IDE = {e["event"]: e for e in ID["events"]} if ID else {}


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
    if ID:
        flat = a[t - 1]
        ax.plot([t - .3, t + .3], [flat, flat], color=RED, lw=1.2, ls=":")
        ax.text(t + .45, flat, "if Iran had\nstayed flat", fontsize=7.5, color=RED, va="center")
        ax.set_xlim(-0.7, t + 1.9)
    ax.set_xticks(x[::4], [LABELS[i][:4] for i in x[::4]])
    ax.set_ylabel("Git pushes per quarter (thousands)")
    ax.set_ylim(0, top * 1.17)
    ax.legend(loc="upper left", bbox_to_anchor=(0, .86), fontsize=9)
    ax.set_title("Git pushes GitHub places in Iran vs its synthetic twin", loc="left", color=INK, fontsize=12)
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
    ax.set_xlabel("Change in attributed git pushes vs synthetic twin, with 95% interval (%)")
    ax.plot([], [], "o", color=ACCENT, label="Full shutdown")
    ax.plot([], [], "o", color=MUTED, label="Partial (mobile only or curfews)")
    ax.plot([], [], "D", mfc="white", mec=RED, mew=1.5, label="Share of the quarter offline (day for day line)")
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
    H = load("heterogeneity")
    share = H["dose_response"]["influence_share"]["IR-2026"] if H else None
    ax.plot(s * 100, fitted * 100, color=ACCENT, lw=2,
            label=f"Version 1 fit, slope {dr['beta']:.2f}" + (f" ({share:.0%} of it is Iran 2026)" if share else ""))
    for e in full:
        x0, x1 = e["share_low"] * 100, e["share_high"] * 100
        xm = e["share_mid"] * 100
        sd = e["sdid"]
        ax.plot([xm, xm], [sd["lo"] * 100, sd["hi"] * 100], color=ACCENT, alpha=.35, lw=2)
        ax.plot([x0, x1], [sd["pct"] * 100] * 2, color=ACCENT, alpha=.35, lw=2)
        ax.plot(xm, sd["pct"] * 100, "o", color=ACCENT, ms=7)
        off, ha = {"TZ-2025": ((-6, 11), "right"), "KZ-2022": ((-7, -6), "right"), "BD-2024": ((7, 0), "left"),
                   "IR-2025": ((7, -8), "left")}.get(e["event"], ((6, 6), "left")) if e["event"] != "IR-2026" else ((-8, -13), "right")
        ax.annotate(f"{e['country']} {e['event'][-4:]}", (xm, sd["pct"] * 100), xytext=off,
                    textcoords="offset points", fontsize=8.5, color=INK, ha=ha)
    if ID:
        j = ID["jump_2026"]
        e = EV["IR-2026"]
        xm = e["share_mid"] * 100
        vs = (j["flat_counterfactual_pct"], j["sanctioned_growth_counterfactual_pct"])
        for v in vs:
            ax.plot(xm, v * 100, "o", mfc="white", mec=ACCENT, ms=6, mew=1.4)
        ax.annotate("Iran 2026 if it wouldn't have\njoined the 2026 jump", (xm, np.mean(vs) * 100), xytext=(-10, 0),
                    textcoords="offset points", fontsize=7.5, color=MUTED, ha="right", va="center")
    ax.axhline(0, color=INK, lw=.8)
    ax.set_xlabel("Share of the quarter the internet was off (%)")
    ax.set_ylabel("Change in attributed git pushes vs twin (%)")
    ax.set_xlim(-14, 68)
    ax.set_xticks(range(0, 70, 10))
    ax.legend(loc="lower left", fontsize=8.5)
    ax.set_title("Bigger share offline, bigger drop. One event sets the slope", loc="left", fontsize=11.5, color=INK)
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
    axes[0].set_ylabel("Attributed pushes vs twin (%)")
    axes[0].set_ylim(-90, 130)
    fig.savefig(FIG / "recovery.png")
    plt.close(fig)


def drift():
    """Repositories and organizations are placed by where their members are seen and include
    dead projects, so they almost never fall. Iran 2026 and Myanmar 2021 are the exceptions."""
    if not ID:
        return
    sf = ID["stock_falls"]
    keys = [("IR-2026", "2026Q1"), ("MM-2021", "2021Q2"), ("MM-2021", "2021Q1"), ("SD-2021", "2021Q4"),
            ("IR-2022", "2022Q4"), ("IR-2025", "2025Q2"), ("BD-2024", "2024Q3")]
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    y = np.arange(len(keys))
    for off, name, col in ((-.18, "repositories", ACCENT), (.18, "organizations", "#7C8CD9")):
        v = [sf["events"][k][f"{name}_{q}"]["pct_change"] * 100 for k, q in keys]
        ax.barh(y + off, v, height=.34, color=col, label=f"{name.capitalize()} placed there")
    ax.set_yticks(y, [f"{EV[k]['country']} {q}" for k, q in keys])
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    r = sf["base_rates"]["repositories"]["share_fall_over_2pct"]
    ax.set_xlabel(f"Change from the quarter before (%). Repository counts fall more than 2% in {r:.1%} of all economy-quarters")
    ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
    ax.grid(axis="y", visible=False)
    ax.set_title("Counts that almost never fall did fall", loc="left", fontsize=12, color=INK)
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


def ooni():
    """Independent daily check: OONI test counts relative to the pre quarter baseline, with
    the registry dates shaded. Wikimedia pageviews added where they exist."""
    X = load("exposure")
    if not X:
        return
    import pandas as pd
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from shutdowns.exposure import load_daily, series, quarter_dates
    od = load_daily("ooni")
    wp = ROOT / "data" / "wikimedia" / "daily_pageviews.csv"
    wd = load_daily("wikimedia") if wp.exists() else None
    ev = pd.read_csv(ROOT / "data" / "events.csv")
    keys = ["IR-2026", "IR-2025", "KZ-2022", "BD-2024", "TZ-2025"]
    XE = {e["event"]: e for e in X["events"]}
    fig, axes = plt.subplots(len(keys), 1, figsize=(8.2, 9.2), sharey=True)
    for ax, k in zip(axes, keys):
        r = ev[ev.event == k].iloc[0]
        a, b = quarter_dates(r.quarter)
        a = pd.Timestamp(a) - pd.Timedelta(days=21)
        b = pd.Timestamp(b)
        base = XE[k]["ooni"]["0.5"]["baseline"]
        o = series(od, r.iso2, a, b) / base * 100
        ax.plot(o.index, o.values, color=ACCENT, lw=1.3, label="OONI tests per day")
        w = XE[k].get("wikimedia")
        if w and w.get("usable"):
            ws = series(wd, r.iso2, a, b) / w["baseline"] * 100
            ax.plot(ws.index, ws.values, color="#7C8CD9", lw=1.3, ls=(0, (3, 2)), label="Wikipedia pageviews per day")
        s0 = pd.Timestamp(r.start_date)
        s1 = pd.Timestamp(r.end_date) if isinstance(r.end_date, str) else b
        ax.axvspan(s0, s1 + pd.Timedelta(days=1), color="#F4E3DA", lw=0, label="dates in my registry")
        ax.axhline(50, color=RED, lw=.8, ls=":")
        ax.set_ylim(0, 220)
        ax.set_xlim(a, b)
        ax.set_title(f"{r.country} {r.quarter}", loc="left", fontsize=10, color=INK)
        ax.grid(axis="x", visible=False)
    h, lab = axes[3].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.07, 0.965), ncol=3, fontsize=8)
    axes[len(keys) // 2].set_ylabel("Share of the usual daily level (%)")
    fig.suptitle("Two independent daily sources line up with the shutdown dates", x=0.07, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "ooni.png")
    plt.close(fig)


def checks():
    """The same headline under every estimator and donor pool."""
    if not ID:
        return
    keys = ["IR-2026", "MM-2021", "SD-2021", "IR-2022", "IR-2025"]
    rows = [("sdid", "Synthetic DiD, all 106 donors"), ("sc", "Synthetic control"), ("ascm", "Augmented synthetic control"),
            ("no_keepiton_shutdown", "No donor with a recorded full shutdown (82)"), ("same_continent", "Same continent only"),
            ("same_income", "Same income group only"), ("no_neighbors", "No neighbors")]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    cols = [ACCENT, "#7C8CD9", MUTED, RED, "#0E7C66"]
    for j, (k, c) in enumerate(zip(keys, cols)):
        e = IDE[k]
        for i, (key, _) in enumerate(rows):
            v = e[key]["pct"] if key in ("sdid", "sc", "ascm") else e["pools"][key]["pct"]
            y = i + (j - 2) * .13
            ax.plot(v * 100, y, "o", color=c, ms=5, label=f"{e['country']} {k[-4:]}" if i == 0 else None)
    ax.set_yticks(range(len(rows)), [r[1] for r in rows])
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    ax.set_xlabel("Change in attributed git pushes vs twin (%)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="y", visible=False)
    ax.set_title("Same sign and similar size under every estimator and donor pool", loc="left", fontsize=11.5, color=INK)
    fig.savefig(FIG / "checks.png")
    plt.close(fig)


def controls():
    """Crises with no full shutdown next to the registry events."""
    if not ID:
        return
    nc = ID["negative_controls"]["controls"]
    rows = sorted([(f"{c['country']} {c['quarter']} ({c['kind']})", c["pct"], c["lo"], c["hi"], MUTED) for c in nc],
                  key=lambda r: r[1])
    ev = sorted([(f"{e['country']} {e['event'][-4:]} (shutdown)", e["sdid"]["pct"], e["sdid"]["lo"], e["sdid"]["hi"],
                  ACCENT if e["kind"] == "full" else "#7C8CD9") for e in ID["events"]], key=lambda r: r[1])
    allr = ev + rows
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    for i, (n, v, lo, hi, c) in enumerate(allr):
        ax.plot([lo * 100, hi * 100], [i, i], color=c, lw=2, alpha=.35, solid_capstyle="round")
        ax.plot(v * 100, i, "o", color=c, ms=6)
    ax.axhline(len(ev) - .5, color=LINE, lw=1)
    ax.set_yticks(range(len(allr)), [r[0] for r in allr], fontsize=8.5)
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    ax.set_xlabel("Change in attributed git pushes vs twin, 95% interval (%)")
    ax.grid(axis="y", visible=False)
    for c, txt in ((ACCENT, "full shutdown"), ("#7C8CD9", "partial shutdown (mobile only, curfews)"), (MUTED, "crisis with no shutdown")):
        ax.plot([], [], "o", color=c, label=txt)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("Shutdowns (top) vs crises with no shutdown (bottom)", loc="left", fontsize=11.5, color=INK)
    fig.savefig(FIG / "controls.png")
    plt.close(fig)


def stacked():
    S = load("stacked")
    if not S:
        return
    st = S["study"]
    k = np.array([r["k"] for r in st])
    m = np.array([r["mean_log"] for r in st])
    se = np.array([r["se"] for r in st])
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    ax.fill_between(k, np.expm1(m - 1.96 * se) * 100, np.expm1(m + 1.96 * se) * 100, color=ACCENT, alpha=.13, lw=0,
                    label="95% band from running the same design on donors")
    for g in S["gaps"]:
        g = np.array([np.nan if v is None else v for v in g], float)
        ax.plot(k, np.expm1(g) * 100, color=MUTED, lw=.8, alpha=.45)
    ax.plot(k, np.expm1(m) * 100, "o-", color=ACCENT, lw=2, ms=5, label="average of the nine events")
    ax.axvspan(-.4, .4, color="#F4E3DA", lw=0)
    ax.axvline(-.5, color=LINE, lw=1)
    ax.axhline(0, color=INK, lw=.8)
    ax.set_xticks(k, ["-2\nheld out", "-1\nheld out", "0\nshutdown", "+1", "+2", "+3", "+4"])
    ax.set_ylabel("Attributed pushes vs twin (%)")
    ax.set_ylim(-90, 130)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Nine events stacked. The drop sits in the shutdown quarter", loc="left", fontsize=11, color=INK)
    fig.savefig(FIG / "stacked.png")
    plt.close(fig)


def heterogeneity():
    H = load("heterogeneity")
    if not H:
        return
    d = H["duration"]
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6))
    ax = axes[0]
    c = d["curve_vs_1"]
    ax.plot([x["slope"] for x in c], [x["power"] * 100 for x in c], "o-", color=ACCENT, ms=3.5, lw=1.8)
    ax.axhline(80, color=RED, lw=1, ls=(0, (4, 3)))
    ax.axvline(H["dose_response"]["beta"], color=MUTED, lw=1, ls=":")
    ax.text(H["dose_response"]["beta"] + .03, 8, f"my estimate {H['dose_response']['beta']:.2f}", color=MUTED, fontsize=8)
    ax.set_xlabel("True slope (1 = a day offline costs a day of attributed activity)")
    ax.set_ylabel("Chance of telling it apart from 1 (%)")
    ax.set_ylim(0, 102)
    ax.set_title("Can the data tell a slope of 1.3 from 1?", loc="left", fontsize=10.5, color=INK)
    ax = axes[1]
    dr = H["dose_response"]
    names = [j["dropped"] for j in dr["jackknife"]]
    b = [j["beta"] for j in dr["jackknife"]]
    s = [j["se"] for j in dr["jackknife"]]
    y = np.arange(len(names))
    for i in y:
        ax.plot([b[i] - 1.96 * s[i], b[i] + 1.96 * s[i]], [i, i], color=ACCENT, lw=2, alpha=.35)
        ax.plot(b[i], i, "o", color=ACCENT, ms=6)
    ax.axvline(1, color=RED, lw=1, ls=(0, (4, 3)))
    ax.set_yticks(y, [f"without {n}" for n in names], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Slope, 95% interval")
    ax.grid(axis="y", visible=False)
    ax.set_title("Drop one event at a time", loc="left", fontsize=10.5, color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "heterogeneity.png")
    plt.close(fig)


def outcomes():
    O = load("outcomes")
    if not O:
        return
    names = ["git_pushes", "developers", "repositories", "organizations"]
    ev = sorted(O["events"], key=lambda e: e["outcomes"]["git_pushes"]["sdid"]["pct"])
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    cols = [ACCENT, "#7C8CD9", MUTED, "#0E7C66"]
    for j, (n, c) in enumerate(zip(names, cols)):
        for i, e in enumerate(ev):
            o = e["outcomes"][n]["sdid"]
            y = i + (j - 1.5) * .17
            ax.plot([o["lo"] * 100, o["hi"] * 100], [y, y], color=c, lw=1.4, alpha=.35)
            ax.plot(o["pct"] * 100, y, "o", color=c, ms=4.5, label=n.replace("_", " ") if i == 0 else None)
    ax.set_yticks(range(len(ev)), [f"{e['country']} {e['event'][-4:]}" for e in ev])
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    ax.set_xlim(-90, 70)
    ax.set_xlabel("Change vs twin, 95% interval (%)")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", visible=False)
    ax.set_title("All four GitHub counts point the same way for the big three", loc="left", fontsize=11.5, color=INK)
    fig.savefig(FIG / "outcomes.png")
    plt.close(fig)


if __name__ == "__main__":
    iran()
    forest()
    dose()
    recovery()
    drift()
    power()
    ooni()
    checks()
    controls()
    stacked()
    heterogeneity()
    outcomes()
    print("figures written")
