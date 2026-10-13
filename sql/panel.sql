-- Builds the country by quarter panel the analysis runs on.
-- Input is GitHub's Innovation Graph (data/raw), output is one row per economy and quarter.

CREATE OR REPLACE TABLE pushes AS
SELECT iso2_code AS iso2, year, quarter, git_pushes
FROM read_csv_auto('data/raw/git_pushes.csv')
WHERE iso2_code IS NOT NULL AND iso2_code <> 'EU';   -- EU is an aggregate, not a country

CREATE OR REPLACE TABLE devs AS
SELECT iso2_code AS iso2, year, quarter, developers
FROM read_csv_auto('data/raw/developers.csv')
WHERE iso2_code IS NOT NULL AND iso2_code <> 'EU';

CREATE OR REPLACE TABLE repos AS
SELECT iso2_code AS iso2, year, quarter, repositories
FROM read_csv_auto('data/raw/repositories.csv')
WHERE iso2_code IS NOT NULL AND iso2_code <> 'EU';

-- quarter index: 2020Q1 = 0
CREATE OR REPLACE TABLE panel AS
SELECT p.iso2,
       (p.year - 2020) * 4 + p.quarter - 1 AS t,
       p.year || 'Q' || p.quarter          AS label,
       p.git_pushes,
       d.developers,
       r.repositories,
       ln(p.git_pushes)                    AS log_pushes,
       ln(r.repositories)                  AS log_repos,
       ln(d.developers)                    AS log_devs
FROM pushes p
LEFT JOIN devs  d USING (iso2, year, quarter)
LEFT JOIN repos r USING (iso2, year, quarter);

-- keep economies seen in every quarter and big enough that the series isn't mostly noise
CREATE OR REPLACE TABLE eligible AS
WITH n AS (SELECT max(t) + 1 AS quarters FROM panel)
SELECT iso2,
       min(git_pushes) AS min_pushes,
       count(*)        AS quarters
FROM panel
GROUP BY iso2
HAVING count(*) = (SELECT quarters FROM n)
   AND count(repositories) = count(*)
   AND count(developers) = count(*);

CREATE OR REPLACE VIEW panel_eligible AS
SELECT panel.*, eligible.min_pushes
FROM panel JOIN eligible USING (iso2)
ORDER BY iso2, t;
