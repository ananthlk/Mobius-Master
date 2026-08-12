# Filler s (Payor Platform Fact Store) — Calibration Report

**Status:** Real calibration run completed, 2026-07-23. Script: `mobius-rag/app/services/retriever/fillers/calibrate_filler_s.py`. Raw artifact: `filler-s-payor-calibration-results.json` (this directory).

**Not a mock.** This ran the actual `fill_shape_fact_store()` against the real, live `MOBIUS_PAYOR_URL` (`https://mobius-payor-ortabkknqa-uc.a.run.app`) — real HTTP round-trips, real responses, no fakes. Per the fleet's standing artifact-validation requirement (a filler's calibration was fabricated once before and caught), the script and its JSON output are attached as the real artifact, not a summary claim.

---

## Result: 6/6 gate-condition predictions matched

| Case | Query | Tags | Expected gate | Actual gate | Hit | Served |
|---|---|---|---|---|---|---|
| `tp_sunshine_phone` | "What is the phone number for Sunshine Health?" | `j:payor.sunshine_health, d:contact` | PASS | PASS ✅ | true | "1-844-477-8313" |
| `tp_aetna_priorauth_url` | "What is the prior authorization URL for Aetna?" | `j:payor.aetna, d:prior_auth` | PASS | PASS ✅ | true | Aetna PA URL |
| `tp_ahca_portal` | "What portal do I use for AHCA Florida Medicaid?" | `j:payor.ahca, d:portal` | PASS | PASS ✅ | **false** | — (see caveat below) |
| `tn_conceptual_with_payer` | "Explain the philosophy behind Sunshine Health's prior authorization process" | `j:payor.sunshine_health, d:prior_auth` | REJECT | REJECT ✅ | n/a (no call made) | — |
| `tn_no_payer_tag` | "What is the credentialing process for behavioral health providers?" | `d:credentialing, p:process` | REJECT | REJECT ✅ | n/a (no call made) | — |
| `known_bug_repro_unstored_payer` | "What is the phone number for Humana?" | `j:payor.humana, d:contact` | PASS | PASS ✅ | true | "1-800-441-5501" |

All 6 gate go/no-go decisions matched expectations — the two conceptual/no-tag rejection cases made **zero HTTP calls** (verified, not assumed), and the four gate-pass cases all correctly reached the fact store.

## Real, live-verified finding: the documented over-fire bug reproduces today, unchanged

`known_bug_repro_unstored_payer` ("phone number for Humana") is not a stored payer in the fact store, yet the client-side gate correctly *passes* it (a `j:payor.*`-shaped tag was present — the gate only checks tag presence, not whether the payer is actually stored, by design per the module spec §4). The server then returned `gate.applied: false, gate.payer_key: null` (correctly could not resolve "humana" to a stored payer) but **still served a fact anyway** (`customer_support_phone`, score 1.0, clearing the ungated `τ=0.85` bump on tag-overlap alone). This is a live, current reproduction of the `[[project-payor-fact-store]]` memory's PARKED "payer j-tag recognition over-fires... on non-stored payer" bug — confirmed still real and unfixed as of this run, not something Filler s introduced or can fix client-side (the ungated-serve decision is entirely server-side, in `fact_store.py`'s blend logic). Documented here for the record, not re-litigated — this is Payor/Eval's known, already-tracked issue.

## Honest caveat — hit-rate numbers are indicative, not final

The `tag_matches` used above are hand-picked stand-ins for what Gate would actually produce for these queries — there is no live Gate/Shape integration wired up yet to generate real `tag_matches` for a real query. What this run *does* validate for real: Filler s's own gate-condition **logic** (the go/no-go decision code this filler owns) behaves correctly against real inputs and a real live service. What it does *not* validate: whether Gate's real tag extraction on these exact query strings would produce the same tags I hand-picked — that depends on Gate's code, not Filler s's, and needs a real end-to-end integration test once Gate→Fillers wiring exists. The `tp_ahca_portal` case's `hit: false` (versus an earlier ad-hoc probe with different/fewer tags that did hit) illustrates this directly: adding one hand-picked `d:portal` tag that isn't a real matching fact tag diluted the blend's tag-overlap score below τ — a hand-crafted-tag artifact, not a finding about Filler s's or the fact store's correctness.

## Latency

`fact_store_ms` ranged 141–535ms across the 4 real calls (n=4, single run, not a load test) — consistent with the `[[project-payor-fact-store]]` memory's documented ~230ms median for a healthy fact-store path.

## Conclusion

Filler s's own code (gate logic, request construction, response parsing, miss/error handling) behaves correctly against the real, live service. Ready to route for cross-agent sign-off (Chat/Eval/DB/TECH) on that basis. Full end-to-end validation (with real Gate-derived tags) is a follow-up once Gate/Fillers integration exists — not a v1 blocker, since Filler s's contract is defined in terms of `tag_matches` it receives, not how those tags get produced.
