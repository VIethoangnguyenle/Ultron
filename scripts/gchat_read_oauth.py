#!/usr/bin/env python3
"""OAuth helper to grant READ access to Hoang's Google Chat spaces + messages.

Used by the @Hoang-mention poller. Scopes: chat.spaces.readonly (list Hoang's
spaces) and chat.messages.readonly (list messages to detect @Hoang mentions).
The token is stored SEPARATELY from the file-attachment token so the two flows
never clobber each other.

Usage (run with the hermes venv python):
  .../venv/bin/python gchat_read_oauth.py --auth-url
  .../venv/bin/python gchat_read_oauth.py --exchange <CODE_OR_FAILED_URL>
  .../venv/bin/python gchat_read_oauth.py --status
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
CLIENT_SECRET = HERMES_HOME / "google_chat_user_client_secret.json"
TOKEN_PATH = HERMES_HOME / "google_chat_read_token.json"
PENDING_PATH = HERMES_HOME / "google_chat_read_oauth_pending.json"
REDIRECT_URI = "http://localhost:1"
SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
]


def _fail(msg: str) -> "NoReturn":
    print(msg, file=sys.stderr)
    sys.exit(1)


def _require_secret() -> None:
    if not CLIENT_SECRET.exists():
        _fail(f"ERROR: no client secret at {CLIENT_SECRET}")


def cmd_auth_url() -> None:
    _require_secret()
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET), scopes=SCOPES, redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=True,
    )
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    PENDING_PATH.write_text(json.dumps({"state": state, "code_verifier": flow.code_verifier}))
    print(url)


def cmd_exchange(code: str) -> None:
    _require_secret()
    if not PENDING_PATH.exists():
        _fail("ERROR: no pending auth. Run --auth-url first.")
    pending = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    from google_auth_oauthlib.flow import Flow
    from urllib.parse import urlparse, parse_qs

    # Accept either a bare auth code or a pasted failed-redirect URL.
    raw = code.strip()
    if raw.startswith("http"):
        qs = parse_qs(urlparse(raw).query)
        codes = qs.get("code") or []
        if not codes:
            _fail("ERROR: no 'code' param found in the URL.")
        raw = codes[0]

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET), scopes=SCOPES, redirect_uri=REDIRECT_URI,
        state=pending["state"], code_verifier=pending["code_verifier"],
    )
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow.fetch_token(code=raw)
    creds = flow.credentials
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    PENDING_PATH.unlink(missing_ok=True)
    print(f"OK: read token saved to {TOKEN_PATH}")


def cmd_status() -> None:
    if TOKEN_PATH.exists():
        print("read token present:", TOKEN_PATH)
    else:
        print("no read token yet — run --auth-url then --exchange")


def main() -> None:
    p = argparse.ArgumentParser(description="Google Chat read-access OAuth (for @mention polling)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--auth-url", action="store_true", help="print the consent URL")
    g.add_argument("--exchange", metavar="CODE_OR_URL", help="exchange an auth code / failed redirect URL")
    g.add_argument("--status", action="store_true", help="show token status")
    a = p.parse_args()
    if a.auth_url:
        cmd_auth_url()
    elif a.exchange:
        cmd_exchange(a.exchange)
    else:
        cmd_status()


if __name__ == "__main__":
    main()
