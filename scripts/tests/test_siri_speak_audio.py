#!/usr/bin/env python3
"""Chứng minh nguồn desktop PHÁT RA TIẾNG THẬT (và nguồn phone thì im) — đo bằng RMS.

    /home/zane/.hermes/hermes-agent/venv/bin/python tests/test_siri_speak_audio.py

Gọi thẳng `maybe_speak()` của siri_speak.py (edge-tts + ffmpeg + paplay THẬT, không giả),
trong lúc đó thu song song hai đường:
  - monitor của sink  → chứng minh audio tới được thiết bị ra của PulseAudio;
  - mic (nếu có)      → chứng minh có tiếng THẬT ngoài không khí.
So RMS lúc im (trước khi phát) với RMS lúc phát; không có thiết bị thu thì nói thẳng là
không kiểm chứng được, KHÔNG suy đoán.
"""
from __future__ import annotations

import array
import importlib.util
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "siri_speak.py"
SENTENCE = "Xin chào anh Hoàng, đây là bài kiểm tra âm thanh của cổng nói."
RATE = 16000
BASELINE_S = 2.0          # thu im lặng trước khi phát, làm mốc so sánh
RECORD_S = 16.0


def load_module():
    spec = importlib.util.spec_from_file_location("siri_speak_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pulse_env() -> dict:
    env = dict(os.environ)
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    env["XDG_RUNTIME_DIR"] = runtime
    env.setdefault("PULSE_SERVER", f"unix:{runtime}/pulse/native")
    return env


def devices() -> tuple[str, str]:
    """(monitor của sink mặc định, source mic đầu tiên) — "" nếu không có."""
    env = pulse_env()
    out = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True,
                         env=env, timeout=10).stdout
    monitor, mic = "", ""
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1]
        if name.endswith(".monitor") and not monitor:
            monitor = name
        elif not name.endswith(".monitor") and not mic:
            mic = name
    return monitor, mic


def start_rec(device: str, path: Path):
    return subprocess.Popen(
        ["parec", "-d", device, "--rate", str(RATE), "--channels", "1", "--format", "s16le"],
        stdout=open(path, "wb"), stderr=subprocess.DEVNULL, env=pulse_env())


def rms(path: Path, start_s: float, end_s: float) -> float:
    raw = path.read_bytes()
    lo, hi = int(start_s * RATE) * 2, int(end_s * RATE) * 2
    chunk = raw[lo:hi]
    chunk = chunk[:len(chunk) - len(chunk) % 2]
    if not chunk:
        return 0.0
    samples = array.array("h")
    samples.frombytes(chunk)
    return math.sqrt(sum(float(s) * s for s in samples) / len(samples))


def run_case(mod, source: str, label: str) -> dict:
    monitor, mic = devices()
    if not monitor:
        print("KHÔNG có source nào để thu — không kiểm chứng được bằng âm thanh.")
        return {}
    tmp = Path(tempfile.mkdtemp(prefix="siri-audio-"))
    mon_raw, mic_raw = tmp / "monitor.raw", tmp / "mic.raw"
    recs = [start_rec(monitor, mon_raw)]
    if mic:
        recs.append(start_rec(mic, mic_raw))
    time.sleep(BASELINE_S)
    t0 = time.time()
    mod.maybe_speak(source, SENTENCE)
    time.sleep(RECORD_S - BASELINE_S)
    for proc in recs:
        proc.terminate()
        proc.wait(timeout=5)
    spoke_at = BASELINE_S + 0.3
    result = {"label": label, "monitor_dev": monitor, "mic_dev": mic,
              "mon_quiet": rms(mon_raw, 0.2, BASELINE_S - 0.2),
              "mon_loud": rms(mon_raw, spoke_at, RECORD_S - 0.5),
              "mic_quiet": rms(mic_raw, 0.2, BASELINE_S - 0.2) if mic else None,
              "mic_loud": rms(mic_raw, spoke_at, RECORD_S - 0.5) if mic else None,
              "dir": str(tmp), "elapsed": round(time.time() - t0, 1)}
    return result


def show(r: dict) -> None:
    if not r:
        return
    print(f"\n[{r['label']}]  (thu {RECORD_S:.0f}s, phát ở giây {BASELINE_S:.0f})")
    print(f"  monitor {r['monitor_dev']}")
    print(f"    RMS im lặng = {r['mon_quiet']:.1f}   RMS lúc phát = {r['mon_loud']:.1f}")
    if r["mic_dev"]:
        print(f"  mic     {r['mic_dev']}")
        print(f"    RMS im lặng = {r['mic_quiet']:.1f}   RMS lúc phát = {r['mic_loud']:.1f}")
    else:
        print("  mic: máy không có source thu ⇒ không kiểm chứng được tiếng ngoài không khí")
    print(f"  file thu: {r['dir']}")


def main() -> int:
    mod = load_module()
    desktop = run_case(mod, mod.SOURCE_DESKTOP, "source=desktop — PHẢI có tiếng")
    show(desktop)
    phone = run_case(mod, mod.SOURCE_PHONE, "source=phone — PHẢI im")
    show(phone)
    if not desktop or not phone:
        return 2
    ok_desktop = desktop["mon_loud"] > max(5.0, desktop["mon_quiet"] * 3 + 1)
    ok_phone = phone["mon_loud"] <= max(5.0, phone["mon_quiet"] * 3 + 1)
    print(f"\n  {'PASS' if ok_desktop else 'FAIL'}  desktop: monitor có tín hiệu (RMS "
          f"{desktop['mon_loud']:.1f} > im lặng {desktop['mon_quiet']:.1f})")
    print(f"  {'PASS' if ok_phone else 'FAIL'}  phone: monitor vẫn im (RMS {phone['mon_loud']:.1f})")
    return 0 if (ok_desktop and ok_phone) else 1


if __name__ == "__main__":
    raise SystemExit(main())
