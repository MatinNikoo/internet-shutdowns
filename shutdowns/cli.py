"""Command line tool. Run `shutdowns --help`, or `shutdowns <command> --help` for one command."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .panel import OUTCOMES as COLUMN
from .specs import SpecError, quarter_range, resolve_economy

ROOT = Path(__file__).resolve().parents[1]
OUTCOMES = list(COLUMN)
LOG_TO_NAME = {v: k for k, v in COLUMN.items()}
POOLS = ["all", "no_keepiton_shutdown", "same_continent", "same_income", "no_neighbors"]

DESCRIPTION = """\
Internet shutdowns and the GitHub activity attributed to a country, measured against a synthetic twin
built from countries that stayed online. Data are quarterly, 2020Q1 to 2026Q1.
Start with `shutdowns estimate --event IR-2026`, or see docs/tutorial.md for a walk through one event."""

EPILOG = """\
examples
  shutdowns events --results                         every event in the registry with its estimate
  shutdowns estimate --event IR-2026                 one registry event, exactly as in the paper
  shutdowns estimate -e Iran -s 2022Q4 --html        any economy and quarter, with an HTML card
  shutdowns estimate -e IR -s 2026-01-08 -t 2026-04-20 --outcome all
  shutdowns compare IR-2026 MM-2021                  two events side by side
  shutdowns estimate -e BD -s 2024Q3 --format csv    the quarterly series, for your own plots
"""


Fmt = argparse.RawDescriptionHelpFormatter


def need_data():
    if not (ROOT / "data" / "raw" / "git_pushes.csv").exists():
        sys.exit("shutdowns: can't find data/raw. Run this from a clone of the repo "
                 "(pip install -e . inside the clone keeps the data next to the code)")


def say(a):
    """Status lines go to stdout, or to stderr when stdout is carrying json or csv."""
    if getattr(a, "format", "text") in ("text", "table"):
        return print
    return lambda *x: print(*x, file=sys.stderr)


def _identification():
    path = ROOT / "results" / "identification.json"
    return json.loads(path.read_text()) if path.exists() else None


def event_notes(ev, r, ide):
    """Lines a report card adds for a registry event, beyond the checks every card has."""
    from . import report
    notes = [f"What happened. {ev.what_happened}. Source {ev.source}"]
    if not ide or r["outcome"] != "log_pushes":
        return notes
    e = {x["event"]: x for x in ide["events"]}.get(ev.event)
    if e:
        notes.insert(0, f"Holm adjusted p across the nine registry events is {report.pfmt(e['p_holm'])}. "
                     + ("Passes every check in the analysis plan." if e["clear_drop"]
                        else "Passes every check in the analysis plan that can be run on it. Backdating can't, "
                             "there are too few quarters before the event." if e.get("passes_all_runnable")
                        else "Does not pass every check in the analysis plan, so I don't call it a clear drop."))
    if ev.event == "IR-2026":
        j = ide["jump_2026"]
        notes.insert(1, f"The twin rises with the jump of about {j['growth_25q4_to_26q1']['median_donor']:.0%} most economies "
                        f"had this quarter. Of four economies under broad sanctions, Russia, Belarus and Cuba mostly didn't get it "
                        f"and Venezuela did (+{j['growth_25q4_to_26q1']['VE']:.0%}). If Iran had grown like the four on average, "
                        f"or stayed flat, "
                        f"the drop is {-j['flat_counterfactual_pct']:.0%} (flat) to {-j['sanctioned_growth_counterfactual_pct']:.0%} "
                        f"(growing like those economies) instead of {-r['sdid']['pct']:.0%}.")
    return notes


def _one(a, p, ide):
    """The design for one outcome. Returns (result, file stem, card notes), or None if the
    economy has no data for this outcome."""
    from .panel import label, country_name, event_windows
    from .design import run, windows, registry_skip
    if a.event:
        ev = p.events[p.events.event == a.event.upper()]
        if ev.empty:
            raise SpecError(f"no event called {a.event}. `shutdowns events` lists them")
        ev = ev.iloc[0]
        iso2 = ev.iso2
        if iso2 not in p.Y.index:
            return None
        pre, head, path = event_windows(p, ev)
        title, stem, rounded = f"{ev.country}, {ev.event[-4:]}", ev.event, None
    else:
        try:
            iso2 = resolve_economy(p, a.economy)
        except SpecError:
            if a.outcome == "all" and p.outcome != "log_pushes":
                return None
            raise
        first, last, rounded = quarter_range(p, a.start, a.end)
        head = list(range(first, last + 1))
        pre, _, path = windows(p, iso2, head, registry_skip(p, iso2, head))
        when = label(first) + (f" to {label(last)}" if last > first else "")
        title, stem = f"{country_name(iso2)}, {when}", f"{iso2}-{label(first)}" + (f"-{label(last)}" if last > first else "")
    if len(pre) < 4:
        raise SpecError("needs at least 4 quarters before the start to build a twin")
    r = run(p, iso2, head, pre=pre, path=path, donors=p.pool(a.donors, iso2) if a.donors != "all" else None)
    r["name"] = a.name or title
    notes = event_notes(ev, r, ide if a.donors == "all" else None) if a.event else []
    if rounded:
        notes.append(rounded[0].upper() + rounded[1:] + ".")
    return r, f"{a.slug or stem}-{LOG_TO_NAME[p.outcome]}" if (a.slug is None or a.outcome == "all") else a.slug, notes


def _estimate(a):
    from .panel import Panel, load_panel
    from . import report
    if bool(a.event) == bool(a.economy):
        sys.exit("shutdowns: give either --event, or --economy with --start (see `shutdowns estimate --help`)")
    if a.economy and not a.start:
        sys.exit("shutdowns: --economy needs --start, for example --start 2022Q4")
    log = say(a)
    df = load_panel()
    ide = _identification()
    done = []
    for o in (OUTCOMES if a.outcome == "all" else [a.outcome]):
        got = _one(a, Panel(df, outcome=o), ide)
        if got is None:
            print(f"shutdowns: skipping {o}, GitHub doesn't publish it for this economy in every quarter", file=sys.stderr)
            continue
        done.append(got)
    for n in done[0][2] if done else []:
        log("note:", n)
    files = []
    if not a.no_files:
        for r, stem, notes in done:
            files += report.card(r, a.out, r["name"], stem, notes, html=a.html)
        if a.outcome == "all":
            fig = Path(a.out) / f"{done[0][1].rsplit('-', 1)[0]}-outcomes.png"
            report.outcomes_figure([d[0] for d in done], fig, f"{done[0][0]['name']}, all four GitHub counts")
            files.append(fig)
    runs = [d[0] for d in done]
    if a.format == "json":
        body = {"name": runs[0]["name"], **report.slim(runs[0])} if len(runs) == 1 else \
            {LOG_TO_NAME[r["outcome"]]: {"name": r["name"], **report.slim(r)} for r in runs}
        print(json.dumps(body, indent=1, default=float))
    elif a.format == "csv":
        print(report.to_csv([{"economy": r["iso2"], "outcome": LOG_TO_NAME[r["outcome"]], **row}
                             for r in runs for row in report.series_rows(r)]), end="")
    else:
        for r in runs:
            s = r["sdid"]
            print(f"{r['name']}, {report.OUT_NAMES[r['outcome']]}: {s['pct']:+.1%} vs twin "
                  f"(95% {s['lo']:+.1%} to {s['hi']:+.1%}), p {report.pfmt(s['p_normal'])}")
    for f in files:
        log("  wrote", f)
    return 0


def _compare(a):
    from .panel import Panel, load_panel
    from . import compare, report
    log = say(a)
    p = Panel(load_panel(), outcome=a.outcome)
    ra, rb = compare.side(p, a.first, a.donors), compare.side(p, a.second, a.donors)
    d = compare.difference(ra, rb)
    slug = a.slug or f"{ra['label']}-vs-{rb['label']}-{a.outcome}".replace(" ", "")
    files = []
    if not a.no_files:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        png = out / f"{slug}.png"
        report.compare_figure(ra, rb, png)
        (out / f"{slug}.md").write_text(compare.markdown(ra, rb, png.name))
        (out / f"{slug}.json").write_text(json.dumps(
            {"first": report.slim(ra), "second": report.slim(rb), "difference": d}, indent=1, default=float))
        files = [png, out / f"{slug}.md", out / f"{slug}.json"]
    if a.format == "json":
        print(json.dumps({"first": report.slim(ra), "second": report.slim(rb), "difference": d}, indent=1, default=float))
    elif a.format == "csv":
        print(report.to_csv(compare.table(ra, rb)), end="")
    else:
        print(compare.text(ra, rb))
    for f in files:
        log("  wrote", f)
    return 0


def _cards(a):
    from .panel import Panel, event_windows
    from .design import run
    from . import report
    p = Panel()
    ide = _identification()
    done = []
    for _, ev in p.events.iterrows():
        if a.only and ev.event not in a.only:
            continue
        pre, head, pth = event_windows(p, ev)
        r = run(p, ev.iso2, head, pre=pre, path=pth)
        files = report.card(r, a.out, f"{ev.country}, {ev.event[-4:]}", ev.event, event_notes(ev, r, ide), html=a.html)
        done.append((ev, r))
        print(ev.event, f"{r['sdid']['pct']:+.1%}", "->", files[1])
    if done and not a.only:
        lines = ["# Report cards", "", "One card per event in `data/events.csv`. Each has the estimate, the twin, the placebos and the checks.", "",
                 "| Event | Kind | Quarters | Synthetic DiD | 95% interval | Card |", "|---|---|---|---|---|---|"]
        for ev, r in sorted(done, key=lambda x: x[1]["sdid"]["pct"]):
            s = r["sdid"]
            links = f"[md]({ev.event}.md), [pdf]({ev.event}.pdf)" + (f", [html]({ev.event}.html)" if a.html else "")
            lines.append(f"| {ev.country}, {ev.event[-4:]} | {ev.kind} | {', '.join(r['quarters'])} | {report.pct(s['pct'], 1)} | "
                         f"{report.pct(s['lo'])} to {report.pct(s['hi'])} | {links} |")
        (Path(a.out) / "index.md").write_text("\n".join(lines) + "\n")
    return 0


def _table(rows, fmt):
    """Print a list of dicts as an aligned table, json or csv."""
    import pandas as pd
    from . import report
    if fmt == "json":
        print(json.dumps(rows, indent=1, default=str))
    elif fmt == "csv":
        print(report.to_csv(rows), end="")
    else:
        print(pd.DataFrame(rows).to_string(index=False, na_rep="") if rows else "nothing matches")


def _events(a):
    from .registry import load
    ev = load()
    if a.country:
        key = a.country.strip().lower()
        ev = ev[(ev.iso2.str.lower() == key) | ev.country.str.lower().str.contains(key)]
    if a.kind:
        ev = ev[ev.kind == a.kind]
    cols = list(ev.columns) if a.all_columns else \
        ["event", "quarter", "kind", "start_date", "end_date", "networks", "days_low", "days_high"]
    ev = ev[cols].copy()
    if a.results:
        res = ROOT / "results" / "events.json"
        got = {e["event"]: e["sdid"] for e in json.loads(res.read_text())["events"]}
        ev["vs_twin_pct"] = [round(got[e]["pct"] * 100, 1) if e in got else None for e in ev.event]
        ev["lo_pct"] = [round(got[e]["lo"] * 100, 1) if e in got else None for e in ev.event]
        ev["hi_pct"] = [round(got[e]["hi"] * 100, 1) if e in got else None for e in ev.event]
    ev = ev.astype(object).where(ev.notna(), None)
    _table(ev.to_dict("records"), a.format)
    return 0


def _economies(a):
    from .panel import Panel, load_meta, country_name
    p = Panel()
    meta = load_meta()
    hit = set(p.events.iso2)
    rows = []
    for iso2 in p.Y.index:
        rows.append({"iso2": iso2, "country": country_name(iso2), "continent": meta.continent.get(iso2),
                     "income": meta.income_2020.get(iso2),
                     "pushes_latest": int(p.raw(iso2)[-1]), "pushes_min": int(p.min_pushes[iso2]),
                     "donor": iso2 in p.donors, "in_registry": iso2 in hit})
    if a.search:
        key = a.search.strip().lower()
        rows = [r for r in rows if key in " ".join(str(v) for v in (r["iso2"], r["country"], r["continent"], r["income"])).lower()]
    if a.donors:
        rows = [r for r in rows if r["donor"]]
    if a.in_registry:
        rows = [r for r in rows if r["in_registry"]]
    _table(rows, a.format)
    return 0


def _validate(a):
    from .registry import validate
    bad = validate(max_quarter=None)
    for b in bad:
        print("problem:", b)
    print("registry ok" if not bad else f"{len(bad)} problems")
    return 1 if bad else 0


def _refresh(a):
    sys.path.insert(0, str(ROOT / "analysis"))
    import fetch_data
    fetch_data.EXT.mkdir(parents=True, exist_ok=True)
    prov = fetch_data.github(latest=True, write=a.apply)
    new = {f: v for f, v in prov["files"].items() if not v["same_as_repo"]}
    if not new:
        print("no change upstream, data/raw is current")
        return 0
    print("upstream differs for", ", ".join(new), "last quarters", {f: v["last_quarter"] for f, v in new.items()})
    if not a.apply:
        print("rerun with --apply to copy them into data/raw, then rerun `make all`")
        return 0
    for f in new:
        src = fetch_data.EXT / "innovationgraph" / "data" / f"{f}.csv"
        (ROOT / "data" / "raw" / f"{f}.csv").write_bytes(src.read_bytes())
    prov["pinned_commit"] = prov["upstream_head"]
    (ROOT / "data" / "provenance_github.json").write_text(json.dumps(prov, indent=1))
    print("copied; update IG_COMMIT in analysis/fetch_data.py to", prov["upstream_head"], "and rerun `make all`")
    return 0


def parser():
    ap = argparse.ArgumentParser(prog="shutdowns", description=DESCRIPTION, epilog=EPILOG, formatter_class=Fmt)
    ap.add_argument("--version", action="version", version=f"shutdowns {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    def add(name, help, **kw):
        return sub.add_parser(name, help=help, description=help, formatter_class=Fmt, **kw)

    def files(c, out_name, with_html=True):
        c.add_argument("--out", default=str(ROOT / out_name), metavar="DIR", help=f"folder for the files it writes (default {out_name})")
        if with_html:
            c.add_argument("--html", action="store_true", help="also write a self contained HTML card")

    def fmt(c, choices=("text", "json", "csv")):
        c.add_argument("--format", choices=choices, default=choices[0],
                       help=f"what to print, default {choices[0]}. json and csv go to stdout and the status lines to stderr")

    e = add("estimate", "run the full design for one event, or any economy and quarters, and write a report card")
    e.add_argument("--event", help="a registry event id such as IR-2026, run with exactly the windows used in the paper")
    e.add_argument("-e", "--economy", help="two letter code or country name, for example IR or Iran")
    e.add_argument("-s", "--start", help="first affected quarter (2022Q4) or date (2022-09-21, read as the quarter it falls in)")
    e.add_argument("-t", "--end", help="last affected quarter or date, same as --start if left out")
    e.add_argument("-o", "--outcome", default="git_pushes", choices=OUTCOMES + ["all"],
                   help="which GitHub count to measure, or all four with a comparison plot (default git_pushes)")
    e.add_argument("-d", "--donors", default="all", choices=POOLS,
                   help="donor pool, default all (106 economies with no registry event). no_keepiton_shutdown drops every economy with a full network shutdown in the "
                        "Access Now tracker, the others keep the same continent, the same income group, or drop the neighbors")
    files(e, "reports/custom")
    e.add_argument("--no-files", action="store_true", help="print only, write nothing")
    e.add_argument("--name", help="title for the card (default is made from the country and quarters)")
    e.add_argument("--slug", help="file name for the card (default like IR-2022Q4-git_pushes)")
    fmt(e)

    c = add("compare", "put two events side by side with a plot and the difference between them")
    c.add_argument("first", help="registry event id (IR-2026) or ECONOMY:START[:END] such as IR:2022Q4 or MM:2021Q1:2021Q2")
    c.add_argument("second", help="same format as first")
    c.add_argument("-o", "--outcome", default="git_pushes", choices=OUTCOMES, help="which GitHub count to measure (default git_pushes)")
    c.add_argument("-d", "--donors", default="all", choices=POOLS, help="donor pool, same choices as estimate (default all)")
    files(c, "reports/custom", with_html=False)
    c.add_argument("--no-files", action="store_true", help="print only, write nothing")
    c.add_argument("--slug", help="file name for the comparison")
    fmt(c)

    k = add("cards", "write a report card for every event in the registry, plus an index")
    files(k, "reports")
    k.add_argument("--only", nargs="*", metavar="EVENT", help="only these event ids, and no index")

    v = add("events", "list the event registry")
    v.add_argument("--country", help="keep one country, by code or name")
    v.add_argument("--kind", choices=["full", "partial"], help="keep full or partial shutdowns")
    v.add_argument("--all-columns", action="store_true", help="show every column, including what happened and the source")
    v.add_argument("--results", action="store_true", help="add the synthetic DiD estimate from results/events.json")
    fmt(v, ("table", "json", "csv"))

    m = add("economies", "list the economies the panel covers and which can serve as donors")
    m.add_argument("--search", help="keep economies whose code, name, continent or income group contains this text")
    m.add_argument("--donors", action="store_true", help="only economies in the donor pool")
    m.add_argument("--in-registry", action="store_true", help="only economies with an event in the registry")
    fmt(m, ("table", "json", "csv"))

    add("validate", "check the event registry (exits 1 if anything is wrong)")
    r = add("refresh", "look for new Innovation Graph quarters on GitHub")
    r.add_argument("--apply", action="store_true", help="copy new quarters into data/raw, otherwise only report")
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    need_data()
    fn = {"estimate": _estimate, "compare": _compare, "cards": _cards, "events": _events, "economies": _economies,
          "validate": _validate, "refresh": _refresh}[a.cmd]
    try:
        return fn(a) or 0
    except SpecError as err:
        print(f"shutdowns: {err}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
