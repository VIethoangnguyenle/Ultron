#!/usr/bin/env python3
"""Poll Hoang's Google Chat spaces for @Hoang mentions, then track whether Hoang
replied within a grace window. Mentions that Hoang leaves unanswered past the
window are emitted as markers under ~/.hermes/mention_pending/ for a separate
LLM cron to answer-or-notify.

Only @Hoang (users/110121981097849566202) is tracked. @all (empty userMention
user) and mentions of anyone else are ignored, per the owner's instruction.

Runs as a no_agent cron job (stdout -> cron log). State persists in
~/.hermes/mention_watch.json so restarts don't re-fire old mentions.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
READ_TOKEN = HERMES_HOME / "google_chat_read_token.json"
STATE_PATH = HERMES_HOME / "mention_watch.json"
PENDING_DIR = HERMES_HOME / "mention_pending"

HOANG_USER = os.environ.get("ULTON_HOANG_USER", "users/110121981097849566202")
WAIT_SEC = int(os.environ.get("ULTON_MENTION_WAIT_SEC", "120"))
LOOKBACK_MIN = int(os.environ.get("ULTON_MENTION_LOOKBACK_MIN", "30"))
PRUNE_SEC = int(os.environ.get("ULTON_MENTION_PRUNE_SEC", "3600"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(s: str) -> float:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _load_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not READ_TOKEN.exists():
        return None
    creds = Credentials.from_authorized_user_info(json.loads(READ_TOKEN.read_text(encoding="utf-8")))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _build_service(creds):
    from googleapiclient.discovery import build
    return build("chat", "v1", credentials=creds)


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"watch": {}}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_spaces(svc):
    """Yield (name, displayName, spaceType) for non-DM spaces Hoang is a member of."""
    out = []
    page = None
    while True:
        resp = svc.spaces().list(pageSize=1000, pageToken=page).execute() if page \
            else svc.spaces().list(pageSize=1000).execute()
        for s in resp.get("spaces", []):
            st = (s.get("spaceType") or s.get("type") or "").upper()
            if st in {"DIRECT_MESSAGE", "DM"}:
                continue
            out.append((s.get("name", ""), s.get("displayName") or s.get("name") or "?", st))
        page = resp.get("nextPageToken")
        if not page:
            break
    return out


def _list_messages_since(svc, space: str, since: datetime):
    """List messages in `space` created after `since`."""
    out = []
    page = None
    flt = f'createTime > "{_rfc3339(since)}"'
    while True:
        kw = dict(parent=space, pageSize=1000, filter=flt)
        if page:
            kw["pageToken"] = page
        resp = svc.spaces().messages().list(**kw).execute()
        out.extend(resp.get("messages", []))
        page = resp.get("nextPageToken")
        if not page:
            break
    return out


def _hoang_mentions(msg: dict) -> bool:
    for a in msg.get("annotations") or []:
        if a.get("type") != "USER_MENTION":
            continue
        user = (a.get("userMention") or {}).get("user") or {}
        if user.get("name") == HOANG_USER:
            return True
    return False


def _hoang_replied(svc, space: str, thread: str, since: datetime) -> bool:
    """True if Hoang posted a message in `thread` after `since`."""
    parts = [f'createTime > "{_rfc3339(since)}"']
    if thread:
        parts.append(f'thread.name = "{thread}"')
    flt = " AND ".join(parts)
    page = None
    while True:
        kw = dict(parent=space, pageSize=1000, filter=flt)
        if page:
            kw["pageToken"] = page
        resp = svc.spaces().messages().list(**kw).execute()
        for m in resp.get("messages", []):
            if (m.get("sender") or {}).get("name") == HOANG_USER:
                return True
        page = resp.get("nextPageToken")
        if not page:
            break
    return False


def _emit_pending(entry: dict) -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    safe = entry.get("message_name", "unknown").replace("/", "_").replace(":", "_")
    path = PENDING_DIR / f"{safe}.json"
    path.write_text(json.dumps({
        "space": entry.get("space"),
        "space_name": entry.get("space_name"),
        "thread": entry.get("thread"),
        "message_name": entry.get("message_name"),
        "text": entry.get("text"),
        "sender": entry.get("sender"),
        "sender_name": entry.get("sender_name"),
        "created_at": entry.get("create_time"),
        "waited_sec": WAIT_SEC,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _kick_reply_job()


REPLY_JOB_ID = "5fc5e2166c3a"  # job ultron-mention-reply (LLM)


def _kick_reply_job() -> None:
    """Đánh thức job trả lời NGAY thay vì để nó tự thức mỗi 2 phút.

    Mỗi lần job LLM thức dậy — kể cả khi không có việc gì — vẫn gửi lại toàn bộ system prompt
    (~27k token). Quét 2 phút/lần = ~19 triệu token/ngày cho việc ngó hàng đợi. Nên: poller (script,
    0 token) phát hiện việc rồi mới kích; job LLM để nhịp thưa làm lưới an toàn.
    """
    hermes = Path(sys.executable).parent / "hermes"
    if not hermes.exists():
        return
    try:
        subprocess.Popen([str(hermes), "cron", "run", REPLY_JOB_ID],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception as exc:  # không chặn poller vì trigger lỗi
        print(f"[mention_poller] kick reply job failed: {exc}")


_MEMBERS_CACHE_PATH = HERMES_HOME / "mention_members_cache.json"


def _load_members_cache() -> dict:
    if _MEMBERS_CACHE_PATH.exists():
        try:
            return json.loads(_MEMBERS_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_members_cache(cache: dict) -> None:
    _MEMBERS_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


_READ_CREDS = None
_DIRECTORY_SVC = None


def _resolve_sender_name(svc, space: str, sender_id: str):
    """Resolve a user id -> display name via Directory API (user OAuth), cached
    globally. Falls back to the raw id when the domain hides directory data."""
    if not sender_id:
        return None
    cache = _load_members_cache()
    names = cache.setdefault("_names", {})
    if sender_id in names:
        return names[sender_id]
    uid = sender_id.rsplit("/", 1)[-1]
    global _DIRECTORY_SVC
    try:
        if _READ_CREDS is None:
            return sender_id
        if _DIRECTORY_SVC is None:
            from googleapiclient.discovery import build as _build
            _DIRECTORY_SVC = _build("admin", "directory_v1", credentials=_READ_CREDS, cache_discovery=False)
        user = _DIRECTORY_SVC.users().get(userKey=uid, projection="basic").execute()
        full = ((user.get("name") or {}).get("fullName")) or None
        if full:
            names[sender_id] = full
            _save_members_cache(cache)
            return full
    except Exception:
        pass
    return sender_id


def main() -> int:
    creds = _load_creds()
    if creds is None:
        print("[mention_poller] no read token; skipping")
        return 0
    global _READ_CREDS
    _READ_CREDS = creds
    svc = _build_service(creds)
    state = _load_state()
    watch = state.setdefault("watch", {})
    now = _now_utc()
    now_ts = now.timestamp()

    # Prune terminal entries older than the prune window.
    for key in list(watch.keys()):
        e = watch[key]
        if e.get("status") != "watching" and now_ts - e.get("first_seen_ts", 0) > PRUNE_SEC:
            del watch[key]

    # Scan for new @Hoang mentions (only messages from the lookback window).
    since = now - timedelta(minutes=LOOKBACK_MIN)
    new_count = 0
    for space, display, stype in _list_spaces(svc):
        try:
            msgs = _list_messages_since(svc, space, since)
        except Exception as exc:
            print(f"[mention_poller] skip {space}: {exc}")
            continue
        for m in msgs:
            msg_name = m.get("name", "")
            if not msg_name or msg_name in watch:
                continue
            sender = (m.get("sender") or {}).get("name", "")
            if sender == HOANG_USER:
                continue  # Hoang self-mention: not a question for him
            if not _hoang_mentions(m):
                continue
            sender_name = _resolve_sender_name(svc, space, sender)
            watch[msg_name] = {
                "space": m.get("space", {}).get("name", space),
                "space_name": m.get("space", {}).get("displayName") or display,
                "thread": (m.get("thread") or {}).get("name"),
                "message_name": msg_name,
                "text": m.get("text") or m.get("argumentText") or "",
                "sender": sender,
                "sender_name": sender_name or sender,
                "create_time": m.get("createTime", ""),
                "create_ts": _parse_ts(m.get("createTime", "")),
                "first_seen_ts": now_ts,
                "status": "watching",
            }
            new_count += 1

    # Advance watching entries: resolved if Hoang replied; else escalate after wait.
    for key, e in watch.items():
        if e.get("status") != "watching":
            continue
        create_ts = e.get("create_ts", 0)
        try:
            if create_ts and _hoang_replied(svc, e.get("space", ""), e.get("thread") or "", _utc_from_ts(create_ts)):
                e["status"] = "resolved"
                continue
        except Exception as exc:
            print(f"[mention_poller] reply-check {key}: {exc}")
            continue
        if create_ts and (now_ts - create_ts) >= WAIT_SEC:
            _emit_pending(e)
            e["status"] = "escalated"
            print(f"[mention_poller] escalated {key}")

    _save_state(state)
    if new_count:
        print(f"[mention_poller] +{new_count} new @Hoang mentions tracked")
    return 0


def _utc_from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


if __name__ == "__main__":
    sys.exit(main())
