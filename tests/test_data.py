"""The event registry, the outside data and the site export."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns import registry  # noqa: E402
from shutdowns.exposure import exposure, disrupted_runs  # noqa: E402


def test_registry_passes_every_check():
    assert registry.validate(max_quarter="2026Q1") == []


@pytest.mark.parametrize("field,value,msg", [
    ("quarter", "2023Q3", "not in or just before"),
    ("source", "http://example.com", "https link"),
    ("kind", "total", "full or partial"),
    ("days_high", 40, "don't fit"),
    ("networks", "satellite", "networks must be"),
])
def test_registry_catches_bad_rows(field, value, msg):
    ev = registry.load()
    ev.loc[ev.event == "SD-2021", field] = value
    probs = registry.validate(ev, keepiton=False)
    assert any(msg in p for p in probs), probs


def test_registry_needs_an_end_date_or_ongoing():
    ev = registry.load()
    ev.loc[ev.event == "TZ-2025", "end_date"] = np.nan
    assert any("not marked ongoing" in p for p in registry.validate(ev, keepiton=False))


def test_registry_crosscheck_catches_a_made_up_date():
    ev = registry.load()
    ev.loc[ev.event == "KZ-2022", "start_date"] = "2022-03-01"
    assert any("KZ-2022" in p for p in registry.crosscheck_keepiton(ev))


def test_negative_controls_have_sources_and_no_overlap_with_events():
    nc = pd.read_csv(ROOT / "data" / "negative_controls.csv")
    ev = registry.load()
    assert nc.source.str.startswith("https://").all()
    assert not set(nc.iso2) & set(ev.iso2)


def daily(counts, start="2025-01-01", iso2="XX"):
    days = pd.date_range(start, periods=len(counts), freq="D")
    return pd.DataFrame({"iso2": iso2, "day": days, "count": counts})


def test_exposure_finds_a_planted_outage():
    # 91 baseline days at ~1000 a day, then a quarter with a 20 day blackout
    rng = np.random.default_rng(0)
    base = rng.normal(1000, 50, 90 + 1 + 90 + 1)        # 2024Q4 baseline + 2025Q1
    d = daily(base, start="2024-10-01")
    q = d.day.between("2025-01-01", "2025-03-31")
    idx = d.index[q][30:50]
    d.loc[idx, "count"] = 5
    x = exposure(d, "XX", ["2025Q1"])
    assert x["usable"] and x["disrupted_days"] == 20
    assert abs(x["share"] - 20 / 90) < 1e-12
    runs = disrupted_runs(d, "XX", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-03-31"), x["baseline"])
    assert runs == [("2025-01-31", "2025-02-19", 20)]


def test_exposure_refuses_a_thin_baseline():
    d = daily(np.full(200, 30.0), start="2024-10-01")
    assert exposure(d, "XX", ["2025Q1"])["usable"] is False


def test_missing_days_count_as_zero():
    d = daily(np.full(200, 1000.0), start="2024-10-01")
    d = d[~d.day.between("2025-02-01", "2025-02-10")]
    assert exposure(d, "XX", ["2025Q1"])["disrupted_days"] == 10


def test_site_json_keeps_the_format_the_live_page_reads():
    s = json.loads((ROOT / "results" / "site.json").read_text())
    assert set(s) == {"labels", "n_donors", "events", "dose", "power"}
    keys = {"id", "country", "kind", "quarters", "what", "source", "pre", "actual", "twin", "sdid", "sc",
            "naive", "full_stop", "share", "days", "made_of", "drift"}
    for e in s["events"]:
        assert set(e) == keys
        assert set(e["sdid"]) == {"pct", "lo", "hi", "p"}
        assert len(e["actual"]) == len(s["labels"]) == len(e["twin"])
    assert {"beta", "se", "lo", "hi"} <= set(s["dose"])


def test_github_data_matches_the_pinned_upstream_copy():
    p = json.loads((ROOT / "data" / "provenance_github.json").read_text())
    assert all(f["same_as_repo"] for f in p["files"].values())
    assert {f["last_quarter"] for f in p["files"].values()} == {"2026Q1"}
