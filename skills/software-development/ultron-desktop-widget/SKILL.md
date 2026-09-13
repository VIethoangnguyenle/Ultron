---
name: ultron-desktop-widget
description: Use when building or fixing the Ultron desktop widget.
---

# Desktop widget "Ultron" (Linux / PyQt6)

## What it is
Ultron's own body on Hoàng's desktop, running on the SAME machine as Hermes.
It is a *client* of the same brain (same rules, same context) — not a second persona.
It reuses the two Siri gates as backend; **never build a new server**.

## Interaction rules (Hoàng, 2026-09-13)
- **VOICE mode = ONLY the corner avatar icon.** Never expand the 280x400 panel in voice mode — the avatar itself (ring colour + pulse) IS the whole UI: listening / thinking / speaking. Click = start or cancel listening.
- **TEXT mode = the 280x400 panel** is the interface (message bubbles + input row + send).
- Mode is remembered across runs (`state.json: mode`).

## Project
- Path: `/home/zane/ultron-widget/` — own venv `.venv` (PyQt6), local git, `.gitignore` includes `.env`.
- `.env` (chmod 600, never committed, never printed): `ULTRON_URL_TEXT`, `ULTRON_URL_VOICE`, `ULTRON_TOKEN`.
- Token source on disk: `~/.hermes/state/siri_token.txt` (copy in; never hardcode into git).
- Assets: `assets/avatar.png` (512px crop of Hoàng's mascot), `assets/avatar_noshadow.png` (512x448), `assets/icon_preview_48.png`.
- State colour ring per status: idle cyan `#22D3EE`, listening green `#34D399`, thinking amber `#FBBF24`, speaking violet `#A78BFA`.

## Backend (the two existing gates — no new server)
```
TEXT  POST http://127.0.0.1:9445/chat      {"text": "...", "conversation": "<id>"}
VOICE POST http://127.0.0.1:9444/siri/say  {"text": "..."}
Header: X-Gitlab-Token: $ULTRON_TOKEN
Resp: {"status", "text", "waited_s", "echo"|"conv", "files"}
```
Handle `status` ok/timeout/empty/error visibly — never fail silently (timeout ⇒ say so).
`files[]` entries need the `X-Gitlab-Token` header, so opening one in a browser gives 401: the widget must DOWNLOAD the file itself (with the header) and open the local copy.
Text mode = full Vietnamese answers + conversation memory (`/chat`); voice mode = short English one-liner (`/say`) that TTS reads aloud.

## Environment (verified)
Ubuntu 22.04.5 · GNOME 42.9 · **X11** `DISPLAY=:0` @1920x1080 (not Wayland) ⇒ Qt frameless + translucent + always-on-top + skip-taskbar all work.
PulseAudio + USB mic works. `python3` in PATH is the Hermes venv ⇒ always use the project venv.
STT: faster-whisper models small/medium/large-v3 already cached in `~/.cache/huggingface` (no download needed). TTS: piper NOT installed, `edge-tts` is available.

## Phases (report + real screenshot after each; user tests before proceeding)
1. Floating icon + drag + position memory + panel skeleton (no backend)
2. Text chat over HTTP
3. Mode toggle + STT
4. TTS + continuous voice conversation (stop on "kết thúc" or stop button)
5. Global hotkey

## Verification pitfalls (learned on this box)
- Screenshot: `ffmpeg -y -loglevel error -f x11grab -i :0 -frames:v 1 out.png` — `-frames:v` must come AFTER `-i`, else it is read as an input option and fails.
- No `scrot`/`gnome-screenshot`/`import`/`xdotool` installed; use `xwininfo`/`xprop`, and drive the app with env vars (e.g. `ULTRON_START_OPEN=1`) instead of simulated clicks.
- Deliver images as REAL chat attachments, never a local path:
  `python3 ~/.hermes/scripts/gchat_send_file.py --space spaces/0dniIqAAAAE --file <png> --text "<caption>"`.
- Reload the Siri gates after editing their code: `systemctl --user kill -s TERM siri-speak siri-chat`, wait ~14s (`restart` is blocked by a guard).
- Drive + test the widget with no human present: `systemd-run --user --unit=wtest --collect -p WorkingDirectory=/home/zane/ultron-widget -p Environment="DISPLAY=:0 ULTRON_START_OPEN=1" ./.venv/bin/python ultron_widget.py`, read geometry with `xwininfo -root -tree | grep '"Ultron"'`, stop with `systemctl --user stop wtest`. Verified: default 48x48@(1848,1008) margin 24px, restores saved pos, clamps 9999/-500 → on-screen, panel 280x400 anchored to icon.
- `systemd-run -p Environment=` SPLITS ON SPACES: a value with a space (e.g. a test message) kills the unit instantly with `Invalid environment block` and no window ever appears — looks like a widget bug but is not. Quote inside the string: `-p 'Environment=DISPLAY=:0 "ULTRON_TEST_SEND=ping widget"'`, or use underscores. Before blaming widget code for a silent no-start, check the unit started.
- NEVER `pkill -f "<name>.py"` from a shell whose own command line contains that literal — the regex matches the running bash and the whole verification dies of SIGTERM. Kill via the systemd unit or by exact PID.
- The desktop may be LOCKED: `ffmpeg x11grab` then captures only the lock screen. Capture the window itself instead: `xwd -silent -id <wid> -out /tmp/w.xwd && ffmpeg -y -i /tmp/w.xwd out.png` (works while locked).

## Look & feel (Hoàng's choices — keep them)
- Icon = **head crop** of `assets/avatar.png` (circular mask inside the state ring); the panel header shows the **full-body** mascot. Fall back to the vector face only when the asset is missing.
- **State and mood are separate layers.** State = functional (idle / listening / thinking / speaking, ring colours above). Mood = flavour drawn on top (happy / curious / worried / sleepy / impatient / neutral) from simple rules — keywords, events, clock — never an extra network call, never ML.
- Animations are REQUIRED, not decoration: breathing at rest, cross-fade (~280ms) on state change, sonar rings while listening, orbiting arc while thinking, faster pulse + micro-bob while speaking, blink every 4–9s, panel slide+fade on open, bubbles fading in.
- **Geometry contract:** glow/sonar need room ⇒ window = 48px icon + 12px transparent padding (72x72), but the VISIBLE icon stays 48px, 24px from the screen edges, and `state.json` keeps storing the ICON's top-left (clamp on the icon rect). Any window-size change ⇒ re-verify position memory + clamp + drag.
- Keep it cheap: one timer (~33ms) only while animating; idle CPU target < 3% of one core — measure it, don't assume.
- Mood table, animation timings and the frame-capture recipe: `references/animation-and-moods.md`.

## Hard constraints
- Independence: never touch `platforms.webhook.*`, the gateway, or the Chat adapter while working on the widget or the Siri gates; keep message/file/state files per-channel.
- Widget code = code ⇒ dispatch to claude (Jarvis); run `python3 ~/.hermes/scripts/claude_mcp_preflight.py` (must exit 0) first. No global installs, no sudo, no model downloads without asking.
