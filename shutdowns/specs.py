"""Turning what a person types into economies and quarters."""
import re
from datetime import date

from .panel import OUTCOMES, index, label


class SpecError(ValueError):
    pass


def to_quarter(text):
    """'2026Q1', '2026q1', '2026-01-08' or '2026-01' to a quarter index. Returns (index, was_a_date)."""
    t = text.strip()
    m = re.fullmatch(r"(\d{4})\s*[Qq]([1-4])", t)
    if m:
        return index(f"{m[1]}Q{m[2]}"), False
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", t)
    if m:
        try:
            d = date(int(m[1]), int(m[2]), int(m[3] or 1))
        except ValueError:
            raise SpecError(f"'{text}' is not a real date")
        return index(f"{d.year}Q{(d.month - 1) // 3 + 1}"), True
    raise SpecError(f"can't read '{text}'. Use a quarter like 2026Q1 or a date like 2026-01-08")


def quarter_range(panel, start, end=None):
    """First and last quarter index, plus a note when dates were rounded to whole quarters."""
    a, a_date = to_quarter(start)
    b, b_date = to_quarter(end) if end else (a, False)
    if b < a:
        raise SpecError(f"the end ({end}) is before the start ({start})")
    if a < 0:
        raise SpecError("the data starts in 2020Q1")
    if b >= panel.T:
        raise SpecError(f"the data ends at {panel.labels[-1]}")
    note = None
    if a_date or b_date:
        span = f"{start} to {end}" if end else start
        note = f"the data are quarterly, so {span} is read as {label(a)}" + (f" to {label(b)}" if b > a else "")
    return a, b, note


def resolve_economy(panel, text):
    """An iso2 code or a country name to an economy that is in the panel."""
    import pycountry
    t = text.strip()
    iso2 = t.upper() if len(t) == 2 else None
    if iso2 is None:
        try:
            iso2 = pycountry.countries.lookup(t).alpha_2
        except LookupError:
            raise SpecError(f"no country called '{text}'. Try the two letter code, or `shutdowns economies --search {t.split()[0]}`")
    if iso2 not in panel.Y.index:
        raise SpecError(f"{iso2} is not in the panel for {next(k for k, v in OUTCOMES.items() if v == panel.outcome)}. GitHub has to publish it in "
                        f"every quarter. `shutdowns economies` lists the ones that qualify")
    return iso2
