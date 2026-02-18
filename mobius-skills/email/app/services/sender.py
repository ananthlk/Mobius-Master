"""Send email via Gmail API, SMTP fallback, or build mailto URL for user client."""
import base64
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Basic email validation (allow comma-separated in string; we normalize to list elsewhere)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalize_addresses(addr: str | list) -> list[str]:
    if isinstance(addr, list):
        out = []
        for a in addr:
            out.extend(_normalize_addresses(a))
        return out
    s = (addr or "").strip()
    if not s:
        return []
    return [a.strip() for a in re.split(r"[\s,;]+", s) if a.strip() and EMAIL_RE.match(a.strip())]


def send_via_gmail_api(to: list[str], cc: list[str], subject: str, body: str, from_addr: str) -> dict:
    """
    Send via Gmail API (OAuth2). Requires credentials and token.
    Returns {"sent": True, "message_id": "..."} or {"sent": False, "error": "..."}.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import os
        from pathlib import Path
    except ImportError as e:
        return {"sent": False, "message_id": None, "error": f"Gmail API deps missing: {e}"}

    from app.config import GMAIL_CREDENTIALS_PATH, GMAIL_OAUTH_TOKEN_PATH

    _email_root = Path(__file__).resolve().parent.parent.parent
    token_path = GMAIL_OAUTH_TOKEN_PATH or str(_email_root / "token.json")
    creds_path = GMAIL_CREDENTIALS_PATH
    if not creds_path or not Path(creds_path).exists():
        return {"sent": False, "message_id": None, "error": "Gmail credentials not found (set GMAIL_CREDENTIALS_PATH)"}

    creds = None
    if token_path and Path(token_path).exists():
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes=["https://www.googleapis.com/auth/gmail.send"])
        except Exception as e:
            logger.warning("Token load failed: %s", e)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes=["https://www.googleapis.com/auth/gmail.send"])
                creds = flow.run_local_server(port=0)
                Path(token_path).parent.mkdir(parents=True, exist_ok=True)
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                return {"sent": False, "message_id": None, "error": f"OAuth flow failed: {e}"}

    msg = MIMEMultipart()
    msg["To"] = ", ".join(to)
    msg["Cc"] = ", ".join(cc) if cc else ""
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8").rstrip("=")
    try:
        service = build("gmail", "v1", credentials=creds)
        send_result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        mid = send_result.get("id")
        if token_path and Path(token_path).exists():
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        return {"sent": True, "message_id": mid, "error": None}
    except Exception as e:
        logger.exception("Gmail API send failed: %s", e)
        return {"sent": False, "message_id": None, "error": str(e)}


def send_via_smtp(to: list[str], cc: list[str], subject: str, body: str, from_addr: str) -> dict:
    """
    Send via SMTP (e.g. Gmail app password). Returns same shape as send_via_gmail_api.
    """
    from app.config import SMTP_HOST, SMTP_PORT, GMAIL_APP_PASSWORD

    if not GMAIL_APP_PASSWORD:
        return {"sent": False, "message_id": None, "error": "GMAIL_APP_PASSWORD not set"}

    msg = MIMEMultipart()
    msg["To"] = ", ".join(to)
    msg["Cc"] = ", ".join(cc) if cc else ""
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    recipients = list(to) + list(cc)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(from_addr, GMAIL_APP_PASSWORD)
            server.sendmail(from_addr, recipients, msg.as_string())
        return {"sent": True, "message_id": None, "error": None}
    except Exception as e:
        logger.exception("SMTP send failed: %s", e)
        return {"sent": False, "message_id": None, "error": str(e)}


def send_via_system(to: list[str], cc: list[str], subject: str, body: str) -> dict:
    """
    Send from system account (mobiushealthai@gmail.com). Tries Gmail API first, then SMTP.
    to/cc can be str or list; will be normalized to list of valid addresses.
    """
    from app.config import MOBIUS_EMAIL_FROM, GMAIL_APP_PASSWORD, GMAIL_CREDENTIALS_PATH
    from pathlib import Path

    to_list = _normalize_addresses(to)
    cc_list = _normalize_addresses(cc)
    if not to_list:
        return {"sent": False, "message_id": None, "error": "No valid 'to' addresses"}

    # Truncate if needed
    from app.config import EMAIL_MAX_SUBJECT_LEN, EMAIL_MAX_BODY_LEN
    subject = (subject or "")[:EMAIL_MAX_SUBJECT_LEN]
    body = (body or "")[:EMAIL_MAX_BODY_LEN]

    # Prefer Gmail API if credentials exist; else SMTP
    if GMAIL_CREDENTIALS_PATH and Path(GMAIL_CREDENTIALS_PATH).exists():
        result = send_via_gmail_api(to_list, cc_list, subject, body, MOBIUS_EMAIL_FROM)
        if result.get("sent"):
            return result
        if GMAIL_APP_PASSWORD:
            return send_via_smtp(to_list, cc_list, subject, body, MOBIUS_EMAIL_FROM)
        return result
    return send_via_smtp(to_list, cc_list, subject, body, MOBIUS_EMAIL_FROM)


def build_mailto_url(to: list[str], cc: list[str], subject: str, body: str) -> str:
    """Build mailto URL for user client. to/cc can be str or list."""
    to_list = _normalize_addresses(to) if to else []
    cc_list = _normalize_addresses(cc) if cc else []
    if not to_list:
        return ""
    # RFC 6068: mailto:addr1,addr2?subject=...&cc=...&body=...
    addrs = ",".join(to_list)
    params = []
    if cc_list:
        params.append(f"cc={quote(','.join(cc_list))}")
    if subject:
        params.append(f"subject={quote(subject)}")
    if body:
        params.append(f"body={quote(body)}")
    if params:
        return "mailto:" + quote(addrs) + "?" + "&".join(params)
    return "mailto:" + addrs
