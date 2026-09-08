# Dependency audit — 2026-09-08

Triggered by a deploy failure, not a schedule. Recorded so the next person does
not redo the analysis.

## What happened

`mobius-db-agent` failed to start after a routine rebuild:

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
This is mcp 2.x, where FastMCP was renamed to MCPServer
```

`requirements.txt` said `mcp[cli]>=1.0.0` with no upper bound. The running
revision worked only because it had been built while 1.x was current. The service
was not broken — it was **unreproducible**, which is harder to notice, because
nothing fails until someone needs a deploy to succeed.

## The scale

**886 of 909 requirement lines across 56 files are unbounded.** Only 23 carry an
upper bound. Widest blast radius: `fastapi` and `uvicorn` (48 files each),
`httpx` (41), `pydantic` (31), `anthropic` (25).

So db-agent was not unlucky. It was representative.

## What was fixed

`mcp` pinned to `<2` in the three places importing the v1 API:

| Repo | Status when found |
|---|---|
| `mobius-db-agent` | deploy already failing |
| `mobius-skills/provider-roster-credentialing` | **live and unreproducible** |
| `mobius-skills-mcp` | not deployed; fleet-wide 15-tool server |

Verified by rebuilding provider-roster-credentialing (rev 00094-5dl, /health ok).
Without the pin that build fails.

## What was cleared, and how

Neither of these needed a pin. Both were checked rather than assumed.

**`anthropic` 0.x → 1.x** — a real breaking major (httpx2 replaces httpx, async
`.with_raw_response` must be awaited, Text Completions removed, Python >= 3.10).
None applies here: 15 files import it, none co-import `httpx`, none use
`with_raw_response` or Text Completions, every Dockerfile is Python 3.11+, and
the entire surface used is `anthropic.Anthropic` + `client.messages.create`.

**`bcrypt` 4 → 5** — the one that would have failed *silently*: a green build and
users unable to log in. Tested directly — generated a hash on 4.3.0, upgraded to
5.0.0 in place, confirmed the stored hash still verifies, wrong passwords are
still rejected, and the `$2b$12$` format is unchanged.

## Still unknown

`redis` (5 -> 8, 21 files), `google-cloud-aiplatform` (1 -> 2), 
`google-cloud-storage` (2 -> 3), and the remaining ~880 unbounded lines. Left
alone deliberately: bounding services that cannot be individually tested trades a
theoretical failure for a real one.

## The pattern worth keeping

**The loud failures are the safe ones.** `mcp` killed a container on import —
impossible to miss, and fixed within the hour. The dangerous class is the one
that builds green and misbehaves at runtime, which is why `bcrypt` got a direct
compatibility test rather than an argument.

Two rules that would have prevented this:
1. An unbounded dependency on a library that ships majors is a latent outage. At
   minimum, bound the ones whose API you import directly by name.
2. A service nobody has rebuilt recently is not known-good. It is unverified.

## Round 2 — the three deferred major bumps (2026-09-08)

Same method as `bcrypt` 4→5: a throwaway venv in `/tmp`, the used surface
discovered by grep across the tree, then the same introspection script run
against both majors and diffed. **No module code, config, or requirements file
was touched, and nothing was deployed.** These are findings, not changes.

### `redis` 5 → 8 — CLEARED

Used surface (8 files): `from_url`, `get`, `set`, `ping`, `pipeline`, `expire`,
`scan_iter`, `publish`, `lpush`, `brpop`, `pubsub`, `redis.TimeoutError`,
`redis.ConnectionError`.

5.3.1 vs 8.1.0: every used name present. One signature differs — `set()` gains
four *optional* params (`ifeq`, `ifne`, `ifdeq`, `ifdne`) appended after the
existing ones. Purely additive; no call site affected.

### `google-cloud-storage` 2 → 3 — CLEARED

Used surface (22 files): `storage.Client` (55), `.bucket()` (65), `.blob()` (55),
`upload_from_*` (37), `download_as_*` (21).

2.19.0 vs 3.13.1 — two signature diffs:

- `Client.__init__` **gains** `api_key`. Additive.
- `Blob.upload_from_string` **drops** `num_retries` and gains
  `crc32c_checksum_value`. A removal, so it was checked directly:
  `grep -rn num_retries --include='*.py'` across the whole tree returns **zero
  hits**. Not a break here.

### `google-cloud-aiplatform` 1 → 2 — CLEARED

The highest-stakes of the three: 44 files, and it is the path every embedding and
every Vertex generation call goes through — `GenerativeModel` (40),
`vertexai.init` (27), `from vertexai.generative_models` (22),
`TextEmbeddingModel` (21), `from vertexai.language_models` (11),
`aiplatform.init` (11), `aiplatform.MatchingEngineIndexEndpoint` (7).

1.165.1 vs 2.1.0: **twelve probes, twelve identical results** — `aiplatform.init`,
`MatchingEngineIndexEndpoint.__init__` / `find_neighbors` / `deploy_index`,
`vertexai.init`, `GenerativeModel.__init__` / `generate_content` / `start_chat`,
`TextEmbeddingModel.from_pretrained` / `get_embeddings`, and the full symbol sets
of both `vertexai.generative_models` and `vertexai.language_models`. Importing
those modules on 2.1.0 under `-W always` emits **no** deprecation warning.

The major bump removed things; none of them are things Mobius touches.

### What this does and does not establish

It establishes that the **names and signatures** Mobius calls survive each bump.
It does not establish runtime behaviour against live GCS, Redis or Vertex — no
network call was made. Any actual upgrade still gets deployed one module at a
time and verified against the running service.

## Round 3 — the fourth mcp instance, and why the first sweep missed it

`mobius-appeals-prototype` was the fourth service importing
`mcp.server.fastmcp.FastMCP`. The first sweep missed it for two reasons, both
worth recording because they generalise:

1. **It has no `requirements.txt`.** Every dependency is installed inline in the
   Dockerfile: `RUN pip install --no-cache-dir fastapi uvicorn pyyaml httpx
   asyncpg "mcp[cli]>=1.0"`. A sweep that reads requirements files sees nothing.
2. **Its failure was swallowed, not fatal.** `api/app.py` wraps the MCP route
   injection in `except Exception as _mcp_err: log.warning("...non-fatal...")`.
   Where db-agent died loudly on import, this container started clean and simply
   served no MCP tools.

So this was not a latent risk. It was a **live capability outage**:

- `Appeals MCP route injection failed (non-fatal): No module named
  'mcp.server.fastmcp'` — first logged **2026-08-10**, revision `00147`.
- **29 days** with zero appeals tools exposed, while callers took **189 `/mcp`
  404s on 2026-09-08 alone** and 11 the day before.
- `GET /mcp` returned 404 on the live revision and 406 on the pinned rebuild —
  406 being what a streamable-HTTP MCP endpoint correctly returns for a bare GET.

**Fix and verification.** Pinned to `"mcp[cli]>=1.0,<2"`. Built on Cloud Build
(green), deployed as a **no-traffic** revision so Cloud Run health-checked it
under real config while 100% of traffic stayed on `00177`. That revision came up
Ready and logged `Appeals MCP routes injected at /mcp (5 tools)`. Only then was
traffic promoted. All five tools now list over `/mcp/tools`:
`appeals_lookup_rules`, `appeals_get_playbook`, `appeals_find_carc`,
`appeals_validate_claim`, `appeals_assemble_letter`.

### The mcp class is now closed

Four services import `mcp.server.fastmcp`; all four are pinned `<2`:
`mobius-db-agent`, `mobius-skills-mcp`, `provider-roster-credentialing`,
`appeals-agent`.

`mobius-chat` is the only other consumer and is a **client**, not a server. Its
runtime imports were tested against mcp 2.2.0 and all pass:
`mcp.client.session.ClientSession`, `mcp.client.streamable_http`, `mcp.types`.
One import does break — `mcp.shared.exceptions.McpError`, renamed to `MCPError`
in 2.x — but it appears **only in `mobius-chat/tests/`**, never at runtime. Chat
is deliberately left unpinned: a rebuild would break its test suite, not the
service. Recorded rather than changed.

The root `requirements.txt:72` carries an unbounded `mcp[cli]>=1.0.0`, but no
image builds from it — `Dockerfile.module-hub` is stdlib-only with no pip step.

### The lesson worth keeping

A swallowed import turns a crash into an invisible capability loss. db-agent's
failure was found in a day because the container died. This one ran for 29 days
looking healthy — `/health` 200, `/docs` 200, startup clean — while the thing it
exists to provide was simply absent. **Any `except Exception: log.warning(...)`
around a capability import needs a readback that proves the capability is
actually there**, or the health check is lying.

## Round 4 — provenance sweep: does anything deploy from code that is on no remote?

Every deployed Cloud Run service, traced from its image back to a git ref.

**Method note, because the naive form of this check over-reports.**
`git rev-list <sha> --not --remotes` excludes remote *branches* but **not tags**.
A first pass flagged `mobius-story-ui`, whose deployed commit is in fact carried
by the pushed tag `v1.0.0`. The correct test is `--not --remotes --tags`.

### Found and fixed

- **`mobius-phi-classifier`** — deployed sha `94cf81b` (2026-07-22) lived on a
  local `feat/phi-classifier` and on no remote for **48 days**: 47 lines across
  `classifier.py`, `config.py`, `models.py` and a test, on a PHI service. The
  branch existed on origin at `bb083cd`; local was exactly one commit ahead.
  Pushed (fast-forward).
- **`mobius-rag`** — not a deployed-image problem but found by the same sweep:
  three commits sat on a local `main`, unpushed since 2026-08-12/17, including
  `feat(curator): the source-registry curator UI`. A direct push was impossible
  (3 ahead, 201 behind). Preserved first to `rescue/unpushed-main-20260908` (a
  pure ref push), then merged onto `origin/main` **in a temporary worktree** so
  the shared checkout's seven in-flight dirty files were never touched. One real
  conflict in `tests/test_curator_service.py`, resolved by inspection: the branch
  side of the hunk was empty, so keeping origin/main's two provenance tests lost
  nothing. Pushed as `d8aef46`.

### The two hand-named tags, traced

Both had no git sha in the tag and no build label, and were left as **unknown**
rather than assumed clean. Both are now resolved:

**`mobius-rag/rag:inletparity`** — Cloud Build `836436b4`, 2026-09-06, source a
GCS tarball. Fingerprinted by blob: `app/main.py` matches exactly one commit,
**`53f6178`**, whose date matches the build. Confirmed across the whole tree —
**224 of 224 `app/**.py` byte-identical, 0 differ, 0 absent**. `53f6178` is an
ancestor of `origin/main`. Safe.

*One real gap it exposed:* of 927 source files in that tarball, 8 are not in git
— five `.claude/worktrees/` scratch files swept in by the upload, and three
**`frontend/dist/` build artifacts** (`index.html`, `index-*.js`, `index-*.css`).
The shipped frontend bundle is therefore not reproducible from git alone, and
`frontend/dist/index.html` is currently uncommitted in the working tree.

**`mobius-task-manager/task-manager:20260719-214044-phi-gate-labelrule`** — no
Cloud Build record; built locally with the classic builder at
2026-07-20T01:41:36Z, which is the local time in the tag. No labels, so no sha to
read. Traced by content instead: the image config's four `COPY` layers were
pulled from Artifact Registry and extracted, and **all 36 shipped files are
byte-identical to `origin/main` today** — 0 differ, 0 absent.

Precisely stated: for task-manager I could not name the *commit that built it*,
but I proved the deployed content is fully recoverable from a pushed ref, which
is the property that actually matters here.

### Standing after this sweep

31 services. Every one is now either traced to a commit on a remote, or proven
byte-recoverable from one. Two commits remain unpushed on `mobius-rag`'s
`retriever-answer-engine` — both dated today, another session's live work, and
deliberately left alone.
