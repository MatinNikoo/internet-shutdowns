# Data card: internet shutdowns and GitHub activity

What's here. Two tables I built for this project, ready to use without running any code.

* `panel.csv` has one row per economy and quarter, 2020Q1 to 2026Q1, 149 economies, 3725 rows. GitHub activity
  (git pushes, developers, repositories, organizations), whether the economy is in the donor pool, which registry
  shutdown (if any) hit that quarter, whether Access Now recorded any full network shutdown there that quarter, OONI
  measurement counts, the OONI share of disrupted days (blank when the baseline is too thin to trust), and region and
  income group.
* `events.csv` is the event registry (dates, full or partial, which networks, day counts, region, a public source for
  every row) with my estimates next to each event.

Where it comes from.

* GitHub Innovation Graph, commit 078fb62, datasheet version 1.0.10. CC0. GitHub places a developer in the
  economy their IP address shows on most days of the quarter, and carries the last location forward on days with no
  activity. So VPN users count wherever the VPN exits. Developers, repositories and organizations are end of quarter
  counts that include inactive accounts. Economies need 100 or more developers doing the activity to be published at
  all, and this panel keeps only economies with every quarter present.
* Access Now KeepItOn shutdown tracker, 2020 to 2025. The flag here is "any record coded as a full network shutdown in
  that quarter", of any scope, so it includes regional and short ones.
* OONI measurement counts (api.ooni.io aggregation endpoint). These are volunteer network tests. Counts swing a lot
  when a heavy volunteer starts or stops, so the disrupted day share is noisy outside very large countries. In quarters
  with no recorded shutdown and a baseline of 5,000 or more tests a day, the share is 1% at the median and 47%
  at the 95th percentile.
* Regions from country_converter, income groups from the World Bank classification via Our World in Data.

Licenses, source by source. The repo's MIT license covers the code only.

* GitHub Innovation Graph columns (git pushes, developers, repositories, organizations) are CC0.
* The Access Now flag (`keepiton_full_network`) is derived from Access Now's KeepItOn data, which they publish under
  CC BY 4.0. Credit Access Now if you reuse it. The 1,418 row extract of the whole tracker in
  `data/keepiton/shutdowns_2020_2025.csv` is the same data, with a few derived columns I added.
* The OONI columns (`ooni_measurements`, `ooni_share_disrupted`) and `data/ooni/daily_measurements.csv.gz` are OONI
  data, CC BY-NC-SA 4.0 (https://github.com/ooni/license/tree/master/data). That means attribution, no commercial
  use, and share alike.
* Wikimedia pageviews (`data/wikimedia/`) are CC0.
* Because `panel.csv` and `events.csv` both carry OONI derived columns, treat both files as CC BY-NC-SA 4.0. Drop the
  OONI columns and the rest is CC0 plus the Access Now flag under CC BY 4.0.

What it's good for. Comparing GitHub activity across economies and quarters, and lining that up with shutdown records.

What it's not good for. National output, productivity or employment. Anything finer than a quarter. Small economies,
where a few accounts move the numbers. Any claim that ignores VPN use.

Rebuild it with `python analysis/release.py` after `make all`.
