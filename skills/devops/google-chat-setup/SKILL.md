---
name: google-chat-setup
description: "Use when setting up or fixing the Hermes Google Chat bot."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, google-chat, gcp, pubsub, messaging, setup]
    homepage: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/google_chat
    related_skills: [hermes-agent]
---

# Google Chat bot setup for Hermes

Connect Hermes Agent to Google Chat (bot). Inbound = Cloud Pub/Sub pull subscription; outbound = Chat REST API. No public URL/tunnel needed. Requires a Google Workspace (Gmail-only accounts cannot host Chat apps).

Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/google_chat
Adapter source: `plugins/platforms/google_chat/adapter.py` (+ `oauth.py`, `setup_files.py`, `cards.py`).

## Two different credentials — do NOT mix them up

1. Service Account JSON (REQUIRED for the bot itself). `{"type": "service_account", ...}`. Env `GOOGLE_CHAT_SERVICE_ACCOUNT_JSON`. Authenticates the bot to read messages / post replies.
2. OAuth client_secret.json (OPTIONAL, only for native file attachments). Has `{"installed": {...}}` or `{"web": {...}}`. Goes to `${HERMES_HOME}/google_chat_user_client_secret.json`. Used by per-user `/setup-files` OAuth flow because Chat `media.upload` rejects service-account auth.

## Host-side prep (idempotent)

```bash
cd ~/.hermes/hermes-agent
# deps check (only google-cloud-pubsub typically missing; rest ship with the venv)
venv/bin/python -c "from plugins.platforms.google_chat.adapter import check_google_chat_requirements"
# if False, install missing google libs into the hermes venv:
#   ~/.hermes/bin/uv pip install --python venv/bin/python google-cloud-pubsub==2.39.0

# store creds private (600)
install -m 600 /path/to/service-account.json ~/.hermes/google-chat-sa.json
install -m 600 /path/to/client_secret.json ~/.hermes/google_chat_user_client_secret.json
```

## Env vars in ~/.hermes/.env (append; drop any active old lines first)

```
GOOGLE_CHAT_SERVICE_ACCOUNT_JSON=/home/zane/.hermes/google-chat-sa.json
GOOGLE_CHAT_PROJECT_ID=<gcp-project-id>
GOOGLE_CHAT_SUBSCRIPTION_NAME=projects/<gcp-project-id>/subscriptions/<sub-id>
GOOGLE_CHAT_ALLOWED_USERS=<comma-separated-emails>   # fail-closed: empty = block everyone
# GOOGLE_CHAT_ALLOW_ALL_USERS=true                   # open access — avoid
# GOOGLE_CHAT_HOME_CHANNEL=spaces/XXXX               # optional cron delivery
```
Note: the wizard writes these as COMMENTED template lines (`# GOOGLE_CHAT_PROJECT_ID=`) near line 529 of .env. Editing via terminal is fine (.env is a credential store; read_file is blocked but terminal works). Remove only ACTIVE (uncommented) lines before re-adding to stay idempotent.

## GCP console steps (human with Admin rights — the SA has NO project-level IAM)

1. Enable 2 APIs in the project: Google Chat API + Cloud Pub/Sub API.
   - https://console.cloud.google.com/apis/library/chat.googleapis.com?project=<proj>
   - https://console.cloud.google.com/apis/library/pubsub.googleapis.com?project=<proj>
2. Pub/Sub > create TOPIC id `hermes-chat-events`.
3. Inside that topic > create PULL subscription id `hermes-chat-events-sub`, retention 7 days.
4. IAM binding — THE step everyone gets wrong (TWO service accounts to grant):
   - On the SUBSCRIPTION: add principal `<your-sa-email>` (the SA whose JSON you downloaded) with role "Pub/Sub Subscriber".
   - On the TOPIC: add the Chat app's OWN push service account with role "Pub/Sub Publisher". Find it in the Chat API Configuration page under "Connection settings" → a read-only "Service Account Email" field shaped like `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`. THIS is the account that pushes events into the topic. Copy it exactly.
   - `chat-api-push@system.gserviceaccount.com` is the LEGACY pusher (older docs) — keep it only if already present; the gsuiteaddons account is the one that actually works for new apps.
   - Do NOT swap these. Subscriber on subscription = YOUR SA; Publisher on topic = the gsuiteaddons service account (NOT your SA).
5. Google Chat API > Configuration: connection = Cloud Pub/Sub, point at TOPIC full name `projects/<proj>/topics/hermes-chat-events` (NOT the subscription, NOT the short id). Enable DM + group. Set app status LIVE.
6. Add the bot to a space (search by app name). ADDED_TO_SPACE resolves the bot user_id.

## Verify (run as the SA, no gcloud needed)

```bash
cd ~/.hermes/hermes-agent
venv/bin/python -c "
import json
from google.oauth2 import service_account
from google.cloud import pubsub_v1
info = json.load(open('/home/zane/.hermes/google-chat-sa.json'))
creds = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/pubsub'])
sub = pubsub_v1.SubscriberClient(credentials=creds)
got = sub.get_subscription(request={'subscription':'projects/<proj>/subscriptions/hermes-chat-events-sub'})
print('OK topic=', got.topic, 'retention=', got.message_retention_duration)
"
```
- PermissionDenied 403 (NOT NotFound) = subscription exists but SA lacks Subscriber → fix step 4.
- IAM propagation is normally instant for Pub/Sub; a 403 after 45s is almost always wrong-resource/wrong-role/wrong-email grant, not propagation.

## Restart & watch the real logs (never guess)

After console done: `hermes gateway restart`, then confirm `gateway_state.json` `platforms` non-empty and `logs/gateway.log` shows `[GoogleChat] Connected; project=...`.

## Machine-specific values (Hoang / this install)

- GCP project: `cosmic-inkwell-508103-s8`
- Service account email (Hermes): `ultron-tr-l-ho-ngnlv@cosmic-inkwell-508103-s8.iam.gserviceaccount.com`
- Chat app pusher SA (grant Publisher on TOPIC): `service-698401240103@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`
- Topic: `projects/cosmic-inkwell-508103-s8/topics/hermes-chat-events`
- Subscription: `projects/cosmic-inkwell-508103-s8/subscriptions/hermes-chat-events-sub`
- SA key path: `/home/zane/.hermes/google-chat-sa.json`
- client_secret path: `/home/zane/.hermes/google_chat_user_client_secret.json`
- Allowlist: `hoangnlv@vnpay.vn` (VNPay Workspace)
- OAuth client (for /setup-files): project `cosmic-inkwell-508103-s8`, client_id `698401240103-*.apps.googleusercontent.com` (desktop, redirect http://localhost)
- Hoang's user id: `users/110121981097849566202`; bot Ultron id: `users/107189931083311611240`

## Proactive escalation + @Hoang mention watch (built on this install)

Two cron-driven features extend the bot beyond plain @bot replies:

1. **Escalate-on-unknown** — when the group agent can't answer a question from a
   non-Hoang user, it replies "hỏi lại Hoàng" in-thread AND writes a JSON marker to
   `~/.hermes/escalations/`. Cron `ultron-escalate` (no_agent, every 2m, script
   `escalate_pending.py`) forwards markers to Hoang's home channel via `hermes send`
   and deletes them on success. Script: `~/.hermes/scripts/escalate_pending.py`.

2. **@Hoang mention watch** — polls Hoang's spaces for `@Hoàng` mentions (NOT @all,
   NOT @Ultron) and auto-answers after a 5-min grace if Hoang hasn't replied.
   - `ultron-mention-poller` (no_agent, every 2m, script `mention_poller.py`): reads
     spaces via Hoang's OWN OAuth token (`~/.hermes/google_chat_read_token.json`, scopes
     `chat.spaces.readonly` + `chat.messages.readonly`) using `spaces.messages.list`,
     detects mentions by `annotations[].userMention.user.name == users/110121981097849566202`,
     tracks reply state in `~/.hermes/mention_watch.json`, emits markers to
     `~/.hermes/mention_pending/` once the grace window (WAIT_SEC=300) passes.
   - `ultron-mention-reply` (LLM, every 2m, toolsets file+terminal): for each pending
     marker decides answer-vs-escalate per SOUL.md scope; answers via
     `~/.hermes/scripts/gchat_reply.py` (posts as the bot SA into the thread), escalates
     via an `~/.hermes/escalations/` marker otherwise. Deletes the pending marker after.
   - Auto-reply only works in spaces where the bot is a MEMBER; elsewhere the message
     fails with 403 "not a member" and the LLM falls back to escalating. To enable
     auto-reply in a work space, add the bot to that space first.
   - OAuth helper for the read token: `~/.hermes/scripts/gchat_read_oauth.py --auth-url`
     then `--exchange <code>` (run with `~/.hermes/hermes-agent/venv/bin/python`).
   - Env tunables (read by mention_poller.py): `ULTON_HOANG_USER`, `ULTON_MENTION_WAIT_SEC`
     (default 120 = 2 min grace), `ULTON_MENTION_LOOKBACK_MIN` (default 30), `ULTON_MENTION_PRUNE_SEC`.
   - Sender display name CANNOT be resolved by a normal user account: `messages.list`,
     `messages.get`, and `members.list` only return `name` (`users/...`) + `type`, never
     `displayName`. Directory API (`admin.directory.user.readonly`) is the only path, but it
     403s unless the Workspace enables contact sharing (VNPay has it disabled — non-admin
     gets "Not Authorized"). Fallback = raw `users/...` id in the DM notice, which is still
     enough to identify the asker from the question text + space name. The read token is
     provisioned WITH the Directory scope, so if contact sharing is ever enabled the name
     resolves automatically with no re-auth.
