# Google Chat (Hermes)

## Architecture
- Inbound: Cloud Pub/Sub pull subscription (optional) or an authenticated HTTP
  callback. Pub/Sub pull mode needs no public URL, tunnel, or TLS cert — same
  ergonomics as a Telegram bot token.
- Outbound: Chat REST API (`chat.googleapis.com`).
- Code: `<hermes-agent>/plugins/platforms/google_chat/` — `plugin.yaml` (env vars),
  `adapter.py`, `oauth.py`, `setup_files.py`.

## Two credentials, two different jobs (the main gotcha)

| Credential | File shape | What it does |
|---|---|---|
| Service Account | `"type": "service_account"` | Connects the bot — receive + send messages in spaces. THE required credential (`GOOGLE_CHAT_SERVICE_ACCOUNT_JSON`). |
| OAuth client secret | `"installed"` or `"web"` | ONLY native file attachments. Per-user OAuth via `/setup-files`; the bot uploads media *as the user* because `media.upload` rejects service-account auth. |

- A `client_secret_*.apps.googleusercontent.com.json` (Desktop app, `"installed"`) is
  NOT the bot connection. It only enables file sending.
- The Service Account needs `roles/pubsub.subscriber` on the subscription only — do
  NOT grant project-level Pub/Sub roles. There is no "Chat Bot Caller" role; Chat
  authority comes from installing the bot in a space, not IAM.

## Requirements
- Google Chat requires a Google Workspace (personal, or work with admin rights to
  publish the app). Gmail-only accounts cannot host Chat apps.

## Env vars (from plugin.yaml)
- Required: `GOOGLE_CHAT_SERVICE_ACCOUNT_JSON` — path to the SA key file, or inline
  JSON. Leave empty to use Application Default Credentials on Cloud Run/GCE
  (falls back to `GOOGLE_APPLICATION_CREDENTIALS`).
- Optional: `GOOGLE_CHAT_PROJECT_ID`, `GOOGLE_CHAT_SUBSCRIPTION_NAME` (Pub/Sub pull
  mode), `GOOGLE_CHAT_ALLOWED_USERS` (comma-separated emails), `GOOGLE_CHAT_HOME_CHANNEL`
  (default space for cron/notification delivery), plus the
  `GOOGLE_CHAT_HTTP_EVENTS_*` vars for callback mode.

## Setup sequence
1. Pick/create a GCP project; enable Google Chat API + Cloud Pub/Sub API.
2. Create a Service Account (grant no project-level role), download the JSON key,
   `chmod 600`.
3. Create a Pub/Sub topic + pull subscription (retention 7 days so backlog
   survives restarts); grant the SA `roles/pubsub.subscriber` on the subscription.
4. Configure the Chat app in the Google Cloud console, publish it to the Workspace.
5. `hermes gateway setup` → Google Chat, set the env vars.
6. Add the bot to the space, @-mention it to test.

## File attachments (optional)
- Store the OAuth client secret: run
  `python -m plugins.platforms.google_chat.oauth --client-secret /path/to/client_secret.json`
  (or use the in-chat `/setup-files` flow). It lands at
  `~/.hermes/google_chat_user_client_secret.json`.
- Each user authorizes once; per-user tokens land in
  `~/.hermes/google_chat_user_tokens/<email>.json`.
