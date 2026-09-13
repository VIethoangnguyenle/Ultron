# Animation & mood model (widget "Ultron")

## State colours (functional layer)

| State | Colour | Motion |
|---|---|---|
| idle | cyan `#22D3EE` | slow breathing ~2.6s, soft outer glow |
| listening | green `#34D399` | two sonar rings expanding + fading, ~1.2s |
| thinking | amber `#FBBF24` | bright arc orbiting the ring, ~700ms/turn, ring dimmed |
| speaking | violet `#A78BFA` | fast glow pulse (~0.6s) + micro-bob of the avatar |

Transitions cross-fade over ~280ms (no colour snap). Hover ⇒ scale ~106% + brighter glow (~150ms); click ⇒ bounce 0.9→1.06→1.0 (~220ms).

## Mood layer (flavour on top of state)

| Mood | Trigger (simple rules) | Effect |
|---|---|---|
| sleepy | 22:00–06:00, or idle > 10 min | slower breathing, dimmer ring, occasional squash-stretch "yawn" + faint 💤 that fades |
| happy | a fresh reply arrives, or message contains praise (cảm ơn / ngon / giỏi / đẹp / ok) | one bounce, glow flash then settle, a few small ✨ sparks fading out |
| curious | long incoming message, or text ending in "?" | ~6° tilt back and forth + one quick ring flicker |
| worried | network error / timeout / HTTP 4xx-5xx | one short shake, ring shifts to pale amber, faint ❓ fading out |
| impatient | waiting for a reply > 25s | light rhythmic tapping of the icon until the reply lands |
| neutral | nothing special | breathing only |

Rules that keep it from fighting the state layer:
- Mood auto-expires after ~1.2–2.5s back to neutral (except sleepy / impatient, which are condition-held).
- The state animation keeps running underneath; mood only adds effects — never replace one with the other.
- Where the transform applies: offset/scale/tilt on the painted avatar, colour and opacity on the ring, never on the window itself (window geometry carries the position contract).
- Blink: every 4–9s (randomised), ~120ms — a dark sweep across the eye area, or a ring flicker if the asset makes the sweep look dirty. Never distort or smear the avatar image.

## Test hooks (for verification without a human)
- `ULTRON_START_OPEN=1` — open the panel at startup (switches to text mode; it is a test hook, not the real click path).
- `ULTRON_TEST_SEND="<message>"` — auto-send from the panel after ~700ms. Systemd caveat: a value containing spaces must be quoted inside the `Environment=` string, otherwise `Invalid environment block`.
- `ULTRON_MOOD=happy|curious|worried|sleepy|impatient|neutral` — pin a mood to photograph it (empty = natural).

## Proving animation in a report
1. Run per state with `systemd-run --user --unit=wtest --collect …`, capture three frames ~200ms apart per state: `xwd -silent -id <wid> -out /tmp/f.xwd && ffmpeg -y -loglevel error -i /tmp/f.xwd out.png`.
2. Assemble a contact sheet / animated GIF with ffmpeg (`hstack`/`vstack`, or `-framerate 5` frames → GIF) so differences are visible in chat… except Google Chat does not play GIFs sent as documents — send a stacked still image per state instead, and treat the GIF as an optional extra.
3. Log the state transitions from the widget (`face state -> thinking (#FBBF24)` …) as line-level evidence next to the images.
