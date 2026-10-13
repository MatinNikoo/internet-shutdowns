"""Packs the results into one small json for the interactive page on my site."""
import json
from pathlib import Path

import pycountry

ROOT = Path(__file__).resolve().parents[1]


def name(iso2):
    c = pycountry.countries.get(alpha_2=iso2)
    if c is None:
        return iso2
    n = getattr(c, "common_name", None) or c.name
    return n.split(",")[0].replace(" (Plurinational State of)", "")


def r(x, k=4):
    return round(float(x), k)


def main():
    E = json.loads((ROOT / "results" / "events.json").read_text())
    S = json.loads((ROOT / "results" / "simulations.json").read_text())
    events = []
    for e in E["events"]:
        events.append({
            "id": e["event"], "country": e["country"], "kind": e["kind"], "quarters": e["quarters"],
            "what": e["what"], "source": e["source"], "pre": e["pre_quarters"],
            "actual": [round(v) for v in e["series"]["actual"]],
            "twin": [round(v) for v in e["series"]["twin"]],
            "sdid": {k: r(e["sdid"][k]) for k in ("pct", "lo", "hi", "p")},
            "sc": r(e["sc"]["pct"]),
            "naive": {k: r(v) for k, v in e["naive"].items()},
            "full_stop": r(e["full_stop_pct"]) if "full_stop_pct" in e else None,
            "share": [r(e["share_low"]), r(e["share_high"])] if "share_low" in e else None,
            "days": [e["days_low"], e["days_high"]] if "days_low" in e else None,
            "made_of": [{"name": name(d["iso2"]), "w": r(d["weight"], 3)} for d in e["twin_made_of"]],
            "drift": {k: {kk: r(v[kk]) for kk in ("pct", "lo", "hi")} for k, v in e["location_drift"].items()},
        })
    out = {
        "labels": E["labels"], "n_donors": E["n_donors"], "events": events,
        "dose": {k: (r(v) if isinstance(v, float) else v) for k, v in E["dose_response"].items()},
        "power": [{"drop": x["drop"], "sdid": r(x["power"], 3),
                   "sc": r(y["power"], 3), "coverage": r(x["coverage"], 3)}
                  for x, y in zip(S["summary"]["sdid"], S["summary"]["sc"])],
    }
    (ROOT / "results" / "site.json").write_text(json.dumps(out, separators=(",", ":")))
    print("site.json", len(json.dumps(out)), "bytes")


if __name__ == "__main__":
    main()
