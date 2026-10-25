# Command line reference

`shutdowns --help` lists the commands and `shutdowns <command> --help` explains every option of one. This page covers what the commands write and how to point them at an event.

## Naming an event

Anywhere a command takes an event it accepts either of these.

* A registry id such as `IR-2026`, case does not matter. It uses the exact windows from the paper. `shutdowns events` lists them.
* An economy with quarters, `--economy Iran --start 2022Q4 --end 2023Q1` for `estimate`, or `IR:2022Q4:2023Q1` for `compare`. The economy is a two letter code or a country name. The quarters can be dates (`2022-09-21`), which are read as the quarter they fall in.

For a custom event, quarters hit by other registry events in the same economy are left out of the pre period, and at least four clean quarters before the start are needed.

## What each command writes

| Command | Files, in `reports/custom/` unless `--out` says otherwise |
|---|---|
| `estimate` | `<slug>.png`, `.md`, `.pdf`, `.json`, plus `.html` with `--html`. With `--outcome all` there is a set per outcome and one `-outcomes.png` |
| `compare` | `<a>-vs-<b>-<outcome>.png`, `.md`, `.json` |
| `cards` | one card per registry event in `reports/`, and `reports/index.md` |

`--no-files` writes nothing and only prints. The default slug looks like `IR-2022Q4-git_pushes`.

## Output formats

`--format json` and `--format csv` go to stdout and the status lines go to stderr, so `shutdowns estimate ... --format csv > file.csv` gives a clean file. Exit code 0 is success, 2 is bad input (the message says what to fix), and `validate` exits 1 when the registry has a problem.

`estimate --format csv` has one row per quarter.

| Column | Meaning |
|---|---|
| `economy`, `outcome` | the treated economy and which count |
| `quarter` | for example 2024Q3 |
| `period` | `before`, `shutdown` or `after` |
| `used_for_twin` | whether the quarter went into building the twin |
| `actual`, `twin` | the count and what the twin predicts |
| `gap_pct` | actual over twin minus one, in percent |
| `band_lo_pct`, `band_hi_pct` | 95% placebo band around the gap, empty before the shutdown |

`estimate --format json` is the same dictionary the cards are written from. The keys most people want are `sdid`, `sc` and `ascm` (each with `pct`, `lo`, `hi`, `p_normal`, `p_perm`), `conformal`, `backdate`, `sensitivity`, `leave_one_out`, `weights` and `series`. Effects named `log` are on the log scale, the `pct` ones are percentages as fractions, so -0.69 is 69% below.

`compare --format json` holds `first`, `second` and `difference`. The difference is the first synthetic DiD effect minus the second on the log scale. Its standard error treats the two as independent, which they are not quite, because both use the same donors.

`events` and `economies` take `--format table`, `json` or `csv`.

## Data location

The package reads the data in `data/` and the SQL in `sql/` relative to the repo, so install it with `pip install -e .` from inside a clone. Outside a clone the commands stop with a message saying so.
