"""Two estimates side by side. Each side is a registry event id (IR-2026) or a spec
ECONOMY:START[:END] (IR:2022Q4, MM:2021Q1:2021Q2)."""
import numpy as np

from .design import run, quarters_from, windows, registry_skip, _phi
from .panel import OUTCOMES, event_windows, label
from .specs import SpecError, quarter_range, resolve_economy
from . import report


def side(panel, spec, donors_kind="all"):
    """Run one side. Returns the design result with 'label' and 'event' added."""
    ev = panel.events[panel.events.event == spec.upper()]
    if len(ev):
        row = ev.iloc[0]
        pre, head, path = event_windows(panel, row)
        iso2, tag = row.iso2, row.event
    else:
        parts = spec.split(":")
        if len(parts) not in (2, 3):
            raise SpecError(f"'{spec}' is neither a registry event (see `shutdowns events`) nor ECONOMY:START[:END]")
        iso2 = resolve_economy(panel, parts[0])
        a, b, _ = quarter_range(panel, parts[1], parts[2] if len(parts) == 3 else None)
        head = quarters_from(label(a), label(b))
        pre, _, path = windows(panel, iso2, head, registry_skip(panel, iso2, head))
        tag = f"{iso2} {label(head[0])}" + (f" to {label(head[-1])}" if len(head) > 1 else "")
    if len(pre) < 4:
        raise SpecError(f"{tag} has fewer than 4 quarters before it, too few to build a twin")
    donors = panel.pool(donors_kind, iso2) if donors_kind != "all" else None
    r = run(panel, iso2, head, pre=pre, path=path, donors=donors)
    r["label"] = tag
    return r


def difference(a, b):
    """Gap between the two synthetic DiD effects on the log scale, treating them as independent."""
    d = a["sdid"]["log"] - b["sdid"]["log"]
    se = float(np.hypot(a["sdid"]["se"], b["sdid"]["se"]))
    z = d / se
    return {"log": float(d), "se": se, "pct": float(np.expm1(d)), "lo": float(np.expm1(d - 1.96 * se)),
            "hi": float(np.expm1(d + 1.96 * se)), "p": float(2 * (1 - _phi(abs(z))))}


def table(a, b):
    rows = []
    for r in (a, b):
        row = {"event": r["label"], "outcome": next(k for k, v in OUTCOMES.items() if v == r["outcome"]), "quarters": " ".join(r["quarters"]),
               "pre_quarters": len(r["pre_quarters"]), "donors": r["n_donors"]}
        for m in ("sdid", "sc", "ascm"):
            row[f"{m}_pct"] = round(r[m]["pct"] * 100, 2)
        row["sdid_lo_pct"] = round(r["sdid"]["lo"] * 100, 2)
        row["sdid_hi_pct"] = round(r["sdid"]["hi"] * 100, 2)
        row["p_normal"] = round(r["sdid"]["p_normal"], 4)
        row["p_perm"] = round(r["sdid"]["p_perm"], 4)
        rows.append(row)
    return rows


def text(a, b):
    d = difference(a, b)
    out = []
    for r in (a, b):
        s = r["sdid"]
        out.append(f"{r['label']}: {report.pct(s['pct'], 1)} vs twin (95% {report.pct(s['lo'])} to {report.pct(s['hi'])}), "
                   f"p {report.pfmt(s['p_normal'])}, {len(r['pre_quarters'])} quarters before, {r['n_donors']} donors")
    out.append(f"Difference: {report.pct(d['pct'], 1)} (95% {report.pct(d['lo'])} to {report.pct(d['hi'])}), p {report.pfmt(d['p'])}")
    out.append("The difference treats the two estimates as independent. They share donors, so the interval is a bit narrow.")
    return "\n".join(out)


def markdown(a, b, png):
    d = difference(a, b)
    what = report.OUT_NAMES.get(a["outcome"], a["outcome"])
    lines = [f"# {a['label']} vs {b['label']}", "",
             f"Change in {what} GitHub attributes to each economy compared with its own synthetic twin.", "",
             f"![comparison]({png})", "",
             "| | Quarters | Pre quarters | Donors | Synthetic DiD | 95% interval | Synthetic control | Augmented SC | p (normal) | p (permutation) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in (a, b):
        s = r["sdid"]
        lines.append(f"| {r['label']} | {', '.join(r['quarters'])} | {len(r['pre_quarters'])} | {r['n_donors']} | {report.pct(s['pct'], 1)} | "
                     f"{report.pct(s['lo'])} to {report.pct(s['hi'])} | {report.pct(r['sc']['pct'], 1)} | {report.pct(r['ascm']['pct'], 1)} | "
                     f"{report.pfmt(s['p_normal'])} | {report.pfmt(s['p_perm'])} |")
    lines += ["", f"Difference in the synthetic DiD effect, first minus second, is {report.pct(d['pct'], 1)} "
              f"(95% {report.pct(d['lo'])} to {report.pct(d['hi'])}, p {report.pfmt(d['p'])}). "
              "It treats the two estimates as independent. They share donors, so the interval is a bit narrow.", "",
              report.CAVEAT, ""]
    return "\n".join(lines)
