# Agent token accounting (Hermes)

Goal: answer "which session / thread / group burns the most tokens, and today?"
with measured numbers, then name the lever that shrinks the spend. And answer
"what mechanisms save tokens?" by auditing what is configured, not by reciting
features.

## Sources of truth

| Question | Source |
|---|---|
| Cumulative per session (from open till now) | `~/.hermes/state.db` → `sessions.input_tokens`, `output_tokens`, `cache_read_tokens`, `api_call_count`, `message_count` |
| Which chat/thread a session belongs to | `sessions.chat_id`, `sessions.thread_id`, `sessions.chat_type` (`dm` vs `group`), `json_extract(origin_json,'$.chat_name')` |
| True per-day attribution (incl. sessions opened on earlier days) | `~/.hermes/logs/agent.log*` lines `agent.conversation_loop: API call #N: ... in=<n> out=<n>` |
| Fixed per-call floor | `hermes prompt-size` (system prompt / tool schemas / memory tier sizes) |
| Scheduled summary + alerting state | `~/.hermes/reports/token_budget.md`, `~/.hermes/token_budget_state.json` |
| Per-day alert threshold override | `~/.hermes/token_budget_overrides.json` = `{"YYYY-MM-DD": <tokens>}`, read by `scripts/token_budget.py:day_threshold()` |
| Which scheduled jobs actually call an LLM | `~/.hermes/cron/jobs.json` (`no_agent` true/false) |

## Nới/siết ngưỡng cảnh báo theo NGÀY (one-day override)

Hoàng nói "hôm nay ngưỡng X" → KHÔNG sửa hằng `DAY_INPUT_ALERT_TOKENS` trong script
(đổi là đổi luôn mọi ngày, phá phạm vi anh chốt). Ghi vào `~/.hermes/token_budget_overrides.json`:
`{"2026-09-15": 120000000}`. Ngày nào có key thì ngưỡng ngày hiệu dụng = giá trị đó, kèm nhãn
"(ngưỡng riêng của ngày)" trong alert; ngày khác vẫn 60M mặc định. Key cũ tự bị dọn
(`prune_overrides`, chạy mỗi lượt thật) ⇒ override tự hết hạn, không rác tích tụ.

Một lượt cảnh báo "day" chỉ bắn MỘT lần/ngày (`token_budget_state.json` → `alerts[day]` chứa `"day"`).
Nâng ngưỡng giữa ngày mà muốn nó còn báo khi vượt mức mới ⇒ phải XOÁ `"day"` khỏi danh sách
của ngày hôm nay, nếu không nó im luôn tới hết ngày.

Kiểm chứng không cần chờ cron: `python3 scripts/token_budget.py --dry-run` (in `→ SẼ báo Hoàng: day`
khi vượt ngưỡng, KHÔNG ghi state). Test đường override: tạm set giá trị nhỏ hơn số hiện tại → phải
in "SẼ báo"; xoá file → rơi về mặc định 60M; JSON hỏng → không crash, rơi về mặc định.

## Queries that work

```sql
-- top sessions, all time
select id, datetime(started_at,'unixepoch','+7 hours') started,
       input_tokens/1000000.0 in_M, api_call_count calls,
       round(input_tokens*1.0/nullif(api_call_count,0)) avg_per_call,
       chat_id, title
from sessions order by input_tokens desc limit 10;

-- per group / per thread
select coalesce(json_extract(origin_json,'$.chat_name'), chat_id) chat,
       coalesce(nullif(thread_id,''),'(no-thread)') thread,
       count(*) sessions, sum(input_tokens)/1000000.0 in_M
from sessions where source='google_chat'
group by chat, thread order by in_M desc limit 10;
```

`sessions.input_tokens` is a running total per session, so grouping it is only
meaningful as "spend attributed to that thread/chat since the session opened".

## Per-day burn from the rotated logs

Logs rotate at ~5 MB (`agent.log`, `agent.log.1`, ...), so older days may be
missing — state which days the parse covers. Parse all of them and aggregate in
Python; never print raw matched lines into context.

```python
import re, glob, collections
pat = re.compile(r'^(\d{4}-\d{2}-\d{2}) \d\d:\d\d:\d\d,\d+ INFO \[(\w+)\] '
                 r'agent\.conversation_loop: API call #\d+: .*? in=(\d+) out=(\d+)')
agg = collections.defaultdict(lambda: [0, 0, 0])   # (day, session) -> in, out, calls
for f in sorted(glob.glob('/home/zane/.hermes/logs/agent.log*')):
    for line in open(f, errors='ignore'):
        m = pat.match(line)
        if m:
            k = (m.group(1), m.group(2))
            agg[k][0] += int(m.group(3)); agg[k][1] += int(m.group(4)); agg[k][2] += 1
# then: filter by day for "today", or by session prefix, and sum
```

## The fixed per-call floor

Spend ≈ `calls × floor + accumulated history`, so there are exactly two things to
attack.

- `hermes prompt-size` breaks the floor into system prompt, tool schemas, memory
  tiers and the skills index. A floor of ~26k/call means a day with ~1.5k calls
  pays ~40M tokens before any conversation content — quote this when someone
  expects a brand-new session to be "free".
- The floor is paid again on every call, including each turn of a tool loop, so
  batching N tool calls into one turn saves N × floor.
- The floor can be trimmed per platform by restricting the toolset (unused
  browser / TTS / vision / code-execution tools each carry schema weight) — a few
  k per call, multiplied by every call of the day.

## Cost-control lever audit ("có cơ chế nào tiết kiệm token không?")

Answer in two blocks: what is already ON, then what is still OFF ranked by
savings. Verify every "ON" from config — do not assume defaults.

| Lever | Where to check |
|---|---|
| Context compression at an absolute token threshold (not % of window) | `compression.threshold_tokens`, `target_ratio` |
| Pruning large tool results / proactive prune | `compression.proactive_prune_*` |
| Compaction after idle | `compression.idle_compact_after_seconds` |
| Per-user sessions inside group chats | `group_sessions_per_user` |
| Cron jobs that avoid the LLM entirely | `cron/jobs.json` → `no_agent: true` |
| Deferred tool schemas (load on demand) | tool count in `prompt-size` vs configured toolsets |
| Prompt caching actually paying off | `sessions.cache_read_tokens` vs `input_tokens` |
| Long-output handling | big tool output written to a file, context keeps the path only |

Levers usually still OFF, worth proposing (biggest first):

1. Session lifetime. A marathon session re-sends its whole context every turn;
   a fresh session starts at the floor (`/new` in the chat, or a scheduled nudge
   when a session crosses ~150 turns / ~100k per turn).
2. Push heavy digging (log sweep, DB scan, graph build) into a child context so
   only the summary returns to the main conversation.
3. Batch tool calls per turn; avoid loops that re-ask the same thing.
4. Trim rarely used tools from the platform toolset.
5. Cheaper model for auxiliary work (titles, summaries, raw-log triage).
6. Turn the watchdog from *reporting* into a hard daily cap that blocks further
   LLM jobs.

## Interpretation rules

- `input_tokens / api_call_count` = average context re-sent per turn. ~25k =
  fresh session; 80–165k = bloated session; that ratio, not the raw total, is
  the thing to fix.
- A session that stays alive for days is the single biggest cost driver — it is
  never the cron jobs. Ranking the chats usually shows one long-lived session
  outweighing dozens of short ones by an order of magnitude.
- Delivering scheduled task output into a live chat session adds a turn to that
  session's context; check which session a recurring delivery targets before
  blaming a job for its own token cost.
- `messages` row counts are not calls (one call leaves several assistant/tool
  rows, compaction replays more). Use `api_call_count` / log lines.
- The scheduled daily report keys on `started_at` day and therefore omits
  marathon sessions from both the daily total and the top-N list; treat its
  "today" figure as a lower bound and re-derive from logs before quoting it.
- Input far outweighs output (~130:1 in practice): rank by input, and treat
  output-side tuning as noise.

## Report shape (what the user wants)

1. Top sessions table (token in, calls, token/turn).
2. Same ranked per group/thread — the user asks "thread vs session".
3. Today's totals + that day's top session.
4. One caveat/insight (e.g. under-counted report) and one concrete lever
   ("open a new session for that chat → ~120k/turn drops to ~25k").

Tables inside a code block (Chat renders monospace alignment), business
language only, @mention the asker, reply in the asking thread.
