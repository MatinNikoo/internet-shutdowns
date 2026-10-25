"""The same design on all four Innovation Graph outcomes.

Pushes are a flow (how much code got uploaded that quarter). Developers, repositories and
organizations are end of quarter counts that include inactive accounts, so they only move
when new accounts stop appearing or when accounts get placed in another country. They
are a check on measurement more than a second measure of work.

Writes results/outcomes.json.   python analysis/outcomes.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel, OUTCOMES, event_windows  # noqa: E402
from shutdowns.design import run  # noqa: E402

RAW = {"git_pushes": "git_pushes", "developers": "developers", "repositories": "repositories",
       "organizations": "organizations"}


def main():
    panels = {k: Panel(outcome=k) for k in OUTCOMES}
    base = panels["git_pushes"]
    rows = []
    for _, ev in base.events.iterrows():
        pre, head, path = event_windows(base, ev)
        row = {"event": ev.event, "country": ev.country, "kind": ev.kind, "outcomes": {}}
        for k, p in panels.items():
            r = run(p, ev.iso2, head, pre=pre, path=[], methods=("sdid", "sc"), extras=False)
            raw = p.df.pivot(index="iso2", columns="t", values=RAW[k]).loc[ev.iso2]
            t0 = head[0]
            prev = max(t for t in pre)
            row["outcomes"][k] = {
                "sdid": {x: r["sdid"][x] for x in ("pct", "lo", "hi", "se", "p_normal", "p_perm")},
                "sc": {x: r["sc"][x] for x in ("pct", "p_normal")},
                # did the count actually fall, or just grow slower than the twin?
                "level_change_vs_last_clean_quarter": float(raw[t0] - raw[prev]),
                "pct_change_vs_last_clean_quarter": float(raw[t0] / raw[prev] - 1)}
        o = row["outcomes"]
        sig = {k: o[k]["sdid"]["p_normal"] < 0.05 for k in o}
        neg = {k: o[k]["sdid"]["pct"] < 0 for k in o}
        row["all_negative"] = all(neg.values())
        row["significant"] = sig
        rows.append(row)
        print(ev.event, "  ".join(f"{k[:5]} {o[k]['sdid']['pct']:+.1%}{'*' if sig[k] else ''}" for k in o))
    (ROOT / "results" / "outcomes.json").write_text(json.dumps({"events": rows}, indent=1))


if __name__ == "__main__":
    main()
