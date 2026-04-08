#!/usr/bin/env python3
"""
5-Factor Revenue Decomposition (Laspeyres-style) — Org vs Market
================================================================
Rev_idx = Bene_idx × Util_idx × Rate_idx × Mix_idx × Interaction_idx

Where:
  Bene_idx   = monthly_avg_benes_t / monthly_avg_benes_base
  Util_idx   = cpb_t / cpb_base  (claims per bene)
  Rate_idx   = Σ(w_base × rpc_t) / Σ(w_base × rpc_base)  -- pure rate, holding mix constant
  Mix_idx    = Σ(w_t × rpc_base) / Σ(w_base × rpc_base)  -- pure mix, holding rates constant
  Interact   = Rev_idx / (Bene × Util × Rate × Mix)        -- residual compounding
"""

import os
from collections import defaultdict
from google.cloud import bigquery

PROJECT = os.environ.get("BQ_PROJECT", "mobius-os-dev")
DATASET = os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
TABLE = f"`{PROJECT}.{DATASET}.stg_doge`"

ORG_NAME = "CHRYSALIS CENTER INC"
ORG_NPIS = ["1174838262", "1891369583", "1700961646", "1598549461"]

# All BH HCPCS codes
BH_CODES = sorted(set([
    "90832", "90834", "90837", "90839", "90840", "90846", "90847", "90853",
    "90791", "90792",
    "H0030", "H0031", "H2011",
    "H0036", "H0037", "T1017",
    "H2017", "H2014",
    "H0001", "H0002",
    "H0004", "H0005", "H0006", "H0007", "H0015", "H0020",
    "H0019", "H0025", "H0040", "H2012", "H2015", "H2016",
    "H0032", "H0046", "H2019", "H2020",
    "H0017", "H0018", "H2013",
    "H0033",
]))

PERIOD_START = "2019-01"
PERIOD_END = "2024-12"
BASE_YEAR = "2020"

# Friendly names for HCPCS codes
CODE_NAMES = {
    "H2019": "In-Home BH", "T1017": "Case Mgmt", "H0032": "MH Svc Plan",
    "H0031": "MH Assess", "H2017": "Psych Rehab", "H0001": "Alcohol Screen",
    "H0002": "BH Screen", "90837": "Psychothrpy 60m", "90834": "Psychothrpy 45m",
    "90832": "Psychothrpy 30m", "90847": "Fam Psychothrpy", "90846": "Fam Psych w/o",
    "90853": "Group Psychothrpy", "90791": "Psych Eval", "90792": "Psych Eval+Med",
    "H0004": "SA Counsel", "H0005": "SA Group", "H0015": "SA Intensive OP",
    "H0020": "SA Met Screen", "H0019": "HCT/Peer Svc",
    "H0025": "BH Prevent Ed", "H2014": "Skills Train",
    "H0036": "Comm Psych Svc", "H0046": "MH Svc (OP)",
    "H2020": "Therapeutic BH", "H0040": "Assertive Comm Tx",
    "90839": "Crisis 60m", "90840": "Crisis +30m",
    "H0017": "Res BH Day", "H0018": "Res BH Night",
    "H0033": "Med Mgmt", "H2011": "Crisis Interv",
    "H2013": "Res Tx", "H2012": "Day Tx BH",
    "H2015": "Comp Comm Svc", "H2016": "Comp Comm Svc",
    "H0006": "SA Case Mgmt", "H0007": "SA Crisis",
    "H0030": "BH Hotline", "H0037": "Comm Psych Support",
    "H0025": "BH Prevent Ed",
}


def compute_5factor(code_rows, bene_rows, base_year="2020"):
    """
    Given code-level and monthly-bene-level rows,
    compute the 5-factor decomposition.

    Returns: (year_data dict, results list)
    """
    # Build code-level structures per year
    year_codes = defaultdict(lambda: defaultdict(lambda: {"claims": 0, "paid": 0.0}))
    for r in code_rows:
        d = year_codes[r["year"]][r["hcpcs_code"]]
        d["claims"] += r["claims"]
        d["paid"] += float(r["paid"] or 0)

    # Build year-level aggregates (with monthly-avg benes)
    year_agg = defaultdict(lambda: {"monthly_benes": [], "claims": 0, "paid": 0.0})
    for r in bene_rows:
        y = year_agg[r["year"]]
        y["monthly_benes"].append(r["benes"] or 0)
        y["claims"] += r["claims"] or 0
        y["paid"] += float(r["paid"] or 0)

    years = sorted(year_codes.keys())
    base = base_year

    year_data = {}
    for y in years:
        agg = year_agg[y]
        avg_benes = sum(agg["monthly_benes"]) / len(agg["monthly_benes"]) if agg["monthly_benes"] else 0
        n_months = len(agg["monthly_benes"])
        claims = agg["claims"]
        paid = agg["paid"]
        cpb = claims / avg_benes if avg_benes else 0
        avg_rpc = paid / claims if claims else 0
        codes_data = year_codes[y]
        year_data[y] = {
            "avg_benes": avg_benes, "n_months": n_months,
            "claims": claims, "paid": paid, "cpb": cpb,
            "avg_rpc": avg_rpc, "n_codes": len(codes_data), "codes": codes_data,
        }

    if base not in year_data:
        return year_data, []

    base_d = year_data[base]
    base_codes = base_d["codes"]
    base_total_claims = base_d["claims"]

    base_weights = {}
    base_rates = {}
    for code, v in base_codes.items():
        base_weights[code] = v["claims"] / base_total_claims if base_total_claims else 0
        base_rates[code] = v["paid"] / v["claims"] if v["claims"] else 0

    results = []
    for y in years:
        d = year_data[y]
        bene_idx = d["avg_benes"] / base_d["avg_benes"] if base_d["avg_benes"] else 1
        util_idx = d["cpb"] / base_d["cpb"] if base_d["cpb"] else 1

        current_codes = d["codes"]
        all_codes_set = set(base_codes.keys()) | set(current_codes.keys())
        current_total_claims = d["claims"]

        num_rate = 0.0
        den_rate = 0.0
        num_mix = 0.0

        for code in all_codes_set:
            w_base = base_weights.get(code, 0)
            rpc_base = base_rates.get(code, 0)
            cv = current_codes.get(code, {"claims": 0, "paid": 0})
            w_now = cv["claims"] / current_total_claims if current_total_claims else 0
            rpc_now = cv["paid"] / cv["claims"] if cv["claims"] else rpc_base
            num_rate += w_base * rpc_now
            den_rate += w_base * rpc_base
            num_mix += w_now * rpc_base

        rate_idx = num_rate / den_rate if den_rate else 1
        mix_idx = num_mix / den_rate if den_rate else 1
        rev_idx = d["paid"] / base_d["paid"] if base_d["paid"] else 1
        product_4 = bene_idx * util_idx * rate_idx * mix_idx
        interact_idx = rev_idx / product_4 if product_4 else 1

        # Code-level weights for this year
        code_weights = {}
        for code in all_codes_set:
            cv = current_codes.get(code, {"claims": 0, "paid": 0})
            code_weights[code] = {
                "w_base": base_weights.get(code, 0),
                "w_now": cv["claims"] / current_total_claims if current_total_claims else 0,
                "rpc_base": base_rates.get(code, 0),
                "rpc_now": cv["paid"] / cv["claims"] if cv["claims"] else 0,
                "claims": cv["claims"],
                "paid": cv["paid"],
            }

        results.append({
            "year": y,
            "bene_idx": round(bene_idx, 4),
            "util_idx": round(util_idx, 4),
            "rate_idx": round(rate_idx, 4),
            "mix_idx": round(mix_idx, 4),
            "interact_idx": round(interact_idx, 4),
            "rev_idx": round(rev_idx, 4),
            "avg_benes": round(d["avg_benes"], 1),
            "claims": d["claims"],
            "paid": round(d["paid"], 2),
            "cpb": round(d["cpb"], 2),
            "avg_rpc": round(d["avg_rpc"], 2),
            "code_weights": code_weights,
        })

    return year_data, results


def main():
    client = bigquery.Client(project=PROJECT)

    npi_list = ", ".join(f"'{n}'" for n in ORG_NPIS)
    code_list = ", ".join(f"'{c}'" for c in BH_CODES)

    # ── All 4 queries at once ──
    # Org: code-level
    q_org_code = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, hcpcs_code,
      SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE}
    WHERE npi IN ({npi_list}) AND hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2 ORDER BY 1, 2
    """

    # Org: monthly benes
    q_org_benes = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE}
    WHERE npi IN ({npi_list}) AND hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2 ORDER BY 1, 2
    """

    # Market: code-level
    q_mkt_code = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, hcpcs_code,
      SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE}
    WHERE hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2 ORDER BY 1, 2
    """

    # Market: monthly benes
    q_mkt_benes = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE}
    WHERE hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2 ORDER BY 1, 2
    """

    print("Running 4 BQ queries (org code, org benes, market code, market benes)...")
    org_code_rows = [dict(r) for r in client.query(q_org_code).result()]
    org_bene_rows = [dict(r) for r in client.query(q_org_benes).result()]
    mkt_code_rows = [dict(r) for r in client.query(q_mkt_code).result()]
    mkt_bene_rows = [dict(r) for r in client.query(q_mkt_benes).result()]
    print(f"  Org: {len(org_code_rows)} code rows, {len(org_bene_rows)} month rows")
    print(f"  Mkt: {len(mkt_code_rows)} code rows, {len(mkt_bene_rows)} month rows")

    # Compute both decompositions
    org_yd, org_res = compute_5factor(org_code_rows, org_bene_rows, BASE_YEAR)
    mkt_yd, mkt_res = compute_5factor(mkt_code_rows, mkt_bene_rows, BASE_YEAR)

    # Build lookup
    org_by_year = {r["year"]: r for r in org_res}
    mkt_by_year = {r["year"]: r for r in mkt_res}
    years = sorted(set(r["year"] for r in org_res) & set(r["year"] for r in mkt_res))

    W = 130

    # ════════════════════════════════════════════════════════════════
    # SECTION 1: RAW SCALE COMPARISON
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 1: RAW SCALE — {ORG_NAME} vs FL MEDICAID BH MARKET")
    print(f"{'═'*W}")
    print(f"  {'Year':>6}  │{'─── ORG ───────────────────────────────────':^44}│{'─── MARKET ────────────────────────────────':^44}│{'─ ORG SHARE ─':^14}│")
    print(f"  {'':>6}  │ {'Avg Mo Benes':>12}  {'Claims':>10}  {'Paid ($M)':>10}  {'CPB':>6} │ {'Avg Mo Benes':>12}  {'Claims':>10}  {'Paid ($M)':>10}  {'CPB':>6} │ {'Rev %':>6}  {'Bene%':>6}│")
    for y in years:
        o = org_by_year[y]
        m = mkt_by_year[y]
        rev_share = o["paid"] / m["paid"] * 100 if m["paid"] else 0
        bene_share = o["avg_benes"] / m["avg_benes"] * 100 if m["avg_benes"] else 0
        print(f"  {y:>6}  │ {o['avg_benes']:>12,.1f}  {o['claims']:>10,}  {o['paid']/1e6:>10.2f}  {o['cpb']:>6.1f} │ {m['avg_benes']:>12,.1f}  {m['claims']:>10,}  {m['paid']/1e6:>10.2f}  {m['cpb']:>6.1f} │ {rev_share:>5.2f}%  {bene_share:>5.2f}%│")

    # ════════════════════════════════════════════════════════════════
    # SECTION 2: 5-FACTOR INDICES SIDE BY SIDE
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 2: 5-FACTOR INDICES (base {BASE_YEAR} = 1.0000)")
    print(f"{'═'*W}")
    print(f"  {'Year':>6}  │{'────────── ORG ──────────────────────────────':^48}│{'────────── MARKET ──────────────────────────────':^48}│{'── RELATIVE ──────────':^24}│")
    print(f"  {'':>6}  │ {'Bene':>7} {'Util':>7} {'Rate*':>7} {'Mix*':>7} {'Inter':>7} {'Rev':>7} │ {'Bene':>7} {'Util':>7} {'Rate*':>7} {'Mix*':>7} {'Inter':>7} {'Rev':>7} │ {'Rate':>6} {'Mix':>6} {'Rev':>6} │")
    for y in years:
        o = org_by_year[y]
        m = mkt_by_year[y]
        rel_rate = o["rate_idx"] / m["rate_idx"] if m["rate_idx"] else 0
        rel_mix = o["mix_idx"] / m["mix_idx"] if m["mix_idx"] else 0
        rel_rev = o["rev_idx"] / m["rev_idx"] if m["rev_idx"] else 0
        print(f"  {y:>6}  │ {o['bene_idx']:>7.4f} {o['util_idx']:>7.4f} {o['rate_idx']:>7.4f} {o['mix_idx']:>7.4f} {o['interact_idx']:>7.4f} {o['rev_idx']:>7.4f} │ {m['bene_idx']:>7.4f} {m['util_idx']:>7.4f} {m['rate_idx']:>7.4f} {m['mix_idx']:>7.4f} {m['interact_idx']:>7.4f} {m['rev_idx']:>7.4f} │ {rel_rate:>6.3f} {rel_mix:>6.3f} {rel_rev:>6.3f} │")

    # ════════════════════════════════════════════════════════════════
    # SECTION 3: YEAR-OVER-YEAR SIDE BY SIDE
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 3: YEAR-OVER-YEAR % CHANGE")
    print(f"{'═'*W}")
    print(f"  {'Period':>12}  │{'────── ORG YoY % ──────────────────────':^42}│{'────── MARKET YoY % ────────────────────':^42}│{'── DELTA (org−mkt) ──':^24}│")
    print(f"  {'':>12}  │ {'ΔRev':>7} {'ΔBene':>7} {'ΔUtil':>7} {'ΔRate':>7} {'ΔMix':>7} │ {'ΔRev':>7} {'ΔMkt':>7} {'ΔUtil':>7} {'ΔRate':>7} {'ΔMix':>7} │ {'ΔRate':>7} {'ΔMix':>7} {'ΔRev':>7}│")

    for i in range(1, len(years)):
        y, yp = years[i], years[i-1]
        o, op = org_by_year[y], org_by_year[yp]
        m, mp = mkt_by_year[y], mkt_by_year[yp]

        def yoy(curr, prev, key):
            return (curr[key] / prev[key] - 1) * 100 if prev[key] else 0

        o_rev = yoy(o, op, "rev_idx")
        o_bene = yoy(o, op, "bene_idx")
        o_util = yoy(o, op, "util_idx")
        o_rate = yoy(o, op, "rate_idx")
        o_mix = yoy(o, op, "mix_idx")

        m_rev = yoy(m, mp, "rev_idx")
        m_bene = yoy(m, mp, "bene_idx")
        m_util = yoy(m, mp, "util_idx")
        m_rate = yoy(m, mp, "rate_idx")
        m_mix = yoy(m, mp, "mix_idx")

        d_rate = o_rate - m_rate
        d_mix = o_mix - m_mix
        d_rev = o_rev - m_rev

        period = f"{yp}→{y}"
        print(f"  {period:>12}  │ {o_rev:>+7.1f} {o_bene:>+7.1f} {o_util:>+7.1f} {o_rate:>+7.1f} {o_mix:>+7.1f} │ {m_rev:>+7.1f} {m_bene:>+7.1f} {m_util:>+7.1f} {m_rate:>+7.1f} {m_mix:>+7.1f} │ {d_rate:>+7.1f} {d_mix:>+7.1f} {d_rev:>+7.1f}│")

    # ════════════════════════════════════════════════════════════════
    # SECTION 4: SERVICE MIX COMPARISON (org vs market top codes)
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 4: SERVICE MIX COMPOSITION — {BASE_YEAR} vs {years[-1]}")
    print(f"{'═'*W}")

    latest = years[-1]
    o_base_cw = org_by_year[BASE_YEAR]["code_weights"]
    o_latest_cw = org_by_year[latest]["code_weights"]
    m_base_cw = mkt_by_year[BASE_YEAR]["code_weights"]
    m_latest_cw = mkt_by_year[latest]["code_weights"]

    all_codes = sorted(set(o_base_cw.keys()) | set(m_base_cw.keys()),
                       key=lambda c: -(o_base_cw.get(c, {}).get("w_base", 0) + m_base_cw.get(c, {}).get("w_base", 0)))

    print(f"  {'Code':>8} {'Name':<18} │{'─── ORG CLAIM SHARE ────────':^30}│{'─── MARKET CLAIM SHARE ─────':^30}│{'── RPC (Org vs Mkt) ──':^24}│")
    print(f"  {'':>8} {'':>18} │ {BASE_YEAR+' Wt':>8} {latest+' Wt':>8} {'Δ Wt':>8}  │ {BASE_YEAR+' Wt':>8} {latest+' Wt':>8} {'Δ Wt':>8}  │ {'Org RPC':>8} {'Mkt RPC':>8} {'Δ%':>6} │")

    for code in all_codes:
        o_wb = o_base_cw.get(code, {}).get("w_base", 0)
        o_wn = o_latest_cw.get(code, {}).get("w_now", 0)
        m_wb = m_base_cw.get(code, {}).get("w_base", 0)
        m_wn = m_latest_cw.get(code, {}).get("w_now", 0)
        o_rpc = o_latest_cw.get(code, {}).get("rpc_now", 0)
        m_rpc = m_latest_cw.get(code, {}).get("rpc_now", 0)

        # Skip codes with negligible presence in both
        if o_wb < 0.005 and o_wn < 0.005 and m_wb < 0.005 and m_wn < 0.005:
            continue

        o_delta = o_wn - o_wb
        m_delta = m_wn - m_wb
        rpc_gap = ((o_rpc / m_rpc) - 1) * 100 if m_rpc else 0
        name = CODE_NAMES.get(code, "")[:18]

        print(f"  {code:>8} {name:<18} │ {o_wb:>8.4f} {o_wn:>8.4f} {o_delta:>+8.4f}  │ {m_wb:>8.4f} {m_wn:>8.4f} {m_delta:>+8.4f}  │ ${o_rpc:>7.2f} ${m_rpc:>7.2f} {rpc_gap:>+5.1f}% │")

    # ════════════════════════════════════════════════════════════════
    # SECTION 5: NARRATIVE SUMMARY
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 5: NARRATIVE — THE STORY")
    print(f"{'═'*W}")

    o_latest = org_by_year[latest]
    m_latest = mkt_by_year[latest]

    # Build narratives per factor
    narratives = []

    # Bene story
    o_bene_cum = (o_latest["bene_idx"] - 1) * 100
    m_bene_cum = (m_latest["bene_idx"] - 1) * 100
    bene_vs = o_bene_cum - m_bene_cum
    if bene_vs > 5:
        narratives.append(f"  📈 PANEL GROWTH: Org grew benes {o_bene_cum:+.1f}% vs market {m_bene_cum:+.1f}% → outpacing market by {bene_vs:.1f}pp")
    elif bene_vs < -5:
        narratives.append(f"  📉 PANEL DECLINE: Org benes {o_bene_cum:+.1f}% vs market {m_bene_cum:+.1f}% → underperforming market by {abs(bene_vs):.1f}pp")
    else:
        narratives.append(f"  ➡️  PANEL: Org benes {o_bene_cum:+.1f}% vs market {m_bene_cum:+.1f}% → roughly tracking market")

    # Util story
    o_util_cum = (o_latest["util_idx"] - 1) * 100
    m_util_cum = (m_latest["util_idx"] - 1) * 100
    util_vs = o_util_cum - m_util_cum
    if util_vs < -5:
        narratives.append(f"  ⚠️  UTILIZATION DROP: Org CPB {o_util_cum:+.1f}% vs market {m_util_cum:+.1f}% → patients getting fewer visits ({util_vs:+.1f}pp vs market)")
    elif util_vs > 5:
        narratives.append(f"  ✅ UTILIZATION GAIN: Org CPB {o_util_cum:+.1f}% vs market {m_util_cum:+.1f}% → deeper engagement per patient ({util_vs:+.1f}pp vs market)")
    else:
        narratives.append(f"  ➡️  UTILIZATION: Org CPB {o_util_cum:+.1f}% vs market {m_util_cum:+.1f}% → similar trend")

    # Rate story (pure — this is the Medicaid reimbursement environment)
    o_rate_cum = (o_latest["rate_idx"] - 1) * 100
    m_rate_cum = (m_latest["rate_idx"] - 1) * 100
    rate_vs = o_rate_cum - m_rate_cum
    narratives.append(f"  {'✅' if rate_vs > 0 else '⚠️ '} PURE RATE: Org rates {o_rate_cum:+.1f}% vs market {m_rate_cum:+.1f}% (holding mix constant) → {rate_vs:+.1f}pp vs market")
    if abs(rate_vs) > 3:
        narratives.append(f"     ↳ This means the org's specific codes are getting {'better' if rate_vs > 0 else 'worse'} reimbursement than market average")

    # Mix story (pure — this is the strategic positioning question)
    o_mix_cum = (o_latest["mix_idx"] - 1) * 100
    m_mix_cum = (m_latest["mix_idx"] - 1) * 100
    mix_vs = o_mix_cum - m_mix_cum

    # Find biggest mix shifters
    o_shifts = []
    for code in all_codes:
        o_wb = o_base_cw.get(code, {}).get("w_base", 0)
        o_wn = o_latest_cw.get(code, {}).get("w_now", 0)
        rpc_b = o_base_cw.get(code, {}).get("rpc_base", 0)
        delta = o_wn - o_wb
        if abs(delta) > 0.01:
            name = CODE_NAMES.get(code, code)
            direction = "grew" if delta > 0 else "shrank"
            o_shifts.append(f"     ↳ {name} ({code}): {direction} from {o_wb:.1%} → {o_wn:.1%} of claims (${rpc_b:.2f}/claim)")

    if o_mix_cum < -2:
        narratives.append(f"  ⚠️  MIX SHIFT (unfavorable): Org mix {o_mix_cum:+.1f}% vs market {m_mix_cum:+.1f}% → shifting toward lower-rate services")
    elif o_mix_cum > 2:
        narratives.append(f"  ✅ MIX SHIFT (favorable): Org mix {o_mix_cum:+.1f}% vs market {m_mix_cum:+.1f}% → shifting toward higher-rate services")
    else:
        narratives.append(f"  ➡️  MIX: Org mix {o_mix_cum:+.1f}% vs market {m_mix_cum:+.1f}% → stable service composition")
    narratives.extend(o_shifts[:4])

    # Interaction story
    o_inter_cum = (o_latest["interact_idx"] - 1) * 100
    if abs(o_inter_cum) > 2:
        narratives.append(f"  {'⚠️ ' if o_inter_cum < 0 else '📊'} INTERACTION: {o_inter_cum:+.1f}% — compounding effect where rate changes and mix shifts reinforce/offset each other")

    # Revenue bottom line
    o_rev_cum = (o_latest["rev_idx"] - 1) * 100
    m_rev_cum = (m_latest["rev_idx"] - 1) * 100
    rev_vs = o_rev_cum - m_rev_cum
    narratives.append(f"\n  {'📈' if rev_vs > 0 else '📉'} BOTTOM LINE: Org revenue {o_rev_cum:+.1f}% vs market {m_rev_cum:+.1f}% ({rev_vs:+.1f}pp {'outperformance' if rev_vs > 0 else 'underperformance'})")

    # Revenue bridge in $
    o_base_rev = org_by_year[BASE_YEAR]["paid"]
    o_curr_rev = o_latest["paid"]
    delta_rev = o_curr_rev - o_base_rev
    narratives.append(f"     Revenue: ${o_base_rev/1e6:.2f}M ({BASE_YEAR}) → ${o_curr_rev/1e6:.2f}M ({latest}) = ${delta_rev/1e6:+.2f}M")

    # Decompose the $ change
    # Each factor's marginal contribution (multiplicative, so we use log decomposition approximation)
    import math
    factors = {
        "Panel growth": o_latest["bene_idx"],
        "Utilization":  o_latest["util_idx"],
        "Pure rates":   o_latest["rate_idx"],
        "Service mix":  o_latest["mix_idx"],
        "Interaction":  o_latest["interact_idx"],
    }
    total_log = sum(math.log(v) for v in factors.values())
    if total_log != 0 and delta_rev != 0:
        narratives.append(f"     Revenue bridge ({BASE_YEAR}→{latest}):")
        for name, val in factors.items():
            contrib = math.log(val) / total_log * delta_rev
            pct = (val - 1) * 100
            narratives.append(f"       {name:.<20} {pct:>+6.1f}%  →  ${contrib/1e6:>+7.2f}M")

    for n in narratives:
        print(n)

    print(f"\n{'═'*W}")


if __name__ == "__main__":
    main()
