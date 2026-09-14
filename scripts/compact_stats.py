#!/usr/bin/env python3
"""Báo cáo hiệu quả nén ngữ cảnh (context compression) của Hermes từ log.

Chỉ ĐỌC log, không ghi log/DB, không sửa cấu hình. Dùng stdlib thuần.

    compact_stats.py --hours 24
    compact_stats.py --since 2026-09-14T08:00:00
    compact_stats.py --since 08:30 --json
    compact_stats.py --hours 6 --send --space spaces/AAQAZxc2km8

Marker được đọc (đúng chuỗi trong log, không đoán):
  - "context compression started: session=... messages=... tokens=~... model=... focus=..."
  - "context compression done: session=... messages=a->b rough_tokens=~... awaiting_real_usage=..."
  - "Auxiliary compression: using custom (<model>) at <url>"   (dòng ngay sau marker started)
  - "micro compaction telemetry: {json}"                        (nén trả góp)
  - "Micro-compaction: recovered rolling summary from transcript"
  - "micro-summarization call failed: ..." / "micro-summarization returned empty content"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_LOG = Path("/home/zane/.hermes/scripts").parent / "logs" / "agent.log"
GCHAT_SENDER = Path("/home/zane/.hermes/scripts/gchat_send_text.py")
DEFAULT_SPACE = "spaces/AAQAZxc2km8"

SLOW_COMPRESSION_SECONDS = 30.0
MAX_COMPRESSIONS_PER_HOUR = 5

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")

STARTED_RE = re.compile(
    r"context compression started: session=(?P<session>\S+)"
    r"(?:\s+messages=(?P<messages>\d+))?"
    r"(?:\s+tokens=~(?P<tokens>[\d,]+))?"
    r"(?:\s+model=(?P<model>\S+))?"
    r"(?:\s+focus=(?P<focus>\S+))?"
)
DONE_RE = re.compile(
    r"context compression done: session=(?P<session>\S+)"
    r"(?:\s+messages=(?P<before>\d+)->(?P<after>\d+))?"
    r"(?:\s+rough_tokens=~(?P<tokens>[\d,]+))?"
)
AUX_RE = re.compile(r"Auxiliary compression: using \S+ \((?P<model>[^)]+)\)")
MICRO_TELEMETRY_MARKER = "micro compaction telemetry: "
MICRO_RECOVERED_MARKER = "Micro-compaction: recovered rolling summary from transcript"
MICRO_FAILED_MARKER = "micro-summarization call failed"
MICRO_EMPTY_MARKER = "micro-summarization returned empty content"


def parse_ts(line: str):
    """Mốc thời gian đầu dòng, None nếu dòng không phải dòng log (JSON xuống dòng...)."""
    m = TS_RE.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
        microsecond=int(m.group(2)) * 1000
    )


def to_int(raw):
    """'101,636' -> 101636. Thiếu/hỏng thì None, không hard-fail."""
    if raw is None:
        return None
    try:
        return int(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def num_or_none(value):
    """Chỉ nhận số thật từ JSON telemetry; bỏ qua null/chuỗi."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def log_paths(primary: Path) -> list[Path]:
    """File chính + file xoay .1 nếu có (log xoay thì mốc 24h vẫn đủ dữ liệu)."""
    paths = []
    for candidate in (primary, primary.with_name(primary.name + ".1")):
        if candidate.is_file():
            paths.append(candidate)
    return paths


def resolve_since(args) -> datetime:
    """--since thắng --hours. 'HH:MM' hiểu là hôm nay; nếu ở tương lai thì lùi 1 ngày."""
    now = datetime.now()
    if not args.since:
        return now - timedelta(hours=args.hours)
    raw = args.since.strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        hh, mm = (int(x) for x in raw.split(":"))
        candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return candidate - timedelta(days=1) if candidate > now else candidate
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise SystemExit_2(f"--since không hợp lệ: {raw!r} (cần ISO-8601 hoặc 'HH:MM')")


class SystemExit_2(Exception):
    """Lỗi tham số -> mã thoát 2."""


def scan(paths: list[Path]) -> dict:
    """Đọc mọi file, trả về các sự kiện thô đã sắp theo thời gian."""
    started, done, micro_rows = [], [], []
    micro_recovered = micro_failed = micro_empty = 0
    aux_pending = []  # (ts, model) — ghép vào lần started gần nhất trước đó
    unreadable = []

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            unreadable.append(f"{path}: {exc}")
            continue
        for line in text.splitlines():
            ts = parse_ts(line)
            if MICRO_TELEMETRY_MARKER in line:
                idx = line.find(MICRO_TELEMETRY_MARKER) + len(MICRO_TELEMETRY_MARKER)
                try:
                    payload = json.loads(line[idx:])
                except ValueError:
                    continue
                if isinstance(payload, dict):
                    micro_rows.append((ts, payload))
                continue
            if MICRO_RECOVERED_MARKER in line:
                micro_recovered += 1
                continue
            if MICRO_FAILED_MARKER in line:
                micro_failed += 1
                continue
            if MICRO_EMPTY_MARKER in line:
                micro_empty += 1
                continue
            if ts is None:
                continue
            aux = AUX_RE.search(line)
            if aux:
                aux_pending.append((ts, aux.group("model")))
                continue
            m = STARTED_RE.search(line)
            if m:
                started.append({
                    "ts": ts,
                    "session": m.group("session"),
                    "messages": to_int(m.group("messages")),
                    "tokens": to_int(m.group("tokens")),
                    "model": m.group("model"),
                    "focus": m.group("focus"),
                    "aux_model": None,
                })
                continue
            m = DONE_RE.search(line)
            if m:
                done.append({
                    "ts": ts,
                    "session": m.group("session"),
                    "messages_before": to_int(m.group("before")),
                    "messages_after": to_int(m.group("after")),
                    "tokens": to_int(m.group("tokens")),
                })

    started.sort(key=lambda e: e["ts"])
    done.sort(key=lambda e: e["ts"])
    aux_pending.sort(key=lambda e: e[0])
    attach_aux(started, aux_pending)
    return {
        "started": started,
        "done": done,
        "micro_rows": micro_rows,
        "micro_recovered": micro_recovered,
        "micro_failed": micro_failed,
        "micro_empty": micro_empty,
        "unreadable": unreadable,
    }


def attach_aux(started: list[dict], aux_pending: list) -> None:
    """Dòng Auxiliary nằm ngay sau started -> gán cho lần started gần nhất trước nó."""
    if not started:
        return
    idx = 0
    for ts, model in aux_pending:
        while idx + 1 < len(started) and started[idx + 1]["ts"] <= ts:
            idx += 1
        event = started[idx]
        if event["ts"] <= ts and event["aux_model"] is None:
            event["aux_model"] = model


def pair_events(started: list[dict], done: list[dict]) -> tuple[list[dict], list[dict]]:
    """Ghép started -> done: mỗi session chạy tuần tự nên chỉ ghép với lần started GẦN NHẤT.

    Lần nén bị bỏ dở (không có dòng done) là chuyện có thật trong log. Nếu xếp hàng FIFO thì
    dòng done kế tiếp sẽ dính vào lần started cũ đó và đẻ ra thời lượng hàng nghìn giây sai bét.
    Hai chốt chặn: started mới của cùng session đẩy started cũ thành lẻ, và messages_before của
    dòng done phải khớp messages của dòng started mới nhận cặp.
    """
    pending: dict[str, dict] = {}
    pairs, orphans = [], []
    stream = [("start", e) for e in started] + [("done", e) for e in done]
    stream.sort(key=lambda item: (item[1]["ts"], item[0] == "done"))

    for kind, event in stream:
        if kind == "start":
            stale = pending.get(event["session"])
            if stale is not None:
                orphans.append(stale)
            pending[event["session"]] = event
            continue
        begin = pending.pop(event["session"], None)
        if begin is None:
            continue  # done không có started trong cửa sổ -> bỏ qua
        counts_known = begin["messages"] is not None and event["messages_before"] is not None
        if counts_known and begin["messages"] != event["messages_before"]:
            orphans.append(begin)  # không phải một cặp -> đừng bịa ra thời lượng
            continue
        tokens_after = event["tokens"]
        recovered = None
        if begin["tokens"] is not None and tokens_after is not None:
            recovered = begin["tokens"] - tokens_after
        dropped = None
        if event["messages_before"] is not None and event["messages_after"] is not None:
            dropped = event["messages_before"] - event["messages_after"]
        pairs.append({
            "session": begin["session"],
            "started_at": begin["ts"],
            "done_at": event["ts"],
            "duration_s": round((event["ts"] - begin["ts"]).total_seconds(), 1),
            "trigger_tokens": begin["tokens"],
            "tokens_after": tokens_after,
            "tokens_recovered": recovered,
            "messages_before": event["messages_before"],
            "messages_after": event["messages_after"],
            "messages_dropped": dropped,
            "main_model": begin["model"],
            "summary_model": begin["aux_model"],
            "focus": begin["focus"],
        })
    orphans.extend(pending.values())
    orphans.sort(key=lambda e: e["ts"])
    pairs.sort(key=lambda p: p["started_at"])
    return pairs, orphans


def stats_of(values: list) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(clean),
        "avg": round(sum(clean) / len(clean), 1),
        "min": min(clean),
        "max": max(clean),
    }


def peak_per_hour(pairs: list[dict], started: list[dict]) -> int:
    """Số lần nén nhiều nhất trong một cửa sổ trượt 60 phút."""
    times = sorted([p["started_at"] for p in pairs] + [e["ts"] for e in started])
    peak = 0
    left = 0
    for right, ts in enumerate(times):
        while ts - times[left] > timedelta(hours=1):
            left += 1
        peak = max(peak, right - left + 1)
    return peak


def summarize_micro(micro_rows: list, scan_result: dict) -> dict:
    """Telemetry trả góp: lấy khoá số nếu có, thiếu khoá thì bỏ qua chứ không lỗi."""
    outcomes: dict[str, int] = {}
    recovered_tokens = []
    durations = []
    for _, payload in micro_rows:
        outcome = payload.get("outcome")
        key = outcome if isinstance(outcome, str) and outcome else "(không rõ)"
        outcomes[key] = outcomes.get(key, 0) + 1

        delta = num_or_none(payload.get("tokens_delta"))
        if delta is None:
            before = num_or_none(payload.get("tokens_before"))
            after = num_or_none(payload.get("tokens_after"))
            if before is not None and after is not None:
                delta = after - before
        if delta is not None:
            recovered_tokens.append(-delta)  # delta âm = co lại = thu hồi dương

        duration_ms = num_or_none(payload.get("duration_ms"))
        if duration_ms is not None:
            durations.append(round(duration_ms / 1000.0, 1))

    return {
        "passes": len(micro_rows),
        "outcomes": outcomes,
        "failed_calls": scan_result["micro_failed"],
        "empty_results": scan_result["micro_empty"],
        "recovered_summaries": scan_result["micro_recovered"],
        "tokens_recovered_total": sum(recovered_tokens) if recovered_tokens else None,
        "tokens_recovered": stats_of(recovered_tokens),
        "duration_s": stats_of(durations),
    }


def build_report(scan_result: dict, since: datetime, until: datetime, paths: list[Path]) -> dict:
    started = [e for e in scan_result["started"] if since <= e["ts"] <= until]
    done = [e for e in scan_result["done"] if since <= e["ts"] <= until + timedelta(minutes=30)]
    pairs, orphans = pair_events(started, done)
    micro_rows = [(ts, p) for ts, p in scan_result["micro_rows"] if ts is None or since <= ts <= until]

    per_session: dict[str, int] = {}
    for event in started:
        per_session[event["session"]] = per_session.get(event["session"], 0) + 1

    micro = summarize_micro(micro_rows, scan_result)
    trigger = stats_of([p["trigger_tokens"] for p in pairs])
    recovered = stats_of([p["tokens_recovered"] for p in pairs])
    duration = stats_of([p["duration_s"] for p in pairs])
    peak_hour = peak_per_hour(pairs, orphans)

    warnings = []
    slow = [p for p in pairs if p["duration_s"] > SLOW_COMPRESSION_SECONDS]
    if slow:
        worst = max(p["duration_s"] for p in slow)
        warnings.append(
            f"{len(slow)} lần nén vượt {SLOW_COMPRESSION_SECONDS:.0f}s (lâu nhất {worst}s)"
        )
    if micro["failed_calls"] or micro["empty_results"]:
        warnings.append(
            f"nén trả góp lỗi: {micro['failed_calls']} lượt gọi hỏng, "
            f"{micro['empty_results']} lượt trả về rỗng"
        )
    if peak_hour > MAX_COMPRESSIONS_PER_HOUR:
        warnings.append(
            f"nén dày: tối đa {peak_hour} lần trong 1 giờ (ngưỡng cảnh báo {MAX_COMPRESSIONS_PER_HOUR})"
        )
    if orphans:
        warnings.append(f"{len(orphans)} lần nén bắt đầu mà chưa thấy dòng done (đang chạy hoặc bị cắt)")
    for problem in scan_result["unreadable"]:
        warnings.append(f"không đọc được log: {problem}")

    return {
        "window": {"since": since.isoformat(timespec="seconds"), "until": until.isoformat(timespec="seconds")},
        "logs": [str(p) for p in paths],
        "batch": {
            "started_total": len(started),
            "paired_total": len(pairs),
            "unpaired_total": len(orphans),
            "per_session": per_session,
            "trigger_tokens": trigger,
            "tokens_recovered": recovered,
            "duration_s": duration,
            "peak_per_hour": peak_hour,
            "events": [
                {**p,
                 "started_at": p["started_at"].isoformat(timespec="seconds"),
                 "done_at": p["done_at"].isoformat(timespec="seconds")}
                for p in pairs
            ],
        },
        "micro": micro,
        "warnings": warnings,
    }


def fmt(value, suffix="") -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.1f}{suffix}"
    if isinstance(value, int):
        return f"{value:,}{suffix}"
    return f"{value}{suffix}"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Bảng canh cột bằng khoảng trắng — không dùng ký tự gạch đứng."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    def line(cells):
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    out = [line(headers), "  ".join("-" * w for w in widths)]
    out.extend(line(r) for r in rows)
    return out


def render(report: dict) -> str:
    batch = report["batch"]
    micro = report["micro"]
    window = report["window"]
    lines = [
        "Báo cáo nén ngữ cảnh Hermes",
        f"Cửa sổ: {window['since'].replace('T', ' ')} -> {window['until'].replace('T', ' ')}",
        f"Nguồn log: {', '.join(Path(p).name for p in report['logs']) or '(không có)'}",
        "",
    ]

    if not batch["started_total"] and not micro["passes"]:
        lines.append("Không có lần nén nào trong cửa sổ này.")
        return "\n".join(lines)

    lines.append("NÉN THEO NGƯỠNG (batch)")
    lines.append("```")
    lines.append(f"Tổng số lần bắt đầu nén : {batch['started_total']}")
    lines.append(f"Ghép đủ started->done   : {batch['paired_total']}")
    lines.append(f"Chưa thấy dòng done     : {batch['unpaired_total']}")
    lines.append(f"Đỉnh trong 1 giờ        : {batch['peak_per_hour']}")
    lines.append("")
    lines.append("Theo session:")
    for session, count in sorted(batch["per_session"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {session}  {count} lần")
    lines.append("```")
    lines.append("")

    if batch["events"]:
        lines.append("CHI TIẾT TỪNG LẦN NÉN")
        lines.append("```")
        rows = []
        for event in batch["events"]:
            rows.append([
                event["started_at"][5:].replace("T", " "),
                event["session"][:22],
                fmt(event["trigger_tokens"]),
                fmt(event["tokens_after"]),
                fmt(event["tokens_recovered"]),
                fmt(event["messages_dropped"]),
                fmt(event["duration_s"], "s"),
                (event["summary_model"] or "-")[:20],
            ])
        lines.extend(table(
            ["Lúc", "Session", "Ngưỡng kích hoạt", "Token sau nén",
             "Token thu hồi", "Msg bỏ", "Thời lượng", "Model tóm tắt"],
            rows,
        ))
        lines.append("```")
        lines.append("")

        lines.append("TỔNG HỢP")
        lines.append("```")
        summary_rows = []
        for label, key, suffix in (
            ("Ngưỡng kích hoạt (token)", "trigger_tokens", ""),
            ("Token thu hồi", "tokens_recovered", ""),
            ("Thời lượng", "duration_s", "s"),
        ):
            stat = batch[key]
            summary_rows.append([
                label, str(stat["count"]),
                fmt(stat["avg"], suffix), fmt(stat["min"], suffix), fmt(stat["max"], suffix),
            ])
        lines.extend(table(["Chỉ số", "Mẫu", "Trung bình", "Nhỏ nhất", "Lớn nhất"], summary_rows))
        total_recovered = sum(
            e["tokens_recovered"] for e in batch["events"] if e["tokens_recovered"] is not None
        )
        lines.append("")
        lines.append(f"Tổng token thu hồi được: {total_recovered:,}")
        lines.append("```")
        lines.append("")

    lines.append("NÉN TRẢ GÓP (micro)")
    lines.append("```")
    if not micro["passes"]:
        lines.append("Không có lượt nén trả góp nào (telemetry chưa xuất hiện trong log).")
    else:
        lines.append(f"Số lượt            : {micro['passes']}")
        for outcome, count in sorted(micro["outcomes"].items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  outcome={outcome}: {count}")
        if micro["tokens_recovered_total"] is not None:
            lines.append(f"Token thu hồi tổng  : {micro['tokens_recovered_total']:,}")
            stat = micro["tokens_recovered"]
            lines.append(
                f"  trung bình/lượt   : {fmt(stat['avg'])}  (min {fmt(stat['min'])}, max {fmt(stat['max'])})"
            )
        if micro["duration_s"]["count"]:
            stat = micro["duration_s"]
            lines.append(
                f"Thời lượng          : tb {fmt(stat['avg'], 's')}, max {fmt(stat['max'], 's')}"
            )
    lines.append(f"Lượt gọi tóm tắt lỗi: {micro['failed_calls']}")
    lines.append(f"Lượt trả về rỗng    : {micro['empty_results']}")
    lines.append(f"Khôi phục summary   : {micro['recovered_summaries']}")
    lines.append("```")

    if report["warnings"]:
        lines.append("")
        lines.append("CẢNH BÁO")
        for warning in report["warnings"]:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def send_to_chat(text: str, space: str, thread: str | None) -> int:
    if not GCHAT_SENDER.is_file():
        print(f"lỗi: không thấy {GCHAT_SENDER}", file=sys.stderr)
        return 1
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
        handle.write(text)
        temp_path = handle.name
    cmd = [sys.executable, str(GCHAT_SENDER), "--space", space, "--text-file", temp_path]
    if thread:
        cmd += ["--thread", thread]
    try:
        return subprocess.run(cmd, check=False).returncode
    finally:
        Path(temp_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Thống kê hiệu quả nén ngữ cảnh của Hermes từ log (chỉ đọc).",
    )
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="đường dẫn agent.log")
    parser.add_argument("--since", help="mốc bắt đầu: ISO-8601 hoặc 'HH:MM'")
    parser.add_argument("--hours", type=float, default=24.0, help="số giờ gần nhất (mặc định 24)")
    parser.add_argument("--send", action="store_true", help="gửi báo cáo qua Google Chat")
    parser.add_argument("--space", default=DEFAULT_SPACE, help="space đích khi --send")
    parser.add_argument("--thread", help="thread đích khi --send")
    parser.add_argument("--json", dest="as_json", action="store_true", help="in JSON thô")
    args = parser.parse_args()

    if args.hours <= 0:
        print("lỗi: --hours phải lớn hơn 0", file=sys.stderr)
        return 2
    if args.send and not args.space:
        print("lỗi: --send cần --space", file=sys.stderr)
        return 2

    try:
        since = resolve_since(args)
    except SystemExit_2 as exc:
        print(f"lỗi: {exc}", file=sys.stderr)
        return 2

    primary = Path(args.log).expanduser()
    paths = log_paths(primary)
    if not paths:
        print(f"lỗi: không đọc được log nào từ {primary}", file=sys.stderr)
        return 2

    report = build_report(scan(paths), since, datetime.now(), paths)
    text = json.dumps(report, ensure_ascii=False, indent=2) if args.as_json else render(report)
    print(text)

    if args.send:
        rc = send_to_chat(render(report), args.space, args.thread)
        if rc != 0:
            print(f"cảnh báo: gửi Google Chat thất bại (mã {rc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
