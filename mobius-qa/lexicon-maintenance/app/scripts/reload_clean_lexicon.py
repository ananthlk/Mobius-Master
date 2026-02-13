#!/usr/bin/env python3
"""
One-time lexicon cleanup: wipe and reload with a clean 2-level taxonomy.

Structure rules:
  - kind: j | d | p
  - code: domain or domain.tag  (max 2 segments, lowercase_snake)
  - domain (no dot): organizational container ONLY -- NO aliases, NO matching
  - tag (with dot): the matchable unit with full metadata
  - parent_code: null for domains, references existing domain for tags
  - spec: { description, strong_phrases[], weak_keywords?, aliases[], refuted_words[], scores? }

Terminology:
  Type (kind)  ->  Domain (parent)  ->  Tag (leaf)
  j / d / p       claims               denial
                  provider             network
                  pharmacy             general

Usage:
  QA_DATABASE_URL='postgresql://postgres:MobiusDev123$@127.0.0.1:5432/mobius_qa' \
  RAG_DATABASE_URL='postgresql://postgres:MobiusDev123$@127.0.0.1:5432/mobius_rag' \
  python3 reload_clean_lexicon.py [--dry-run]
"""

import json
import os
import sys
import uuid
import re

# ---------------------------------------------------------------------------
# Clean taxonomy definition
# ---------------------------------------------------------------------------

TAG_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")


def _entry(kind: str, code: str, description: str,
           strong_phrases: list[str] | None = None,
           weak_keywords: list[str] | None = None,
           aliases: list[str] | None = None,
           refuted_words: list[str] | None = None,
           scores: dict | None = None,
           parent_code: str | None = None) -> dict:
    """Build a single lexicon entry dict.

    Domain containers (no dot in code) must NOT have strong_phrases, aliases, or refuted_words.
    Only leaf tags (with dot) carry matching metadata.
    """
    assert kind in ("j", "d", "p"), f"Invalid kind: {kind}"
    assert TAG_CODE_RE.match(code), f"Invalid code: {code}"
    if "." in code:
        assert parent_code is not None, f"Child tag {code} requires parent_code"
    else:
        assert parent_code is None, f"Root tag {code} must not have parent_code"
        # Domain containers must NOT carry matching metadata
        assert not strong_phrases, f"Domain container '{code}' must not have strong_phrases -- use a .general leaf tag"
        assert not aliases, f"Domain container '{code}' must not have aliases -- use a .general leaf tag"
        assert not refuted_words, f"Domain container '{code}' must not have refuted_words -- use a .general leaf tag"

    spec: dict = {"description": description}
    if strong_phrases:
        spec["strong_phrases"] = strong_phrases
    if weak_keywords:
        spec["weak_keywords"] = {"any_of": weak_keywords, "min_hits": 1}
    if aliases:
        spec["aliases"] = aliases
    if refuted_words:
        spec["refuted_words"] = refuted_words
    if scores:
        spec["scores"] = scores

    return {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "code": code,
        "parent_code": parent_code,
        "spec": spec,
        "active": True,
    }


ENTRIES: list[dict] = []

# ===== J -- Jurisdiction =====

ENTRIES += [
    # State
    _entry("j", "state", "State"),
    _entry("j", "state.florida", "Florida", ["florida", "state of florida"], parent_code="state"),

    # Payor
    _entry("j", "payor", "Payor"),
    _entry("j", "payor.molina_healthcare", "Molina Healthcare", ["molina healthcare", "molina"], parent_code="payor"),
    _entry("j", "payor.sunshine_health", "Sunshine Health", ["sunshine health", "sunshine"], parent_code="payor"),
    _entry("j", "payor.unitedhealthcare", "UnitedHealthcare", ["unitedhealthcare community plan", "united healthcare", "united"], parent_code="payor"),

    # Program
    _entry("j", "program", "Program"),
    _entry("j", "program.medicaid", "Medicaid", ["medicaid"], parent_code="program"),
    _entry("j", "program.mma", "MMA", ["mma", "managed medical assistance"], parent_code="program"),
    _entry("j", "program.smi", "SMI", ["smi", "serious mental illness"], parent_code="program"),
    _entry("j", "program.comprehensive_ltc", "Long Term Care", ["comprehensive long term care", "ltc"], parent_code="program"),
    _entry("j", "program.cwsp", "CWSP", ["cwsp", "child welfare specialty plan"], parent_code="program"),
    _entry("j", "program.hiv_aids", "HIV/AIDS", ["hiv", "aids", "hiv/aids"], parent_code="program"),

    # Provider (jurisdiction)
    _entry("j", "provider", "Provider"),
    _entry("j", "provider.child_welfare", "Child Welfare", ["child welfare"], parent_code="provider"),

    # Regulatory Authority
    _entry("j", "regulatory_authority", "Regulatory Authority"),
    _entry("j", "regulatory_authority.ahca", "AHCA", ["ahca", "agency for health care administration"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.cms", "CMS", ["cms", "centers for medicare", "centers for medicare & medicaid services"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.dcf", "DCF", ["dcf", "department of children and families"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.fbha", "FBHA", ["fbha", "florida behavioral health association"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.gsa", "GSA", ["gsa", "general services administration"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.hhs", "HHS", ["hhs", "department of health and human services"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.oig", "OIG", ["oig", "office of inspector general"], parent_code="regulatory_authority"),
    _entry("j", "regulatory_authority.ssa", "SSA", ["ssa", "social security administration"], parent_code="regulatory_authority"),
]

# ===== D -- Domain =====

ENTRIES += [
    # ── Claims ────────────────────────────────────────────────────────────
    _entry("d", "claims", "Claims"),
    _entry("d", "claims.general", "General Claims", ["claims", "claim", "billing"],
           aliases=["claim processing"],
           parent_code="claims"),
    _entry("d", "claims.submission", "Claims Submission", ["submit claims", "claim submission"],
           parent_code="claims"),
    _entry("d", "claims.denial", "Claims Denial", ["denial", "denied claim", "rejected", "rejection"],
           refuted_words=["approved", "approval"],
           parent_code="claims"),
    _entry("d", "claims.timely_filing", "Timely Filing", ["timely filing", "filing limit"],
           parent_code="claims"),
    _entry("d", "claims.clean_claim", "Clean Claim", ["clean claim"],
           parent_code="claims"),
    _entry("d", "claims.corrected_claims", "Corrected Claims", ["corrected claim", "replacement claim"],
           parent_code="claims"),
    _entry("d", "claims.electronic_claims", "Electronic Claims", ["electronic claims", "edi", "837"],
           parent_code="claims"),
    _entry("d", "claims.paper_claims", "Paper Claims", ["paper claim", "paper claims"],
           parent_code="claims"),
    _entry("d", "claims.billing_forms", "Billing Forms", ["cms-1500", "ub-04"],
           parent_code="claims"),
    _entry("d", "claims.coordination_of_benefits", "Coordination of Benefits", ["coordination of benefits", "cob"],
           parent_code="claims"),
    _entry("d", "claims.appeals_grievances", "Appeals & Grievances", ["appeals", "grievances", "reconsideration", "dispute"],
           parent_code="claims"),
    _entry("d", "claims.payer_id", "Payer ID", ["payer id"],
           parent_code="claims"),

    # ── Eligibility ───────────────────────────────────────────────────────
    _entry("d", "eligibility", "Eligibility"),
    _entry("d", "eligibility.general", "General Eligibility", ["eligibility"],
           aliases=["member eligibility"],
           parent_code="eligibility"),
    _entry("d", "eligibility.enrollment", "Enrollment", ["enrollment"],
           parent_code="eligibility"),
    _entry("d", "eligibility.verification", "Verification", ["verify eligibility", "eligibility verification"],
           parent_code="eligibility"),
    _entry("d", "eligibility.member_status", "Member Status", ["member status"],
           parent_code="eligibility"),
    _entry("d", "eligibility.plan_assignment", "Plan Assignment", ["plan assignment", "assigned"],
           parent_code="eligibility"),

    # ── Pharmacy ──────────────────────────────────────────────────────────
    _entry("d", "pharmacy", "Pharmacy"),
    _entry("d", "pharmacy.general", "General Pharmacy", ["pharmacy", "prescription"],
           aliases=["pharmaceutical"],
           parent_code="pharmacy"),
    _entry("d", "pharmacy.preferred_drug_list", "Preferred Drug List", ["preferred drug list", "pdl", "formulary"],
           parent_code="pharmacy"),
    _entry("d", "pharmacy.specialty_pharmacy", "Specialty Pharmacy", ["specialty pharmacy"],
           parent_code="pharmacy"),
    _entry("d", "pharmacy.controlled_substances", "Controlled Substances", ["controlled substances"],
           parent_code="pharmacy"),
    _entry("d", "pharmacy.drug_utilization_review", "Drug Utilization Review", ["drug utilization review", "dur"],
           parent_code="pharmacy"),
    _entry("d", "pharmacy.pharmacy_benefit", "Pharmacy Benefit", ["pharmacy benefit"],
           parent_code="pharmacy"),

    # ── Compliance ────────────────────────────────────────────────────────
    _entry("d", "compliance", "Compliance"),
    _entry("d", "compliance.general", "General Compliance", ["compliance", "regulatory compliance"],
           parent_code="compliance"),
    _entry("d", "compliance.hipaa", "HIPAA", ["hipaa"],
           parent_code="compliance"),
    _entry("d", "compliance.fraud_waste_abuse", "Fraud Waste & Abuse", ["fraud waste and abuse", "fwa"],
           parent_code="compliance"),
    _entry("d", "compliance.audits", "Audits", ["audit", "audits"],
           parent_code="compliance"),
    _entry("d", "compliance.confidentiality", "Confidentiality", ["confidentiality", "privacy"],
           parent_code="compliance"),
    _entry("d", "compliance.nondiscrimination", "Nondiscrimination", ["nondiscrimination", "section 1557"],
           parent_code="compliance"),
    _entry("d", "compliance.linguistically_appropriate", "Linguistically Appropriate", ["linguistically appropriate"],
           parent_code="compliance"),

    # ── Contact Information ───────────────────────────────────────────────
    _entry("d", "contact_information", "Contact Information"),
    _entry("d", "contact_information.general", "General Contact", ["contact information", "tty"],
           aliases=["contact info"],
           parent_code="contact_information"),
    _entry("d", "contact_information.phone", "Phone", ["phone", "telephone"],
           parent_code="contact_information"),
    _entry("d", "contact_information.fax", "Fax", ["fax"],
           parent_code="contact_information"),
    _entry("d", "contact_information.email", "Email", ["email"],
           parent_code="contact_information"),
    _entry("d", "contact_information.website", "Website", ["website", "web site", "url"],
           parent_code="contact_information"),
    _entry("d", "contact_information.portal", "Portal", ["portal", "login", "availity essentials", "correspondence hub"],
           parent_code="contact_information"),
    _entry("d", "contact_information.facebook", "Facebook", ["facebook"],
           parent_code="contact_information"),
    _entry("d", "contact_information.member_services", "Member Services", ["member services"],
           parent_code="contact_information"),
    _entry("d", "contact_information.provider_contact", "Provider Contact", ["provider contact"],
           parent_code="contact_information"),
    _entry("d", "contact_information.sms", "SMS / Text", ["sms", "text message"],
           parent_code="contact_information"),
    _entry("d", "contact_information.preferred_language", "Preferred Language", ["preferred language", "language line", "language services"],
           parent_code="contact_information"),

    # ── Utilization Management ────────────────────────────────────────────
    _entry("d", "utilization_management", "Utilization Management"),
    _entry("d", "utilization_management.general", "General UM", ["utilization management", "um"],
           aliases=["utilization review"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.prior_authorization", "Prior Authorization", ["prior authorization", "prior auth"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.medical_necessity", "Medical Necessity", ["medical necessity"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.referrals", "Referrals", ["referral", "referrals"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.inpatient_auth", "Inpatient Authorization", ["inpatient authorization", "inpatient auth"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.outpatient_auth", "Outpatient Authorization", ["outpatient authorization", "outpatient auth"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.dme_auth", "DME Authorization", ["durable medical equipment authorization", "dme authorization", "dme"],
           parent_code="utilization_management"),
    _entry("d", "utilization_management.authorization_denial", "Authorization Denial", ["authorization denied", "auth denial", "authorization denial"],
           refuted_words=["approved", "authorized"],
           parent_code="utilization_management"),

    # ── Health Care Services ──────────────────────────────────────────────
    _entry("d", "health_care_services", "Health Care Services"),
    _entry("d", "health_care_services.general", "General Health Services", ["health care services", "health services"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.behavioral_health", "Behavioral Health", ["behavioral health"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.primary_care", "Primary Care", ["primary care", "pcp"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.urgent_care", "Urgent Care", ["urgent care"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.substance_use_disorders", "Substance Use Disorders", ["substance use disorders", "substance abuse"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.managed_care", "Managed Care", ["managed care", "medicaid managed care"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.appropriate_services", "Appropriate Services", ["appropriate services"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.mental_health", "Mental Health", ["mental health services", "mental health"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.physical_therapy", "Physical Therapy", ["physical therapy", "pt"],
           parent_code="health_care_services"),
    _entry("d", "health_care_services.occupational_therapy", "Occupational Therapy", ["occupational therapy", "ot"],
           parent_code="health_care_services"),

    # ── Provider ──────────────────────────────────────────────────────────
    _entry("d", "provider", "Provider"),
    _entry("d", "provider.general", "General Provider", ["healthcare provider", "medical provider"],
           aliases=["provider"],
           parent_code="provider"),
    _entry("d", "provider.network", "Provider Network", ["provider network", "participating providers"],
           parent_code="provider"),
    _entry("d", "provider.services", "Provider Services", ["provider services"],
           parent_code="provider"),
    _entry("d", "provider.relations", "Provider Relations", ["provider relations"],
           parent_code="provider"),
    _entry("d", "provider.manual", "Provider Manual", ["provider manual"],
           parent_code="provider"),

    # ── Responsibilities ──────────────────────────────────────────────────
    _entry("d", "responsibilities", "Responsibilities"),
    _entry("d", "responsibilities.general", "General Responsibilities", ["provider responsibilities"],
           aliases=["responsibilities"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.abuse_neglect_reporting", "Abuse/Neglect Reporting", ["abuse", "neglect", "abuse reporting"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.continuity_of_care", "Continuity of Care", ["continuity of care"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.reporting_incidents", "Reporting Incidents", ["reporting incidents", "incident report"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.training", "Training", ["training"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.hipaa_training", "HIPAA Training", ["hipaa training"],
           parent_code="responsibilities"),
    _entry("d", "responsibilities.fwa_training", "FWA Training", ["fraud waste abuse training", "fwa training"],
           parent_code="responsibilities"),

    # ── Quality Program ───────────────────────────────────────────────────
    _entry("d", "quality_program", "Quality Program"),
    _entry("d", "quality_program.general", "General Quality", ["quality program"],
           parent_code="quality_program"),
    _entry("d", "quality_program.quality_improvement", "Quality Improvement", ["quality improvement committee", "quality improvement"],
           parent_code="quality_program"),
    _entry("d", "quality_program.quality_management", "Quality Management", ["quality management"],
           parent_code="quality_program"),
    _entry("d", "quality_program.satisfaction_assessment", "Satisfaction Assessment", ["behavioral health satisfaction assessment", "member satisfaction"],
           parent_code="quality_program"),

    # ── Billing Codes ─────────────────────────────────────────────────────
    _entry("d", "billing_codes", "Billing Codes"),
    _entry("d", "billing_codes.general", "General Billing Codes", ["billing codes"],
           parent_code="billing_codes"),
    _entry("d", "billing_codes.procedure_code", "Procedure Codes", ["procedure code", "cpt", "icd"],
           parent_code="billing_codes"),

    # ── Credentialing ─────────────────────────────────────────────────────
    _entry("d", "credentialing", "Credentialing"),
    _entry("d", "credentialing.general", "General Credentialing", ["credentialing", "clia"],
           parent_code="credentialing"),

    # ── Tools ─────────────────────────────────────────────────────────────
    _entry("d", "tools", "Tools"),
    _entry("d", "tools.portal", "Portals & Systems", ["portal", "availity essentials", "correspondence hub"],
           parent_code="tools"),

    # ── Benefits ──────────────────────────────────────────────────────────
    _entry("d", "benefits", "Benefits"),
    _entry("d", "benefits.general", "General Benefits", ["benefits", "covered benefits"],
           aliases=["benefit plan"],
           parent_code="benefits"),

    # ── Care Management ───────────────────────────────────────────────────
    _entry("d", "care_management", "Care Management"),
    _entry("d", "care_management.general", "General Care Management", ["care management", "care coordination", "case management", "disease management"],
           parent_code="care_management"),

    # ── Place of Service (NEW) ────────────────────────────────────────────
    _entry("d", "place_of_service", "Place of Service"),
    _entry("d", "place_of_service.inpatient", "Inpatient", ["inpatient", "hospital admission"],
           parent_code="place_of_service"),
    _entry("d", "place_of_service.outpatient", "Outpatient", ["outpatient", "ambulatory"],
           parent_code="place_of_service"),
    _entry("d", "place_of_service.home_health", "Home Health", ["home health", "home care"],
           parent_code="place_of_service"),
    _entry("d", "place_of_service.telehealth", "Telehealth", ["telehealth", "telemedicine"],
           parent_code="place_of_service"),

    # ── Data Reporting (NEW) ──────────────────────────────────────────────
    _entry("d", "data_reporting", "Data Reporting"),
    _entry("d", "data_reporting.hedis", "HEDIS", ["hedis", "healthcare effectiveness"],
           parent_code="data_reporting"),
    _entry("d", "data_reporting.encounter_data", "Encounter Data", ["encounter data", "encounter submission"],
           parent_code="data_reporting"),
    _entry("d", "data_reporting.quality_metrics", "Quality Metrics", ["quality metrics", "performance measures"],
           parent_code="data_reporting"),
]

# ===== P -- Procedural =====

ENTRIES += [
    # Communication
    _entry("p", "communication", "Communication"),
    _entry("p", "communication.call", "Call", ["call", "call provider services", "call member services"],
           parent_code="communication"),
    _entry("p", "communication.email", "Email", ["email", "e-mail", "send an email"],
           parent_code="communication"),
    _entry("p", "communication.contact", "Contact", ["contact", "reach out", "notify"],
           parent_code="communication"),

    # Submission
    _entry("p", "submission", "Submission"),
    _entry("p", "submission.submit", "Submit", ["submit", "file", "submit claims"],
           parent_code="submission"),
    _entry("p", "submission.resubmit", "Resubmit", ["resubmit", "re-submit", "corrected claim"],
           parent_code="submission"),

    # Review & Status
    _entry("p", "review", "Review & Status"),
    _entry("p", "review.check_status", "Check Status", ["check status", "claim status", "status inquiry"],
           parent_code="review"),
    _entry("p", "review.review", "Review", ["review", "review reports", "review rejection report"],
           parent_code="review"),

    # Dispute
    _entry("p", "dispute", "Dispute"),
    _entry("p", "dispute.appeal", "Appeal", ["appeal", "reconsideration", "request reconsideration"],
           parent_code="dispute"),

    # Verification
    _entry("p", "verification", "Verification"),
    _entry("p", "verification.verify", "Verify", ["verify eligibility", "eligibility verification", "confirm eligibility"],
           parent_code="verification"),

    # Compliance Actions
    _entry("p", "compliance_action", "Compliance Actions"),
    _entry("p", "compliance_action.required", "Required Action", ["required", "must", "shall"],
           parent_code="compliance_action"),
    _entry("p", "compliance_action.prohibited", "Prohibited Action", ["prohibited", "must not", "shall not"],
           parent_code="compliance_action"),
]


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv

    qa_url = os.environ.get("QA_DATABASE_URL")
    rag_url = os.environ.get("RAG_DATABASE_URL")
    if not qa_url:
        print("ERROR: QA_DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    import psycopg2
    import psycopg2.extras

    # Validate all entries first
    codes_by_kind: dict[str, set[str]] = {"j": set(), "d": set(), "p": set()}
    for e in ENTRIES:
        k, c = e["kind"], e["code"]
        if c in codes_by_kind[k]:
            print(f"ERROR: Duplicate {k}.{c}", file=sys.stderr)
            sys.exit(1)
        codes_by_kind[k].add(c)
        if e["parent_code"] and e["parent_code"] not in codes_by_kind[k]:
            print(f"ERROR: {k}.{c} references parent {e['parent_code']} which hasn't been defined yet", file=sys.stderr)
            sys.exit(1)

    # Validate domain containers have no matching metadata
    for e in ENTRIES:
        if "." not in e["code"]:
            spec = e["spec"]
            for field in ("strong_phrases", "aliases", "refuted_words"):
                if spec.get(field):
                    print(f"ERROR: Domain container {e['kind']}.{e['code']} must not have {field}", file=sys.stderr)
                    sys.exit(1)

    j_count = sum(1 for e in ENTRIES if e["kind"] == "j")
    d_count = sum(1 for e in ENTRIES if e["kind"] == "d")
    p_count = sum(1 for e in ENTRIES if e["kind"] == "p")
    domain_count = sum(1 for e in ENTRIES if "." not in e["code"])
    tag_count = sum(1 for e in ENTRIES if "." in e["code"])
    total = len(ENTRIES)
    print(f"Validated {total} entries: J={j_count}, D={d_count}, P={p_count}")
    print(f"  Domains (containers): {domain_count}  |  Tags (matchable): {tag_count}")

    if dry_run:
        print("\n[DRY RUN] Would execute:")
        print(f"  1. TRUNCATE policy_lexicon_entries in mobius_qa")
        print(f"  2. INSERT {total} clean entries")
        print(f"  3. Bump lexicon revision")
        if rag_url:
            print(f"  4. TRUNCATE policy_lexicon_candidates + policy_lexicon_candidate_catalog in mobius_rag")
        else:
            print(f"  4. SKIP RAG cleanup (RAG_DATABASE_URL not set)")
        print("\nEntries:")
        for e in ENTRIES:
            parent = f"  (parent: {e['parent_code']})" if e["parent_code"] else ""
            is_domain = "." not in e["code"]
            marker = "[DOMAIN]" if is_domain else "[TAG]   "
            sp = e["spec"].get("strong_phrases", [])
            al = e["spec"].get("aliases", [])
            rf = e["spec"].get("refuted_words", [])
            phrases_str = f"  phrases={sp}" if sp else ""
            alias_str = f"  aliases={al}" if al else ""
            refute_str = f"  refuted={rf}" if rf else ""
            print(f"  {marker} {e['kind']}.{e['code']}{parent}  -- {e['spec']['description']}{phrases_str}{alias_str}{refute_str}")
        return

    # 1. Truncate and reload QA
    print("\nConnecting to QA database...")
    qa = psycopg2.connect(qa_url)
    qa.autocommit = True
    cur = qa.cursor()

    print("Truncating policy_lexicon_entries...")
    cur.execute("TRUNCATE TABLE policy_lexicon_entries")

    print(f"Inserting {total} clean entries...")
    for e in ENTRIES:
        cur.execute(
            """
            INSERT INTO policy_lexicon_entries (id, kind, code, parent_code, spec, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
            """,
            (e["id"], e["kind"], e["code"], e["parent_code"], json.dumps(e["spec"]), e["active"]),
        )

    # Bump revision (policy_lexicon_meta has columns: id, lexicon_version, lexicon_meta, revision, created_at, updated_at)
    cur.execute("SELECT id, COALESCE(revision,0)::bigint FROM policy_lexicon_meta ORDER BY updated_at DESC NULLS LAST LIMIT 1")
    meta_row = cur.fetchone()
    if meta_row and meta_row[0]:
        new_rev = int(meta_row[1] or 0) + 1
        cur.execute("UPDATE policy_lexicon_meta SET revision=%s, updated_at=NOW() WHERE id=%s", (new_rev, meta_row[0]))
    else:
        new_rev = 1
        cur.execute(
            "INSERT INTO policy_lexicon_meta(id, lexicon_version, lexicon_meta, revision, created_at, updated_at) VALUES (%s, 'v2', '{}'::jsonb, %s, NOW(), NOW())",
            (str(uuid.uuid4()), new_rev),
        )
    print(f"Lexicon revision bumped to: {new_rev}")

    cur.close()
    qa.close()
    print("QA database updated successfully.")

    # 2. Truncate RAG candidate tables
    if rag_url:
        print("\nConnecting to RAG database...")
        rag = psycopg2.connect(rag_url)
        rag.autocommit = True
        rcur = rag.cursor()
        print("Truncating policy_lexicon_candidates...")
        rcur.execute("TRUNCATE TABLE policy_lexicon_candidates")
        print("Truncating policy_lexicon_candidate_catalog...")
        rcur.execute("TRUNCATE TABLE policy_lexicon_candidate_catalog")
        rcur.close()
        rag.close()
        print("RAG candidate tables cleared.")
    else:
        print("\nRAG_DATABASE_URL not set, skipping candidate table cleanup.")

    print(f"\nDone. {total} entries loaded (J={j_count}, D={d_count}, P={p_count}).")
    print(f"  Domains: {domain_count}  |  Tags: {tag_count}")


if __name__ == "__main__":
    main()
