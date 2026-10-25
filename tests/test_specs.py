"""Reading quarters, dates and country names the way the command line does."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shutdowns.panel import Panel  # noqa: E402
from shutdowns.specs import SpecError, quarter_range, resolve_economy, to_quarter  # noqa: E402


@pytest.mark.parametrize("text,idx,was_date", [
    ("2020Q1", 0, False), ("2026q1", 24, False), (" 2022Q4 ", 11, False),
    ("2022-09-21", 10, True), ("2022-10", 11, True), ("2021-12-31", 7, True)])
def test_to_quarter(text, idx, was_date):
    assert to_quarter(text) == (idx, was_date)


@pytest.mark.parametrize("text", ["2022", "Q4 2022", "2022Q5", "2022-13-01", "2022-02-30", "", "last spring"])
def test_to_quarter_rejects_junk(text):
    with pytest.raises(SpecError):
        to_quarter(text)


@pytest.fixture(scope="module")
def panel():
    return Panel()


def test_quarter_range_notes_rounding_only_for_dates(panel):
    assert quarter_range(panel, "2022Q3", "2022Q4") == (10, 11, None)
    a, b, note = quarter_range(panel, "2026-01-08", "2026-03-31")
    assert (a, b) == (24, 24) and "quarterly" in note and note.endswith("2026Q1")
    with pytest.raises(SpecError, match="data ends"):
        quarter_range(panel, "2026Q2")
    with pytest.raises(SpecError, match="starts in 2020Q1"):
        quarter_range(panel, "2019Q4")


def test_resolve_economy_takes_codes_and_names(panel):
    assert resolve_economy(panel, "ir") == "IR"
    assert resolve_economy(panel, "Iran") == "IR"
    assert resolve_economy(panel, "Myanmar") == "MM"
    with pytest.raises(SpecError, match="not in the panel"):
        resolve_economy(panel, "VA")
