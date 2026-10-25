# Tutorial, one event from start to finish

This walks through Iran in early 2026 with the command line, the way I would hand it to a journalist or a researcher who has never opened the repo. It takes about ten minutes. Every number below is what the commands print on the data in this repo.

## Set up

Clone the repo and install it from inside the clone, so the data stays next to the code.

```bash
pip install -r requirements.txt
pip install -e .
shutdowns --version
```

If you don't want the `shutdowns` command, `python -m shutdowns` does the same thing from the repo folder.

## Pick an event

The registry has nine events. I start by looking at the ones for Iran, with the estimate I published next to each.

```bash
shutdowns events --country iran --results
```

```
  event quarter    kind start_date   end_date         networks  days_low  days_high  vs_twin_pct  lo_pct  hi_pct
IR-2025  2025Q2    full 2025-06-17 2025-06-25 fixed and mobile       7.0        9.0        -17.8   -35.4     4.6
IR-2026  2026Q1    full 2026-01-08            fixed and mobile      48.0       58.0        -69.0   -75.6   -60.6
IR-2022  2022Q4 partial 2022-09-21 2022-10-15           mobile                             -22.0   -43.1     6.9
```

Iran 2026 is the big one. If you want an economy that isn't in the registry, `shutdowns economies --search` finds the code and tells you whether it can be a donor.

## Run it

```bash
shutdowns estimate --event IR-2026
```

```
Iran, 2026, git pushes: -69.0% vs twin (95% -75.6% to -60.6%), p <0.001
  wrote reports/custom/IR-2026-git_pushes.png
  wrote reports/custom/IR-2026-git_pushes.md
  wrote reports/custom/IR-2026-git_pushes.pdf
  wrote reports/custom/IR-2026-git_pushes.json
```

Three lines of notes print before that. They come from the paper and say how the number fits the analysis plan. The first line is the answer. The git pushes GitHub places in Iran in 2026Q1 are 69% below what a synthetic twin predicts, and the interval runs from 76% to 61% below. Add `--html` to get a single page you can email, with the figure inside it.

## Read the card

Open `reports/custom/IR-2026-git_pushes.png`. It has three panels.

* Left. Iran's actual pushes against the twin, a weighted mix of 106 countries that had no shutdown in my registry. The twin stays near Iran's line until the shaded quarter, then the two split.
* Middle. The gap between the two lines. Dots before the shaded quarter show how far off the twin usually is, and the blue band is how far off it would be by chance, from running the same method on every donor.
* Right. Every donor given a fake shutdown. Iran's gap sits far outside that crowd, which is what the small permutation p value (0.009, one in 107) says.

The markdown and PDF cards add four checks, and the numbers to look at are these.

* The conformal test gives p = 0.045, the smallest it can give with 22 quarters.
* Holding out the last two quarters before the shutdown, the twin misses them by +2% and -15%, both inside the placebo band.
* The twin's path would have to be 3.4 times worse than the worst miss in Iran's own past before the result goes away.
* Leaving out each of the 31 donors with weight over 1% in turn keeps the answer between -69.2% and -68.7%.

## Ask whether the donors are doing it

The twin is only as good as the countries it is built from, so I change them.

```bash
shutdowns estimate --event IR-2026 --donors no_keepiton_shutdown --no-files
shutdowns estimate --event IR-2026 --donors same_continent --no-files
shutdowns estimate --event IR-2026 --donors same_income --no-files
shutdowns estimate --event IR-2026 --donors no_neighbors --no-files
```

They give -68.9%, -70.6%, -67.8% and -69.1%. The first drops every country with a full network shutdown in the Access Now tracker, the next two keep only donors on the same continent or in the same income group, and the last drops the neighbors. Nothing moves the answer by more than a couple of points.

## Look at the other counts

```bash
shutdowns estimate --event IR-2026 --outcome all --no-files
```

```
Iran, 2026, git pushes: -69.0% vs twin (95% -75.6% to -60.6%), p <0.001
Iran, 2026, developers: -6.4% vs twin (95% -9.0% to -3.7%), p <0.001
Iran, 2026, repositories: -9.4% vs twin (95% -12.9% to -5.7%), p <0.001
Iran, 2026, organizations: -8.8% vs twin (95% -16.0% to -0.9%), p 0.030
```

Without `--no-files` this also writes a plot with all four intervals. Pushes fall far more than the other three counts. Repository and organization counts almost never shrink, so a gap that shows up in them is worth noticing. The README covers what it could mean. My best guess is that some of the activity moved to other countries along with the VPN users, but I can't test that.

## Put it next to another event

```bash
shutdowns compare IR-2026 MM-2021
```

```
IR-2026: -69.0% vs twin (95% -76% to -61%), p <0.001, 21 quarters before, 106 donors
MM-2021: -56.4% vs twin (95% -69% to -39%), p <0.001, 4 quarters before, 106 donors
Difference: -28.8% (95% -53% to +7%), p 0.102
The difference treats the two estimates as independent. They share donors, so the interval is a bit narrow.
```

The plot puts both gaps on one time axis, counted in quarters from the first shutdown quarter. Iran's drop looks larger, but the interval for the difference includes zero, so I can't tell the two apart. Myanmar also has only four quarters of history before the coup, which makes its twin much weaker than Iran's.

## Try your own dates

Any economy in the panel, any quarters. Dates work too and are read as the quarter they fall in, because the data are quarterly.

```bash
shutdowns estimate --economy Iran --start 2022-09-21 --end 2022-12-31
```

```
note: The data are quarterly, so 2022-09-21 to 2022-12-31 is read as 2022Q3 to 2022Q4.
Iran, 2022Q3 to 2022Q4, git pushes: -5.7% vs twin (95% -35.0% to +36.8%), p 0.757
```

That is a different question from the registry's Iran 2022 (which counts 2022Q4 alone and gets -22%), and the interval shows how little a two quarter window can tell you here. A shutdown of a few days inside a quarter mostly can't be seen in quarterly data. I measured how often the method catches planted drops of different sizes, and the table is in the README.

## Take the numbers into your own tools

`--format csv` prints the quarterly series, and `--format json` prints everything the card is made from.

```bash
shutdowns estimate --economy BD --start 2024Q3 --no-files --format csv > bd.csv
```

```python
import pandas as pd
import matplotlib.pyplot as plt

d = pd.read_csv("bd.csv")
ax = d.plot(x="quarter", y=["actual", "twin"], figsize=(8, 3.5))
ax.set_ylabel("git pushes")
plt.savefig("bd.png", dpi=150)
```

The csv has one row per quarter with the actual count, the twin, the gap in percent, and the placebo band for the quarters after the start. Columns are listed in [cli.md](cli.md).

## What not to conclude

The number is the change in GitHub activity placed in a country by IP address. It is not lost work, and it is not an effect of the shutdown alone, because shutdowns come with protests, wars and coups. The README has the full list of limits, and the paper has the checks.
