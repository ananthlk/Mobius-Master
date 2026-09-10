#!/usr/bin/env python3
"""Probe an MCP server: list tools, then call one, reporting isError verbatim.

Written for the appeals-misroute investigation (2026-09-10). The point is the
THREE-WAY comparison, because that is what separated the defects:

  * which server ADVERTISES the tool          -> list_tools
  * what the server RETURNS when called       -> content text
  * what the transport SAYS about it          -> isError, reported raw, never
                                                 coerced with a default

`getattr(result, "isError", False)` fails OPEN -- a renamed or absent attribute
reads as success. So this prints the attribute's presence separately from its
value; "absent" and "False" are different findings and must not be conflated.

Usage:
  probe_mcp_tool.py <mcp-url> [tool_name] [json_args]

  probe_mcp_tool.py https://host/mcp
  probe_mcp_tool.py https://host/mcp appeals_lookup_rules '{"carc":"197"}'

Run it against BOTH the primary (CHAT_SKILLS_MCP_URL) and each EXTRA_MCP_URLS
entry. A tool absent from the server that chat dispatches to, but present on
another, is the misroute.
"""
from __future__ import annotations
import asyncio, json, sys

SENTINEL = object()


async def probe(url: str, tool: str | None, args: dict) -> int:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10),
                                 follow_redirects=True) as http_client:
        async with streamable_http_client(url, http_client=http_client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                names = sorted(t.name for t in (await session.list_tools()).tools)
                print(f"{url}\n  advertises {len(names)} tool(s)")
                for n in names:
                    print(f"    {n}")
                if not tool:
                    return 0

                print(f"\n  call_tool({tool!r}, {args!r})")
                if tool not in names:
                    print(f"    NOT ADVERTISED by this server -- expect an unknown-tool error")
                result = await session.call_tool(tool, args)
                text = "".join(getattr(c, "text", "") for c in (result.content or []))

                raw = getattr(result, "isError", SENTINEL)
                if raw is SENTINEL:
                    # Distinct from False: the flag chat's code reads does not
                    # exist on this SDK version, and its getattr default would
                    # silently report success.
                    print("    isError  ATTRIBUTE ABSENT  <-- getattr(...,False) would read as SUCCESS")
                else:
                    print(f"    isError  {raw!r}")
                print(f"    text     {text[:300]!r}")
                return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    tool = sys.argv[2] if len(sys.argv) > 2 else None
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    try:
        return asyncio.run(asyncio.wait_for(probe(url, tool, args), 90))
    except Exception as exc:
        # Report the class, not just the message -- a transport error and a
        # protocol error look identical in str() and mean different things.
        print(f"FAILED  {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
