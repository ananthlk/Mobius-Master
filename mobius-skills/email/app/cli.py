"""
CLI for email skill: prepare, send, mailto. Test before MCP integration.

Usage:
  python -m app.cli prepare --to you@example.com --subject "Hi" --body "Hello"
  python -m app.cli prepare --to you@example.com --llm "Remind them about the meeting tomorrow"
  python -m app.cli send --to you@example.com --subject "Test" --body "From CLI" [--confirm]
  python -m app.cli mailto --to you@example.com --subject "Hi" --body "Hello"
"""
import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

from app.skills import build_mailto_url, craft_email_with_llm, prepare_draft, send_via_system


def _list_arg(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def cmd_prepare(args):
    to = _list_arg(args.to)
    cc = _list_arg(args.cc or "")
    subject = args.subject or ""
    body = args.body or ""
    if args.llm:
        out = craft_email_with_llm(to, cc, args.llm)
        if out.get("error"):
            print("LLM error:", out["error"], file=sys.stderr)
        subject = out.get("subject") or subject
        body = out.get("body") or body
    draft = prepare_draft(to, cc, subject, body)
    mailto = build_mailto_url(draft["to"], draft["cc"], draft["subject"], draft["body"])
    print(json.dumps({"draft": draft, "mailto": mailto}, indent=2))


def cmd_send(args):
    to = _list_arg(args.to)
    cc = _list_arg(args.cc or "")
    subject = args.subject or ""
    body = args.body or ""
    if args.confirm:
        draft = prepare_draft(to, cc, subject, body)
        print("Draft:", json.dumps(draft, indent=2))
        ok = input("Send? [y/N]: ").strip().lower()
        if ok != "y":
            print("Aborted.")
            return
    result = send_via_system(to, cc, subject, body)
    print(json.dumps(result, indent=2))
    if not result.get("sent"):
        sys.exit(1)


def cmd_mailto(args):
    to = _list_arg(args.to)
    cc = _list_arg(args.cc or "")
    subject = args.subject or ""
    body = args.body or ""
    url = build_mailto_url(to, cc, subject, body)
    print(url)


def main():
    parser = argparse.ArgumentParser(description="Mobius email CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # prepare
    p_prepare = sub.add_parser("prepare", help="Prepare draft (optional LLM craft)")
    p_prepare.add_argument("--to", required=True, help="Comma-separated to addresses")
    p_prepare.add_argument("--cc", default="", help="Comma-separated cc")
    p_prepare.add_argument("--subject", default="", help="Subject (or use --llm)")
    p_prepare.add_argument("--body", default="", help="Body (or use --llm)")
    p_prepare.add_argument("--llm", default="", help="User text for LLM to craft subject+body")
    p_prepare.set_defaults(run=cmd_prepare)

    # send
    p_send = sub.add_parser("send", help="Send via system (mobiushealthai@gmail.com)")
    p_send.add_argument("--to", required=True, help="Comma-separated to addresses")
    p_send.add_argument("--cc", default="", help="Comma-separated cc")
    p_send.add_argument("--subject", required=True, help="Subject")
    p_send.add_argument("--body", required=True, help="Body")
    p_send.add_argument("--confirm", action="store_true", help="Show draft and confirm before send")
    p_send.set_defaults(run=cmd_send)

    # mailto
    p_mailto = sub.add_parser("mailto", help="Print mailto URL (user client)")
    p_mailto.add_argument("--to", required=True, help="Comma-separated to addresses")
    p_mailto.add_argument("--cc", default="", help="Comma-separated cc")
    p_mailto.add_argument("--subject", default="", help="Subject")
    p_mailto.add_argument("--body", default="", help="Body")
    p_mailto.set_defaults(run=cmd_mailto)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
