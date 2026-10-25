import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.cli import main  # noqa: E402


def test_estimate_writes_a_card_that_matches_the_study(tmp_path):
    assert main(["estimate", "--economy", "IR", "--start", "2022Q4", "--out", str(tmp_path), "--slug", "ir"]) == 0
    for ext in ("md", "pdf", "png", "json"):
        assert (tmp_path / f"ir.{ext}").stat().st_size > 500
    r = json.loads((tmp_path / "ir.json").read_text())
    study = {e["event"]: e for e in json.loads((ROOT / "results" / "events.json").read_text())["events"]}
    # same windows as the study, so the same number
    assert abs(r["sdid"]["pct"] - study["IR-2022"]["sdid"]["pct"]) < 1e-9
    md = (tmp_path / "ir.md").read_text()
    assert "ir.png" in md and "\u2014" not in md and "\u2013" not in md


def test_validate_and_events_run(capsys):
    assert main(["validate"]) == 0
    assert main(["events"]) == 0
    assert "IR-2026" in capsys.readouterr().out


def study():
    return {e["event"]: e for e in json.loads((ROOT / "results" / "events.json").read_text())["events"]}


def test_estimate_event_reproduces_the_study_and_writes_html(tmp_path, capsys):
    assert main(["estimate", "--event", "mm-2021", "--out", str(tmp_path), "--html"]) == 0
    text = capsys.readouterr().out
    r = json.loads((tmp_path / "MM-2021-git_pushes.json").read_text())
    assert abs(r["sdid"]["pct"] - study()["MM-2021"]["sdid"]["pct"]) < 1e-9
    assert r["quarters"] == ["2021Q1", "2021Q2"]
    assert "Myanmar, 2021" in text
    page = (tmp_path / "MM-2021-git_pushes.html").read_text()
    assert "data:image/png;base64," in page and "http://" not in page and "src=\"https" not in page
    assert "\u2014" not in page and "\u2013" not in page


def test_dates_are_read_as_the_quarters_they_fall_in(tmp_path, capsys):
    assert main(["estimate", "-e", "Iran", "-s", "2022-09-21", "-t", "2022-12-31", "--outcome", "developers",
                 "--out", str(tmp_path), "--format", "json"]) == 0
    got = capsys.readouterr()
    r = json.loads(got.out)
    assert r["quarters"] == ["2022Q3", "2022Q4"] and r["outcome"] == "log_devs"
    assert "quarterly" in got.err
    assert (tmp_path / "IR-2022Q3-2022Q4-developers.md").exists()


def test_csv_series_matches_the_json(capsys):
    import io
    import pandas as pd
    assert main(["estimate", "-e", "BD", "-s", "2024Q3", "--no-files", "--format", "csv"]) == 0
    df = pd.read_csv(io.StringIO(capsys.readouterr().out))
    assert list(df.columns)[:6] == ["economy", "outcome", "quarter", "period", "used_for_twin", "actual"]
    assert len(df) == 25 and set(df.economy) == {"BD"}
    shut = df[df.period == "shutdown"]
    assert list(shut.quarter) == ["2024Q3"]
    assert (df.loc[df.period == "before", "band_lo_pct"].isna()).all()
    assert (df.actual > 0).all() and (df.twin > 0).all()
    assert abs(shut.gap_pct.iloc[0] / 100 - (shut.actual.iloc[0] / shut.twin.iloc[0] - 1)) < 0.01


def test_all_outcomes_writes_four_cards_and_one_comparison(tmp_path, capsys):
    assert main(["estimate", "-e", "IR", "-s", "2026Q1", "--outcome", "all", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    for o in ("git pushes", "developers", "repositories", "organizations"):
        assert o in out
    names = {f.name for f in tmp_path.iterdir()}
    assert {"IR-2026Q1-outcomes.png", "IR-2026Q1-organizations.md", "IR-2026Q1-git_pushes.pdf"} <= names


def test_bad_input_gives_a_message_and_exit_code_2(capsys):
    for args, word in ((["estimate", "-e", "ZZ", "-s", "2022Q4"], "not in the panel"),
                       (["estimate", "-e", "Atlantis", "-s", "2022Q4"], "no country"),
                       (["estimate", "-e", "IR", "-s", "2026Q2"], "data ends"),
                       (["estimate", "-e", "IR", "-s", "2022Q4", "-t", "2022Q2"], "before the start"),
                       (["estimate", "-e", "IR", "-s", "22Q4"], "can't read"),
                       (["estimate", "-e", "IR", "-s", "2020Q3"], "at least 4"),
                       (["estimate", "--event", "XX-1999"], "no event"),
                       (["compare", "IR-2026", "nonsense"], "neither a registry event")):
        assert main(args + ["--no-files"]) == 2, args
        assert word in capsys.readouterr().err, args


def test_estimate_needs_one_way_to_say_which_event():
    for args in (["estimate"], ["estimate", "--event", "IR-2026", "-e", "IR"], ["estimate", "-e", "IR"]):
        with pytest.raises(SystemExit):
            main(args)


def test_compare_difference_is_the_gap_between_the_two_effects(tmp_path, capsys):
    assert main(["compare", "IR-2026", "MM:2021Q1:2021Q2", "--out", str(tmp_path), "--format", "json"]) == 0
    d = json.loads(capsys.readouterr().out)
    a, b = d["first"]["sdid"], d["second"]["sdid"]
    assert abs(d["difference"]["log"] - (a["log"] - b["log"])) < 1e-12
    assert abs(d["difference"]["se"] - (a["se"] ** 2 + b["se"] ** 2) ** .5) < 1e-12
    assert d["difference"]["lo"] < d["difference"]["pct"] < d["difference"]["hi"]
    # the custom spec is the same windows as the registry event
    assert abs(b["pct"] - study()["MM-2021"]["sdid"]["pct"]) < 1e-9
    assert {f.suffix for f in tmp_path.iterdir()} == {".png", ".md", ".json"}
    assert "Difference in the synthetic DiD effect" in (next(tmp_path.glob("*.md"))).read_text()


def test_compare_csv_has_one_row_per_side(capsys):
    assert main(["compare", "KZ-2022", "TZ-2025", "--no-files", "--format", "csv"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3 and lines[0].startswith("event,outcome")


def test_events_filters_and_formats(capsys):
    assert main(["events", "--country", "iran", "--kind", "full", "--format", "json", "--results"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {r["event"] for r in rows} == {"IR-2025", "IR-2026"}
    assert all(r["lo_pct"] < r["vs_twin_pct"] < r["hi_pct"] for r in rows)
    assert main(["events", "--format", "csv", "--all-columns"]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("event,iso2,country")


def test_economies_search_and_donor_filter(capsys):
    assert main(["economies", "--search", "iran", "--format", "json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r["iso2"] for r in rows] == ["IR"] and rows[0]["donor"] is False and rows[0]["in_registry"] is True
    assert main(["economies", "--donors", "--format", "csv"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 107


def test_help_describes_every_option():
    from shutdowns.cli import parser
    ap = parser()
    subs = next(a for a in ap._actions if hasattr(a, "choices") and isinstance(a.choices, dict)).choices
    assert set(subs) == {"estimate", "compare", "cards", "events", "economies", "validate", "refresh"}
    for name, sp in subs.items():
        for act in sp._actions:
            assert act.help, f"{name} {act.option_strings or act.dest} has no help text"


def test_version_flag(capsys):
    import shutdowns
    with pytest.raises(SystemExit):
        main(["--version"])
    assert shutdowns.__version__ in capsys.readouterr().out
