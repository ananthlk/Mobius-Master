# RAG refactor — Write-Coordination Protocol

**Status:** in force 2026-07-22 (Ananth's call). **Why:** all RAG legs + Lexicon share ONE working tree (`/Users/ananth/Mobius`) with **no branches** (Ananth can't create more). Parallel edits will clobber. This protocol lets legs work concurrently where safe and serializes where they'd collide.

**Enforced by:** Master RAG (coordinator, holds the edit token). **Structurally gated by:** Technical Review. **Ownership source of truth:** `docs/rag-agents/module-map.md`.

## The rules

1. **Edit only YOUR files.** A leg edits only the modules/paths assigned to it in the module-map. You never touch another leg's files. Non-overlapping files = edit freely, in parallel, no token needed.

2. **Shared-seam files are SERIALIZED — one leg at a time, via the edit token.** These files span legs or are the god-file; only the token-holder may edit them:
   - `app/main.py` (god-file — everyone's routes buried here)
   - `app/worker/**` (Sourcing ingest-half ⟷ Curation chunk/embed-half)
   - any file two legs both need to touch for a seam
   To edit one: request the token from Master RAG → it grants ONE leg → edit → **commit** → release → next leg.

3. **Small, frequent, scoped commits.** In a shared tree, uncommitted changes are visible to everyone. Commit your unit as soon as it's coherent; never leave large uncommitted WIP on a shared area; never commit another leg's work. Clear scoped commit messages (`[sourcing] ...`, `[curation] ...`).

4. **Single writers for the two governance files:** `ownership.yaml` → Technical Review only. The structure/module-map → Technical Review (with Master RAG). Don't edit these directly.

5. **Every seam cut is structurally gated.** Before a shared-seam change merges, Technical Review verifies it (byte-compat / single-owner / no-god-file). A cut isn't done until I re-run the check.

## Order of operations (unblocks clean ownership fastest)

1. **`app/main.py` → per-leg routers** (Master RAG coordinates, holds the token). This extracts each leg's routes into `app/routers/*` and is what turns leg ownership into clean path-globs. **Do this first** — it unblocks everyone.
2. **`app/worker` split** (Sourcing + Curation propose the line; token-serialized; I gate).
3. **`app/curator` → `app/web_sourcing` rename** (Sourcing; I gate the collision fix).
4. **Per-leg module work** — parallel on own files once the seams above are cut.

Retriever's engine refactor stays **parked** (P2) throughout — not part of this sprint.
