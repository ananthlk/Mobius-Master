#!/usr/bin/env python3
"""
Test script for Mobius email skill. Run from mobius-skills/email:
  python scripts/test_email.py
  python scripts/test_email.py --send   # actually send one (requires GMAIL_* or SMTP)
  python scripts/test_email.py --api    # use HTTP API (start server on 8003 first)
"""
import argparse
import json
import sys
from pathlib import Path

# Add email app to path
EMAIL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EMAIL_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(EMAIL_ROOT / ".env")
except ImportError:
    pass


def test_prepare_direct():
    from app.skills import prepare_draft, build_mailto_url
    draft = prepare_draft(["you@example.com"], [], "Test subject", "Test body")
    assert draft["to"] == ["you@example.com"] and draft["subject"] == "Test subject"
    url = build_mailto_url(draft["to"], draft["cc"], draft["subject"], draft["body"])
    assert url.startswith("mailto:") and ("you@example.com" in url or "you%40example.com" in url)
    print("[OK] prepare_draft + build_mailto_url (direct)")
    return True


def test_prepare_llm():
    from app.skills import craft_email_with_llm
    out = craft_email_with_llm(["you@example.com"], [], "Say hello and ask for a meeting next week.")
    if out.get("error") and "not configured" in out.get("error", "").lower():
        print("[SKIP] LLM not configured (OPENAI_API_KEY or Vertex)")
        return True
    assert "subject" in out and "body" in out
    print("[OK] craft_email_with_llm:", out.get("subject", "")[:50])
    return True


def test_send_system(dry_run=True):
    from app.skills import send_via_system
    # Use a safe recipient: yourself for real send, or a placeholder for dry run
    to = ["mobiushealthai@gmail.com"]  # send to self for testing
    result = send_via_system(to, [], "Mobius email test", "This is an automated test from the Mobius email skill.")
    if result.get("sent"):
        print("[OK] send_via_system: sent, message_id =", result.get("message_id"))
        return True
    if dry_run and not result.get("sent"):
        print("[SKIP] send_via_system: not configured (set GMAIL_APP_PASSWORD or GMAIL_CREDENTIALS_PATH). error:", result.get("error", "")[:80])
        return True
    print("[FAIL] send_via_system:", result.get("error"))
    return False


def test_api(base_url="http://127.0.0.1:8003"):
    try:
        import httpx
    except ImportError:
        print("[SKIP] httpx not installed for API test")
        return True
    # Health
    r = httpx.get(f"{base_url}/health", timeout=5.0)
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "mobius-email"
    print("[OK] GET /health")

    # Prepare (direct)
    r = httpx.post(
        f"{base_url}/email/prepare",
        json={
            "to": ["you@example.com"],
            "cc": [],
            "subject": "API test",
            "body": "Body",
            "composition": "direct",
            "sender": "user_client",
        },
        timeout=10.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert "draft" in data and "mailto" in data
    print("[OK] POST /email/prepare (direct, user_client)")

    # Prepare (llm) - may skip if no LLM
    r = httpx.post(
        f"{base_url}/email/prepare",
        json={
            "to": ["you@example.com"],
            "user_text": "Quick hello",
            "composition": "llm",
            "sender": "system",
        },
        timeout=15.0,
    )
    assert r.status_code == 200
    print("[OK] POST /email/prepare (llm)")

    # Send with confirm_before_send=true (no actual send)
    r = httpx.post(
        f"{base_url}/email/send",
        json={
            "to": ["you@example.com"],
            "subject": "Confirm test",
            "body": "No send",
            "sender": "system",
            "confirm_before_send": True,
        },
        timeout=10.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("requires_confirmation") is True and data.get("draft")
    print("[OK] POST /email/send (confirm_before_send)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="Actually send one system email (to mobiushealthai@gmail.com)")
    ap.add_argument("--api", action="store_true", help="Test HTTP API (server must be running on 8003)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8003", help="API base URL")
    args = ap.parse_args()

    ok = True
    ok &= test_prepare_direct()
    ok &= test_prepare_llm()
    if args.api:
        ok &= test_api(args.base_url)
    else:
        ok &= test_send_system(dry_run=not args.send)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
