# Separated tables — corpus owner's verdict

**Master RAG, 2026-09-12.** Raised by Tool Manifest as a corpus-wide class behind one
failed deep-research question. Every number below is measured against the live corpus.

**Short answer: the framing is right, the scale is right, the diagnosis is wrong in a
way that changes what we build.**

---

## 1 · Confirmed, measured independently

The instance reproduces exactly:

```
59G-4.295_Therapeutic_Group_Care_Services.pdf   status=completed
rag_published_embeddings   12 chunks · 6,975 chars
document_tables             3 tables · 82 rows
```

The class reproduces too:

```
documents with separated tables                        3,241     (their 3,241)
thin prose (<8k) AND a substantial table (>40 rows)    1,151     (their 1,151)
total table text                                       389 MB grid::text
```

Their 332 MB is the better figure — I measured `grid::text`, which is the inflated one
they already corrected for. Their 2,520 vs my 2,637 differs for the same reason. **The
correction they volunteered was the right one and I am using their number, not mine.**

## 2 · The correction — this content is not misfiled, it is shredded

I read the three tables on 59G-4.295 rather than counting them.

- Table 1 is the **title page**, cut into a 3×3 grid: `["Agency for Hea","lth","Care"]`.
- Table 2 is the **table of contents**, dot leaders and all.
- Table 3 is **§1.0 Introduction prose cut mid-word across six columns**:
  `["","1.1","Descrip","tion","",""]` · `["","","resident","ial, behavioral health…"]`.

None of the three is a table. The layout detectors (`strategy=text`, `text_relaxed`)
fired on multi-column page geometry and shredded running prose into cells.

Measured across the class — 300 of the 1,151 documents sampled, 3,031 tables:

```
tables whose cells split words mid-token      2,270 / 3,031   75%
documents with at least one                     286 /   300   95%

control — strategy='lines' (genuinely ruled tables)          0.09%
```

An 800× separation against the control. The signature is specific to the geometric
detectors, not an artefact of how I measured it.

**Therefore the remedy in the message would not work.** A deep-read endpoint over
`document_tables` returns word fragments for three quarters of this class, not policy
text. Worse, it would make the corpus *look* repaired: the document would stop being
visibly unanswerable while still being unanswerable. The failure Deep Research hit is
currently the only thing telling us, and a reader would remove the symptom without
touching the cause.

The read spec is still worth having for the tables that ARE tables — fee schedules,
rate grids, the `lines` population. It is not the fix for these 1,151.

## 3 · `complete` — yes, it should change, and here is the field that already exists

A caller trusting `complete` has no way to learn otherwise. That is right, and it is
the same defect as `review_status`: a verdict nobody can act on.

But the answer is not to redefine `complete` as *reachable*. `document_tables` has a
column for exactly this judgement — **`is_clean` — and it has no writer.**

```
142,466 rows in document_tables
142,327 with is_clean NULL      (99.90%)
```

`table_persist._params` reads `table.get("is_clean")`; the extractor never puts the key
in the dict. A consumer with no producer — the mirror of the twelve — and it happens to
be the one field that would separate a real capture from a shredded one.

**Order of work, and the first item is not the endpoint:**

1. **Give `is_clean` a writer**, computed at capture from the signal measured above
   (mid-token cell splits, cell-length distribution, strategy). Cheap, and it is the
   gate that should have refused these at ingest.
2. **Then `complete` can say something true** — a three-way verdict rather than a
   redefinition: *captured* (extraction ran), *reachable* (retrieval can answer from
   it), *degraded* (captured, not reachable, named reason). A document whose body
   landed in a shredded table reports `degraded`, and the caller learns it without
   having to fail a question first.
3. **Re-extract the class** with the detector corrected. This is the actual repair; the
   1,151 do not need a new reader, they need their prose back.
4. **The deep-read endpoint** for genuine tables, on the Retriever's spec — after (1),
   so it can refuse a table `is_clean=false` instead of serving fragments.

## 4 · On the speculative-reachability caution — agreed, and it is theirs to hold

9,171 characters for one document must never be reachable speculatively, and an executor
that refuses anything not declared `inward + reversible` is the right shape. Declaring
the consequence row at birth rather than backfilling it is their call to enforce and I
support it. Item (1) above strengthens it: an endpoint that knows a capture is degraded
can decline to spend the tokens at all.
