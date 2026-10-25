"""One page report card for one estimate: a markdown file, a PDF, an optional HTML page
and the figure, plus the tables and figures the compare and outcomes commands use.

    card(result, out_dir, name, slug)   result is what design.run() returns
"""
import base64
import csv
import html as htmllib
import io
import json
from pathlib import Path

import numpy as np

INK, MUTED, LINE, ACCENT, RED = "#0E1726", "#596476", "#DCE1E9", "#2F4BC4", "#C2410C"
NAMES = {"sdid": "Synthetic DiD", "sc": "Synthetic control", "ascm": "Augmented synthetic control"}
OUT_NAMES = {"log_pushes": "git pushes", "log_devs": "developers", "log_repos": "repositories",
             "log_orgs": "organizations"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": LINE, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#EEF1F5", "grid.linewidth": 0.8, "figure.dpi": 150,
        "legend.frameon": False})
    return plt


def pct(x, d=0):
    return f"{x * 100:+.{d}f}%"


def _charts(r, axes):
    lab = r["series"]["labels"]
    x = np.arange(len(lab))
    a = np.array(r["series"]["actual"])
    w = np.array(r["series"]["twin"])
    head = [lab.index(q) for q in r["quarters"]]
    what = OUT_NAMES.get(r["outcome"], r["outcome"])
    ax = axes[0]
    for t in head:
        ax.axvspan(t - .5, t + .5, color="#F4E3DA", lw=0)
    ax.plot(x, np.exp(w) / 1000, color=MUTED, lw=1.5, ls=(0, (4, 3)), label="synthetic twin")
    ax.plot(x, np.exp(a) / 1000, color=ACCENT, lw=2, label=r["iso2"] + ", actual")
    ax.set_xticks(x[::4], [lab[i][:4] for i in x[::4]])
    ax.set_ylabel("thousands")
    ax.set_title(f"{what.capitalize()} per quarter, attributed to {r['iso2']}", loc="left", fontsize=10, color=INK)
    ax.legend(loc="upper left", fontsize=8)
    ax = axes[1]
    g = np.expm1(np.array(r["series"]["gap"])) * 100
    band = np.array([b if b is not None else np.nan for b in r["series"]["band"]])
    gl = np.array(r["series"]["gap"])
    ok = ~np.isnan(band)
    ax.fill_between(x[ok], np.expm1(gl[ok] - band[ok]) * 100, np.expm1(gl[ok] + band[ok]) * 100,
                    color=ACCENT, alpha=.13, lw=0, label="95% placebo band")
    pre = [lab.index(q) for q in r["pre_quarters"]]
    ax.plot(x[pre], g[pre], "o", color=MUTED, ms=3.5, label="before")
    post = head + [lab.index(q) for q in r["path_quarters"]]
    ax.plot(x[post], g[post], "o-", color=ACCENT, ms=4.5, lw=1.6, label="shutdown and after")
    ax.axhline(0, color=INK, lw=.8)
    for t in head:
        ax.axvspan(t - .5, t + .5, color="#F4E3DA", lw=0)
    ax.set_xticks(x[::4], [lab[i][:4] for i in x[::4]])
    ax.set_title("Gap to the twin (%)", loc="left", fontsize=10, color=INK)
    ax.legend(loc="best", fontsize=7.5)
    ax = axes[2]
    sp = np.expm1(np.array(r["placebos"]["space"])) * 100
    ax.hist(sp, bins=25, color=LINE, edgecolor="white")
    ax.axvline(r["sdid"]["pct"] * 100, color=RED, lw=2)
    ax.text(r["sdid"]["pct"] * 100, ax.get_ylim()[1] * .92, f"  {pct(r['sdid']['pct'], 1 if abs(r['sdid']['pct']) < .01 else 0)}", color=RED,
            fontsize=9, ha="left" if r["sdid"]["pct"] < np.median(sp) / 100 else "right")
    ax.set_title("Same design run on every donor (%)", loc="left", fontsize=10, color=INK)
    ax.grid(axis="y", visible=False)


def figure(r, path):
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), gridspec_kw={"width_ratios": [1.25, 1.25, 1]})
    _charts(r, axes)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def pfmt(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def rows(r):
    out = []
    for m in ("sdid", "sc", "ascm"):
        if m in r:
            s = r[m]
            out.append((NAMES[m], pct(s["pct"], 1), f"{pct(s['lo'])} to {pct(s['hi'])}",
                        pfmt(s["p_normal"]), pfmt(s["p_perm"])))
    return out


def checks(r):
    c = []
    if "conformal" in r:
        cf = r["conformal"]
        if cf["open_low"] and cf["open_high"]:
            c.append(f"Conformal test. p = {cf['p']:.3f}. With {cf['n_periods']} quarters the smallest possible p is "
                     f"{cf['min_p']:.3f}, so this test can't give an interval here.")
        else:
            c.append(f"Conformal test. p = {cf['p']:.3f} (smallest possible {cf['min_p']:.3f}), interval "
                     f"{pct(cf['lo_pct'])} to {pct(cf['hi_pct'])}.")
    b = r.get("backdate")
    if b:
        held = ", ".join(pct(np.expm1(g)) for g in b["held_out"])
        c.append(f"Backdating. Fitting without {' and '.join(b['held_quarters'])}, the twin misses those quarters by {held}. "
                 + ("Inside the placebo band." if b["inside_band"] else "Outside the placebo band, so the pre trend is shaky."))
    elif "backdate" in r:
        c.append("Backdating. Too few pre quarters to hold any out.")
    s = r.get("sensitivity")
    if s:
        if s["breakdown_m"] > 0:
            c.append(f"Breakdown. The twin's path would have to be off by {s['breakdown_m']:.1f} times the worst miss "
                     f"in the {s['benchmark']} before the result goes away.")
        else:
            c.append("Breakdown. The interval already includes zero, so there is nothing to break.")
    lo = r.get("leave_one_out")
    if lo and lo["n"]:
        c.append(f"Leave one donor out. Dropping each of the {lo['n']} donors with weight over 1% keeps the estimate between "
                 f"{pct(lo['min_pct'], 1)} and {pct(lo['max_pct'], 1)}.")
    return c


CAVEAT = ("This is GitHub activity placed in the country by IP address, not national output. People on a VPN get "
          "placed wherever the VPN exits, and shutdowns usually come with other trouble (protests, conflict), "
          "so the gap is the change in attributed activity during everything that happened that quarter.")


def markdown(r, name, png, extra=None):
    what = OUT_NAMES.get(r["outcome"], r["outcome"])
    q = ", ".join(r["quarters"])
    lines = [f"# {name}", "",
             f"Change in {what} GitHub attributes to **{r['iso2']}** in {q}, compared with a synthetic twin built from "
             f"{r['n_donors']} economies. {len(r['pre_quarters'])} quarters before the event are used to build the twin.", "",
             f"![report card]({png})", "",
             "| Method | Change vs twin | 95% interval | p (normal) | p (permutation) |", "|---|---|---|---|---|"]
    lines += ["| " + " | ".join(x) + " |" for x in rows(r)]
    lines += ["", "**Checks**", ""] + [f"* {c}" for c in checks(r)]
    if extra:
        lines += [f"* {x}" for x in extra]
    tw = ", ".join(f"{w['iso2']} {w['w']:.2f}" for w in r["weights"][:6])
    lines += ["", f"Biggest donor weights: {tw}.", "", CAVEAT, ""]
    return "\n".join(lines)


def pdf(r, name, path, extra=None):
    plt = _plt()
    from matplotlib.backends.backend_pdf import PdfPages
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.07, 0.955, name, fontsize=16, color=INK, weight="bold")
    what = OUT_NAMES.get(r["outcome"], r["outcome"])
    fig.text(0.07, 0.93, f"Change in {what} attributed to {r['iso2']} in {', '.join(r['quarters'])} vs a synthetic twin "
             f"({r['n_donors']} donor economies, {len(r['pre_quarters'])} pre quarters)", fontsize=9, color=MUTED)
    y = 0.895
    cols = (0.07, 0.36, 0.52, 0.74, 0.86)
    for c, h in zip(cols, ("Method", "vs twin", "95% interval", "p normal", "p perm")):
        fig.text(c, y, h, fontsize=9, color=MUTED, weight="bold")
    for row in rows(r):
        y -= 0.022
        for c, v in zip(cols, row):
            fig.text(c, y, v, fontsize=9, color=INK)
    ax1 = fig.add_axes([0.08, 0.60, 0.86, 0.20])
    ax2 = fig.add_axes([0.08, 0.335, 0.52, 0.20])
    ax3 = fig.add_axes([0.67, 0.335, 0.27, 0.20])
    _charts(r, [ax1, ax2, ax3])
    import textwrap
    y = 0.27
    for c in checks(r) + list(extra or []):
        for k, line in enumerate(textwrap.wrap(c, 125)):
            fig.text(0.07 if k == 0 else 0.085, y, ("• " if k == 0 else "") + line, fontsize=7.5, color=INK)
            y -= 0.0135
        y -= 0.004
    fig.text(0.07, 0.02, "GitHub activity placed in the country by IP address, not national output. "
             "VPN users get placed where the VPN exits.", fontsize=7, color=MUTED)
    with PdfPages(path) as pp:
        pp.savefig(fig)
    plt.close(fig)


def card(r, out_dir, name, slug, extra=None, html=False, with_pdf=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{slug}.png"
    figure(r, png)
    files = [png, out_dir / f"{slug}.md"]
    files[1].write_text(markdown(r, name, png.name, extra))
    if with_pdf:
        files.append(out_dir / f"{slug}.pdf")
        pdf(r, name, files[-1], extra)
    files.append(out_dir / f"{slug}.json")
    files[-1].write_text(json.dumps(slim(r), indent=1, default=float))
    if html:
        files.append(out_dir / f"{slug}.html")
        files[-1].write_text(page(r, name, png, extra))
    return files


def slim(r):
    return {k: v for k, v in r.items() if k != "placebos"}


def series_rows(r):
    """The quarterly series behind a card as plain rows, counts and percentages instead of logs."""
    lab = r["series"]["labels"]
    head, pre = set(r["quarters"]), set(r["pre_quarters"])
    rows = []
    for i, q in enumerate(lab):
        g, band = r["series"]["gap"][i], r["series"]["band"][i]
        rows.append({
            "quarter": q, "period": "shutdown" if q in head else "before" if q < min(head) else "after",
            "used_for_twin": q in pre,
            "actual": round(float(np.exp(r["series"]["actual"][i]))),
            "twin": round(float(np.exp(r["series"]["twin"][i]))),
            "gap_pct": round(float(np.expm1(g)) * 100, 3),
            "band_lo_pct": None if band is None else round(float(np.expm1(g - band)) * 100, 3),
            "band_hi_pct": None if band is None else round(float(np.expm1(g + band)) * 100, 3)})
    return rows


def to_csv(rows):
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


CSS = """
:root { --ink:#0E1726; --muted:#596476; --line:#DCE1E9; --bg:#fff; --soft:#F6F8FB; --accent:#2F4BC4; }
@media (prefers-color-scheme: dark) { :root { --ink:#E7ECF4; --muted:#9AA6B8; --line:#2A3445; --bg:#0F1623; --soft:#161F2E; --accent:#8FA4FF; } }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:920px; margin:0 auto; padding:32px 20px 56px; }
h1 { font-size:1.7rem; margin:0 0 4px; }
.lede { color:var(--muted); margin:0 0 20px; }
.big { font-size:2.6rem; font-weight:700; color:var(--accent); margin:0; line-height:1.1; }
.bigsub { color:var(--muted); margin:2px 0 22px; }
img { width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
table { border-collapse:collapse; width:100%; margin:18px 0; font-size:.95rem; }
th, td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
h2 { font-size:1.05rem; margin:28px 0 6px; }
ul { padding-left:20px; } li { margin:5px 0; }
.note { color:var(--muted); font-size:.88rem; border-top:1px solid var(--line); margin-top:30px; padding-top:14px; }
@media (max-width:560px) { .big { font-size:2.1rem; } table { font-size:.85rem; } th, td { padding:6px 5px; } }
"""


def page(r, name, png, extra=None):
    """A self contained HTML card, the figure is embedded so the file can be sent on its own."""
    e = htmllib.escape
    what = OUT_NAMES.get(r["outcome"], r["outcome"])
    s = r["sdid"]
    img = base64.b64encode(Path(png).read_bytes()).decode()
    body = "".join(f"<tr><td>{e(m)}</td><td class=num>{e(a)}</td><td class=num>{e(b)}</td><td class=num>{e(c)}</td>"
                   f"<td class=num>{e(d)}</td></tr>" for m, a, b, c, d in rows(r))
    items = "".join(f"<li>{e(c)}</li>" for c in checks(r) + list(extra or []))
    tw = ", ".join(f"{w['iso2']} {w['w']:.2f}" for w in r["weights"][:6])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)}</title><style>{CSS}</style></head>
<body><main>
<h1>{e(name)}</h1>
<p class="lede">{e(what.capitalize())} GitHub attributes to {e(r['iso2'])} in {e(', '.join(r['quarters']))}, compared with a synthetic twin
built from {r['n_donors']} economies. {len(r['pre_quarters'])} quarters before the event are used to build the twin.</p>
<p class="big">{e(pct(s['pct'], 1))}</p>
<p class="bigsub">vs the twin, 95% interval {e(pct(s['lo']))} to {e(pct(s['hi']))}, synthetic DiD</p>
<img alt="Actual and twin series, gap to the twin with a placebo band, and the same design run on every donor" src="data:image/png;base64,{img}">
<table><thead><tr><th>Method</th><th class=num>Change vs twin</th><th class=num>95% interval</th><th class=num>p (normal)</th><th class=num>p (permutation)</th></tr></thead>
<tbody>{body}</tbody></table>
<h2>Checks</h2><ul>{items}</ul>
<p>Biggest donor weights: {e(tw)}.</p>
<p class="note">{e(CAVEAT)}</p>
</main></body></html>
"""


def outcomes_figure(results, path, title):
    """Synthetic DiD estimate and interval for each of the four GitHub counts."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    names = [OUT_NAMES.get(r["outcome"], r["outcome"]) for r in results]
    for i, r in enumerate(results):
        s = r["sdid"]
        ax.plot([s["lo"] * 100, s["hi"] * 100], [i, i], color=ACCENT, lw=2.2, solid_capstyle="round")
        ax.plot(s["pct"] * 100, i, "o", color=ACCENT, ms=6)
        ax.text(s["lo"] * 100 - 1, i, pct(s["pct"], 1), fontsize=8.5, color=INK, ha="right", va="center")
    ax.axvline(0, color=INK, lw=.8)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.margins(x=.14)
    ax.set_xlabel("change vs twin (%), 95% interval")
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def compare_figure(a, b, path):
    """Gap to the twin in event time for two runs, and their three estimates side by side."""
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.5, 1]})
    cols = (ACCENT, RED)
    ax = axes[0]
    for run_, col in zip((a, b), cols):
        lab = run_["series"]["labels"]
        first = lab.index(run_["quarters"][0])
        ks = [i - first for i in range(len(lab)) if -8 <= i - first <= 8]
        g = np.array(run_["series"]["gap"])
        band = np.array([v if v is not None else np.nan for v in run_["series"]["band"]])
        idx = [first + k for k in ks]
        ax.plot(ks, np.expm1(g[idx]) * 100, "o-", color=col, ms=3.5, lw=1.6, label=run_["label"])
        ok = ~np.isnan(band[idx])
        k_ok = np.array(ks)[ok]
        if len(k_ok) == 1:
            ax.vlines(k_ok, np.expm1(g[idx][ok] - band[idx][ok]) * 100, np.expm1(g[idx][ok] + band[idx][ok]) * 100,
                      color=col, lw=5, alpha=.18)
        ax.fill_between(k_ok, np.expm1(g[idx][ok] - band[idx][ok]) * 100, np.expm1(g[idx][ok] + band[idx][ok]) * 100,
                        color=col, alpha=.10, lw=0)
    ax.axhline(0, color=INK, lw=.8)
    ax.axvline(-.5, color=MUTED, lw=.8, ls=":")
    ax.set_xlabel("quarters from the first shutdown quarter")
    ax.set_title("Gap to the twin (%)", loc="left", fontsize=10, color=INK)
    ax.legend(loc="best", fontsize=8)
    ax = axes[1]
    labels, y = [], 0
    for run_, col in zip((a, b), cols):
        for m in ("sdid", "sc", "ascm"):
            s = run_[m]
            ax.plot([s["lo"] * 100, s["hi"] * 100], [y, y], color=col, lw=2, solid_capstyle="round")
            ax.plot(s["pct"] * 100, y, "o", color=col, ms=5)
            labels.append(f"{NAMES[m]}")
            y += 1
        y += .6
    ax.set_yticks([0, 1, 2, 3.6, 4.6, 5.6], labels)
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=.8)
    ax.set_title("Three estimators, 95% interval (%)", loc="left", fontsize=10, color=INK)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
