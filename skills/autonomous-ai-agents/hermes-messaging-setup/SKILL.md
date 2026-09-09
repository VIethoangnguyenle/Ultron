---
name: hermes-messaging-setup
description: Use when connecting Hermes to a messaging platform.
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, gateway, messaging, platforms, google-chat, telegram, discord, slack, setup]
---

# Connecting Hermes to a Messaging Platform

Procedure for wiring a messaging platform into the Hermes gateway so the agent
can receive and answer messages there.

## 1. Check live state before answering "is X connected"
- Read `~/.hermes/channel_directory.json` and `~/.hermes/gateway_state.json`; both
  carry a `platforms` map. An empty `{}` means nothing is connected yet.
- Never claim a platform works just because it is listed in config.
  `config.yaml` → `platform_toolsets` lists platforms Hermes *supports*, not what
  is *connected*. E.g. a `google_chat:` key there does not mean the bot is live.

## 2. The authoritative credential/config list is the platform plugin's plugin.yaml
- Platform adapters live in `<hermes-agent>/plugins/platforms/<name>/` (or under
  `plugins/platforms/<name>/` for IRC/Teams). Read the `plugin.yaml` for the exact
  `requires_env` (required) and `optional_env` (optional) variables.
- This file is more reliable than prose docs: it lists every knob (allowed users,
  home channel, subscription, etc.) and is versioned with the code.
- `hermes gateway setup` → pick the platform walks through the same env vars
  interactively; use it when a human can answer prompts.

## 3. Distinguish credential TYPES before wiring — a platform often needs two
- A single platform can use one credential for the *bot connection* and a SECOND
  for an *auxiliary feature*. Identify each file by its top-level JSON key
  (`"type": "service_account"` vs `"installed"` vs `"web"`) before deciding what it
  does. Wiring the wrong one is the #1 time sink.
- Secrets go in `~/.hermes/.env` (or via setup), never in `config.yaml`. `chmod 600`
  any JSON key files.

## 4. Verify after connecting
- After adding the bot to a space/group, actually message it (or @-mention it) and
  confirm a reply lands before telling the user it works. `gateway_state.json`
  updating its `platforms` map is the read-back that confirms the adapter connected.

## Platform references
- `references/google-chat.md` — Google Chat specifics: the two-credential split,
  Pub/Sub architecture, env vars, and setup sequence.
