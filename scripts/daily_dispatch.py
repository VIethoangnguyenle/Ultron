#!/usr/bin/env python3
"""Config-driven daily dispatcher — ONE cron job instead of N one-shot jobs.

Why (Hoàng, 2026-09-10): every ad-hoc "làm X lúc 9h" used to create its own cron job record,
plus its delivery rows, fire lock, and the whole one-shot lifecycle (catch-up window, dispatch
claim, wedged-removal guards, terminal records that linger until the retention sweep). Those
leftovers are debris nobody cleans. One dispatcher + one editable config means:

  - a new scheduled action is a CONFIG LINE, not a job
  - turning it off is `enabled: false` (or deleting the line) — no cron surgery
  - one-shot actions expire by themselves (`date:` / `until:`) so nothing rots
  - one job to inspect, one place to look when something didn't fire

Config  ~/.hermes/schedules.yaml        State  ~/.hermes/schedules.state.json
Log     ~/.hermes/cron/dispatch.log     Failures  -> ~/.hermes/escalations/ (forwarded to Hoàng)

Usage:
  daily_dispatch.py                  # tick: fire what is due (this is what cron runs)
  daily_dispatch.py --list           # show the schedule + today's outcome
  daily_dispatch.py --dry-run        # show what WOULD fire, change nothing
  daily_dispatch.py --run <id>       # fire one action now, ignoring the clock
  daily_dispatch.py --prune          # list expired / switched-off actions worth deleting

Action fields: id (required), when "HH:MM", script, args[], enabled, days[], date (one-shot),
until (expiry), catch_up_minutes (default 120), retry (attempts per day, default 1).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
CONFIG = HOME / "schedules.yaml"
STATE = HOME / "schedules.state.json"
LOG = HOME / "cron" / "dispatch.log"
ESCALATIONS = HOME / "escalations"
SCRIPTS = HOME / "scripts"
PY = HOME / "hermes-agent" / "venv" / "bin" / "python"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_CATCH_UP_MIN = 120   # gateway was down at 09:00 but up at 09:40 -> still fire
ACTION_TIMEOUT_S = 180


# ---------------------------------------------------------------- config / state

def load_config(path: Path = CONFIG) -> list:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml
        data = yaml.safe_load(raw)
    except ImportError:  # YAML is nicer to edit; JSON still works without pyyaml
        data = json.loads(raw)
    actions = (data or {}).get("actions") or []
    if not isinstance(actions, list):
        raise SystemExit("schedules.yaml: 'actions' phải là danh sách")
    return actions


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def _st(state: dict, aid: str, today: str = None) -> dict:
    """That day's record for one action: {date, tries, ok, alerted}.

    ``today`` is passed in so the decision depends on the clock being evaluated, not on
    ``date.today()`` — otherwise ``is_due`` disagrees with any non-current ``now`` (seen when
    simulating other days: an action already run that day still reported "tới giờ").
    """
    day = today or date.today().isoformat()
    cur = state.get(aid)
    if not isinstance(cur, dict):
        cur = {}
    if cur.get("date") != day:
        cur = {"date": day, "tries": 0, "ok": None, "alerted": None}
    return cur


# ---------------------------------------------------------------- scheduling

def _parse_hhmm(value: str):
    hh, mm = str(value).split(":")
    return int(hh), int(mm)


def is_due(action: dict, now: datetime, state: dict) -> tuple:
    """-> (due: bool, reason: str). Pure decision from config + state + clock."""
    aid = action.get("id")
    if not aid:
        return False, "thiếu id"
    if not action.get("enabled", True):
        return False, "đang tắt (enabled: false)"

    today = now.date()
    if action.get("date") and str(action["date"]) != today.isoformat():
        return False, f"chỉ chạy ngày {action['date']} (hôm nay {today.isoformat()})"
    if action.get("until") and today.isoformat() > str(action["until"]):
        return False, f"đã hết hạn ({action['until']})"
    days = action.get("days")
    if days:
        allowed = {str(d).strip().lower()[:3] for d in (days if isinstance(days, list) else [days])}
        if WEEKDAYS[today.weekday()] not in allowed:
            return False, f"không thuộc {sorted(allowed)}"

    st = _st(state, aid, today.isoformat())
    max_tries = max(1, int(action.get("retry", 1)))
    if st.get("date") == today.isoformat():
        if st.get("ok"):
            return False, "đã chạy hôm nay"
        if st.get("tries", 0) >= max_tries:
            return False, f"đã thử {st.get('tries')} lần và lỗi — không thử lại hôm nay"

    hh, mm = _parse_hhmm(action.get("when") or action.get("at") or "09:00")
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < target:
        return False, f"chưa tới giờ ({target.strftime('%H:%M')})"
    catch_up = int(action.get("catch_up_minutes", DEFAULT_CATCH_UP_MIN))
    if now - target > timedelta(minutes=catch_up):
        return False, f"trễ quá {catch_up}' (lỡ cửa sổ) — bỏ qua"
    return True, "tới giờ"


def build_cmd(action: dict) -> list:
    script = action.get("script")
    if not script:
        raise SystemExit(f"action {action.get('id')}: thiếu 'script'")
    py = str(PY) if PY.exists() else sys.executable
    path = Path(script)
    if not path.is_absolute():
        path = SCRIPTS / script
    return [py, str(path), *[str(a) for a in (action.get("args") or [])]]


def fire(action: dict, dry_run: bool = False) -> tuple:
    """Run the action's script. -> (ok, output). Never raises."""
    cmd = build_cmd(action)
    if dry_run:
        return True, "DRY-RUN: " + " ".join(cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ACTION_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, f"quá {ACTION_TIMEOUT_S}s không xong"
    except Exception as exc:
        return False, f"không chạy được: {exc}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {err or out or '(không có output)'}"
    return True, out or "(không có output)"


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")


def escalate(action: dict, reason: str, output: str) -> None:
    """Failures go through the existing escalation pipeline -> Hoàng's DM (once per day)."""
    ESCALATIONS.mkdir(parents=True, exist_ok=True)
    payload = {
        "from": "Ultron (daily dispatcher)",
        "space": "nội bộ — job định kỳ",
        "question": f"Action '{action.get('id')}' chạy lỗi: {reason}",
        "reason": (output or "")[:800],
    }
    (ESCALATIONS / f"dispatch-{int(time.time())}-{action.get('id')}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- commands

def cmd_tick(actions: list, state: dict, dry_run: bool) -> int:
    """Fire what is due. Records EVERY attempt (success or failure) so a broken action retries
    only up to `retry` times a day instead of every tick, and alerts at most once a day."""
    now = datetime.now()
    fired, problems = [], []
    for action in actions:
        due, _reason = is_due(action, now, state)
        if not due:
            continue
        aid = action.get("id")
        ok, output = fire(action, dry_run=dry_run)
        if ok:
            fired.append(f"{aid}: {output.splitlines()[0][:120] if output else 'ok'}")
            log(f"FIRED {aid} -> {output[:200]!r}")
            if not dry_run:
                st = _st(state, aid, now.date().isoformat())
                st.update({"tries": st.get("tries", 0) + 1, "ok": True})
                state[aid] = st
                save_state(state)
        else:
            problems.append(f"{aid}: {output}")
            log(f"FAILED {aid} -> {output[:300]!r}")
            if not dry_run:
                st = _st(state, aid)
                first_alert = st.get("alerted") != now.date().isoformat()
                st.update({"tries": st.get("tries", 0) + 1, "ok": False})
                if first_alert:
                    st["alerted"] = now.date().isoformat()
                    escalate(action, "chạy lỗi", output)
                state[aid] = st
                save_state(state)
    if fired or problems:
        stamp = now.strftime("%Y-%m-%d %H:%M")
        print(f"[{stamp}] daily dispatch: {len(fired)} chạy, {len(problems)} lỗi")
        for line in fired:
            print(f"  ok   {line}")
        for line in problems:
            print(f"  LỖI  {line}")
    return 1 if problems else 0


def cmd_list(actions: list, state: dict) -> int:
    today = date.today().isoformat()
    if not actions:
        print(f"(chưa có action nào trong {CONFIG})")
        return 0
    print(f"{'id':26} {'giờ':6} {'bật':6} {'hôm nay':10} điều kiện")
    for a in actions:
        aid = a.get("id", "?")
        cond = []
        if a.get("date"):
            cond.append(f"ngày {a['date']}")
        if a.get("until"):
            cond.append(f"đến {a['until']}")
        if a.get("days"):
            cond.append("/".join(a["days"]) if isinstance(a["days"], list) else str(a["days"]))
        st = _st(state, aid)
        if st.get("date") == today:
            why = {True: "đã chạy", False: f"lỗi (thử {st.get('tries')}x)"}.get(st.get("ok"), "-")
        else:
            why = "-"
        print(f"{aid:26} {str(a.get('when') or a.get('at') or '09:00'):6} "
              f"{str(a.get('enabled', True)):6} {why:10} {', '.join(cond) or 'mỗi ngày'}")
    return 0


def cmd_prune(actions: list, state: dict) -> int:
    """Expired / finished one-shots are safe to delete — report them, never auto-delete."""
    today = date.today().isoformat()
    stale = []
    for a in actions:
        aid = a.get("id")
        if a.get("date") and str(a["date"]) < today:
            stale.append(f"{aid}  (one-shot ngày {a['date']} đã qua)")
        elif a.get("until") and str(a["until"]) < today:
            stale.append(f"{aid}  (hết hạn {a['until']})")
        elif not a.get("enabled", True):
            stale.append(f"{aid}  (đang tắt)")
    if not stale:
        print("Không có action nào hết hạn / tắt — config sạch.")
        return 0
    print(f"{len(stale)} action có thể xoá khỏi {CONFIG}:")
    for line in stale:
        print("  -", line)
    print("\n(em không tự xoá — cần Hoàng xác nhận)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", metavar="ID")
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args()

    if a.config != str(CONFIG):
        globals()["CONFIG"] = Path(a.config)
    actions = load_config(Path(a.config))
    state = load_state()

    if a.list:
        return cmd_list(actions, state)
    if a.prune:
        return cmd_prune(actions, state)
    if a.run:
        match = [x for x in actions if x.get("id") == a.run]
        if not match:
            print(f"không có action id='{a.run}'", file=sys.stderr)
            return 2
        ok, output = fire(match[0], dry_run=a.dry_run)
        print(("ok   " if ok else "LỖI  ") + str(output)[:500])
        return 0 if ok else 1
    return cmd_tick(actions, state, dry_run=a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
