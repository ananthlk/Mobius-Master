# How to Read a Mobius Response Card
> Every answer from Mobius arrives as a structured card. This guide explains how cards are shaped, how to navigate their tabs, and what the badges and formats mean.

## Purpose
The response card is the surface every Mobius answer lives on. Understanding its modes, tabs, badges, and section formats lets you read an answer at a glance — and know how much to trust it. This is the canonical user-facing reference for the answer-card surface (authored by the UX team, 2026-07-13).

## Audience
End users of Mobius Chat. No technical background needed.

## What are the card modes? (Factual, Canonical, Blended, Recital)
Mobius picks the card mode automatically based on what kind of content it found; the mode sets the card's visual treatment and organization:

| Mode | When you see it | What makes it different |
|---|---|---|
| **Factual** (blue) | Single-fact questions — e.g. a specific rate or code lookup | Direct answer only; sections hidden by default |
| **Canonical** (green) | Policy or rule questions from authoritative sources | All sections visible immediately; "Approved" badge |
| **Blended** (violet) | Most questions — multi-source synthesis | Direct answer + expandable sections via the Details tab |
| **Recital** (violet, tinted) | Verbatim-critical content — founding documents, essays, exact policy quotes | Serif prose with a violet left border; no bullet compression |

## How do I use the Details and Citations tabs?
The **tab bar** appears on Blended and Canonical cards whenever there's more than a direct answer:
- **Details tab** — expandable sections organized by intent (requirements, process steps, exceptions, definitions, references). Each section uses the format best suited to its content (see formats below).
- **Citations tab** — formatted, numbered reference strings **you can copy directly into a denial letter, appeal, or documentation note**. Each citation includes the source document and locator (e.g. document name · section · effective date), with a per-citation Copy button.

Follow-up chips appear *below* the card bubble, not inside it — click one to send that question directly.

## What is a Recital card? (verbatim content)
When Mobius retrieves content that must not be paraphrased — a founding document, a verbatim policy statement, an official position — it switches to **Recital mode**: the prose renders exactly as written, in a serif typeface, with a violet left border and a "Verbatim" badge signaling that this is a quoted voice, plus an attribution line (e.g. "From the Mobius founding essay") and a **Read the full essay** button that opens the complete document.

Try it: ask **"why the name mobius"** or **"recite the why mobius essay"** to see Recital mode in action.

## What section formats can an answer use? (envelope formats)
Inside the Details tab, each section chooses the format that fits its content — not every answer is a bullet list. Six formats (all examples below are **illustrative, not current rates or rules**):
- **Bullets** (default) — short lists of requirements or notes.
- **Table** — comparisons, e.g. codes vs rates vs minimums.
- **Steps** — numbered process sequences (submit → include modifier → attach auth).
- **Stats** — key numbers as tiles (a rate, a claim window, a sessions-per-auth count).
- **Bars** — relative values compared visually.
- **Conditions** — if/then rules ("IF session > 52 min → use the 60-minute code").

The format is chosen automatically, but **you can steer it by asking** — "show me a rate comparison table" or "give me the steps to appeal this."

## What do the confidence badges mean?
The badge in the top-left corner of every card tells you how Mobius rates the answer:

| Badge | Meaning |
|---|---|
| ✓ **Approved – Authoritative** | Sourced from a document with verified authority (e.g. the FL AHCA fee schedule, CMS policy). High confidence. |
| ✓ **Approved – Informational** | Sourced from internal knowledge or a credible secondary source. Use as a starting point. |
| **Blended · 0.74** | Synthesized across multiple sources; the 0–1 confidence score is shown. Verify edge cases. |
| **Verbatim · Mobius founding document** | Exact quoted content. No paraphrasing has occurred. |

## Where do my uploaded files show? (the Vault block)
The **Vault block** lives in the left sidebar — a violet card showing your recently uploaded files with tabs (**Recent / Liked / Tasks / Uploads**) and a **Manage →** link. Click Manage or any item to open the full **Vault panel**, where you can download originals, see indexing status (Ready / Indexing / Failed / Expired chips), and manage TTL (documents expire after 7 days by default). **Promote to corpus** arrives once your org corpus is enabled; until then, uploaded files are searchable only within your own session.

## Doc-readiness notes
- **Primary audience tag:** user.
- **Source:** authored by the UX agent (canonical reference, artifact 4d5775e3, 2026-07-13); converted to corpus markdown by the product-awareness agent with one curation intervention: the mockups' realistic-looking rate examples are explicitly labeled illustrative so retrieval never serves them as real fee-schedule data.
- **Cross-links:** Recital mode ↔ the founding essay (about module); Vault ↔ the chat doc's Operations Suite section.
