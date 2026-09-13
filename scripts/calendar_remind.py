#!/usr/bin/env python3
"""Quét lịch Hoàng mỗi 2 phút, tới mốc thì nhắc họp: DM Google Chat + đọc to trên máy.

Thuần script, 0 token. Chỉ nhắc HỌP NỘI BỘ / REVIEW TÀI LIỆU DỰ ÁN — lịch cá nhân,
sự kiện cả ngày, sự kiện đã huỷ hay không có ai tham dự đều bỏ qua, vì nhắc lung tung
vài hôm là anh tắt luôn cái nhắc.

    calendar_remind.py              # cron gọi cái này
    calendar_remind.py --dry-run    # in ra việc sẽ nhắc, KHÔNG gửi, KHÔNG phát tiếng
    calendar_remind.py --test-voice # phát thử một câu để kiểm loa (gõ tay thôi)
    calendar_remind.py --dry-run --date 2026-09-15   # coi ngày đó là "hôm nay"

Cấu hình: state/calendar_remind.json (tự tạo mặc định lần đầu chạy).
Chống trùng: state/calendar_seen.json, khoá "<event_id>:<mốc>" — mỗi mốc chỉ nhắc 1 lần.
Token: google_calendar_token.json (xin bằng gcal_auth.py), KHÔNG dùng chung token Gmail.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

HERMES = Path.home() / ".hermes"
SCRIPT_DIR = Path(__file__).resolve().parent
TOKEN = HERMES / "google_calendar_token.json"
CONFIG = HERMES / "state" / "calendar_remind.json"
SEEN = HERMES / "state" / "calendar_seen.json"
LOG = HERMES / "logs" / "calendar_remind.log"
SEND = SCRIPT_DIR / "gchat_send_text.py"
EDGE_TTS = HERMES / "hermes-agent" / "venv" / "bin" / "edge-tts"
VOICE_NAME = "vi-VN-NamMinhNeural"
# edge-tts xuất mp3, mà paplay/aplay chỉ nuốt được wav — đó đúng là lý do
# "Failed to open audio file" trong log cũ. Nên phải đổi định dạng, hoặc đi đường
# gstreamer. Giữ đường dẫn tuyệt đối vì cron có PATH rất nghèo.
XDG_RUNTIME = "/run/user/1001"
TMPDIR = Path(tempfile.gettempdir())
VOICE_MP3 = TMPDIR / "hermes_calendar_voice.mp3"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
CATCHUP_MIN = 5          # mốc trễ quá ngần này thì thôi, khỏi nhắc muộn
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

DEFAULT_CONFIG = {
    "enabled": True,
    "lead_minutes": [10, 0],
    "voice": True,
    "quiet_hours": ["21:00", "07:00"],
    "space": "spaces/0dniIqAAAAE",
    "only_internal": True,
    "keywords": ["review", "tài liệu", "tai lieu", "document", "họp", "hop", "meeting",
                 "dự án", "du an", "sme", "vbsme", "nghiệp vụ", "nghiep vu"],
    "internal_domain": "vnpay.vn",
}


# --- hạ tầng nhỏ ---------------------------------------------------------------

def _tool(path: str) -> str:
    """Đường dẫn nếu chạy được, không thì mò trong PATH, không thấy nữa thì chuỗi rỗng."""
    if os.access(path, os.X_OK):
        return path
    return shutil.which(Path(path).name) or ""


FFMPEG = _tool(str(Path.home() / ".local" / "bin" / "ffmpeg"))
GST_PLAY = _tool("/usr/bin/gst-play-1.0")
PAPLAY = _tool("/usr/bin/paplay")
APLAY = _tool("/usr/bin/aplay")


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {msg}\n")


def load_config() -> dict:
    """Đọc config; thiếu file thì tạo bản mặc định, thiếu khoá thì bù khoá."""
    if not CONFIG.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_CONFIG)
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **cfg}


def load_seen() -> dict:
    if not SEEN.exists():
        return {}
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(seen: dict, now: dt.datetime) -> None:
    """Ghi lại, bỏ khoá của sự kiện đã qua hơn 1 ngày để file khỏi phình."""
    cut = (now - dt.timedelta(days=1)).isoformat()
    kept = {k: v for k, v in seen.items() if str(v) >= cut}
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")


def in_quiet_hours(now: dt.datetime, window: list) -> bool:
    """quiet_hours ["21:00","07:00"] là khoảng vắt qua nửa đêm."""
    if not window or len(window) != 2:
        return False
    try:
        start = dt.time.fromisoformat(window[0])
        end = dt.time.fromisoformat(window[1])
    except ValueError:
        return False
    cur = now.time()
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end


# --- lấy & lọc sự kiện ---------------------------------------------------------

def fetch_events(creds, now: dt.datetime) -> list:
    """Sự kiện trong [00:00 hôm nay, 00:00 mai) theo giờ Việt Nam."""
    from googleapiclient.discovery import build

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + dt.timedelta(days=1)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return svc.events().list(
        calendarId="primary", timeMin=day_start.isoformat(), timeMax=day_end.isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=100,
    ).execute().get("items", [])


def is_internal(ev: dict, domain: str) -> bool:
    suffix = "@" + domain.lstrip("@").lower()
    people = [ev.get("organizer", {}).get("email", "")]
    people += [at.get("email", "") for at in ev.get("attendees", []) or []]
    return any((p or "").strip().lower().endswith(suffix) for p in people)


def wanted(ev: dict, cfg: dict) -> bool:
    """Chỉ giữ họp nội bộ / review tài liệu dự án."""
    if ev.get("status") == "cancelled":
        return False
    if not ev.get("start", {}).get("dateTime"):
        return False
    if ev.get("visibility") == "private":
        return False
    if not (ev.get("attendees") or []):
        return False
    blob = f"{ev.get('summary', '')} {ev.get('description', '')}".lower()
    if not any(k.lower() in blob for k in cfg["keywords"]):
        return False
    if not cfg.get("only_internal"):
        return True
    return is_internal(ev, cfg["internal_domain"])


def due_marks(ev: dict, cfg: dict, now: dt.datetime, seen: dict) -> list:
    """Các mốc đã tới giờ nhắc mà chưa nhắc: [(lead, thời điểm bắt đầu)]."""
    start = dt.datetime.fromisoformat(ev["start"]["dateTime"]).astimezone(TZ)
    out = []
    for lead in cfg["lead_minutes"]:
        key = f"{ev['id']}:{lead}"
        if key in seen:
            continue
        mark = start - dt.timedelta(minutes=int(lead))
        late = (now - mark).total_seconds() / 60.0
        if 0 <= late <= CATCHUP_MIN:
            out.append((int(lead), start))
    return out


def all_marks(ev: dict, cfg: dict) -> list:
    """Mọi mốc nhắc của sự kiện, không xét đã tới giờ hay chưa — dành cho --date."""
    start = dt.datetime.fromisoformat(ev["start"]["dateTime"]).astimezone(TZ)
    return [(int(lead), start) for lead in cfg["lead_minutes"]]


# --- soạn tin & gửi ------------------------------------------------------------

def where(ev: dict) -> str:
    link = ev.get("hangoutLink") or ""
    loc = (ev.get("location") or "").strip()
    return link or loc


def chat_text(ev: dict, lead: int, start: dt.datetime) -> str:
    title = ev.get("summary") or "(không tên)"
    head = f"⏰ {lead} phút nữa họp" if lead > 0 else "⏰ Tới giờ họp"
    place = where(ev)
    tail = f" ({place})" if place else ""
    return f"{head}: {title} — {start.strftime('%H:%M')}{tail}"


def voice_text(ev: dict, lead: int, start: dt.datetime) -> str:
    title = (ev.get("summary") or "cuộc họp")[:60]
    if lead > 0:
        return f"Anh ơi, {lead} phút nữa họp {title}, lúc {start.strftime('%H')} giờ {start.strftime('%M')}."
    return f"Anh ơi, tới giờ họp {title} rồi."


def send_chat(space: str, text: str) -> bool:
    r = subprocess.run([sys.executable, str(SEND), "--space", space, "--text", text],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log(f"LỖI gửi Chat: exit={r.returncode} {r.stderr.strip()[:160]}")
        return False
    return True


def audio_env() -> dict:
    """Thiếu XDG_RUNTIME_DIR là không công cụ nào tìm ra socket PulseAudio → câm tịt."""
    return {**os.environ, "XDG_RUNTIME_DIR": XDG_RUNTIME}


def _run(cmd: list, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          timeout=timeout, env=audio_env(), stdin=subprocess.DEVNULL)


def _tail(out: str) -> str:
    return " ".join((out or "").split())[:140] or "(không có thông báo lỗi)"


def _to_wav(src: Path) -> Path:
    """mp3 → wav trong /tmp. Người gọi có trách nhiệm xoá. Hỏng thì ném lỗi."""
    if not FFMPEG:
        raise RuntimeError("không có ffmpeg để đổi mp3 sang wav")
    fd, name = tempfile.mkstemp(prefix="hermes_voice_", suffix=".wav", dir=str(TMPDIR))
    os.close(fd)
    conv = _run([FFMPEG, "-y", "-loglevel", "error", "-i", src, name], 60)
    if conv.returncode == 0:
        return Path(name)
    Path(name).unlink(missing_ok=True)
    raise RuntimeError(f"ffmpeg đổi mp3→wav lỗi: {_tail(conv.stderr)}")


def _play_wav_player(player: str, label: str, src: Path) -> tuple[bool, str]:
    """paplay/aplay: chỉ phát wav — nguồn mp3 thì đổi trước, phát xong xoá file tạm."""
    if not player:
        return False, f"không có {label}"
    wav = src if src.suffix.lower() == ".wav" else _to_wav(src)
    try:
        play = _run([player, wav], 120)
        if play.returncode != 0:
            return False, f"exit={play.returncode} {_tail(play.stderr)}"
        return True, ""
    finally:
        if wav != src:
            wav.unlink(missing_ok=True)


def _play_gst(src: Path) -> tuple[bool, str]:
    """gst-play đọc thẳng mp3, khỏi qua bước đổi định dạng."""
    if not GST_PLAY:
        return False, "không có gst-play-1.0"
    play = _run([GST_PLAY, "--quiet", src], 120)
    if play.returncode != 0:
        return False, f"exit={play.returncode} {_tail(play.stderr)}"
    return True, ""


PLAYERS = [
    ("ffmpeg+paplay", lambda src: _play_wav_player(PAPLAY, "paplay", src)),
    ("gst-play-1.0", _play_gst),
    ("ffmpeg+aplay", lambda src: _play_wav_player(APLAY, "aplay", src)),
]


def _safe_play(fn, src: Path) -> tuple[bool, str]:
    try:
        return fn(src)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def play_audio(src: Path) -> tuple[str | None, list[str]]:
    """Thử lần lượt, dừng ở cách đầu tiên kêu được.

    Trả (tên cách đã dùng | None, danh sách lý do hỏng của các cách đã thử).
    """
    fails = []
    for label, fn in PLAYERS:
        ok, reason = _safe_play(fn, src)
        if ok:
            return label, fails
        fails.append(f"{label}: {reason}")
    return None, fails


def synth(text: str) -> Path:
    """edge-tts → mp3 ở một đường dẫn cố định: giữ lại được để còn chẩn đoán khi câm,
    mà cũng không đẻ thêm rác trong /tmp vì lần chạy sau ghi đè."""
    if not EDGE_TTS.exists():
        raise RuntimeError(f"không thấy edge-tts: {EDGE_TTS}")
    gen = subprocess.run([str(EDGE_TTS), "--voice", VOICE_NAME, "--text", text,
                          "--write-media", str(VOICE_MP3)],
                         capture_output=True, text=True, timeout=60)
    if gen.returncode != 0 or not VOICE_MP3.exists():
        raise RuntimeError(f"edge-tts exit={gen.returncode} {_tail(gen.stderr)}")
    return VOICE_MP3


def speak(text: str) -> tuple[str | None, Path | None, list[str]]:
    """Đọc to. Mọi lỗi âm thanh đều nuốt lại thành 1 dòng log — phần gửi Chat vẫn chạy tiếp."""
    try:
        mp3 = synth(text)
    except Exception as exc:
        log(f"LỖI tạo tiếng: {type(exc).__name__}: {exc}")
        return None, None, [f"edge-tts: {exc}"]
    tool, fails = play_audio(mp3)
    if tool:
        log(f"đã phát qua {tool} ({mp3})")
        return tool, mp3, fails
    log(f"KHÔNG phát được tiếng ({mp3}); " + " | ".join(fails))
    return None, mp3, fails


# --- luồng chính ---------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Nhắc họp từ Google Calendar")
    p.add_argument("--dry-run", action="store_true", help="in ra, không gửi, không phát tiếng")
    p.add_argument("--test-voice", action="store_true", help="phát thử một câu kiểm loa")
    p.add_argument("--date", metavar="YYYY-MM-DD",
                   help="coi ngày này là 'hôm nay' (giờ VN) để soi mọi mốc nhắc; chỉ dùng kèm --dry-run")
    a = p.parse_args()

    cfg = load_config()

    if a.test_voice:
        line = "Anh ơi, đây là câu thử loa của Hermes. Nghe rõ không ạ?"
        print(f"phát thử: {line}")
        tool, mp3, fails = speak(line)
        if tool:
            print(f"đã phát qua {tool} ({mp3})")
            return 0
        print("KHÔNG phát được tiếng, từng cách hỏng như sau:")
        for reason in fails:
            print(f"  - {reason}")
        print("chi tiết trong logs/calendar_remind.log")
        return 1

    if a.date and not a.dry_run:
        print("--date chỉ dùng kèm --dry-run (tránh gửi tin nhầm cho một ngày khác)")
        return 2

    if not cfg.get("enabled") and not a.date:
        return 0

    if not TOKEN.exists():
        msg = "chưa cấp quyền Calendar — chạy scripts/gcal_auth.py để cấp (bỏ qua lần chạy này)"
        print(msg)
        log(msg)
        return 0

    sys.path.insert(0, str(SCRIPT_DIR))
    import gcal_auth  # noqa: E402

    try:
        creds = gcal_auth.load_creds()
    except Exception as exc:
        log(f"token Calendar không dùng được: {type(exc).__name__}: {exc}")
        print("token Calendar không dùng được — chạy lại scripts/gcal_auth.py")
        return 0
    if not creds or not creds.valid:
        log("token Calendar hết hạn, không làm mới được")
        print("token Calendar hết hạn — chạy lại scripts/gcal_auth.py")
        return 0

    now = dt.datetime.now(TZ)
    if a.date:
        try:
            now = dt.datetime.combine(dt.date.fromisoformat(a.date), dt.time(0, 0), TZ)
        except ValueError:
            print(f"--date không hợp lệ: {a.date!r} (cần YYYY-MM-DD)")
            return 2
        print(f"[dry-run] coi hôm nay là {now:%Y-%m-%d} (giờ VN) — liệt kê MỌI mốc của ngày đó")

    try:
        events = fetch_events(creds, now)
    except Exception as exc:
        log(f"LỖI đọc lịch: {type(exc).__name__}: {exc}")
        print(f"lỗi đọc lịch: {exc}")
        return 0

    seen = load_seen()
    quiet = in_quiet_hours(now, cfg.get("quiet_hours"))
    jobs = []
    for ev in events:
        if not wanted(ev, cfg):
            continue
        marks = all_marks(ev, cfg) if a.date else due_marks(ev, cfg, now, seen)
        jobs += [(ev, lead, start) for lead, start in marks]

    if not jobs:
        if a.dry_run:
            print(f"{len(events)} sự kiện trong ngày, không có mốc nào tới giờ nhắc"
                  f"{' (đang trong giờ yên lặng)' if quiet else ''}")
        return 0

    for ev, lead, start in jobs:
        text = chat_text(ev, lead, start)
        mark = start - dt.timedelta(minutes=lead)
        if a.dry_run:
            hush = in_quiet_hours(mark, cfg.get("quiet_hours")) if a.date else quiet
            spoken = "không (giờ yên lặng)" if hush else ("có" if cfg.get("voice") else "tắt")
            print(f"[dry-run] mốc {lead}p | nhắc lúc {mark.strftime('%H:%M')} "
                  f"| họp {start.strftime('%H:%M')} | {ev.get('summary')}")
            print(f"          chat: {text}")
            print(f"          đọc to: {spoken} | {voice_text(ev, lead, start)}")
            continue
        send_chat(cfg["space"], text)
        if cfg.get("voice") and not quiet:
            speak(voice_text(ev, lead, start))
        seen[f"{ev['id']}:{lead}"] = start.isoformat()

    if a.dry_run:
        print(f"[dry-run] tổng {len(jobs)} nhắc — chưa gửi gì, chưa ghi state")
        return 0

    save_seen(seen, now)
    log(f"nhắc {len(jobs)} mốc: " + "; ".join(f"{e.get('summary')}({l}p)" for e, l, _ in jobs))
    print(f"đã nhắc {len(jobs)} mốc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
