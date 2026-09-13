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

### Kiểm chứng MẶT/MOOD phải làm ở cỡ ICON thật (bài học 2026-09-13)
- Soi "mắt/miệng có khác nhau không" bằng ảnh bảng tổng dễ bị thu nhỏ rồi kết luận sai. Cách đúng: crop từng cụm ở cỡ thật 48px rồi phóng to ≥4x bằng nearest-neighbour (`ffmpeg -vf "crop=w:h:x:y,scale=iw*4:ih*4:flags=neighbor"`) mới đánh giá.
- **Nghiệm thu đúng cho "mặt đổi theo cảm xúc": xuất bản ẢNH XÁM (bỏ sạch màu).** Bỏ màu mà vẫn phân biệt được → khác biệt nằm ở nét mặt; chỉ nhận ra nhờ màu viền → **CHƯA ĐẠT** (đã dính đúng ca này: 6 mood đạt nhưng listening/thinking/speaking chỉ khác màu).
- Cách sửa hiệu quả: tăng delta HÌNH HỌC (mắt to hơn ≥25%, con ngươi lệch ≥25% chiều cao mắt, miệng mở 3 mức chênh ≥2px ở 48px) rồi **đo bằng số pixel khác nhau trên ảnh xám** (ngưỡng lệch 18/255, sàn ≥55 px/cặp) — không tin cảm nhận bằng mắt.
- Giữ luật cũ: voice = chỉ icon, KHÔNG mở panel; panel 280x400 chỉ dành cho text.
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
3. Animation + mood layer (ring colours, breathing, sonar, orbit, blink) WITH the idle-CPU budget held
4. Emotion face: eyes + mouth driven by state/mood
5. Mode toggle + mic/STT
6. TTS + continuous voice conversation (stop on "kết thúc" or stop button)
7. Global hotkey
Write the NEXT phase's spec file to disk before the current dispatch returns — an idle pipeline is the only real waste here, and Hoàng's standing instruction is "cứ làm với nhau, anh mong kết quả", i.e. do not ask per step, land evidence per step.

## Verification pitfalls (learned on this box)
- Screenshot: `ffmpeg -y -loglevel error -f x11grab -i :0 -frames:v 1 out.png` — `-frames:v` must come AFTER `-i`, else it is read as an input option and fails.
- No `scrot`/`gnome-screenshot`/`import`/`xdotool` installed; use `xwininfo`/`xprop`, and drive the app with env vars (e.g. `ULTRON_START_OPEN=1`) instead of simulated clicks.
- Deliver images as REAL chat attachments, never a local path:
  `python3 ~/.hermes/scripts/gchat_send_file.py --space spaces/0dniIqAAAAE --file <png> --text "<caption>"`.
- Reload the Siri gates after editing their code: `systemctl --user kill -s TERM siri-speak siri-chat`, wait ~14s (`restart` is blocked by a guard).
- Drive + test the widget with no human present: `systemd-run --user --unit=wtest --collect -p WorkingDirectory=/home/zane/ultron-widget -p Environment="DISPLAY=:0 ULTRON_START_OPEN=1" ./.venv/bin/python ultron_widget.py`, read geometry with `xwininfo -root -tree | grep '"Ultron"'`, stop with `systemctl --user stop wtest`. Verified: default 48x48@(1848,1008) margin 24px, restores saved pos, clamps 9999/-500 → on-screen, panel 280x400 anchored to icon.
- `systemd-run -p Environment=` SPLITS ON SPACES: a value with a space (e.g. a test message) kills the unit instantly with `Invalid environment block` and no window ever appears — looks like a widget bug but is not. Quote inside the string: `-p 'Environment=DISPLAY=:0 "ULTRON_TEST_SEND=ping widget"'`, or use underscores. Before blaming widget code for a silent no-start, check the unit started.
- NEVER `pkill -f "<name>.py"` from a shell whose own command line contains that literal — the regex matches the running bash and the whole verification dies of SIGTERM. Kill via the systemd unit or by exact PID.
- NEVER `ps -eo pid,etime,cmd | grep ultron_widget` while a claude dispatch is alive: claude's own cmdline IS the whole spec (thousands of chars), so the grep floods the context. Use `pgrep -af pattern | cut -c1-80` or filter by name only (`ps -eo pid,comm`), and check the dispatch with the process tool instead.
- The desktop may be LOCKED: `ffmpeg x11grab` then captures only the lock screen. Capture the window itself instead: `xwd -silent -id <wid> -out /tmp/w.xwd && ffmpeg -y -i /tmp/w.xwd out.png` (works while locked).
- The project ships its own harness: `tests/verify_phase25.py` (offscreen suite asserting geometry, animations, moods, file-download, token 401) and `tests/capture_p25.sh run|stop|wid|burst`. RUN it as one input — never as the proof: the same agent wrote the code AND the test, so re-verify independently on real X11 (geometry via `xwininfo`, CPU per the recipe, one real send through `:9445`). Its suite passing while the widget still burns 8.8% CPU is the normal case, not a contradiction.

## Look & feel (Hoàng's choices — keep them)
- Icon = **head crop** of `assets/avatar.png` (circular mask inside the state ring); the panel header shows the **full-body** mascot. Fall back to the vector face only when the asset is missing.
- **State and mood are separate layers.** State = functional (idle / listening / thinking / speaking, ring colours above). Mood = flavour drawn on top (happy / curious / worried / sleepy / impatient / neutral) from simple rules — keywords, events, clock — never an extra network call, never ML.
- Animations are REQUIRED, not decoration: breathing at rest, cross-fade (~280ms) on state change, sonar rings while listening, orbiting arc while thinking, faster pulse + micro-bob while speaking, blink every 4–9s, panel slide+fade on open, bubbles fading in.
- **Geometry contract:** glow/sonar need room ⇒ window = 48px icon + 12px transparent padding (72x72), but the VISIBLE icon stays 48px, 24px from the screen edges, and `state.json` keeps storing the ICON's top-left (clamp on the icon rect). Any window-size change ⇒ re-verify position memory + clamp + drag.
- Keep it cheap: one timer (~33ms) only while animating; idle CPU target < 3% of one core. Measure it, don't assume — and measure AFTER ~10s of warm-up with no forced state/mood: read `/proc/<pid>/stat` fields 14+15 twice, 10s apart. A reading taken right after launch (or while a state/mood is pinned) inflates the number and sends you chasing a bug that is not there. Recipe + optimisation list: `references/animation-and-moods.md`.
- **Emotion face is DRAWN, not baked**: eyes + mouth are re-painted per mood on top of the asset (auto-calibrated from the image, cached pixmaps, `ULTRON_FACE=0` off switch) — calibration + the full eye/mouth table live in `references/animation-and-moods.md`. Adding an expression must never require a new image file.
- Mood table, animation timings and the frame-capture recipe: `references/animation-and-moods.md`.

## Hard constraints
- Independence: never touch `platforms.webhook.*`, the gateway, or the Chat adapter while working on the widget or the Siri gates; keep message/file/state files per-channel.
- Widget code = code ⇒ dispatch to claude (Jarvis); run `python3 ~/.hermes/scripts/claude_mcp_preflight.py` (must exit 0) first. No global installs, no sudo, no model downloads without asking.
- **One dispatch per working tree at a time.** Two Jarvises editing the same repo clobber each other ⇒ queue the next widget phase until the running one reports. A task in a DIFFERENT directory (e.g. `~/.hermes/scripts`) may run concurrently — use the wait to land unrelated work instead of idling.
- Long dispatches run as `timeout N claude -p …` in the background — the wrapper KILLS the run mid-flight when `N` expires (exit 124), and it commonly dies after committing the code but before the final report. On exit 124, check `git log --oneline -3` + `git status --short` + whatever artifacts it already wrote BEFORE re-dispatching; usually you only need to finish the verification yourself and hand back the one missing piece. Keep each dispatch to a bounded chunk and end the spec with "commit, then a short report" so a kill costs as little as possible.
