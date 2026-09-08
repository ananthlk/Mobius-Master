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
