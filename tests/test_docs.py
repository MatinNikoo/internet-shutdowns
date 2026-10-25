"""The README quotes numbers. Each one here is recomputed from results/ and has to appear
in the README exactly as written, so the text can't drift from the code."""
import json
import math
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
R = {n: json.loads((ROOT / "results" / f"{n}.json").read_text())
     for n in ("identification", "exposure", "heterogeneity", "stacked", "events", "simulations", "short_history")}
I = {e["event"]: e for e in R["identification"]["events"]}
ie_mm = I["MM-2021"]
WORDS = {6: "six", 7: "seven", 8: "eight", 9: "nine"}
EV = pd.read_csv(ROOT / "data" / "events.csv").set_index("event").to_dict("index")


def p(x):
    return f"{round(x * 100):.0f}%"


def s2(x):
    return f"−{abs(x):.2f}" if x < 0 else f"{x:.2f}"


def s(x):
    v = round(x * 100)
    return ("−" if v < 0 else "+") + f"{abs(v)}%" if v else "0%"


def s1(x):
    v = round(x * 100, 1)
    return ("−" if v < 0 else "+") + f"{abs(v):.1f}%"


def holm(x):
    return "<0.001" if x < 0.001 else f"{x:.2f}"


def claims():
    j = R["identification"]["jump_2026"]
    sf = R["identification"]["stock_falls"]
    dr = R["heterogeneity"]["dose_response"]
    c2 = R["stacked"]["C2"]
    c3 = R["exposure"]["C3"]
    ie = I["IR-2026"]
    out = [
        f"{p(-ie['sdid']['pct'])} below its twin (95% interval {p(-ie['sdid']['hi'])} to {p(-ie['sdid']['lo'])})",
        f"or {p(-j['flat_counterfactual_pct'])} below if Iran would have stayed flat",
        f"came in {p(-I['MM-2021']['sdid']['pct'])} below",
        f"Russia {s(j['growth_25q4_to_26q1']['RU'])}, Belarus {s(j['growth_25q4_to_26q1']['BY'])}, Cuba {s(j['growth_25q4_to_26q1']['CU'])}",
        f"Venezuela grew {p(j['growth_25q4_to_26q1']['VE'])}",
        f"That's why I give the range {p(-j['flat_counterfactual_pct'])} to {p(-ie['sdid']['pct'])}",
        f"the median donor was up {p(j['what_jumped']['median_donor_pushes'])}, and {p(j['what_jumped']['share_donors_over_20pct'])} of donors grew by more than 20%",
        f"median growth between {p(min(j['what_jumped']['earlier_q1_median_pushes'].values()))} and {p(max(j['what_jumped']['earlier_q1_median_pushes'].values()))}",
        f"more pushes per developer ({s(j['what_jumped']['median_donor_pushes_per_developer'])}) rather than more developers ({s(j['what_jumped']['median_donor_developers'])})",
        f"the drop is {p(-j['flat_counterfactual_pct'])} to {p(-j['sanctioned_growth_counterfactual_pct'])}",
        f"offline for {R['exposure']['events'][[e['event'] for e in R['exposure']['events']].index('IR-2026')]['ooni']['0.5']['disrupted_days']} days in 2026Q1",
        f"about 1 in {round(1 / R['exposure']['timing']['joint_chance'], -3):,.0f}",
        f"in only {sf['base_rates']['repositories']['share_fall_over_2pct'] * 100:.1f}% of country quarters",
        f"Iran's repositories fell {-sf['events']['IR-2026']['repositories_2026Q1']['pct_change'] * 100:.1f}% and its organizations "
        f"{-sf['events']['IR-2026']['organizations_2026Q1']['pct_change'] * 100:.1f}%",
        f"Myanmar's repositories fell {-sf['events']['MM-2021']['repositories_2021Q2']['pct_change'] * 100:.1f}%",
        f"was {p(-next(c['pct'] for c in R['identification']['negative_controls']['controls'] if c['control'] == 'IL-2023'))} below its twin",
        f"average {p(-c2['pooled_pct'])} below their twins (95% {p(-c2['hi_pct'])} to {p(-c2['lo_pct'])})",
        f"and {p(-c2['without_IR-2026']['pooled_pct'])} without Iran 2026 (p = {c2['without_IR-2026']['p']:.3f})",
        f"{p(dr['influence_share']['IR-2026'])} of the fit is Iran 2026, it's {dr['iran_2026_alternatives']['flat']['beta']:.2f} if Iran missed the jump",
        f"tells 1.3 from 1 only {p(R['heterogeneity']['duration']['power_at_1_31'])} of the time",
        f"still grew {sf['events']['IR-2026']['developers_2026Q1']['pct_change'] * 100:.1f}%",
        f"slope on the log scale is {c3['beta']:.2f} ({c3['lo']:.2f} to {c3['hi']:.2f})",
        f"this one is {c3['interval_width']:.2f} wide",
        f"without it the slope is {c3['without_IR-2026']['beta']:.2f} (−{abs(c3['without_IR-2026']['lo']):.2f} to {c3['without_IR-2026']['hi']:.2f})",
        f"gives {c3['event_window_version']['beta']:.2f} ({c3['event_window_version']['lo']:.2f} to {c3['event_window_version']['hi']:.2f})",
        f"gives {c3['full_only']['beta']:.2f} ({c3['full_only']['lo']:.2f} to {c3['full_only']['hi']:.2f})",
        f"exposure of {p(c3['exposure_used']['PK-2023'])} from OONI",
        f"Iran 2022 gets {p(c3['exposure_used']['IR-2022'])} because",
        f"pool to {s1(c2['short_only']['pooled_pct'])} (95% {s(c2['short_only']['lo_pct'])} to {s(c2['short_only']['hi_pct'])}, p = {c2['short_only']['p']:.3f})",
        f"The four full shutdowns of {max(EV[e]['days_high'] for e in c2['short_only']['events']):.0f} days or less",
        f"the smallest permutation p is 1/{R['events']['n_donors'] + 1}, and times nine events that is {9 / (R['events']['n_donors'] + 1):.2f}",
        f"permutation p is {ie_mm['sdid']['p_perm']:.3f} (2 of {R['events']['n_donors'] + 1}) in the full pool and "
        f"{ie_mm['pools']['no_keepiton_shutdown']['p_perm']:.3f} in the 82 pool",
        f"Ethiopia has the largest placebo gap in {sum(1 for e in I.values() if e['placebo_extremes']['top'][0]['iso2'] == 'ET')} of the 9 windows",
        f"a miss of {ie_mm['sensitivity']['worst_miss_log']:.3f} in logs and a breakdown value of {ie_mm['sensitivity']['breakdown_m']:.1f}",
        f"floor of {ie_mm['conformal']['min_p']:.3f}",
        f"wo quarters before average {s(next(r['mean_pct'] for r in R['stacked']['study'] if r['k'] == -2))} and {s(next(r['mean_pct'] for r in R['stacked']['study'] if r['k'] == -1))}",
        " and ".join(WORDS[r["n_events"]] for r in R["stacked"]["study"] if r["k"] in (-2, -1)) + " events",
        f"estimate is {s2(R['heterogeneity']['full_vs_partial']['estimate']['diff_log'])} (se {R['heterogeneity']['full_vs_partial']['estimate']['se']:.2f})",
        f"estimate is {R['heterogeneity']['baseline_size']['estimate_per_10x']:.3f} (se {R['heterogeneity']['baseline_size']['se']:.3f})",
        f"that comes to {R['heterogeneity']['baseline_size']['mdd_across_range']:.2f}, about the size of a month offline ({R['heterogeneity']['plausible_difference_log']:.2f})",
        f"by {s(math.expm1(I['SD-2021']['backdate']['held_out'][0]))} and {s(math.expm1(I['SD-2021']['backdate']['held_out'][1]))}",
        f"off by {ie['sensitivity']['breakdown_m']:.1f} times the worst miss",
        f"(p = {ie['conformal']['p']:.3f}, the smallest possible)",
        f"could miss {R['identification']['vpn'][0]['mde_share_of_missing']:.0f} times the whole missing amount",
        f"Detectable difference {R['heterogeneity']['full_vs_partial']['mdd']:.2f} in logs",
        f"Detectable difference {R['heterogeneity']['baseline_size']['mdd_per_10x']:.2f} in logs per tenfold size",
        f"({R['events']['n_donors'] - ie['pools']['no_keepiton_shutdown']['n_donors']} of them)",
        f"drop sits right in the shutdown quarter ({s(next(r['mean_pct'] for r in R['stacked']['study'] if r['k'] == 0))}, p < 0.001)",
        f"{R['exposure']['noise_floor']['baseline_100_1000']['p95'] * 100:.0f}% of days at the 95th percentile",
    ]
    for ev in ("IR-2026", "MM-2021", "SD-2021", "IR-2022", "IR-2025", "KZ-2022", "TZ-2025", "PK-2023", "BD-2024"):
        e = I[ev]
        out.append(f"{s(e['sdid']['lo'])} to {s(e['sdid']['hi'])} | {s(e['sc']['pct'])} | {s(e['ascm']['pct'])} | "
                   f"{holm(e['p_holm'])} | {holm(e['p_holm_perm'])} |")
    for k, label in (("IR-2026", "Iran 2026"), ("MM-2021", "Myanmar 2021"), ("SD-2021", "Sudan 2021")):
        q = I[k]["pools"]["no_keepiton_shutdown"]
        out.append(f"| {label} | {s(I[k]['sdid']['pct'])} ({s(I[k]['sdid']['lo'])} to {s(I[k]['sdid']['hi'])}) | "
                   + (f"{s(q['pct'])} ({s(q['lo'])} to {s(q['hi'])}), " if k != "SD-2021" else f"{s(q['pct'])}, ")
                   + f"permutation p {q['p_perm']:.3f} |")
    sim = {r["drop"]: r for r in R["simulations"]["summary"]["sdid"]}
    sc = {r["drop"]: r for r in R["simulations"]["summary"]["sc"]}
    for d in (0.0, 0.1, 0.2, 0.35, 0.5):
        a, b = sim[d], sc[d]
        lead = f"{a['power'] * 100:.1f}% (false alarms)" if d == 0 else f"{round(a['power'] * 100)}%"
        scp = f"{b['power'] * 100:.1f}%" if d == 0 else f"{round(b['power'] * 100)}%"
        out.append(f"| {lead} | {scp} | {round(a['coverage'] * 100)}% |")
    sh = R["short_history"]["settings"]
    out += [f"the false alarm rate is {sh['myanmar_like']['false_alarm_normal'] * 100:.1f}% with the normal p value and "
            f"{sh['myanmar_like']['false_alarm_permutation'] * 100:.1f}% with the permutation p",
            f"it is {sh['sudan_like']['false_alarm_normal'] * 100:.1f}% and {sh['sudan_like']['false_alarm_permutation'] * 100:.1f}%, and "
            f"{sh['sudan_like']['false_alarm_normal_small_donors'] * 100:.1f}% with small donors",
            f"{R['short_history']['sims']} fake events each"]
    return out


@pytest.mark.parametrize("claim", claims())
def test_readme_number_matches_results(claim):
    assert claim in README, claim


TUTORIAL = (ROOT / "docs" / "tutorial.md").read_text()


def printed(args, capsys):
    from shutdowns.cli import main
    assert main(args) == 0
    return capsys.readouterr().out.strip().splitlines()


def test_tutorial_shows_what_the_commands_print(capsys):
    lines = printed(["events", "--country", "iran", "--results"], capsys)
    lines += [x for x in printed(["estimate", "--event", "IR-2026", "--outcome", "all", "--no-files"], capsys)
              if not x.startswith("note:")]
    lines += printed(["compare", "IR-2026", "MM-2021", "--no-files"], capsys)
    lines += printed(["estimate", "-e", "Iran", "-s", "2022-09-21", "-t", "2022-12-31", "--no-files"], capsys)
    for line in lines:
        assert line.rstrip() in TUTORIAL, line


@pytest.mark.parametrize("pool,pct", [("no_keepiton_shutdown", "-68.9%"), ("same_continent", "-70.6%"),
                                      ("same_income", "-67.8%"), ("no_neighbors", "-69.1%")])
def test_tutorial_donor_pool_numbers(pool, pct, capsys):
    out = printed(["estimate", "--event", "IR-2026", "--donors", pool, "--no-files"], capsys)
    assert any(pct in x for x in out) and pct in TUTORIAL


def test_tutorial_card_numbers_match_the_saved_results():
    ie = I["IR-2026"]
    held = ie["backdate"]["held_out"]
    claims = [f"p = {ie['conformal']['p']:.3f}, the smallest it can give with {ie['conformal']['n_periods']} quarters",
              f"misses them by +{round((math.exp(held[0]) - 1) * 100)}% and {round((math.exp(held[1]) - 1) * 100)}%",
              f"{ie['sensitivity']['breakdown_m']:.1f} times worse than the worst miss",
              f"{ie['leave_one_out']['n']} donors with weight over 1%",
              f"between {ie['leave_one_out']['min_pct'] * 100:.1f}% and {ie['leave_one_out']['max_pct'] * 100:.1f}%",
              f"({ie['sdid']['p_perm']:.3f}, one in 107)",
              f"{ie['n_donors']} countries"]
    for c in claims:
        assert c in TUTORIAL, c
