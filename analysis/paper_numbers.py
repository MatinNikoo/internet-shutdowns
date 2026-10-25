"""Writes every number the paper quotes into paper/numbers.tex (as macros) and the paper's
tables into paper/tables/, straight from results/*.json. The paper never has a number
typed in by hand.

    python analysis/paper_numbers.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper"
R = {n: json.loads((ROOT / "results" / f"{n}.json").read_text())
     for n in ("events", "identification", "outcomes", "exposure", "heterogeneity", "stacked", "discovery",
               "simulations")}
I = {e["event"]: e for e in R["identification"]["events"]}
EVN = {"KZ-2022": "KZ", "SD-2021": "SD", "BD-2024": "BD", "TZ-2025": "TZ", "IR-2025": "IRb", "IR-2026": "IRc",
       "IR-2022": "IRa", "MM-2021": "MM", "PK-2023": "PK"}
NAMES = {"KZ-2022": "Kazakhstan 2022", "SD-2021": "Sudan 2021", "BD-2024": "Bangladesh 2024", "TZ-2025": "Tanzania 2025",
         "IR-2025": "Iran 2025", "IR-2026": "Iran 2026", "IR-2022": "Iran 2022", "MM-2021": "Myanmar 2021",
         "PK-2023": "Pakistan 2023"}
ORDER = ["IR-2026", "MM-2021", "SD-2021", "IR-2022", "IR-2025", "KZ-2022", "TZ-2025", "PK-2023", "BD-2024"]


def pct(x, d=0):
    s = f"{x * 100:.{d}f}"
    return ("$-$" + s[1:] if s.startswith("-") else ("+" + s if x > 0 else s)) + "\\%"


def plain(x, d=0):
    return f"{x * 100:.{d}f}\\%"


def num(x, d=2):
    s = f"{x:.{d}f}"
    return "$-$" + s[1:] if s.startswith("-") else s


def p(x):
    return "$<$0.001" if x < 0.001 else f"{x:.3f}"


def peq(x):
    return "$p<0.001$" if x < 0.001 else f"$p = {x:.3f}$"


def main():
    m = {}

    def put(k, v):
        assert k.isalpha(), k
        m[k] = v

    for ev, k in EVN.items():
        e = I[ev]
        put(f"sdid{k}", pct(e["sdid"]["pct"]))
        put(f"sdidlo{k}", pct(e["sdid"]["lo"]))
        put(f"sdidhi{k}", pct(e["sdid"]["hi"]))
        put(f"sc{k}", pct(e["sc"]["pct"]))
        put(f"ascm{k}", pct(e["ascm"]["pct"]))
        put(f"holm{k}", p(e["p_holm"]))
        put(f"conf{k}", p(e["conformal"]["p"]))
        put(f"confmin{k}", p(e["conformal"]["min_p"]))
        put(f"bdm{k}", num(e["sensitivity"]["breakdown_m"], 1))
    j = R["identification"]["jump_2026"]
    put("jumpmedian", pct(j["growth_25q4_to_26q1"]["median_donor"]))
    put("jumpRU", pct(j["growth_25q4_to_26q1"]["RU"]))
    put("jumpBY", pct(j["growth_25q4_to_26q1"]["BY"]))
    put("jumpCU", pct(j["growth_25q4_to_26q1"]["CU"]))
    put("jumpVE", pct(j["growth_25q4_to_26q1"]["VE"]))
    put("rankRU", str(j["donor_quarter_effects"]["RU"]["rank_from_bottom"]))
    put("rankCU", str(j["donor_quarter_effects"]["CU"]["rank_from_bottom"]))
    put("rankBY", str(j["donor_quarter_effects"]["BY"]["rank_from_bottom"]))
    put("flatIR", pct(j["flat_counterfactual_pct"]))
    put("flatabsIR", plain(-j["flat_counterfactual_pct"]))
    put("sdidabsIRc", plain(-I["IR-2026"]["sdid"]["pct"]))
    put("sancgrowthIR", pct(j["sanctioned_growth_counterfactual_pct"]))
    put("sanctwinIR", pct(j["sanctioned_twin_pct"]))
    put("IRmissfactor", num(I["IR-2026"]["sensitivity"]["bias_to_erase_factor"], 1))
    put("IRworstmiss", pct(I["IR-2026"]["sensitivity"]["worst_miss_log"]))
    nc = R["identification"]["negative_controls"]
    put("ncn", str(nc["n"]))
    put("ncrej", str(nc["rejections"]))
    put("ncallowed", str(nc["allowed"]))
    il = next(c for c in nc["controls"] if c["control"] == "IL-2023")
    put("ncIL", pct(il["pct"]))
    w = [(c["hi"] - c["lo"]) * 100 for c in nc["controls"]]
    put("ncwidthmin", f"{min(w):.0f}")
    put("ncwidthmax", f"{max(w):.0f}")
    put("ncILp", peq(il["p_normal"]))
    v = {x["event"]: x for x in R["identification"]["vpn"]}
    put("vpnmissing", f"{v['IR-2026']['missing_pushes'] / 1000:,.0f}")
    put("vpnexcess", f"{v['IR-2026']['exit_excess'] / 1e6:.1f}")
    put("vpnse", f"{v['IR-2026']['exit_se'] / 1e6:.1f}")
    put("vpnmde", f"{v['IR-2026']['mde_share_of_missing']:.0f}")
    sf = R["identification"]["stock_falls"]
    put("repofallbase", plain(sf["base_rates"]["repositories"]["share_fall_over_2pct"], 1))
    put("orgfallbase", plain(sf["base_rates"]["organizations"]["share_fall_over_2pct"], 1))
    put("repoIR", pct(sf["events"]["IR-2026"]["repositories_2026Q1"]["pct_change"], 1))
    put("orgIR", pct(sf["events"]["IR-2026"]["organizations_2026Q1"]["pct_change"], 1))
    put("devIR", pct(sf["events"]["IR-2026"]["developers_2026Q1"]["pct_change"], 1))
    put("repoMM", pct(sf["events"]["MM-2021"]["repositories_2021Q2"]["pct_change"], 1))
    put("orgMM", pct(sf["events"]["MM-2021"]["organizations_2021Q2"]["pct_change"], 1))
    put("orgBD", pct(sf["events"]["BD-2024"]["organizations_2024Q3"]["pct_change"], 1))
    O = {e["event"]: e["outcomes"] for e in R["outcomes"]["events"]}
    for ev, k in (("IR-2026", "IRc"), ("MM-2021", "MM"), ("SD-2021", "SD")):
        for o, ok in (("developers", "dev"), ("repositories", "repo"), ("organizations", "org")):
            put(f"out{ok}{k}", pct(O[ev][o]["sdid"]["pct"], 1))
    X = R["exposure"]
    XE = {e["event"]: e for e in X["events"]}
    put("ooniIRshare", plain(XE["IR-2026"]["ooni"]["0.5"]["share"]))
    put("ooniIRdays", str(XE["IR-2026"]["ooni"]["0.5"]["disrupted_days"]))
    put("ooniIRbdays", str(XE["IR-2025"]["ooni_runs"][-1][2]))
    put("timingjoint", f"{X['timing']['joint_chance']:.1e}".replace("e-0", "\\times10^{-") + "}")
    nf = X["noise_floor"]
    put("noisebigpfifty", plain(nf["baseline_5000_up"]["p50"], 1))
    put("noisebigpninetyfive", plain(nf["baseline_5000_up"]["p95"]))
    put("noisesmallpninetyfive", plain(nf["baseline_100_1000"]["p95"]))
    put("wikinoisepninetyfive", plain(X["wikimedia_noise_floor"]["p95"]))
    c3 = X["C3"]
    put("cthreebeta", num(c3["beta"]))
    put("cthreelo", num(c3["lo"]))
    put("cthreehi", num(c3["hi"]))
    put("cthreewidth", num(c3["interval_width"]))
    put("cthreewithout", num(c3["without_IR-2026"]["beta"]))
    put("cthreewithoutse", num(c3["without_IR-2026"]["se"]))
    put("cthreedepth", num(c3["depth_version"]["beta"]))
    H = R["heterogeneity"]
    dr = H["dose_response"]
    put("dosebeta", num(dr["beta"]))
    put("doselo", num(dr["lo"]))
    put("dosehi", num(dr["hi"]))
    put("doseinfluence", plain(dr["influence_share"]["IR-2026"]))
    jk = {x["dropped"]: x for x in dr["jackknife"]}
    put("dosewithout", num(jk["IR-2026"]["beta"]))
    put("dosewithoutse", num(jk["IR-2026"]["se"]))
    put("dosedayslo", num(dr["days_uncertainty"]["p2_5"]))
    put("dosedayshi", num(dr["days_uncertainty"]["p97_5"]))
    put("dosebootlo", num(dr["placebo_bootstrap"]["p2_5"]))
    put("doseboothi", num(dr["placebo_bootstrap"]["p97_5"]))
    put("doseintercept", num(dr["with_intercept"]["a"], 3))
    put("doseinterceptse", num(dr["with_intercept"]["se_a"], 3))
    alt = dr["iran_2026_alternatives"]
    put("doseflat", num(alt["flat"]["beta"]))
    put("dosesancgrowth", num(alt["sanctioned_growth"]["beta"]))
    put("dosesanctwin", num(alt["sanctioned_twin"]["beta"]))
    put("plausible", plain(1 - __import__("math").exp(-H["plausible_difference_log"])))
    put("plausiblelog", num(H["plausible_difference_log"]))
    fvp = H["full_vs_partial"]
    put("fvpmdd", num(fvp["mdd"]))
    put("fvpdiff", num(fvp["estimate"]["diff_log"]))
    put("fvpse", num(fvp["estimate"]["se"]))
    put("fvpsize", plain(fvp["curve"][0]["power"], 1))
    d = H["duration"]
    put("durmddzero", num(d["mdd_slope_vs_0"]))
    put("durmddone", num(d["mdd_slope_vs_1"]))
    put("durpower", plain(d["power_at_1_31"]))
    put("durmddonewithout", num(d["mdd_slope_vs_1_without_IR-2026"]))
    b = H["baseline_size"]
    put("sizemdd", num(b["mdd_per_10x"]))
    put("sizeest", num(b["estimate_per_10x"], 3))
    put("sizese", num(b["se"], 3))
    S = R["stacked"]
    st = {r["k"]: r for r in S["study"]}
    put("stackzero", pct(st[0]["mean_pct"]))
    put("stackzerop", peq(st[0]["p"]))
    put("stackmtwo", pct(st[-2]["mean_pct"]))
    put("stackmtwop", peq(st[-2]["p"]))
    put("stackmone", pct(st[-1]["mean_pct"]))
    put("stackmonep", peq(st[-1]["p"]))
    put("stackone", pct(st[1]["mean_pct"]))
    put("stackonep", peq(st[1]["p"]))
    c2 = S["C2"]
    put("ctwo", pct(c2["pooled_pct"]))
    put("ctwolo", pct(c2["lo_pct"]))
    put("ctwohi", pct(c2["hi_pct"]))
    put("ctwoeq", pct(c2["equal_weight"]["pooled_pct"]))
    put("ctwowithout", pct(c2["without_IR-2026"]["pooled_pct"]))
    put("ctwowithoutp", peq(c2["without_IR-2026"]["p"]))
    # permutation p, the 82 donor pool, short pool, c3 variants, jump, short history sims
    for ev, k in (("IR-2026", "IRc"), ("MM-2021", "MM"), ("SD-2021", "SD")):
        e = I[ev]
        put(f"perm{k}", f"{e['sdid']['p_perm']:.3f}")
        put(f"holmperm{k}", f"{e['p_holm_perm']:.3f}")
        q = e["pools"]["no_keepiton_shutdown"]
        put(f"poolpct{k}", pct(q["pct"]))
        put(f"poollo{k}", pct(q["lo"]))
        put(f"poolhi{k}", pct(q["hi"]))
        put(f"poolp{k}", f"{q['p_perm']:.3f}")
    put("holmpermothers", f"{min(e['p_holm_perm'] for k, e in I.items() if k not in ('IR-2026', 'MM-2021', 'SD-2021')):.2f}")
    put("npool", str(I["IR-2026"]["pools"]["no_keepiton_shutdown"]["n_donors"]))
    put("permminp", f"{1 / (R['events']['n_donors'] + 1):.4f}")
    put("holmpermmin", f"{9 / (R['events']['n_donors'] + 1):.3f}")
    put("ethbiggest", str(sum(1 for e in I.values() if e["placebo_extremes"]["top"][0]["iso2"] == "ET")))
    so = R["stacked"]["C2"]["short_only"]
    put("shortpool", pct(so["pooled_pct"], 1))
    put("shortpoollo", pct(so["lo_pct"]))
    put("shortpoolhi", pct(so["hi_pct"]))
    put("shortpoolp", f"{so['p']:.3f}")
    put("shortpooldays", str(so["max_days"]))
    for key, k in (("full_only", "full"), ("event_window_version", "window")):
        put(f"cthree{k}", num(c3[key]["beta"]))
        put(f"cthree{k}lo", num(c3[key]["lo"]))
        put(f"cthree{k}hi", num(c3[key]["hi"]))
    put("cthreewithoutlo", num(c3["without_IR-2026"]["lo"]))
    put("cthreewithouthi", num(c3["without_IR-2026"]["hi"]))
    put("exposurePK", plain(c3["exposure_used"]["PK-2023"]))
    put("exposureIRa", plain(c3["exposure_used"]["IR-2022"]))
    wj = j["what_jumped"]
    put("jumpdev", pct(wj["median_donor_developers"]))
    put("jumpperdev", pct(wj["median_donor_pushes_per_developer"]))
    put("jumpshare", plain(wj["share_donors_over_20pct"]))
    eq = list(wj["earlier_q1_median_pushes"].values())
    put("jumpearlylo", plain(min(eq)))
    put("jumpearlyhi", plain(max(eq)))
    SH = json.loads((ROOT / "results" / "short_history.json").read_text())
    put("shsims", str(SH["sims"]))
    for key, k in (("myanmar_like", "MM"), ("sudan_like", "SD")):
        st_ = SH["settings"][key]
        put(f"shnormal{k}", plain(st_["false_alarm_normal"], 1))
        put(f"shperm{k}", plain(st_["false_alarm_permutation"], 1))
        put(f"shsmall{k}", plain(st_["false_alarm_normal_small_donors"], 1))
    put("MMworstmiss", num(I["MM-2021"]["sensitivity"]["worst_miss_log"], 3))
    put("sizemddrange", num(H["baseline_size"]["mdd_across_range"]))
    put("sizedecades", num(H["baseline_size"]["size_range_decades"]))
    D = R["discovery"]
    nd = {(n["iso2"], n["quarter"]): n for n in D["new"]}
    put("discSDa", pct(nd[("SD", "2024Q1")]["sdid_pct"]))
    put("discSDb", pct(nd[("SD", "2024Q2")]["sdid_pct"]))
    put("discSDse", num(nd[("SD", "2024Q1")]["se"]))
    put("discUG", pct(nd[("UG", "2021Q1")]["sdid_pct"]))
    put("discUA", pct(nd[("UA", "2022Q1")]["sdid_pct"]))
    put("discTG", pct(nd[("TG", "2025Q3")]["sdid_pct"]))
    put("discTGdays", str(nd[("TG", "2025Q3")]["days"]))
    put("discn", str(len(D["new"])))
    put("discexam", str(sum(n["exam"] for n in D["new"])))
    sim = {r["drop"]: r for r in R["simulations"]["summary"]["sdid"]}
    put("simsize", plain(sim[0.0]["power"], 1))
    put("simpowtwenty", plain(sim[0.2]["power"]))
    put("simpowthirtyfive", plain(sim[0.35]["power"]))
    put("simcov", plain(sim[0.0]["coverage"]))
    put("ndonors", str(R["events"]["n_donors"]))
    sd_b = I["SD-2021"]["backdate"]["held_out"]
    ir_b = I["IR-2026"]["backdate"]["held_out"]
    import math
    put("bdSDa", pct(math.expm1(sd_b[0])))
    put("bdSDb", pct(math.expm1(sd_b[1])))
    put("bdIRa", pct(math.expm1(ir_b[0])))
    put("bdIRb", pct(math.expm1(ir_b[1])))
    put("loomaxmove", num(max(e["leave_one_out"]["max_move_se"] for e in I.values())))
    put("nkioexcluded", str(R["events"]["n_donors"] - I["IR-2026"]["pools"]["no_keepiton_shutdown"]["n_donors"]))
    cf = I["IR-2026"]["conformal"]
    put("confloIRc", pct(cf["lo_pct"]))
    put("confhiIRc", pct(cf["hi_pct"]))
    put("confnIRc", str(cf["n_periods"]))
    ch = [e["timing"]["chance_rate"] for e in R["exposure"]["events"] if e.get("timing") and e["kind"] == "full"]
    put("chancemin", plain(min(ch)))
    put("chancemax", plain(max(ch)))
    runs = XE["IR-2026"]["ooni_runs"]
    put("ooniJan", str(runs[0][2]))
    put("ooniMar", str(runs[1][2]))
    import pandas as pd
    sup = pd.read_csv(ROOT / "data" / "raw" / "supplementary" / "git_pushes_weighted_by_profile_economy.csv")
    ip = pd.read_csv(ROOT / "data" / "raw" / "git_pushes.csv")
    # the supplement sums 2025Q3 to 2026Q2, but IP based pushes only go to 2026Q1. stand in
    # 2026Q1 again for the missing 2026Q2 so both sides cover four quarters
    ip = ip[((ip.year == 2025) & (ip.quarter >= 3)) | ((ip.year == 2026) & (ip.quarter == 1))]
    last = ip[ip.year == 2026].set_index("iso2_code").git_pushes
    ip = ip.groupby("iso2_code").git_pushes.agg(["sum", "count"])
    ip["sum"] = ip["sum"] + last.reindex(ip.index).fillna(0)
    sup = sup.set_index("classified_iso2_code").join(ip)
    sup = sup[sup["count"] == 3]
    ratio = sup.pushes / sup["sum"]
    put("chinaratioraw", f"{ratio['CN']:.1f}")
    put("chinaratio", f"{ratio['CN'] / ratio.median():.1f}")
    put("supn", str(len(sup)))
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    (OUT / "numbers.tex").write_text("% written by analysis/paper_numbers.py, do not edit\n" + "\n".join(lines) + "\n")

    # table 1: main estimates and checks
    rows = []
    for ev in ORDER:
        e = I[ev]
        c = e["checks"]
        f2 = "n/a" if c["F2_backdate"] is None else ("pass" if c["F2_backdate"] else "fail")
        rows.append(" & ".join([
            NAMES[ev], e["kind"], pct(e["sdid"]["pct"]), f"{pct(e['sdid']['lo'])} to {pct(e['sdid']['hi'])}",
            pct(e["sc"]["pct"]), pct(e["ascm"]["pct"]), p(e["p_holm"]),
            p(e["conformal"]["p"]) + f" ({e['conformal']['min_p']:.3f})", f2,
            "pass" if c["F3_donors"] else "fail", num(e["sensitivity"]["breakdown_m"], 1),
            "yes" if e["clear_drop"] else ("yes$^\\dagger$" if e.get("passes_all_runnable") else "no")]) + " \\\\")
    (OUT / "tables").mkdir(exist_ok=True)
    (OUT / "tables" / "main.tex").write_text("\n".join(rows) + "\n")

    # table 2: four outcomes
    rows = []
    for ev in ORDER:
        o = O[ev]
        cells = []
        for k in ("git_pushes", "developers", "repositories", "organizations"):
            s = o[k]["sdid"]
            cells.append(pct(s["pct"], 1) + ("$^*$" if s["p_normal"] < 0.05 else ""))
        rows.append(" & ".join([NAMES[ev]] + cells) + " \\\\")
    (OUT / "tables" / "outcomes.tex").write_text("\n".join(rows) + "\n")

    # table 3: negative controls
    rows = []
    for c in sorted(nc["controls"], key=lambda c: c["pct"]):
        rows.append(" & ".join([c["country"].replace("ü", "\\\"u"), c["quarter"], c["kind"], pct(c["pct"]),
                                f"{pct(c['lo'])} to {pct(c['hi'])}", p(c["p_normal"])]) + " \\\\")
    (OUT / "tables" / "controls.tex").write_text("\n".join(rows) + "\n")

    # table 4: exposure and timing
    rows = []
    for ev in ORDER:
        x = XE[ev]
        o = x["ooni"]["0.5"]
        lo_, hi_ = x["registry_days"] or (None, None)
        reg = "partial" if lo_ is None else (f"{lo_:g}" if lo_ == hi_ else f"{lo_:g} to {hi_:g}")
        if not o["usable"]:
            rows.append(f"{NAMES[ev]} & {reg} & \\multicolumn{{3}}{{l}}{{too few OONI tests (baseline {o['baseline']:.0f} a day)}} & \\\\")
            continue
        runs = "; ".join(f"{a[5:]} to {b[5:]}" for a, b, n in x.get("ooni_runs", []) if n >= 3) or "none"
        t = x.get("timing")
        w = x.get("wikimedia") or {}
        wr = "; ".join(f"{a[5:]} to {b[5:]}" for a, b, n in x.get("wikimedia_runs", []) or []) if w.get("usable") else "n/a"
        rows.append(" & ".join([NAMES[ev], reg, str(o["disrupted_days"]), runs,
                                ("yes" if t["ooni_run_in_window"] else "no") + f" ({t['chance_rate']:.2f})", wr]) + " \\\\")
    (OUT / "tables" / "exposure.tex").write_text("\n".join(rows) + "\n")

    # table 5: events found by rule
    rows = []
    for n in D["new"]:
        if n["exam"]:
            continue
        rows.append(" & ".join([n["iso2"], n["quarter"], str(n["days"]), n["cause"], pct(n["sdid_pct"]),
                                num(n["se"]), pct(n["predicted_pct_beta_fit"])]) + " \\\\")
    (OUT / "tables" / "discovery.tex").write_text("\n".join(rows) + "\n")
    print(len(m), "numbers written")


if __name__ == "__main__":
    main()
