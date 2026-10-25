The [`git_pushes_weighted_by_profile_economy.csv`](./git_pushes_weighted_by_profile_economy.csv) and [`git_pushes_weighted_by_profile_economy_per_capita.csv`](./git_pushes_weighted_by_profile_economy_per_capita.csv) datasets were prepared for the [Global Digital Collaboration Conference 2026 (GDC26)](https://globaldigitalcollaboration.org/gdc26?day=sept-1), 1-3 September in Geneva, to inform the D5 and D10 rankings.

Note: the rankings are not reproducible from the other datasets in this repo alone, as they rely on additional data sources and processing steps that are not included here.

## Methodology

Git pushes from each economy were summed across Q3 2025 + Q4 2025 + Q1 2026 + Q2 2026. To adjust for biases caused by VPN usage, LLM classification was used to extract the [ISO 3166-1 alpha-2 code](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) from the profiles of GitHub users who contributed git pushes during this period, which were then used to construct ratios of ISO 3166-1 alpha-2 codes based on profile location vs. ISO 3166-1 alpha-2 codes based on IP address. These ratios were then used to weight the git pushes from each economy.

The per capita dataset was produced using the latest available data for population ages 15-64 from the World Bank: [SP.POP.1564.TO, World Population Prospects, United Nations (UN), UN Population Division; Staff estimates, World Bank (WB)](https://data.worldbank.org/indicator/SP.POP.1564.TO). Microstates, [defined by the International Monetary Fund (IMF) as economies with a population of less than 200,000](https://www.elibrary.imf.org/view/journals/007/2024/035/article-A001-en.xml), were excluded from the per capita dataset.
