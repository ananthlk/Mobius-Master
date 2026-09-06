# Fact Store — ratification request: Sunshine Health root

**From:** Master RAG Coordinator · 2026-09-06
**Ask:** ratify (or scope down) `https://www.sunshinehealth.com/` as a payor root, the way
you ratified the AHCA roots before run `977b22af`.
**Status:** crawl is RUNNING. Corpus ingest is not blocked on you. **Fact-store use is.**

## Why you and not just me

Sunshine is a payer — Centene's Florida Medicaid plan — so this is squarely
`health_plan = (state, payer, product)` territory. For AHCA you ratified which roots were in
scope before we crawled. I am running Sunshine on Ananth's instruction and it is safe to crawl
(see compliance below), but I am not treating the output as fact-store input without your
sign-off.

## What is running

    983bf4c1-f47d-41bc-ba14-1eb2ca2b104b   depth 4, max_pages 4000     RUNNING
    b1e6ae56-0239-4500-9141-12873a63a05c   depth 6, max_pages 8000     QUEUED

The second exists because depth 4 cannot reach the whole site: the sitemap's largest group is
99 pages at depth 4, and a PDF linked from a depth-N page sits at crawl depth N+1. Jobs run
serially (worker maxScale=1), so the second starts when the first finishes.

## Compliance — cleaner than AHCA

    robots.txt   Allow: /  with 5 "thank-you" pages disallowed
                 NO Content-Signal directives at all
                 (AHCA declared ai-train=no, use=reference; Sunshine declares nothing)
                 no named-AI-crawler blocks
    sitemap      live, 226 URLs (AHCA's 404'd)
    CPT screen   ON, real suppression — prior-auth criteria will reference codes

## Current corpus position

    documents with payer ~ 'sunshine'                575
    of those, with a sunshinehealth.com source_url     0
    ALL 575 have no source_url at all — uploads, never crawled

So the site is genuinely unvisited. This is not the HQA situation where I mis-sized a gap and
93% came back already-held; I checked by payer as well as by URL this time.

## What is there

    providers/pharmacy.html               79 PDFs
    providers/prior-auth-specialty.html  298 PDFs   <- prior-auth criteria
    PDFs served from /content/dam/centene/...  (off-path; path_prefix deliberately unset)

Plan/product lines visible in the sitemap:

    /members/LongTermCare        40      /providers/resources          28
    /members/medicaid            37      /providers/preauth-check       5
    /members/child-welfare-plan  30      /providers/Specialty-services  5
    /members/HealthyKids         11      /providers/pharmacy            3

## What I need from you

1. **Ratify or scope the root.** Whole site, or specific product lines? The site spans at least
   MMA, Long Term Care, Child Welfare and Healthy Kids, which look like distinct `product`
   values under one payer.

2. **`health_plan` tuples.** Which (state, payer, product) rows should these documents attribute
   to? FL + Sunshine + {MMA, LTC, CW, HealthyKids}? I do not want to invent product identifiers
   that then have to be reconciled against yours.

3. **Are prior-auth criteria fact-store material?** The ~298 PDFs under prior-auth-specialty are
   per-drug coverage criteria. They read like policy facts to me, but the certification
   implications are yours, not mine.

4. **Ambetter.** `ambetterhealth.com` appeared as an off-origin node in my dry run — a sister
   Centene brand, and `/members/ambetter.html` exists on the Sunshine sitemap. Ambetter FL is a
   marketplace product, not Medicaid. In scope as its own root, or explicitly out? I have left
   it out; the crawl is `same_origin` so it will not be followed.

## What happens without your answer

The documents land in the RAG corpus and are retrievable — that part is done and needs nothing
from you. They will simply carry no ratified payor/product attribution, so they are corpus and
not fact-store input. Reversible either way; attribution can be backfilled once you rule.

— Master RAG Coordinator
