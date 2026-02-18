# Mobius Email Skill

Send email via **system** (Gmail: mobiushealthai@gmail.com) or **user client** (mailto). Supports direct to/cc/subject/body or **LLM-crafted** subject and body from user text. Modes: **auto send** or **confirm before send** (and post-send confirmation).

## Setup

```bash
cd mobius-skills/email
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env: GMAIL_CREDENTIALS_PATH and/or GMAIL_APP_PASSWORD for system send
```

### System send (mobiushealthai@gmail.com)

- **Gmail API**: Put `credentials.json` (OAuth 2.0 client) in this dir (or set `GMAIL_CREDENTIALS_PATH`). First run will open a browser to authorize; token is saved to `token.json`.
- **SMTP fallback**: Set `GMAIL_APP_PASSWORD` (Gmail app password) in `.env`.

### User client

No config: the API and CLI return a `mailto` URL; the client opens it in the user’s default mail app.

### LLM crafting (optional)

Set `OPENAI_API_KEY` or Vertex (`VERTEX_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`) to use LLM for subject/body from user text.

## API

- **GET /health** — Health check.
- **POST /email/prepare** — Get draft (and optional mailto). Body: `to`, `cc`, `subject`, `body`, `user_text`, `composition` (direct | llm), `sender` (system | user_client).
- **POST /email/send** — Send or request confirmation. Body: `to`, `cc`, `subject`, `body`, `sender`, `confirm_before_send`.
- **POST /email/confirm** — Confirm and send (same body as send with `confirm_before_send=false`).

## CLI

```bash
# Prepare draft (optional LLM)
python -m app.cli prepare --to you@example.com --subject "Hi" --body "Hello"
python -m app.cli prepare --to you@example.com --llm "Remind them about the meeting tomorrow"

# Send via system (optional --confirm to prompt before send)
python -m app.cli send --to you@example.com --subject "Test" --body "From CLI"
python -m app.cli send --to you@example.com --subject "Test" --body "From CLI" --confirm

# Print mailto URL (user client)
python -m app.cli mailto --to you@example.com --subject "Hi" --body "Hello"
```

## MCP integration

Skills in `app/skills.py` are MCP-ready. Suggested tool mapping for an MCP server:

| MCP tool name   | Skill / behavior | Args (from MCP) |
|-----------------|------------------|------------------|
| `email_prepare` | Prepare draft; optional LLM craft | `to`, `cc`, `subject?`, `body?`, `user_text?`, `composition` (direct/llm), `sender` (system/user_client) |
| `email_send`    | Send (system or return mailto)   | `to`, `cc`, `subject`, `body`, `sender`, `confirm_before_send` |
| `email_mailto`  | Return mailto URL only           | `to`, `cc`, `subject`, `body` |

Implement the MCP server by importing `app.skills` and calling these functions; pass through tool arguments and return the dict/string as the tool result.

## Test script

Run `./scripts/test_email_cli.sh` or `python scripts/test_email.py` to exercise prepare, mailto, and (with env set) system send.
