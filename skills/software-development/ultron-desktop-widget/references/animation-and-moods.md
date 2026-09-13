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

## Emotion face (eyes + mouth, drawn over the asset)

The mascot image is only the BASE — the expression is painted at runtime, so a new expression must never require a new image file.

Calibration (once, at startup):
1. Scan `assets/avatar.png` for cyan pixel clusters inside the face region — expect exactly 3: the mouth is the LOWEST cluster and sits between the two eye clusters.
2. Store per part: centre, bbox, the asset's own cyan (average of the cluster's pixels), and the screen colour as the MEDIAN of the face region (the robot's face is a flat dark screen ⇒ this is what erases the original feature with no visible patch).
3. Any part the scan cannot find ⇒ leave that part of the original image untouched. Never draw blind, never crash on a swapped asset.

Per frame: paint the screen colour over the old eyes/mouth (slightly rounded), then draw the current mood's shapes in the SAME cyan and stroke weight.

| Mood | Eyes | Mouth |
|---|---|---|
| neutral | original image, nothing painted | original |
| happy | `^ ^` upward arcs + a spark at the outer corner | deeper, wider smile |
| curious | rounder pupils shifted up, one side raised | small `o`, slightly off-centre |
| worried | smaller, drooped down + two brow strokes | gentle wavy line / slight frown |
| sleepy | half-closed lines, occasionally fully shut | slack, half-open (yawn) + 💤 |
| impatient | narrowed + rhythmic twitch | pressed flat line |
| listening | wide + a highlight dot | small closed smile (attentive) |
| thinking | pupils up-right, occasionally sweeping | `~` squiggle, offset to one side |
| speaking | slight bob | mouth opening/closing in ~140ms cycles (≥3 levels) — this is what sells "it is talking" |

Blink overrides the eyes for ~120ms every 4–9s at any state/mood (in sleepy it holds shut longer instead).

Cost control: cache one `QPixmap` per (mood, size, eyes open/closed, mouth level) — rebuilding QPainter paths every frame throws away the idle-CPU budget. Ship an off switch (`ULTRON_FACE=0`) so a bad-eyed asset can be sidelined without editing code.

## Test hooks (for verification without a human)
- `ULTRON_START_OPEN=1` — open the panel at startup (switches to text mode; it is a test hook, not the real click path).
- `ULTRON_TEST_SEND="<message>"` — auto-send from the panel after ~700ms. Systemd caveat: a value containing spaces must be quoted inside the `Environment=` string, otherwise `Invalid environment block`.
- `ULTRON_MOOD=happy|curious|worried|sleepy|impatient|neutral` — pin a mood to photograph it (empty = natural).
- `ULTRON_STATE=idle|listening|thinking|speaking` — pin a state (needed to photograph listening/speaking, which no click can reach without STT/TTS).
- `ULTRON_AVATAR_FULL=1` — force the full-body asset in the panel header (check the head-crop/full-body split without touching `assets/`).
- All of these are hooks, not the real paths: `ULTRON_START_OPEN` switches mode to text first, so never use it to "prove" the voice-mode rule.

## Proving animation in a report
1. Run per state with `systemd-run --user --unit=wtest --collect …`, capture three frames ~200ms apart per state: `xwd -silent -id <wid> -out /tmp/f.xwd && ffmpeg -y -loglevel error -i /tmp/f.xwd out.png`.
2. Assemble a contact sheet / animated GIF with ffmpeg (`hstack`/`vstack`, or `-framerate 5` frames → GIF) so differences are visible in chat… except Google Chat may not animate a GIF sent as a document — always send the stacked still image per state as the reliable carrier and treat the GIF as the extra.
   Multi-state GIF: `xwd` frame names restart per state, so copy every burst into ONE numbered sequence first (`cp <state>_f<i>.png $(printf '/tmp/g/f%03d.png' $n)`), then
   `ffmpeg -y -framerate 8 -i /tmp/g/f%03d.png -vf "unpremultiply=inplace=1,scale=216:216:flags=neighbor,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse" out.gif`
   (`unpremultiply` first — without it the transparent background turns into garbage noise; `flags=neighbor` keeps the 48px art crisp instead of blurred).
3. Log the state transitions from the widget (`face state -> thinking (#FBBF24)` …) as line-level evidence next to the images.

## Measuring idle CPU honestly
```
pid=$(systemctl --user show -p MainPID --value wtest)
a=$(awk '{print $14+$15}' /proc/$pid/stat); sleep 10; b=$(awk '{print $14+$15}' /proc/$pid/stat)
percent=$(awk -v d=$((b-a)) 'BEGIN{printf "%.1f", d/10/100*100}')   # % of one core
```
Warm up ~10s first, and measure with NO `ULTRON_STATE`/`ULTRON_MOOD` pinned — startup painting and mood transitions dominate a short window and read far higher than steady-state idle. Cheapest fixes, in order: repaint only when something actually changed (dirty flag), pre-render the glow ring into a cached `QPixmap` per radius instead of drawing gradients every frame, drop the timer to 50–100ms when only breathing is running, stop the timer entirely when no effect is active. Re-run the harness after optimising: cutting CPU by deleting an effect is a regression, not a fix.
