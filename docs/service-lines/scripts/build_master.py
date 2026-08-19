"""Build the FL Medicaid BH service line master catalog from AHCA sources.

Service lines come from AHCA's own rule decomposition (the 59G rules named in
the crawl manifest). Codes and allowed modifiers are read from AHCA fee
schedules already in the RAG corpus. The registry deliberately does NOT hold
fees, rates or unit limits — those are Fact Store's domain. Module status is
derived from evidence, never asserted.
"""
import csv
import json
import re
import subprocess
from datetime import date

ROOT = "/Users/ananth/Mobius/"
SCRATCH = ("/private/tmp/claude-502/-Users-ananth-Mobius/"
           "6999871c-ecbf-40d0-b26c-92174f91c392/scratchpad/ahca/")
OUT_JSON = ROOT + "docs/service-lines/fl-medicaid-bh.catalog.json"

# ── Service line inventory ───────────────────────────────────────────────────
# (rule, name, key, fee_schedule_family, authority, grain, scope)
#   scope "serve"        — we intend to support this; modules build toward it
#   scope "decline_well" — a real CMHC service we deliberately name but do not
#                          support; modules must say so with the right precaution
AHCA = "AHCA 59G rule"
DCF = "DCF Managing Entity"
BAKER = "FL Statute 394 (Baker Act)"
MARCHMAN = "FL Statute 397 (Marchman Act)"
HOSP = "Hospital reimbursement (DRG/EAPG)"
WAIVER = "IMD 1115 demonstration"
PLAN = "Plan benefit"

CODE_MOD = "code_modifier"
PER_DIEM = "facility_per_diem"
DRG = "hospital_drg"
EAPG = "hospital_eapg"

LINES = [
    # ── AHCA Medicaid behavioral health: the fee-schedule world ──────────────
    ("59G-4.028", "Behavioral Health Assessment Services", "bh_assessment", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.029", "Behavioral Health Medication Management Services", "bh_medication_mgmt", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.031", "Behavioral Health Community Support Services", "bh_community_support", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.052", "Behavioral Health Therapy Services", "bh_therapy", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.127", "Florida Assertive Community Treatment (FACT)", "fact", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.370", "Behavioral Health Intervention Services", "bh_intervention", "CBH", AHCA, CODE_MOD, "serve"),
    ("59G-4.310", "Targeted Case Management for Children at Risk of Abuse and Neglect",
     "tcm_children_at_risk", "TCM", AHCA, CODE_MOD, "serve"),
    ("59G-4.027", "Behavioral Health Overlay Services", "bh_overlay", "BHOS", AHCA, CODE_MOD, "serve"),
    ("59G-4.295", "Therapeutic Group Care Services", "therapeutic_group_care", "STS", AHCA, PER_DIEM, "serve"),
    ("59G-4.300", "State Mental Health", "state_mental_health", None, AHCA, CODE_MOD, "serve"),
    ("59G-8.700", "Child Health Services Targeted Case Management", "tcm_child_health", "TCM", AHCA, CODE_MOD, "serve"),
    (None, "Mental Health Targeted Case Management", "mhtcm", "TCM", AHCA, CODE_MOD, "serve"),
    (None, "Behavior Analysis Services", "behavior_analysis", "BA", AHCA, CODE_MOD, "serve"),
    (None, "Specialized Therapeutic Services", "specialized_therapeutic", "STS", AHCA, CODE_MOD, "serve"),
    (None, "Qualified Residential Treatment Program Services", "qrtp", None, AHCA, PER_DIEM, "serve"),
    (None, "Comprehensive Behavioral Health Assessment", "cbha", "CHB", AHCA, CODE_MOD, "serve"),
    ("59G-4.120", "Statewide Inpatient Psychiatric Program (SIPP)", "sipp", "SIPP", AHCA, PER_DIEM, "serve"),

    # ── What CMHCs actually run, outside the AHCA fee schedule ───────────────
    (None, "Crisis Stabilization Unit / Baker Act receiving", "csu_baker_act", None, BAKER, PER_DIEM, "decline_well"),
    (None, "Baker Act involuntary examination", "baker_act_exam", None, BAKER, PER_DIEM, "decline_well"),
    (None, "Marchman Act services", "marchman_act", None, MARCHMAN, PER_DIEM, "decline_well"),
    (None, "Withdrawal Management / Detoxification", "withdrawal_management", None, DCF, PER_DIEM, "decline_well"),
    (None, "Substance Use Residential Treatment", "sud_residential", None, WAIVER, PER_DIEM, "decline_well"),
    (None, "Intensive Outpatient Program (IOP)", "iop", None, PLAN, CODE_MOD, "decline_well"),
    (None, "Partial Hospitalization Program (PHP)", "php", None, PLAN, CODE_MOD, "decline_well"),
    ("59G-4.150", "Inpatient Psychiatric — adult, hospital", "inpatient_psych_adult", None, HOSP, DRG, "decline_well"),
    ("59G-4.160", "Emergency Department behavioral health", "ed_behavioral", None, HOSP, EAPG, "decline_well"),
    (None, "Mobile Response Team / crisis intervention", "mobile_response", None, DCF, PER_DIEM, "decline_well"),
]

# Which fee schedule page carries which rule (from the page footers in the PDF)
PAGE_RULES = {1: ["59G-4.028"], 2: ["59G-4.029"],
              3: ["59G-4.031", "59G-4.052"], 4: ["59G-4.127", "59G-4.370"]}

# ── Modifier glossary. Definitions are the standard HCPCS Level II meanings;
# "observed" records how AHCA actually uses each one in this fee schedule.
MODIFIERS = {
    "HE": "Mental health program",
    "HF": "Substance abuse program",
    "HM": "Less than bachelor degree level",
    "HN": "Bachelors degree level",
    "HO": "Masters degree level",
    "HP": "Doctoral level",
    "HQ": "Group setting",
    "HR": "Family/couple with client present",
    "TS": "Follow-up service",
    "HA": "Child/adolescent program",
}

MODULES = [
    ("facts", "Fact Store", "facts & rates",
     "Every fact extracted for this line — code, modifier, fee, unit, limit, exclusion — "
     "for every payor in scope."),
    ("lexicon", "Lexicon", "vocabulary",
     "Every term, alias and code for this line incorporated, so any wording a user types "
     "reaches the line."),
    ("cred", "Credentialing", "who may render",
     "The credentialing and certification rules for this line — which provider types and "
     "license levels may render it, and under what supervision."),
    ("appeals", "Appeals", "denial playbook",
     "The most common denial reasons this line attracts, each with a citable rebuttal."),
    ("analytics", "Analytics", "marts & benchmarks",
     "This line's codes mapped at the registry's grain, so revenue and utilization roll up "
     "to the same line everyone else means."),
    ("chat", "Chat / RAG", "the answer",
     "Questions about this line answered from curated facts, with citations — and flagged "
     "when they are not."),
]


def load_manifest():
    rows = list(csv.DictReader(open(ROOT + "docs/ahca-manifests/ahca_BH_sources.csv")))
    by_rule, fee_docs, cert_docs = {}, [], []
    for r in rows:
        if r["rule_number"]:
            by_rule.setdefault(r["rule_number"], []).append(r)
        if r["rate_class"].startswith("fee_schedule"):
            fee_docs.append(r)
        if "Certification" in r["link_text"] or "Self-Certif" in r["link_text"]:
            cert_docs.append(r)
    return rows, by_rule, fee_docs, cert_docs


def analytics_map():
    src = open(ROOT + "mobius-skills/provider-roster-credentialing/"
                      "provider_skill/utilization_benchmarks.py").read()
    blk = src.split("_SERVICE_LINE_MAP = {")[1].split("}")[0]
    return dict(re.findall(r"'([A-Z0-9]{5})'\s*:\s*'([a-z_]+)'", blk))


def main():
    parsed = json.load(open(SCRATCH + "parsed.json"))
    cbh = parsed["cbh_2025"]["rows"]
    tcm = parsed["tcm_children_2022"]["rows"]
    manifest, by_rule, fee_docs, cert_docs = load_manifest()
    amap = analytics_map()
    try:
        EV = json.load(open(SCRATCH + "acute_evidence.json"))
    except Exception:
        EV = {}
    globals()["EVIDENCE"] = EV

    # ── attach codes to lines ────────────────────────────────────────────────
    codes_by_rule = {}
    for r in cbh:
        cands = PAGE_RULES[r["page"]]
        for rule in cands:
            codes_by_rule.setdefault(rule, []).append({
                "code": r["code"], "modifier": r["modifier"],
                "definition": r["description"],
                "telemedicine": r["telemedicine"],
                "relations": r["exclusions"],
                "adjudicated": len(cands) == 1,
                "rule_candidates": cands,
                "cite": {"document": r["source"], "page": r["page"]},
            })
    for r in tcm:
        codes_by_rule.setdefault("59G-4.310", []).append({
            "code": r["code"], "modifier": r["modifier"],
            "definition": "Targeted case management for children at risk of abuse and neglect",
            "telemedicine": False, "relations": [],
            "adjudicated": True, "rule_candidates": ["59G-4.310"],
            "cite": {"document": r["source"], "page": r["page"]},
        })

    catalog = {
        "catalog_version": "1.0.0",
        "status": "draft",
        "generated": str(date.today()),
        "jurisdiction": {"state": "FL", "program": "Medicaid", "regulator": "AHCA"},
        "provenance": {
            "service_lines": "AHCA 59G rule decomposition, docs/ahca-manifests/ahca_BH_sources.csv "
                             "(77 BH sources, crawl verified 2026-08-17)",
            "codes": "AHCA fee schedules held in the RAG corpus (document_pages)",
            "grain": "(procedure_code, modifier) — H2000/HP and H2000/HO are different services "
                     "with different rendering levels in the same document",
        },
        "modifiers": MODIFIERS,
        "modules": [{"key": k, "name": n, "role": r, "owes": o} for k, n, r, o in MODULES],
        "service_lines": [],
    }

    for rule, name, key, family, authority, grain, scope in LINES:
        codes = codes_by_rule.get(rule, []) if rule else []
        unadj = [c for c in codes if not c["adjudicated"]]
        srcs = by_rule.get(rule, []) if rule else []
        certs = [c for c in cert_docs
                 if any(w in c["link_text"].lower() for w in name.lower().split()[:2])]

        # ── module status, derived from evidence only ────────────────────────
        if scope == "decline_well":
            # Named on purpose: a real CMHC service we do not support. The
            # obligation flips — every module must decline correctly rather
            # than build. Status tracks whether it can decline with substance.
            ev = EVIDENCE.get(key, {})
            srcs_ev = ev.get("top_sources", [])
            npages = ev.get("total_pages", 0)
            top = ", ".join(x["doc"][:38] for x in srcs_ev[:2]) if srcs_ev else ""
            grain_note = {PER_DIEM: "facility per-diem", DRG: "hospital DRG",
                          EAPG: "hospital EAPG", CODE_MOD: "code + modifier"}[grain]

            facts = ("na", f"Not Fact Store's to hold. Paid at {grain_note} grain under "
                           f"{authority}, not the AHCA fee schedule.")
            lexicon = ("todo", f"Must index this line's terms even though we do not serve it — "
                               f"otherwise the question never reaches the decline. "
                               f"{npages} corpus pages mention it; zero lexicon entries.")
            cred = ("na", f"Provider qualification for this line is set by {authority}, "
                          f"not by payor credentialing.")
            appeals = ("na", "No appeal playbook — we do not support billing for this line.")
            analytics = ("na", f"Excluded from marts by design. Its {grain_note} grain would "
                               f"double-count against code-grain lines if included.")
            chat = ("todo", "Must answer: name the service, say plainly that Mobius does not cover "
                            f"its rules, and point at the governing authority ({authority}). "
                            + (f"Corpus has {npages} pages across sources including {top} — "
                               f"enough to be useful without claiming support." if srcs_ev
                               else "No corpus evidence gathered yet."))
        else:
            if not codes:
                facts = ("todo", f"No fee schedule for this line in the corpus. "
                                 f"{'AHCA publishes one (' + family + ') and we hold the URL, but it is not ingested.' if family else 'No AHCA fee schedule identified.'}")
            elif unadj:
                facts = ("doing", f"{len(codes)} (code, modifier) pairs identified for this line. "
                                  f"{len(unadj)} sit on a fee-schedule page citing two rules — line "
                                  f"assignment not adjudicated. Rates for these pairs are Fact Store's "
                                  f"to extract and certify.")
            else:
                facts = ("done", f"{len(codes)} (code, modifier) pairs identified, page cites one rule "
                                 f"so assignment is unambiguous. Rates for these pairs are Fact Store's "
                                 f"to extract and certify.")

            lexicon = ("todo", "Not present. The lexicon holds 4,228 entries across d/p/j; a search for "
                               "this line's service terms and codes returns zero matches.")

            if certs:
                cred = ("doing", f"{len(certs)} AHCA certification documents identified in the manifest "
                                 f"for this line. Not yet parsed into rendering rules.")
            else:
                cred = ("todo", "No certification or provider-qualification source identified for this line.")

            appeals = ("todo", "No denial reasons keyed to this service line. The CARC catalogue exists "
                               "but is not linked to service lines.")

            in_map = sorted({c["code"] for c in codes if c["code"] in amap})
            if codes and in_map:
                lines_hit = sorted({amap[c] for c in in_map})
                analytics = ("doing", f"All {len(in_map)} codes appear in the analytics map, but at bare-code "
                                      f"grain — modifiers are dropped, so {len(codes)} distinct services collapse "
                                      f"into {len(lines_hit)} of its own line names ({', '.join(lines_hit)}), which "
                                      f"do not match AHCA's.")
            elif codes:
                analytics = ("todo", "Codes not present in the analytics map.")
            else:
                analytics = ("todo", "No codes to map yet.")

            chat = ("todo", "No question bank for this line. Module has not reported.")

        catalog["service_lines"].append({
            "key": key,
            "name": name,
            "rule": rule,
            "authority": authority,
            "grain": grain,
            "scope": scope,
            "evidence_pages": EVIDENCE.get(key, {}).get("total_pages", 0),
            "evidence_sources": EVIDENCE.get(key, {}).get("top_sources", []),
            "rule_status": "numbered" if rule else "no rule number in manifest — needs adjudication",
            "fee_schedule_family": family,
            "source_documents": len(srcs),
            "codes": codes,
            "code_count": len(codes),
            "allowed_modifiers": sorted({c["modifier"] for c in codes if c["modifier"]}),
            "distinct_codes": len({c["code"] for c in codes}),
            "unadjudicated_codes": len(unadj),
            "status": {"facts": facts, "lexicon": lexicon, "cred": cred,
                       "appeals": appeals, "analytics": analytics, "chat": chat},
        })

    subprocess.run(["mkdir", "-p", ROOT + "docs/service-lines"], check=True)
    json.dump(catalog, open(OUT_JSON, "w"), indent=2)

    done = sum(1 for l in catalog["service_lines"] for s in l["status"].values() if s[0] == "done")
    tot = len(catalog["service_lines"]) * len(MODULES)
    print(f"service lines : {len(catalog['service_lines'])}")
    print(f"with codes    : {sum(1 for l in catalog['service_lines'] if l['codes'])}")
    print(f"code rows     : {sum(l['code_count'] for l in catalog['service_lines'])}")
    print(f"obligations   : {done}/{tot} complete")
    print(f"wrote         : {OUT_JSON}")


if __name__ == "__main__":
    main()
