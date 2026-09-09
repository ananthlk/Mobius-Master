# Adoption Attach-Rate Assumptions — Footnoted

> Model inputs for the Mobius revenue model: of organizations that become platform customers, the share that also adopts each product layer. Net posture: **base case** — Copilot leans high, App Store leans low, and the two roughly offset. Benchmarks pulled 2026-09-02.

| Layer | Attach rate | Posture |
|---|---|---|
| Adopt Platform | 100.0% | Definitional [^1] |
| Adopt Copilot | 60.0% | Base if bundled; aggressive if a paid add-on [^2][^3][^4] |
| Adopt Agentic | 40.0% | Aggressive years 1–3; base by ~2028 if vendor-embedded [^5][^6][^7] |
| Adopt App Store | 15.0% | Conservative vs. mature marketplaces; base for paid attach in a young one [^8][^9] |

**Structural notes.** (a) Treat the tiers as a nested funnel — agentic adopters ⊂ copilot adopters — or the multiplication double-counts. (b) Each rate conflates two different numbers: org-level attach and seat-level activation; in healthcare copilots those differ by ~2× at the same institutions [^3][^4]. (c) These need a time dimension — the agentic and app-store benchmarks below move fast; band them low/base/high with a year ramp.

[^1]: 100% is valid only as "is a platform customer" — it is conditional on the sale, so it anchors the funnel by definition. If "adopt" means *actively uses*, enterprise seat activation typically runs 60–80%, not 100%.

[^2]: Paid-add-on comparator: Microsoft 365 Copilot reached ~4.4–6.5% of eligible commercial Microsoft 365 seats two-plus years post-launch (20M seats of ~450M in Q3 FY26; ~30M of ~464M by Aug 2026). If Mobius Copilot is separately priced, 60% is far above the best-known software comparator. Sources: [SQ Magazine Copilot statistics](https://sqmagazine.co.uk/copilot-statistics/), [AI Business Weekly](https://aibusinessweekly.net/p/microsoft-copilot-statistics).

[^3]: Bundled / high-ROI healthcare comparator: 62.6% of US hospitals on Epic (1,744 of 2,784) had adopted an ambient AI tool by June 2025 — org-level attach when the capability rides an existing platform and has direct time-savings ROI. KLAS finds >70% of large IDNs deployed or piloting ambient scribes. 60% org-level attach is consistent with this. Sources: [AJMC](https://www.ajmc.com/view/ambient-ai-tool-adoption-in-us-hospitals-and-associated-factors), [Medical Economics](https://www.medicaleconomics.com/view/take-note-the-ai-scribe-era-is-here).

[^4]: Seat-level check on the same institutions: clinician-level ambient-AI adoption is ~35% today, expected ~40% over three years ([Menlo Ventures, State of AI in Healthcare 2025](https://menlovc.com/perspective/2025-the-state-of-ai-in-healthcare/)). So 60% of *orgs* = base case; 60% of *seats* = aggressive.

[^5]: McKinsey: only 23% of organizations have scaled any agentic system into production; fewer than 10% of experimenters got one far enough to deliver measurable value; healthcare trails at ~18% with at least one agent in production (banking/insurance lead at ~47%). Sources: [TURION.AI summary](https://turion.ai/blog/state-of-ai-agents-enterprise-adoption-2026/), [Digital Applied data points](https://www.digitalapplied.com/blog/ai-agent-adoption-2026-enterprise-data-points).

[^6]: Gartner cuts both ways: >40% of agentic AI projects predicted canceled by 2027 (unclear ROI, weak risk controls) — but 40% of enterprise applications will embed task-specific agents by end-2026, up from <5% in 2025. The reconciliation: *customer-driven* agent projects fail; *vendor-embedded* agents diffuse with the platform. Source: [Gartner via Hostinger roundup](https://www.hostinger.com/tutorials/agentic-ai-statistics).

[^7]: Segment adjustment: Mobius buyers are small FL BH providers/CMHCs with thin IT capacity — the trailing edge of the healthcare-trails-at-18% stat. 40% is reachable only if "agentic" means embedded human-in-loop automation inside workflows they already use (appeals drafting, denial follow-up). Model 15–20% in years 1–2 ramping to 40%.

[^8]: Mature-marketplace ceiling: ~91% of Salesforce customers have installed ≥1 AppExchange app; athenahealth's Marketplace (500+ vetted apps) is a standard part of that platform. Against mature *usage* benchmarks, 15% is very low — but those ecosystems took a decade-plus to build. Sources: [Salesforce Ben](https://www.salesforceben.com/biggest-myths-appexchange/), [athenahealth](https://www.athenahealth.com/resources/blog/what-is-athenahealth-marketplace).

[^9]: Early-marketplace reality: a new app store faces cold start (few apps → few installs → few developers), small-provider segments install fewer apps than enterprises, and if "adopt" means *pays for* a third-party app the attach is far below install rates. As a paid-attach assumption in years 1–3, 15% is a sane base case.
