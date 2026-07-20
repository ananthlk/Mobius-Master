# Instant RAG — P0 UX Spec (UX agent, 2026-07-09)

Companion to `docs/instant-rag-progress-contract.md`. Authored by the UX agent; captured
here as the durable source of truth (cross-session relay kept failing). Chat wires this
against the live SSE bridge `GET /chat/uploads/{document_id}/events`.

## Foreground cutoff

`FOREGROUND_CUTOFF_S = 12`. Two uses:
1. **Pre-commit** (from upload response): if `estimated_seconds >= 12` → skip the strip,
   show the background toast immediately.
2. **Mid-progress escape**: if `elapsed >= 12` and not yet `ready` → drop to background,
   rely on the durable notify (§3 of the contract).

> ⚠ Depends on RAG returning a realistic `estimated_seconds`. If RAG returns a flat high
> value (e.g. 30) for small docs, the foreground strip never shows. Fix is on RAG; a
> fallback is to pre-commit on `page_count` rather than `estimated_seconds` — decide with UX.

## Foreground progress strip

Slim band **above** the composer, never in the message list. 4px bar driven by `pct`.

```
[📄 Aetna_policy.pdf]  ████████░░░░  Chunking · 9/20 · 5s  [×]
```

Layout: doc icon + truncated filename | flex-1 progress bar | stage microcopy | `[×]` escape.

**Stage microcopy** (map from the `stage` field):

| `stage` | user sees |
|---|---|
| `queued` | `Queued…` |
| `extracting` | `Extracting pages…` |
| `chunking` (no `chunks_total`) | `Splitting into chunks…` |
| `chunking` (with `chunks_done`/`chunks_total`) | `Chunking · {done}/{total}` |
| `embedding` | `Indexing…` (not "Embedding" — ML term is invisible to users) |
| `publishing` | `Almost ready…` |
| `ready` | `Ready ✓` |

**On `ready` terminal event:**
1. Bar → 100%, color → `var(--mobius-success)` (400ms ease)
2. Label → `Ready ✓` for 400ms
3. Strip collapses (height 0, 300ms)
4. Composer: if empty → populate the suggested question + focus, **do NOT auto-submit**.
   If the user already typed → don't overwrite (the doc chip in the attach zone suffices).

**CSS:**
```css
.rag-progress-strip { display:flex; align-items:center; gap:.75rem; padding:.45rem .75rem; max-width:640px; margin:0 auto .5rem; background:var(--mobius-bg-secondary); border:1px solid var(--mobius-border-light); border-radius:var(--mobius-radius-base); font-size:var(--mobius-text-xs); overflow:hidden; transition:max-height .3s ease, opacity .3s ease; }
.rag-progress-strip--collapsed { max-height:0; opacity:0; padding:0; margin:0; }
.rag-progress-strip__name { flex-shrink:0; max-width:180px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--mobius-text-secondary); }
.rag-progress-strip__bar-wrap { flex:1; height:4px; background:var(--mobius-border); border-radius:var(--mobius-radius-full); overflow:hidden; }
.rag-progress-strip__bar { height:100%; border-radius:inherit; background:var(--mobius-violet); transition:width .4s ease, background .3s ease; }
.rag-progress-strip__bar--ready { background:var(--mobius-success); }
.rag-progress-strip__stage { flex-shrink:0; min-width:160px; color:var(--mobius-text-muted); white-space:nowrap; }
.rag-progress-strip__close { flex-shrink:0; border:none; background:transparent; color:var(--mobius-text-muted); cursor:pointer; font-size:1rem; line-height:1; padding:0 .2rem; }
.rag-progress-strip__close:hover { color:var(--main-text); }
```

## Background states

- **Pre-commit toast** (`estimated_seconds >= 12`): `"{filename}" is processing — I'll let
  you know when it's ready` — 3s auto-fade, reuse `_showToast()`. No action.
- **Mid-progress `[×]` click** (user backgrounds manually): same toast, to confirm the escape.
- **User navigates away while bar showing**: drop the strip silently, no toast (SSE replays
  the terminal event on re-subscribe).
- **Ready nudge chip** (reuse `.reminder-nudge`, doc icon): `📄 "{filename}" is ready
  [Ask now] [×]`. `Ask now` → origin thread + focus composer with the suggested question;
  `[×]` one-shot dismiss.
- **System message on ready**: `✓ {filename} is ready — ask me about it.` Two chips:
  `[Ask about this →]` (pin doc, populate suggested question, focus) + `[View in Vault ↗]`
  (**stub/hide for P0** — Vault is P1).

## Failed state

**Foreground (strip transforms in place):**
- Bar freezes at current `pct`, color → `var(--mobius-error)`.
- Stage label → `Couldn't process` (or `Couldn't process · {error}` if `failed.error` is
  user-readable).
- `retryable: true` → `[Retry]` (re-process on the existing `document_id` — see contract §2).
- `retryable: false` → `[Remove]`.

**System message on failed:**
- Retryable: `⚠ {filename} couldn't be processed` + `[Retry] [Remove]`.
- Non-retryable: `⚠ {filename} couldn't be read — {failed.error}` + `[Remove]`.
- Never "an error occurred" — surface the failure mode when we know it.
