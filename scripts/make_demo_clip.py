#!/usr/bin/env python3
"""Dựng clip minh hoạ (demo) từ vài dòng chữ + giọng đọc — chạy local.

Vì sao có script này: cần clip hướng dẫn tester / minh hoạ luồng thì phải vẽ "màn hình giả"
bằng chữ rồi ghép thành video. ffmpeg bản static KHÔNG có filter drawtext → vẽ chữ bằng PIL,
phần còn lại giao cho ffmpeg (encode, concat, nhép tiếng, chuẩn hoá độ to).

Dùng:
  python3 make_demo_clip.py --text-file slides.txt --out /tmp/demo.mp4 \
      [--narration "lời đọc"] [--narration-file loi.txt] [--narration-speed 1.0] \
      [--seconds 6] [--voice vi-VN-NamMinhNeural] [--silent]

slides.txt: mỗi slide là 1 khối, các khối cách nhau bằng dòng `---`.
  Dòng đầu của khối = tiêu đề (chữ lớn), các dòng sau = nội dung (chữ nhỏ).

  BƯỚC 1: Mở màn ĐĂNG NHẬP
  user: ngocmai87
  -> Đăng nhập thành công
  ---
  BƯỚC 2: Chuyển tiền nội bộ
  Nhập số tiền 50.000.000
  ---
  BƯỚC 3: Bấm xác nhận
  !! Lỗi hệ thống — giao dịch không thực hiện được

Kết quả: 1 file .mp4 (h264 + aac, chuẩn hoá độ to -16 LUFS) + in đường dẫn ra stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
BG = (11, 37, 69)
FG = (255, 255, 255)
ACCENT = (255, 196, 0)
HERMES_VENV_PY = Path.home() / ".hermes/hermes-agent/venv/bin/python"


def _sh(cmd: list[str], **kw) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write("\n".join(cmd) + "\n" + (r.stderr or "")[-1500:] + "\n")
        raise SystemExit(f"lệnh ffmpeg lỗi (exit {r.returncode})")


def _font(bold: bool, size: int):
    from PIL import ImageFont
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_slide(lines: list[str], out_png: Path, w: int = 1280, h: int = 720) -> None:
    """Vẽ 1 slide: dòng đầu là tiêu đề, các dòng sau là nội dung; tự xuống dòng."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    pad, y = 70, 120

    d.rectangle([0, 0, w, 8], fill=ACCENT)
    if not lines:
        img.save(out_png)
        return

    f_head, f_body = _font(True, 48), _font(False, 32)
    for i, ln in enumerate(_wrap(d, lines[0], f_head, w - 2 * pad)):
        d.text((pad, y), ln, font=f_head, fill=ACCENT if i == 0 else FG)
        y += 62
    y += 30
    body = " ".join(lines[1:]).strip()
    if body:
        for ln in _wrap(d, body, f_body, w - 2 * pad):
            d.text((pad, y), ln, font=f_body, fill=FG)
            y += 44
    d.text((pad, h - 70), "Ultron · demo", font=_font(False, 22), fill=(150, 165, 190))
    img.save(out_png)


def _sentences(text: str) -> list[str]:
    """Tách lời đọc thành từng câu để (a) đọc có nhịp nghỉ, (b) bớt lỗi khi câu quá dài."""
    import re
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    out = [p.strip() for p in parts if p.strip()]
    return out or [text.strip()]


def _tts_open(text: str, out_mp3: Path, voice: str, speed: float, tries: int = 3) -> bool:
    """Gọi edge-tts 1 câu. Trả True/False — edge hay chập chờn nên phải thử lại."""
    import edge_tts

    rate = f"{int(round((speed - 1) * 100)):+d}%"
    for i in range(tries):
        try:
            asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(out_mp3)))
            if out_mp3.exists() and out_mp3.stat().st_size > 1000:
                return True
        except Exception as e:  # edge đóng socket giữa chừng là chuyện thường
            if i == tries - 1:
                sys.stderr.write(f"[tts] {voice}: {type(e).__name__} ({text[:40]}…)\n")
        time.sleep(1.2 * (i + 1))
    return False


def _tts(text: str, out_mp3: Path, voice: str, speed: float) -> None:
    """Đọc lời thuyết minh: tách câu → đọc từng câu (thử lại + giọng dự phòng) → ghép lại."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        if HERMES_VENV_PY.exists():
            os.execv(str(HERMES_VENV_PY), [str(HERMES_VENV_PY), __file__, *sys.argv[1:]])
        raise SystemExit("thiếu edge-tts — cài: uv pip install edge-tts")

    work = out_mp3.parent / "tts_parts"
    work.mkdir(exist_ok=True)
    gap = work / "gap.mp3"
    _sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", "0.30", "-c:a", "libmp3lame", str(gap)])

    # Chọn giọng 1 lần cho cả clip: edge hay chặn 1 giọng nào đó theo từng lúc, nếu đổi giữa
    # chừng thì clip bị lẫn giọng nam/nữ nghe rất kỳ. → thử giọng chính trước, hỏng thì đổi hẳn.
    fallback = "vi-VN-HoaiMyNeural"
    probe = work / "probe.mp3"
    if voice != fallback and not _tts_open("Xin chào.", probe, voice, speed, tries=2):
        sys.stderr.write(f"[tts] giọng {voice} đang bị chặn → dùng {fallback} cho cả clip\n")
        voice = fallback

    pieces: list[Path] = []
    for i, sent in enumerate(_sentences(text), 1):
        part = work / f"s{i:02d}.mp3"
        ok = _tts_open(sent, part, voice, speed) or _tts_open(sent, part, fallback, speed, tries=3)
        if not ok:
            sys.stderr.write(f"[tts] bỏ câu không đọc được: {sent[:60]}…\n")
            continue
        pieces.append(part)

    if not pieces:
        raise SystemExit("❌ không đọc được câu nào — edge-tts có thể đang bị chặn, thử lại sau")

    listing = work / "tts_list.txt"
    lines = []
    for idx, p in enumerate(pieces):
        if idx:
            lines.append(f"file '{gap}'\n")
        lines.append(f"file '{p}'\n")
    listing.write_text("".join(lines), encoding="utf-8")
    _sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(out_mp3)])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text-file", required=True, help="file slide (khối cách nhau bằng '---')")
    p.add_argument("--out", required=True, help="file .mp4 đầu ra")
    p.add_argument("--narration", default="", help="lời đọc (bỏ trống + không có file → clip im lặng)")
    p.add_argument("--narration-file", default="", help="file chứa lời đọc")
    p.add_argument("--narration-speed", type=float, default=1.0, help="1.0 = bình thường, 0.9 = chậm hơn")
    p.add_argument("--seconds", type=float, default=6.0, help="số giây mỗi slide (khi không có lời đọc)")
    p.add_argument("--voice", default="vi-VN-NamMinhNeural", help="giọng edge-tts (mặc định nam Việt Nam)")
    p.add_argument("--silent", action="store_true", help="cố tình làm clip không tiếng")
    p.add_argument("--keep", action="store_true", help="giữ thư mục làm việc để soi lại")
    a = p.parse_args()

    raw = Path(a.text_file).read_text(encoding="utf-8")
    slides = [[l.strip() for l in blk.splitlines() if l.strip()] for blk in raw.split("\n---")]
    slides = [s for s in slides if s]
    if not slides:
        return print("❌ file slide rỗng") or 1

    narration = a.narration
    if a.narration_file:
        narration = Path(a.narration_file).read_text(encoding="utf-8").strip()

    work = Path(tempfile.mkdtemp(prefix="demo_clip_"))
    try:
        pngs = []
        for i, sl in enumerate(slides, 1):
            png = work / f"slide{i}.png"
            render_slide(sl, png)
            pngs.append(png)

        audio: Path | None = None
        if narration and not a.silent:
            audio = work / "narration.mp3"
            _tts(narration, audio, a.voice, a.narration_speed)
            raw_dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(audio)], capture_output=True, text=True).stdout.strip()
            dur = float(raw_dur) if raw_dur else 0.0
            per = (dur + 0.8) / len(slides)  # chia đều theo độ dài lời đọc + 0.8s lấy hơi
        else:
            per = a.seconds

        parts = []
        for i, png in enumerate(pngs, 1):
            part = work / f"pan{i}.mp4"
            _sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
                 "-t", f"{per:.2f}", "-r", "15", "-pix_fmt", "yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", str(part)])
            parts.append(part)

        listing = work / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        silent = work / "silent.mp4"
        _sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(silent)])

        out = Path(a.out)
        if audio:
            _sh(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                 "-af", "loudnorm=I=-16:TP=-1.5", "-shortest", str(out)])
        else:
            shutil.copy(silent, out)

        meta = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
             "-of", "default=nw=1", str(out)], capture_output=True, text=True).stdout.strip()
        print(f"✅ clip: {out}\n   {len(slides)} slide × ~{per:.1f}s | tiếng: {'có' if audio else 'không'}\n   {meta}")
        return 0
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"   (thư mục làm việc giữ lại: {work})")


if __name__ == "__main__":
    raise SystemExit(main())
