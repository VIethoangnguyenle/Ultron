#!/usr/bin/env python3
"""Bóc lời thoại (transcript) từ audio/video — chạy LOCAL, không gửi ra cloud.

Vì sao local: clip tester gửi có thể chứa dữ liệu khách hàng/số tài khoản → không
đẩy lên Groq/OpenAI. Model faster-whisper nằm trong venv riêng, tải 1 lần rồi dùng offline.

Script tự nhảy sang python của venv whisper nếu đang chạy bằng python khác:
  python3 audio_transcribe.py <file.wav|file.mp4|file.mp3> [--model small] [--lang vi]

Kết quả: in transcript + ghi cạnh file gốc: <tên>.transcript.txt và .transcript.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

VENV_PY = Path.home() / ".hermes/venvs/whisper/bin/python"
VENV_PY_FALLBACK = Path.home() / ".hermes/venvs/whisper/Scripts/python.exe"  # Windows, phòng hờ


def _reexec_in_venv() -> None:
    py = VENV_PY if VENV_PY.exists() else VENV_PY_FALLBACK
    if not py.exists() or Path(sys.executable).resolve() == py.resolve():
        return
    os.execv(str(py), [str(py), str(Path(__file__).resolve()), *sys.argv[1:]])


try:
    import faster_whisper  # noqa: F401
except ImportError:
    _reexec_in_venv()
    raise SystemExit(
        "Chưa có faster-whisper. Tạo venv:\n"
        "  uv venv ~/.hermes/venvs/whisper --python 3.11\n"
        "  uv pip install --python ~/.hermes/venvs/whisper/bin/python faster-whisper"
    )

import argparse  # noqa: E402

from faster_whisper import WhisperModel  # noqa: E402


def extract_audio(src: Path, dst: Path) -> Path:
    """Nếu đầu vào là video → tách track tiếng bằng ffmpeg (16kHz mono, chuẩn cho STT)."""
    if src.suffix.lower() in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
        return src
    ffmpeg = os.environ.get("FFMPEG_BIN", str(Path.home() / ".local/bin/ffmpeg"))
    if not Path(ffmpeg).exists():
        import shutil
        ffmpeg = shutil.which("ffmpeg") or ffmpeg
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-vn",
                        "-ac", "1", "-ar", "16000", str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg lỗi khi tách tiếng: {r.stderr.strip()[:300]}")
    return dst


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("media")
    p.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3 (mặc định small)")
    p.add_argument("--lang", default="vi", help="mã ngôn ngữ, mặc định vi; 'auto' để tự đoán")
    p.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 4))
    p.add_argument("--json", action="store_true", help="in JSON thay vì text")
    a = p.parse_args()

    src = Path(a.media).expanduser()
    if not src.exists():
        print(f"ERROR: không thấy file {src}", file=sys.stderr)
        return 2

    work = Path("/tmp") / f"stt_{src.stem}.wav"
    audio = extract_audio(src, work)

    model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=a.threads)
    segs, info = model.transcribe(str(audio), language=None if a.lang == "auto" else a.lang,
                                  vad_filter=True, beam_size=5)
    rows = [{"tu_giay": round(s.start, 2), "den_giay": round(s.end, 2), "loi": s.text.strip()}
            for s in segs]
    text = " ".join(r["loi"] for r in rows).strip()
    out = {"file": str(src), "model": a.model, "ngon_ngu_doan_duoc": info.language,
           "do_tin_cay": round(info.language_probability, 3), "so_doan": len(rows),
           "transcript": text, "cac_doan": rows}
    Path(f"{src}.transcript.txt").write_text(text + "\n", encoding="utf-8")
    Path(f"{src}.transcript.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print(f"=== TRANSCRIPT ({len(rows)} đoạn, ngôn ngữ: {out['ngon_ngu_doan_duoc']}) ===")
    for r in rows:
        print(f"  [{int(r['tu_giay']//60):02d}:{int(r['tu_giay']%60):02d}] {r['loi']}")
    print(f"=== LỜI THOẠI ĐẦY ĐỦ ===\n{text}")
    print(f"(đã lưu: {src}.transcript.txt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
