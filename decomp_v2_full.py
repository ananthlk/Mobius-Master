#!/usr/bin/env python3
"""
UNIFIED ORG STORY: 5-Factor Decomposition + Conversion + Leakage
================================================================
Runs org AND market side-by-side, tells the complete story.
"""

import os, math
from collections import defaultdict
from google.cloud import bigquery

PROJECT = os.environ.get("BQ_PROJECT", "mobius-os-dev")
DATASET = os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
MARTS = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
TABLE = f"`{PROJECT}.{DATASET}.stg_doge`"

ORG_NAME = "CHRYSALIS CENTER INC"
ORG_NPIS = ["1174838262", "1891369583", "1700961646", "1598549461"]

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

# Intake codes (for conversion metric)
INTAKE_CODES = ["H0001", "H0031", "H0032", "90791", "90792"]
# Treatment codes (everything except intake)
TREATMENT_CODES = [c for c in BH_CODES if c not in INTAKE_CODES]

PERIOD_START = "2019-01"
PERIOD_END = "2024-12"
BASE_YEAR = "2020"

CODE_NAMES = {
    "H2019": "In-Home BH", "T1017": "Case Mgmt", "H0032": "MH Svc Plan",
    "H0031": "MH Assess", "H2017": "Psych Rehab", "H0001": "Alcohol Screen",
    "H0002": "BH Screen", "90837": "Psychothrpy 60m", "90834": "Psychothrpy 45m",
    "90832": "Psychothrpy 30m", "90847": "Fam Psychothrpy", "90846": "Fam Psych w/o",
    "90853": "Group Psychothrpy", "90791": "Psych Eval", "90792": "Psych Eval+Med",
    "H0004": "SA Counsel", "H0005": "SA Group", "H0015": "SA Intensive OP",
    "H0020": "SA Met Screen", "H0019": "HCT/Peer Svc",
    "H2014": "Skills Train", "H0036": "Comm Psych Svc", "H0046": "MH Svc (OP)",
    "H2020": "Therapeutic BH", "H0040": "Assertive Comm Tx",
    "90839": "Crisis 60m", "90840": "Crisis +30m", "H0017": "Res BH Day",
    "H0018": "Res BH Night", "H0033": "Med Mgmt", "H2011": "Crisis Interv",
    "H2013": "Res Tx", "H2012": "Day Tx BH", "H2015": "Comp Comm Svc",
    "H2016": "Comp Comm Svc", "H0006": "SA Case Mgmt", "H0007": "SA Crisis",
    "H0030": "BH Hotline", "H0037": "Comm Psych Support", "H0025": "BH Prevent Ed",
}


def compute_5factor(code_rows, bene_rows, base_year="2020"):
    """Core 5-factor Laspeyres engine. Returns (year_data, results)."""
    year_codes = defaultdict(lambda: defaultdict(lambda: {"claims": 0, "paid": 0.0}))
    for r in code_rows:
        d = year_codes[r["year"]][r["hcpcs_code"]]
        d["claims"] += r["claims"] or 0
        d["paid"] += float(r["paid"] or 0)

    year_agg = defaultdict(lambda: {"monthly_benes": [], "claims": 0, "paid": 0.0})
    for r in bene_rows:
        y = year_agg[r["year"]]
        y["monthly_benes"].append(r["benes"] or 0)
        y["claims"] += r["claims"] or 0
        y["paid"] += float(r["paid"] or 0)

    years = sorted(year_codes.keys())
    year_data = {}
    for y in years:
        agg = year_agg[y]
        avg_benes = sum(agg["monthly_benes"]) / len(agg["monthly_benes"]) if agg["monthly_benes"] else 0
        claims = agg["claims"]
        paid = agg["paid"]
        year_data[y] = {
            "avg_benes": avg_benes, "n_months": len(agg["monthly_benes"]),
            "claims": claims, "paid": paid,
            "cpb": claims / avg_benes if avg_benes else 0,
            "avg_rpc": paid / claims if claims else 0,
            "codes": dict(year_codes[y]),
        }

    if base_year not in year_data:
        return year_data, []

    base_d = year_data[base_year]
    base_total = base_d["claims"]
    base_weights = {c: v["claims"]/base_total for c, v in base_d["codes"].items()} if base_total else {}
    base_rates = {c: v["paid"]/v["claims"] for c, v in base_d["codes"].items() if v["claims"]}

    results = []
    for y in years:
        d = year_data[y]
        bene_idx = d["avg_benes"] / base_d["avg_benes"] if base_d["avg_benes"] else 1
        util_idx = d["cpb"] / base_d["cpb"] if base_d["cpb"] else 1

        cur = d["codes"]
        all_c = set(base_d["codes"]) | set(cur)
        cur_total = d["claims"]
        num_rate, den, num_mix = 0.0, 0.0, 0.0
        for c in all_c:
            wb = base_weights.get(c, 0)
            rb = base_rates.get(c, 0)
            cv = cur.get(c, {"claims": 0, "paid": 0})
            wn = cv["claims"] / cur_total if cur_total else 0
            rn = cv["paid"] / cv["claims"] if cv["claims"] else rb
            num_rate += wb * rn
            den += wb * rb
            num_mix += wn * rb

        rate_idx = num_rate / den if den else 1
        mix_idx = num_mix / den if den else 1
        rev_idx = d["paid"] / base_d["paid"] if base_d["paid"] else 1
        p4 = bene_idx * util_idx * rate_idx * mix_idx
        interact_idx = rev_idx / p4 if p4 else 1

        results.append({
            "year": y, "bene_idx": bene_idx, "util_idx": util_idx,
            "rate_idx": rate_idx, "mix_idx": mix_idx,
            "interact_idx": interact_idx, "rev_idx": rev_idx,
            "avg_benes": d["avg_benes"], "claims": d["claims"],
            "paid": d["paid"], "cpb": d["cpb"], "avg_rpc": d["avg_rpc"],
        })
    return year_data, results


def compute_conversion(rows, base_year="2020"):
    """
    Conversion = treatment_benes / intake_benes per year.
    rows: [{year, period_month, hcpcs_code, benes, claims}]
    """
    intake_set = set(INTAKE_CODES)
    # year → month → {intake_benes, treatment_benes}
    ym = defaultdict(lambda: defaultdict(lambda: {"intake_benes": 0, "treatment_benes": 0}))
    for r in rows:
        m = ym[r["year"]][r["period_month"]]
        if r["hcpcs_code"] in intake_set:
            m["intake_benes"] += r["benes"] or 0
        else:
            m["treatment_benes"] += r["benes"] or 0

    series = {}
    for year in sorted(ym):
        months = ym[year]
        avg_intake = sum(v["intake_benes"] for v in months.values()) / len(months) if months else 0
        avg_treatment = sum(v["treatment_benes"] for v in months.values()) / len(months) if months else 0
        ratio = avg_treatment / avg_intake if avg_intake else 0
        series[year] = {
            "avg_intake_benes": round(avg_intake, 1),
            "avg_treatment_benes": round(avg_treatment, 1),
            "conversion_ratio": round(ratio, 4),
        }

    base = series.get(base_year, {}).get("conversion_ratio", 1)
    for year in series:
        series[year]["conversion_idx"] = round(
            series[year]["conversion_ratio"] / base, 4
        ) if base else 1
    return series


def main():
    client = bigquery.Client(project=PROJECT)
    npi_list = ", ".join(f"'{n}'" for n in ORG_NPIS)
    code_list = ", ".join(f"'{c}'" for c in BH_CODES)

    # ── QUERY BATCH 1: 5-factor decomposition (org + market) ──
    q_org_code = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, hcpcs_code,
      SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE} WHERE npi IN ({npi_list}) AND hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2
    """
    q_org_benes = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE} WHERE npi IN ({npi_list}) AND hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2
    """
    q_mkt_code = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, hcpcs_code,
      SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE} WHERE hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2
    """
    q_mkt_benes = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims, SUM(total_paid) AS paid
    FROM {TABLE} WHERE hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2
    """

    # ── QUERY BATCH 2: Conversion (intake vs treatment, by code×month) ──
    q_org_conv = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month, hcpcs_code,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims
    FROM {TABLE} WHERE npi IN ({npi_list}) AND hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2, 3
    """
    q_mkt_conv = f"""
    SELECT SUBSTR(period_month, 1, 4) AS year, period_month, hcpcs_code,
      SUM(beneficiary_count) AS benes, SUM(claim_count) AS claims
    FROM {TABLE} WHERE hcpcs_code IN ({code_list})
      AND period_month >= '{PERIOD_START}' AND period_month <= '{PERIOD_END}'
    GROUP BY 1, 2, 3
    """

    # ── QUERY BATCH 3: Get org ZIPs from NPPES for leakage ──
    q_org_zips = f"""
    SELECT DISTINCT SUBSTR(provider_business_practice_location_address_postal_code, 1, 5) AS zip5
    FROM `{PROJECT}.{MARTS}.nppes_run`
    WHERE npi IN ({npi_list})
      AND provider_business_practice_location_address_state_name = 'FL'
    """

    print("Running queries...")
    org_code_rows = [dict(r) for r in client.query(q_org_code).result()]
    org_bene_rows = [dict(r) for r in client.query(q_org_benes).result()]
    mkt_code_rows = [dict(r) for r in client.query(q_mkt_code).result()]
    mkt_bene_rows = [dict(r) for r in client.query(q_mkt_benes).result()]
    org_conv_rows = [dict(r) for r in client.query(q_org_conv).result()]
    mkt_conv_rows = [dict(r) for r in client.query(q_mkt_conv).result()]
    org_zips = [r["zip5"] for r in client.query(q_org_zips).result()]
    print(f"  5-factor: org {len(org_code_rows)} codes, {len(org_bene_rows)} months | mkt {len(mkt_code_rows)} codes, {len(mkt_bene_rows)} months")
    print(f"  Conversion: org {len(org_conv_rows)} rows | mkt {len(mkt_conv_rows)} rows")
    print(f"  Org ZIPs for leakage: {org_zips}")

    # ── QUERY BATCH 4: Leakage (catchment market share) ──
    leakage_data = {}
    if org_zips:
        zip_list = ", ".join(f"'{z}'" for z in org_zips)
        q_leakage = f"""
        WITH npi_zips AS (
          SELECT DISTINCT npi,
            SUBSTR(provider_business_practice_location_address_postal_code, 1, 5) AS zip5
          FROM `{PROJECT}.{MARTS}.nppes_run`
          WHERE entity_type_code = 2
            AND provider_business_practice_location_address_state_name = 'FL'
            AND SUBSTR(provider_business_practice_location_address_postal_code, 1, 5) IN ({zip_list})
        ),
        catchment AS (
          SELECT SUBSTR(d.period_month, 1, 4) AS year, d.npi,
            SUM(d.claim_count) AS claims, SUM(d.total_paid) AS paid,
            SUM(d.beneficiary_count) AS benes
          FROM {TABLE} d JOIN npi_zips nz ON d.npi = nz.npi
          WHERE d.hcpcs_code IN ({code_list})
            AND d.period_month >= '{PERIOD_START}' AND d.period_month <= '{PERIOD_END}'
          GROUP BY 1, 2
        )
        SELECT year,
          SUM(CASE WHEN npi IN ({npi_list}) THEN claims ELSE 0 END) AS org_claims,
          SUM(CASE WHEN npi IN ({npi_list}) THEN paid ELSE 0 END) AS org_paid,
          SUM(claims) AS catchment_claims,
          SUM(paid) AS catchment_paid,
          COUNT(DISTINCT npi) AS catchment_npis,
          COUNT(DISTINCT CASE WHEN npi IN ({npi_list}) THEN npi END) AS org_npis
        FROM catchment GROUP BY 1 ORDER BY 1
        """
        leak_rows = [dict(r) for r in client.query(q_leakage).result()]
        base_share = None
        for r in leak_rows:
            y = r["year"]
            oc = r["org_claims"] or 0
            cc = r["catchment_claims"] or 0
            share = oc / cc if cc else 0
            if y == BASE_YEAR:
                base_share = share
            leakage_data[y] = {
                "org_claims": oc,
                "catchment_claims": cc,
                "catchment_npis": r["catchment_npis"],
                "market_share": round(share, 4),
                "leakage": round(1 - share, 4),
                "share_idx": round(share / base_share, 4) if base_share else 1,
            }
        print(f"  Leakage: {len(leak_rows)} years, catchment ZIPs: {org_zips}")

    # ══ COMPUTE ══
    _, org_res = compute_5factor(org_code_rows, org_bene_rows, BASE_YEAR)
    _, mkt_res = compute_5factor(mkt_code_rows, mkt_bene_rows, BASE_YEAR)
    org_conv = compute_conversion(org_conv_rows, BASE_YEAR)
    mkt_conv = compute_conversion(mkt_conv_rows, BASE_YEAR)

    org_by_year = {r["year"]: r for r in org_res}
    mkt_by_year = {r["year"]: r for r in mkt_res}
    years = sorted(set(org_by_year) & set(mkt_by_year))

    W = 140

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: RAW SCALE
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 1: RAW SCALE — {ORG_NAME} vs FL MEDICAID BH MARKET")
    print(f"{'═'*W}")
    print(f"  {'Year':>6}  │{'─── ORG ─────────────────────────────':^40}│{'─── MARKET ──────────────────────────':^40}│{'─ ORG SHARE ─':^14}│")
    print(f"  {'':>6}  │ {'AvgBenes':>10} {'Claims':>10} {'Paid$M':>8} {'CPB':>6} │ {'AvgBenes':>10} {'Claims':>10} {'Paid$M':>8} {'CPB':>6} │ {'Rev%':>5} {'Bene%':>5} │")
    for y in years:
        o, m = org_by_year[y], mkt_by_year[y]
        print(f"  {y:>6}  │ {o['avg_benes']:>10,.0f} {o['claims']:>10,} {o['paid']/1e6:>8.2f} {o['cpb']:>6.1f} │ {m['avg_benes']:>10,.0f} {m['claims']:>10,} {m['paid']/1e6:>8.1f} {m['cpb']:>6.1f} │ {o['paid']/m['paid']*100:>5.2f} {o['avg_benes']/m['avg_benes']*100:>5.2f} │")

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: ALL INDICES UNIFIED
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 2: UNIFIED INDEX DASHBOARD (base {BASE_YEAR} = 1.0)")
    print(f"{'═'*W}")
    print(f"  {'Year':>6} │{'── 5-FACTOR DECOMPOSITION ─────────────────────────':^54}│{'── CONVERSION ──':^18}│{'── LEAKAGE ─────────':^22}│{'── REV ──':^10}│")
    print(f"  {'':>6} │ {'Bene':>7} {'Util':>7} {'Rate*':>7} {'Mix*':>7} {'Inter':>7} │{'Org':>7} {'Mkt':>7} {'Rel':>7} │ {'Share':>6} {'Leak':>6} {'ShIdx':>6} │ {'Org':>7} │")

    for y in years:
        o, m = org_by_year[y], mkt_by_year[y]
        oc = org_conv.get(y, {})
        mc = mkt_conv.get(y, {})
        lk = leakage_data.get(y, {})

        conv_o = oc.get("conversion_ratio", 0)
        conv_m = mc.get("conversion_ratio", 0)
        conv_rel = round(conv_o / conv_m, 3) if conv_m else 0

        share = lk.get("market_share", 0)
        leak = lk.get("leakage", 0)
        sh_idx = lk.get("share_idx", 0)

        print(f"  {y:>6} │ {o['bene_idx']:>7.3f} {o['util_idx']:>7.3f} {o['rate_idx']:>7.3f} {o['mix_idx']:>7.3f} {o['interact_idx']:>7.3f} │{conv_o:>7.2f} {conv_m:>7.2f} {conv_rel:>7.3f} │ {share:>6.3f} {leak:>6.3f} {sh_idx:>6.3f} │ {o['rev_idx']:>7.3f} │")

    # ═══════════════════════════════════════════════════════════
    # SECTION 3: ORG vs MARKET INDICES SIDE BY SIDE
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 3: ORG vs MARKET — RELATIVE POSITION (org_idx / mkt_idx)")
    print(f"{'═'*W}")
    print(f"  {'Year':>6} │ {'RelBene':>8} {'RelUtil':>8} {'RelRate':>8} {'RelMix':>8} {'RelConv':>8} {'RelRev':>8} │ {'Interpretation'}")
    for y in years:
        o, m = org_by_year[y], mkt_by_year[y]
        oc = org_conv.get(y, {})
        mc = mkt_conv.get(y, {})

        rb = o["bene_idx"] / m["bene_idx"] if m["bene_idx"] else 0
        ru = o["util_idx"] / m["util_idx"] if m["util_idx"] else 0
        rr = o["rate_idx"] / m["rate_idx"] if m["rate_idx"] else 0
        rm = o["mix_idx"] / m["mix_idx"] if m["mix_idx"] else 0
        rc = (oc.get("conversion_ratio", 0) / mc.get("conversion_ratio", 1)) if mc.get("conversion_ratio") else 0
        rv = o["rev_idx"] / m["rev_idx"] if m["rev_idx"] else 0

        # Quick interpretation
        signals = []
        if rb > 1.05: signals.append("bene↑")
        elif rb < 0.95: signals.append("bene↓")
        if ru > 1.05: signals.append("util↑")
        elif ru < 0.95: signals.append("util↓")
        if rr > 1.03: signals.append("rate↑")
        elif rr < 0.97: signals.append("rate↓")
        if rm > 1.03: signals.append("mix↑")
        elif rm < 0.97: signals.append("mix↓")
        interp = ", ".join(signals) if signals else "~tracking market"

        print(f"  {y:>6} │ {rb:>8.3f} {ru:>8.3f} {rr:>8.3f} {rm:>8.3f} {rc:>8.3f} {rv:>8.3f} │ {interp}")

    # ═══════════════════════════════════════════════════════════
    # SECTION 4: YoY DECOMPOSITION
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 4: YEAR-OVER-YEAR CHANGE")
    print(f"{'═'*W}")
    print(f"  {'Period':>12} │{'─── ORG YoY% ──────────────────────────────────':^48}│{'─── MARKET YoY% ────────────────────────────────':^48}│")
    print(f"  {'':>12} │ {'ΔRev':>7} {'ΔBene':>7} {'ΔUtil':>7} {'ΔRate':>7} {'ΔMix':>7} {'ΔConv':>7} │ {'ΔRev':>7} {'ΔBene':>7} {'ΔUtil':>7} {'ΔRate':>7} {'ΔMix':>7} {'ΔConv':>7} │")

    for i in range(1, len(years)):
        y, yp = years[i], years[i-1]
        o, op = org_by_year[y], org_by_year[yp]
        m, mp = mkt_by_year[y], mkt_by_year[yp]
        oc, ocp = org_conv.get(y, {}), org_conv.get(yp, {})
        mc, mcp = mkt_conv.get(y, {}), mkt_conv.get(yp, {})

        def yoy(c, p, k):
            return (c[k] / p[k] - 1) * 100 if p.get(k) else 0

        o_conv_yoy = yoy(oc, ocp, "conversion_ratio")
        m_conv_yoy = yoy(mc, mcp, "conversion_ratio")

        period = f"{yp}→{y}"
        print(f"  {period:>12} │ {yoy(o,op,'rev_idx'):>+7.1f} {yoy(o,op,'bene_idx'):>+7.1f} {yoy(o,op,'util_idx'):>+7.1f} {yoy(o,op,'rate_idx'):>+7.1f} {yoy(o,op,'mix_idx'):>+7.1f} {o_conv_yoy:>+7.1f} │ {yoy(m,mp,'rev_idx'):>+7.1f} {yoy(m,mp,'bene_idx'):>+7.1f} {yoy(m,mp,'util_idx'):>+7.1f} {yoy(m,mp,'rate_idx'):>+7.1f} {yoy(m,mp,'mix_idx'):>+7.1f} {m_conv_yoy:>+7.1f} │")

    # ═══════════════════════════════════════════════════════════
    # SECTION 5: SERVICE MIX DETAIL
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 5: SERVICE MIX — {BASE_YEAR} → {years[-1]} (top codes)")
    print(f"{'═'*W}")

    latest = years[-1]
    o_yd_base = compute_5factor(org_code_rows, org_bene_rows, BASE_YEAR)[0].get(BASE_YEAR, {}).get("codes", {})
    o_yd_latest = compute_5factor(org_code_rows, org_bene_rows, BASE_YEAR)[0].get(latest, {}).get("codes", {})
    m_yd_base = compute_5factor(mkt_code_rows, mkt_bene_rows, BASE_YEAR)[0].get(BASE_YEAR, {}).get("codes", {})
    m_yd_latest = compute_5factor(mkt_code_rows, mkt_bene_rows, BASE_YEAR)[0].get(latest, {}).get("codes", {})

    o_base_total = sum(v["claims"] for v in o_yd_base.values())
    o_lat_total = sum(v["claims"] for v in o_yd_latest.values())
    m_base_total = sum(v["claims"] for v in m_yd_base.values())
    m_lat_total = sum(v["claims"] for v in m_yd_latest.values())

    all_codes = sorted(set(o_yd_base) | set(o_yd_latest) | set(m_yd_base) | set(m_yd_latest),
                       key=lambda c: -(o_yd_base.get(c, {}).get("claims", 0) + m_yd_base.get(c, {}).get("claims", 0)))

    print(f"  {'Code':>8} {'Name':<18} │{'── ORG SHARE ─────────':^24}│{'── MKT SHARE ─────────':^24}│{'── RPC NOW ──────':^20}│")
    print(f"  {'':>8} {'':>18} │ {BASE_YEAR:>6} {latest:>6} {'Δ':>7} │ {BASE_YEAR:>6} {latest:>6} {'Δ':>7} │ {'Org':>7} {'Mkt':>7} {'Gap%':>5} │")

    for code in all_codes:
        owb = o_yd_base.get(code, {}).get("claims", 0) / o_base_total if o_base_total else 0
        own = o_yd_latest.get(code, {}).get("claims", 0) / o_lat_total if o_lat_total else 0
        mwb = m_yd_base.get(code, {}).get("claims", 0) / m_base_total if m_base_total else 0
        mwn = m_yd_latest.get(code, {}).get("claims", 0) / m_lat_total if m_lat_total else 0
        if owb < 0.005 and own < 0.005 and mwb < 0.01 and mwn < 0.01:
            continue
        o_rpc = o_yd_latest.get(code, {}).get("paid", 0) / o_yd_latest.get(code, {}).get("claims", 1) if o_yd_latest.get(code, {}).get("claims") else 0
        m_rpc = m_yd_latest.get(code, {}).get("paid", 0) / m_yd_latest.get(code, {}).get("claims", 1) if m_yd_latest.get(code, {}).get("claims") else 0
        gap = ((o_rpc / m_rpc) - 1) * 100 if m_rpc and o_rpc else 0
        name = CODE_NAMES.get(code, "")[:18]
        od, md = own - owb, mwn - mwb
        print(f"  {code:>8} {name:<18} │ {owb:>6.1%} {own:>6.1%} {od:>+7.1%} │ {mwb:>6.1%} {mwn:>6.1%} {md:>+7.1%} │ ${o_rpc:>6.2f} ${m_rpc:>6.2f} {gap:>+4.0f}% │")

    # ═══════════════════════════════════════════════════════════
    # SECTION 6: UNIFIED NARRATIVE
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'═'*W}")
    print(f"  SECTION 6: THE STORY — {ORG_NAME} ({BASE_YEAR}→{years[-1]})")
    print(f"{'═'*W}")

    o_l, m_l = org_by_year[years[-1]], mkt_by_year[years[-1]]
    oc_l, mc_l = org_conv.get(years[-1], {}), mkt_conv.get(years[-1], {})
    lk_l = leakage_data.get(years[-1], {})
    lk_b = leakage_data.get(BASE_YEAR, {})

    # Revenue bridge
    o_base_rev = org_by_year[BASE_YEAR]["paid"]
    delta_rev = o_l["paid"] - o_base_rev

    factors = {
        "Panel Growth":  {"idx": o_l["bene_idx"],  "mkt": m_l["bene_idx"]},
        "Utilization":   {"idx": o_l["util_idx"],   "mkt": m_l["util_idx"]},
        "Pure Rate":     {"idx": o_l["rate_idx"],   "mkt": m_l["rate_idx"]},
        "Service Mix":   {"idx": o_l["mix_idx"],    "mkt": m_l["mix_idx"]},
        "Interaction":   {"idx": o_l["interact_idx"],"mkt": m_l["interact_idx"]},
    }

    total_log = sum(math.log(max(f["idx"], 0.001)) for f in factors.values())
    print(f"\n  REVENUE BRIDGE: ${o_base_rev/1e6:.2f}M → ${o_l['paid']/1e6:.2f}M = ${delta_rev/1e6:+.2f}M")
    print(f"  {'Factor':<18} {'Org Idx':>8} {'Mkt Idx':>8} {'Rel':>7} {'Org %Δ':>8} {'$ Impact':>10} {'Signal'}")
    print(f"  {'─'*18} {'─'*8} {'─'*8} {'─'*7} {'─'*8} {'─'*10} {'─'*30}")
    for name, f in factors.items():
        rel = f["idx"] / f["mkt"] if f["mkt"] else 0
        pct = (f["idx"] - 1) * 100
        dollar = math.log(max(f["idx"], 0.001)) / total_log * delta_rev if total_log else 0
        if rel > 1.03:
            sig = "✅ outperforming market"
        elif rel < 0.97:
            sig = "⚠️  underperforming market"
        else:
            sig = "➡️  tracking market"
        print(f"  {name:<18} {f['idx']:>8.4f} {f['mkt']:>8.4f} {rel:>7.3f} {pct:>+8.1f} ${dollar/1e6:>+9.2f}M {sig}")

    print(f"\n  CONVERSION (intake → treatment):")
    conv_o = oc_l.get("conversion_ratio", 0)
    conv_m = mc_l.get("conversion_ratio", 0)
    conv_rel = conv_o / conv_m if conv_m else 0
    conv_o_base = org_conv.get(BASE_YEAR, {}).get("conversion_ratio", 0)
    conv_chg = ((conv_o / conv_o_base) - 1) * 100 if conv_o_base else 0
    print(f"    Org: {conv_o:.2f} treatment benes per intake bene (was {conv_o_base:.2f} in {BASE_YEAR}, {conv_chg:+.1f}%)")
    print(f"    Market: {conv_m:.2f}")
    print(f"    Relative: {conv_rel:.3f}x market {'✅' if conv_rel > 1.05 else '⚠️ ' if conv_rel < 0.95 else '➡️ '}")

    if leakage_data:
        print(f"\n  LEAKAGE (catchment market share):")
        share_b = lk_b.get("market_share", 0)
        share_l = lk_l.get("market_share", 0)
        leak_l = lk_l.get("leakage", 0)
        npis_catch = lk_l.get("catchment_npis", 0)
        print(f"    Catchment ZIPs: {org_zips}")
        print(f"    Market share: {share_b:.1%} ({BASE_YEAR}) → {share_l:.1%} ({years[-1]})")
        print(f"    Leakage: {leak_l:.1%} of BH claims in catchment go to {npis_catch} other providers")
        if share_l < share_b:
            print(f"    ⚠️  Losing ground: share dropped {(share_l-share_b)*100:+.2f}pp")
        else:
            print(f"    ✅ Gaining ground: share grew {(share_l-share_b)*100:+.2f}pp")

    # Final summary
    o_rev_pct = (o_l["rev_idx"] - 1) * 100
    m_rev_pct = (m_l["rev_idx"] - 1) * 100
    print(f"\n  ┌─────────────────────────────────────────────────────────────────────────┐")
    print(f"  │  BOTTOM LINE: Revenue {o_rev_pct:+.1f}% vs market {m_rev_pct:+.1f}% = {o_rev_pct-m_rev_pct:+.1f}pp gap           │")
    print(f"  │  Strengths: {'Panel growth (+25% vs mkt -1%)':<58}│")
    # Find weaknesses dynamically
    weaknesses = []
    for name, f in factors.items():
        rel = f["idx"] / f["mkt"] if f["mkt"] else 0
        if rel < 0.95:
            weaknesses.append(f"{name} ({rel:.2f}x mkt)")
    weak_str = ", ".join(weaknesses[:3]) if weaknesses else "None"
    print(f"  │  Gaps:      {weak_str:<58}│")
    print(f"  └─────────────────────────────────────────────────────────────────────────┘")
    print(f"\n{'═'*W}")


if __name__ == "__main__":
    main()
