# Context-compression audit (Hermes)

Goal: answer "how does this agent compact context, is it working, and which lever
actually moves it?" with numbers read from config + logs, and a clear split between
what is a config change and what needs code.

## 1. Read the knobs

```bash
hermes config get compression
```

- `threshold_tokens` (absolute) is applied as a CAP on `threshold` (a ratio of
  the model window): whichever is lower wins. An absolute 100k on a 1M-window
  model therefore fires at 10% of the window — so resolve the window before
  judging the value (`curl -s <gateway>/v1/models` → `max_input_tokens`; the
  bundled model table is only a fallback). Per-model overrides live in
  `model_thresholds`, so one model can carry a different threshold from the rest.
- Raising the threshold is not merely "later": the pass reclaims
  `threshold − post_size` and post_size ≈ 0.8 × threshold, so reclaim scales with
  the threshold — ~17–20k reclaimed per pass at 100k, ~3× that at 300k, with the
  pass count dropping in the same proportion.
- `target_ratio` bounds how much of the threshold the protected tail may keep
  (0.2 of 100k = the tail may hold ~20k).
- `proactive_prune_tokens` / `proactive_prune_min_result_chars` /
  `proactive_prune_min_reclaim_tokens` govern the deterministic (no-LLM)
  tool-result prune.
- `micro_compact` (+ cadence) is the amortizing pass; `idle_compact_after_seconds`
  the after-idle pass; `model` overrides the summarizer; `engine` selects a
  context-engine plugin if installed.

## 2. Measure the passes from agent.log

Line shapes (prefix `YYYY-MM-DD HH:MM:SS,mmm LEVEL [session] module:`):

```
context compression started: session=<id> messages=<n> ... tokens=~<n>
context compression done:    session=<id> messages=<a>-><b> ... tokens=~<n>
```

```python
import re, glob, collections
start = re.compile(r'^(\S+ \S+) .*context compression started: session=(\S+) '
                   r'messages=(\d+) .*tokens=~([\d,]+)')
done  = re.compile(r'^(\S+ \S+) .*context compression done: session=(\S+) '
                   r'messages=(\d+)->(\d+) .*tokens=~([\d,]+)')
ev = collections.defaultdict(list)
for f in sorted(glob.glob('/home/zane/.hermes/logs/agent.log*')):
    for line in open(f, errors='ignore'):
        m = start.match(line) or done.match(line)
        if m:
            ev[m.group(2)].append((m.group(1), line[:5].strip(), m.groups()))
# per session: count passes, average trigger/after/reclaimed tokens, messages
# dropped, and wall time = done_ts - started_ts of consecutive pairs
```

Report per session: number of passes, average trigger tokens, average tokens after,
average reclaimed, average messages dropped, wall time per pass. Aggregate in
Python and print the summary only — never dump the matched lines into context.

**Pairing rule (get this wrong and every duration is garbage):** pair a `started`
with the `done` of the SAME session, and require the done line's messages-before to
equal the started line's messages. An aborted pass emits no `done` at all, so naive
FIFO pairing marries an old `started` to the next session's `done` (observed as an
absurd 31,182 s duration). Count leftover `started` lines separately as aborted
passes — they leave that session over the threshold with no summary written.

Re-runnable version of this whole section: `~/.hermes/scripts/compact_stats.py`
(`--hours N | --since ISO | --json | --send --space <id> [--thread <id>]`). Schedule
it through `~/.hermes/schedules.yaml` (0 tokens, `until:` to self-expire) rather
than re-deriving the numbers by hand each time someone asks.

## 3. Which layer actually ran

Hermes has four compaction layers; the trap is that one of them is wired to a
branch that rarely executes:

| Layer | What it does | How to prove it ran |
|---|---|---|
| Deterministic tool-result prune | Drops/truncates large tool results, keeps the latest few, no LLM call | it has **no log line of its own** — read the gate instead: it fires only after the prune threshold has been re-accumulated, and that same number doubles as the re-arm runway, so it can land at most once per compaction cycle |
| Batch/summarize compaction | Summarizes the unprotected middle into one message | the `compression started/done` log lines |
| Micro-compaction | Runs every N turns to amortize, keeps occupancy flat | opt-in flag + its own log lines |
| Idle compaction | Compacts after the session goes quiet | flag + log lines |

```bash
grep -rn "prune_tool_results_only" --include=*.py agent/ | grep -v tests   # call sites
```

General rule: grep a knob's call sites AND its gate, then ask which of its numbers
doubles as an accumulation amount. Match the symptom to its real cause:

- value set but the layer never fires → look for a sibling flag that disables it
  (`compression.checkpoint_required` force-disables micro-compaction and logs a
  warning line) or a per-session counter that another layer resets;
- layer fires far less often than the threshold predicts → the threshold is also
  the re-arm runway (true for `proactive_prune_tokens`);
- no log line at all → the layer is silent, so prove it with a probe or a code
  read. Absence of a line proves idleness only for layers that log their passes.

Micro-compaction's gates, in the order they bite: the flag is set on the
compressor *after* construction (so `hermes config get` showing it true is not
evidence it is live); the cadence counter (`micro_compact_every_n_turns`) must be
reached; a non-empty folding window must exist between the protected head and the
protected tail; and a batch compaction resets the micro cursor/rolling-summary
state, so a session that batch-compacts every few turns can starve the amortized
pass. Its proof-of-run marker is `micro compaction telemetry:`.

## 4. Latency and the summarizer model

One compaction = one auxiliary LLM call, on the main provider unless
`compression.model` overrides it. Measured with the main model as summarizer:
~55 s of wall time per pass, blocking inside the turn (a turn that compacts feels
like a hang).

- List the gateway's models before choosing: `curl -s <gateway>/v1/models -H
  "Authorization: Bearer $KEY"` (provider env var lives in `~/.hermes/.env`); a
  fast sibling of the main model is the right summarizer.
- Prompt-cache breaks: check `sessions.cache_read_tokens / input_tokens`. Near
  zero cache hits means each pass costs little extra, which is an argument FOR
  amortized (micro) compaction. High cache hits invert that trade-off.

## 5. Why the sawtooth happens, and the lever ranking

With an absolute threshold of ~100k and `target_ratio` 0.2, a pass triggers around
101k, lands around 80k, i.e. reclaims only ~22k tokens and drops ~15–30 messages.
A session that is genuinely busy re-crosses the threshold within minutes (two
passes two minutes apart is normal), so the cost is not one pause — it is a pause
per few turns for as long as the session lives.

Ranked by durability:

1. Deterministic tool-result prune BEFORE the summarize decision (no LLM, no
   latency, prose stays verbatim) — code change.
2. Per-tool result caps plus an aggregate tool-result budget (industry shape:
   total ~200k, shell ~30k, search/fetch ~20k per result) — code change.
3. Post-compaction re-injection of the most recently read files (Hermes
   re-injects only skill *markers* of pruned skills, not bodies or files) — code change.
4. Summarizer → fast sibling model — config.
5. Micro-compaction on with a small cadence — config, only AFTER (4).
6. Raising the threshold — config, and the one lever that moves the pass *rate*
   directly: reclaim per pass scales with the threshold (post ≈ 0.8 × threshold),
   so a higher threshold buys proportionally fewer passes for proportionally more
   tokens per turn. Treat it as a spend decision, not a technicality.

Claude Code's rule, useful for both explanation and arithmetic: it compacts when
the window has ~33k left — 20k reserved for the summary it is about to write plus
a 13k trigger — so 200k → ~167k (the familiar "83.5%" figure) and 1M → ~967k.
Microcompact runs before that as content-clearing of old tool results, and after a
compaction it spends up to 50k re-reading the most important files (max 5 × 5k).
Hermes equivalents: tool-result clearing ≙ the deterministic prune (silent,
re-arm-gated) · auto-compact summarize ≙ batch compaction · blocking limit +
reactive retry ≙ threshold plus cooldown/attempt cap · post-compact file restore
≙ not implemented (only pruned-skill markers come back).

## Threshold change = a spend decision (ask Hoàng)

Never raise a threshold quietly — it multiplies the input cost of every subsequent
turn. Put the arithmetic in one table and ask for an explicit pick:

```
threshold     est. tokens/turn   cost vs today   passes
100k (now)        ~85k             1x            baseline
300k             ~250k             3x            ~3x fewer
500k             ~420k             5x            ~5x fewer
~window-33k      ~900k            10x+           ~10x fewer
```

Quality is part of the trade, so state it: long-context reading accuracy is ~93% at
256k and degrades to ~76% at 1M — a mid threshold (256–300k) usually beats "match
Claude". Bundle every config change into ONE deferred gateway restart
(`scripts/gw_restart.txt`); code levers (per-tool caps, file re-injection) wait for
a separate go-ahead.

## 6. Manual compaction from chat

`/compress [focus]`, `/compress --preview` and `/compress here N` are dispatched by
the gateway, not only by the CLI, so they can be typed in the chat channel — handy to
compact on a topic before switching subjects.

## 7. Report shape

One screen: (a) table of passes — session, passes, trigger→after, reclaimed, wall
time; (b) which layer is wired and which never fires, each with the evidence;
(c) ranked levers split explicitly into config vs code, with the config ones
reversible first. Business language in group chats (no file paths or symbols);
technical detail is fine in the DM with Hoàng.
