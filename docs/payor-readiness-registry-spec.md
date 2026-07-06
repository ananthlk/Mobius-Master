---
title: Payor Readiness Registry — spec & agent charter
status: draft
owner: payor-platform-agent
created: 2026-07-03
audience: internal
---

# Payor Readiness Registry

## 1. Charter (what this agent owns)

One authoritative record, **per payor**, of everything Mobius needs to *fully support*
that payor — and a live scorecard of whether we have it, whether it is current, and
where the gaps are.

The agent's job is **not** to store documents or build integrations. It is to:

1. **Define the requirement** — the fixed checklist of asset types a supported payor must have.
2. **Track coverage & freshness** — is each required asset present in RAG, and is it in compliance?
3. **Emit work orders on gaps** — when something is missing/stale, dispatch a typed signal to the
   agent that can build it (RAG ingestion/curator, credentialing, an integrations agent).
4. **Maintain** — re-verify on a cadence; flag drift; keep the registry the single source of truth
   for "how ready are we for payor X".

This agent is the **requirements + coverage layer**. It sits *on top of* infrastructure that
already exists (below).

## 2. What already exists (do not rebuild)

| Concern | Where it lives today | Reuse as |
|---|---|---|
| URL discovery + liveness + drift | `mobius-rag` `discovered_sources` (payer/state/program, `last_fetch_at`, `content_hash`, `content_changed_at`, `curation_status`, `ingested_doc_id`) | **Freshness/compliance engine.** A daily worker already re-fetches `curation_status='canonical'` URLs and detects content change. |
| Ingested corpus + policy dates | `mobius-rag` `documents` (`payer`/`state`/`program`, `effective_date`, `termination_date`, `review_status`) | **Corpus presence** — the thing a registry row points at once ingested. |
| Payer normalization | `mobius-chat/config/payer_normalization.yaml` | **Canonical payor names + aliases.** Registry uses canonical only. |
| Payer→(state,program) inference | `mobius-rag/app/main.py` rules table | Seed classification for new payors. |
| Per-payor knowledge pack (proto) | `mobius-skills/appeals-agent/knowledge/payors/sunshine_health.yaml` | Prior art for `sources[]` + `gap:` markers + `Refresh:`/`Last verified:` header. |
| The site map | `mobius-rag/scripts/curator/sitemap_data_v0.json` | Raw URL inventory the registry's `provider_site_map` asset reconciles against. |

**Key distinction:** `discovered_sources` is *bottom-up* ("here is what we crawled"). This registry
is *top-down* ("here is what a payor is REQUIRED to have"). A URL can exist in `discovered_sources`
and still be a **gap** here if it's the wrong asset type or unverified — and a required asset can be
`missing` with zero rows in `discovered_sources`. That delta is the product.

## 3. Required-asset taxonomy

Two layers. `layer='corpus'` = must be ingested into RAG. `layer='surface'` = an operational
endpoint/contact, tracked but not necessarily embedded. APIs are a third concern (§6).

| asset_type | layer | required | default TTL | notes |
|---|---|---|---|---|
| `provider_manual` | corpus | yes | 365d | Primary billing/policy authority. |
| `member_handbook` | corpus | yes | 365d | Member-facing benefits/coverage. |
| `medical_policies` | corpus | yes | 90d | Clinical coverage policies (may be a set). |
| `um_policies` | corpus | yes | 90d | Utilization mgmt / prior-auth criteria. |
| `billing_manual` | corpus | yes | 180d | Claims/coding/EDI companion guide. |
| `fee_schedule` | corpus | no | 90d | Where published (ties to DOGE rate work). |
| `provider_site_map` | surface | yes | 30d | Reconcile vs `sitemap_data_v0.json`. |
| `provider_login_url` | surface | yes | 180d | Provider portal login. |
| `eligibility_check_url` | surface | yes | 180d | Web eligibility lookup. |
| `authorization_check_url` | surface | yes | 180d | Web prior-auth submission/status. |
| `supported_portal` | surface | yes | 180d | e.g. Availity — one row per portal. |
| `customer_support_phone` | surface | yes | 180d | Provider services line. |
| `claims_fax` | surface | no | 180d | Where fax is a channel. |
| `appeals_fax` | surface | no | 180d | Distinct from claims fax (see Sunshine). |
| `edi_payer_id` | surface | yes | 365d | Clearinghouse payer ID. |

Taxonomy is versioned in-table (`asset_type` is an enum-by-convention, not a DB enum, so adding
types is a data change, not a migration).

## 4. Schema (Postgres, in the mobius-rag DB)

Two new tables + one view. Follows the existing `app/migrations/*.sql` convention.

```sql
-- migrations/add_payor_readiness_registry.sql

CREATE TABLE IF NOT EXISTS payor_readiness_asset (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity (canonical payor name from payer_normalization.yaml)
    payor                   VARCHAR(120) NOT NULL,
    state                   VARCHAR(2),
    program                 VARCHAR(100),
    asset_type              VARCHAR(60)  NOT NULL,   -- see §3 taxonomy
    layer                   VARCHAR(10)  NOT NULL,   -- 'corpus' | 'surface'
    label                   TEXT,                    -- human title, e.g. "Aetna Better Health FL Provider Manual 2026"

    -- Requirement
    required                BOOLEAN NOT NULL DEFAULT TRUE,

    -- Coverage status (derived, but stored for query/dashboard)
    status                  VARCHAR(20) NOT NULL DEFAULT 'missing',
        -- 'present' | 'missing' | 'stale' | 'out_of_compliance' | 'needs_auth' | 'n_a'

    -- Where the asset actually is
    source_url              TEXT,
    discovered_source_id    UUID REFERENCES discovered_sources(id) ON DELETE SET NULL,
    document_id             UUID REFERENCES documents(id) ON DELETE SET NULL,  -- set when ingested
    value_text              TEXT,   -- for phone/fax/edi_payer_id where the "asset" is a value, not a URL

    -- Compliance (hybrid: TTL floor + upstream override — see §5)
    ttl_days                INTEGER,
    last_verified_at        TIMESTAMP,          -- when THIS agent last confirmed it
    last_updated_upstream   TIMESTAMP,          -- source's own last-modified, when knowable
    compliance_reason       TEXT,               -- why out_of_compliance, when it is

    -- Gap loop
    gap_workorder_ref       TEXT,               -- id of the emitted signal (§7); NULL if no open gap
    confidence              VARCHAR(10) DEFAULT 'medium',  -- high|medium|low
    notes                   TEXT,

    created_at              TIMESTAMP NOT NULL DEFAULT now(),
    updated_at              TIMESTAMP NOT NULL DEFAULT now(),

    UNIQUE (payor, state, program, asset_type, COALESCE(source_url, ''))
);
CREATE INDEX IF NOT EXISTS ix_pra_payor  ON payor_readiness_asset (payor);
CREATE INDEX IF NOT EXISTS ix_pra_status ON payor_readiness_asset (status);

CREATE TABLE IF NOT EXISTS payor_api_capability (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payor               VARCHAR(120) NOT NULL,
    state               VARCHAR(2),
    program             VARCHAR(100),
    capability          VARCHAR(60) NOT NULL,   -- 'eligibility_270_271' | 'auth_278' | 'claims_837' | 'era_835' | 'roster_feed' | 'provider_directory'
    required            BOOLEAN NOT NULL DEFAULT TRUE,
    status              VARCHAR(20) NOT NULL DEFAULT 'gap',
        -- 'available' | 'partial' | 'gap' | 'n_a'
    transport           VARCHAR(40),            -- 'availity' | 'change_healthcare' | 'direct_api' | 'portal_only' | 'phone_only'
    integration_ref     TEXT,                   -- link to code/service that implements it
    gap_workorder_ref   TEXT,
    confidence          VARCHAR(10) DEFAULT 'medium',
    notes               TEXT,
    last_verified_at    TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (payor, state, program, capability)
);

-- Readiness scorecard: one row per payor with coverage %, gap counts, and
-- freshness rolled up. Joins to discovered_sources for real liveness.
CREATE OR REPLACE VIEW payor_readiness_scorecard AS
SELECT
    a.payor, a.state, a.program,
    COUNT(*) FILTER (WHERE a.required)                                   AS required_assets,
    COUNT(*) FILTER (WHERE a.required AND a.status = 'present')          AS present_assets,
    COUNT(*) FILTER (WHERE a.required AND a.status = 'missing')          AS missing_assets,
    COUNT(*) FILTER (WHERE a.required AND a.status IN
                     ('stale','out_of_compliance','needs_auth'))         AS noncompliant_assets,
    ROUND(100.0 * COUNT(*) FILTER (WHERE a.required AND a.status='present')
                / NULLIF(COUNT(*) FILTER (WHERE a.required), 0), 1)      AS coverage_pct,
    MIN(a.last_verified_at)                                              AS oldest_verification
FROM payor_readiness_asset a
GROUP BY a.payor, a.state, a.program;
```

## 5. Compliance model (hybrid)

A required asset is **in compliance** iff `status='present'` AND not expired. Expiry is computed
per asset:

- **TTL floor (always):** `now() - last_verified_at > ttl_days` → `stale`.
- **Upstream override (when knowable):** if the linked `discovered_sources.content_changed_at`
  is newer than our `last_verified_at`, the source drifted → `out_of_compliance` regardless of TTL.
  This piggybacks on the curator's existing hash-diff loop — no new crawler needed.
- `discovered_sources.curation_status='stale'` (404/410) → asset `status='missing'`.
- `curation_status='needs_auth'` (401/403 login wall) → asset `status='needs_auth'` (signal a human upload).

A nightly reconcile job recomputes `status` for every row from these inputs. It is read-only against
`discovered_sources`/`documents`; it only writes `payor_readiness_asset.status` + `compliance_reason`.

## 6. Gap → work-order loop

When the reconcile finds a required asset `missing`/`stale`, it emits **one signal per gap** to the
agent that can fix it, and stores the returned id in `gap_workorder_ref`. Reuse the existing
feedback-signal contract (same mechanism as `doc_stale` → `docs_refresh`):

| gap on… | routed to | payload |
|---|---|---|
| corpus asset missing/stale | RAG curator/ingestion | `{category:'payor_asset_gap', area_tags:['rag','<payor>'], asset_type, source_url}` |
| surface URL 404 / needs_auth | curator (or human-upload prompt) | `{category:'payor_surface_gap', ...}` |
| API capability gap | integrations agent (spec-only for now) | `{category:'payor_api_gap', capability, transport}` |

The registry never builds the asset; it files the ticket and tracks it to closure (gap clears when the
next reconcile sees the asset present + fresh, which nulls `gap_workorder_ref`).

## 7. Worked example — Aetna Better Health of Florida

Seed classification (verified from `mobius-rag/app/main.py`): payor `Aetna Better Health`,
state `FL`, program `Medicaid`. Rows below are the **initial catalogue**; unverified cells are
honest gaps with a workorder, which is the point — the registry surfaces exactly what to go get.

| asset_type | required | status | source_url / value | note |
|---|---|---|---|---|
| provider_manual | yes | **missing** | — | gap → RAG curator: locate & ingest FL provider manual |
| member_handbook | yes | **missing** | — | gap → RAG curator |
| medical_policies | yes | **missing** | — | Aetna/Centene clinical policy set; gap |
| um_policies | yes | **missing** | — | prior-auth criteria; gap |
| billing_manual | yes | **missing** | — | EDI companion guide; gap |
| fee_schedule | no | **missing** | — | ties to DOGE FL Medicaid rate work |
| provider_site_map | yes | **missing** | — | reconcile vs sitemap_data_v0.json (only Sunshine/AHCA present today) |
| provider_login_url | yes | **missing** | — | verify Availity vs native portal |
| eligibility_check_url | yes | **missing** | — | likely Availity |
| authorization_check_url | yes | **missing** | — | likely Availity |
| supported_portal | yes | **needs_auth** | Availity (assumed) | confirm Aetna Better Health FL is transacted via Availity |
| customer_support_phone | yes | **missing** | — | provider services line — do not guess |
| edi_payer_id | yes | **missing** | — | clearinghouse payer ID |

**API capabilities (Aetna Better Health FL):**

| capability | required | status | transport | note |
|---|---|---|---|---|
| eligibility_270_271 | yes | gap | availity? | confirm real-time 270/271 availability |
| auth_278 | yes | gap | availity? | prior-auth 278 |
| claims_837 | yes | gap | clearinghouse | with edi_payer_id |
| era_835 | yes | gap | clearinghouse | remittance |
| roster_feed | no | gap | — | ties to credentialing/roster module |

Every row is currently a gap — **that is a correct, useful first state.** It means: 13 corpus/surface
work orders + 5 API items to close before Aetna is "ready." Filling them (from the payor website via
the curator, or verified web lookup) is the next step, not fabrication.

## 8. Acceptance criteria

1. Migration creates both tables + the view; no change to `discovered_sources`/`documents`.
2. Aetna Better Health FL seeded with the full required taxonomy (present rows where verifiable,
   gap rows otherwise) — `coverage_pct` computes and is honest.
3. Nightly reconcile recomputes `status` from `discovered_sources` liveness + TTL, with zero writes
   to those source tables.
4. A missing/stale required asset produces exactly one open work-order signal, tracked in
   `gap_workorder_ref`, that clears when the asset lands.
5. `payor_readiness_scorecard` answers "how ready are we for payor X" in one query.

## 9. Next steps (proposed order)

1. **Land the migration** (this file's DDL) into `mobius-rag/app/migrations/` + SQLAlchemy models.
2. **Seed Aetna** from the taxonomy (gaps as gaps).
3. **Reconcile job** — read `discovered_sources`/`documents`, write `status`. Hook into the nightly pipeline.
4. **Fill Aetna gaps** — point the curator at aetnabetterhealth.com/florida + Availity; verified web lookup for phone/EDI ID.
5. **Second payor** (Sunshine Health) — import from the appeals-agent YAML to prove the migration path.
