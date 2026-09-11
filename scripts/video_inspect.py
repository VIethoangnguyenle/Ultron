#!/usr/bin/env python3
"""Phân tích video (clip bug tester gửi): metadata + lọc khung hình khác nhau + tách tiếng.

Vì sao cần: model chính không "xem" được video. Muốn hiểu clip thì:
  1) ffprobe → clip dài bao nhiêu, độ phân giải, có tiếng không
  2) ffmpeg  → lấy mẫu khung hình dày (mặc định ~2 khung/giây)
  3) PIL     → bỏ khung gần giống nhau (ảnh-hash) → giữ lại các MỐC THAY ĐỔI
               + luôn giữ khung cuối (thường là chỗ hiện lỗi) + ghép contact sheet
  4) đưa ẢNH (contact sheet / từng khung) cho vision_analyze đọc → viết kết luận

Vì sao không dùng `select=gt(scene,x)` làm chính: với clip quay màn hình (nền gần
như đứng yên, chỉ đổi chữ/nút) điểm "scene" rất thấp, lọc cảnh-đổi cho ra 0 khung.
Cách ảnh-hash bên dưới ổn định hơn và tự đánh số mốc thời gian.

Usage:
  video_inspect.py <video> [--out DIR] [--max-frames 18] [--rate 2] [--audio] [--json]

Ví dụ:
  video_inspect.py ~/.hermes/cache/videos/xxxx.mp4 --audio
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
FFPROBE = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: Path) -> dict:
    r = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise SystemExit(f"ffprobe lỗi: {r.stderr.strip()[:300]}")
    d = json.loads(r.stdout)
    fmt, streams = d.get("format", {}), d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fr = v.get("avg_frame_rate") or "0/1"
    try:
        num, den = (int(x) for x in fr.split("/"))
        fps = round(num / den, 2) if den else 0
    except Exception:
        fps = 0
    return {
        "duong_dan": str(path),
        "dung_luong_mb": round(int(fmt.get("size") or 0) / 1048576, 2),
        "thoi_luong_giay": round(float(fmt.get("duration") or 0), 2),
        "do_phan_giai": f"{v.get('width','?')}x{v.get('height','?')}",
        "fps": fps,
        "codec_video": v.get("codec_name", "?"),
        "co_tieng": bool(a),
        "codec_audio": (a or {}).get("codec_name"),
    }


def _ahash(path: Path):
    """Chữ ký ảnh: hash 32x32 (độ nhạy cao) + bảng điểm xám 32x32 để đo sai khác thật."""
    from PIL import Image
    im = Image.open(path).convert("L").resize((32, 32))
    try:
        px = list(im.getdata())          # Pillow < 14
    except Exception:
        px = list(im.tobytes())
    avg = sum(px) / len(px)
    bits = 0
    for i, p in enumerate(px):
        if p > avg:
            bits |= 1 << i
    return (bits, px)


def _dist(a, b) -> tuple:
    """(khoảng cách hash, sai khác trung bình mỗi điểm ảnh 0-255)."""
    ha, pa = a
    hb, pb = b
    mad = sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)
    return bin(ha ^ hb).count("1"), mad


def _khac_nhau(a, b) -> bool:
    """Hai khung coi là KHÁC nếu đổi cảnh rõ (hash) hoặc đổi chữ/nút đủ nhiều (sai khác điểm ảnh)."""
    hd, mad = _dist(a, b)
    return hd >= 4 or mad >= 2.5


def sample_and_filter(path: Path, out: Path, rate: float, max_frames: int, duration: float):
    """Lấy mẫu ~rate khung/giây (tối đa 300 khung), bỏ khung trùng, giữ tối đa max_frames."""
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for f in raw.glob("*.jpg"):
        f.unlink()
    run([FFMPEG, "-y", "-v", "error", "-i", str(path), "-vf", f"fps={rate}", "-q:v", "3",
         str(raw / "f_%05d.jpg")])
    files = sorted(raw.glob("f_*.jpg"))
    if not files:
        return [], []
    step = 1.0 / rate
    kept, hashes = [], []
    for i, f in enumerate(files):
        t = i * step
        sig = _ahash(f)
        if kept and not _khac_nhau(sig, hashes[-1]):
            continue
        kept.append((t, f))
        hashes.append(sig)
    # khung cuối thường là chỗ hiện thông báo lỗi — chỉ thêm nếu khác khung vừa giữ
    last = (len(files) * step, files[-1])
    if kept and kept[-1][1] != files[-1] and _khac_nhau(_ahash(files[-1]), hashes[-1]):
        kept.append(last)
    if len(kept) > max_frames:
        # giữ đều max_frames mốc, luôn gồm mốc đầu + cuối
        idx = [round(i * (len(kept) - 1) / (max_frames - 1)) for i in range(max_frames)]
        kept = [kept[i] for i in sorted(set(idx))]
    return kept, files


def make_sheet(kept, out: Path, cols: int = 3):
    if not kept:
        return None
    from PIL import Image, ImageDraw, ImageFont
    fnt = ImageFont.truetype(FONT, 26)
    tile_w = 560
    tiles = []
    for t, f in kept:
        im = Image.open(f).convert("RGB")
        im = im.resize((tile_w, max(1, int(im.height * tile_w / im.width))))
        tiles.append((t, im))
    tile_h = max(im.height for _, im in tiles) + 46
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tile_w * cols, tile_h * rows), (10, 10, 14))
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(tiles):
        x, y = (i % cols) * tile_w, (i // cols) * tile_h
        sheet.paste(im, (x, y + 46))
        d.text((x + 12, y + 8), f"giây {int(t // 60):02d}:{int(t % 60):02d}", font=fnt, fill=(255, 210, 90))
    p = out / "contact_sheet.jpg"
    sheet.save(p, quality=88)
    return str(p)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--out", default=None)
    p.add_argument("--rate", type=float, default=2.0, help="số khung lấy mẫu mỗi giây (mặc định 2)")
    p.add_argument("--max-frames", type=int, default=18, help="số khung khác nhau giữ lại (mặc định 18)")
    p.add_argument("--audio", action="store_true", help="tách luôn track tiếng (clip có thuyết minh)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    vid = Path(a.video).expanduser()
    if not vid.exists():
        print(f"ERROR: không thấy file {vid}", file=sys.stderr)
        return 2
    out = Path(a.out).expanduser() if a.out else Path("/tmp") / f"video_{vid.stem}"
    if a.out is None and out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    meta = probe(vid)
    kept, rawfiles = sample_and_filter(vid, out, a.rate, a.max_frames, meta["thoi_luong_giay"])
    sheet = make_sheet(kept, out)
    frames = [{"giay": round(t, 1), "anh": str(f)} for t, f in kept]

    audio = None
    if a.audio or meta["co_tieng"]:
        wav = out / "audio.wav"
        r = run([FFMPEG, "-y", "-v", "error", "-i", str(vid), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        if r.returncode == 0 and wav.exists():
            audio = str(wav)

    manifest = {**meta, "thu_muc": str(out), "so_khung_lay_mau": len(rawfiles),
                "khung_khac_nhau": frames, "contact_sheet": sheet, "audio": audio}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    print("=== THÔNG TIN CLIP ===")
    print(f"  file       : {meta['duong_dan']}")
    print(f"  thời lượng : {meta['thoi_luong_giay']}s | {meta['do_phan_giai']} | {meta['fps']} fps | {meta['codec_video']} | {meta['dung_luong_mb']} MB")
    print(f"  tiếng      : {'có (' + str(meta['codec_audio']) + ')' if meta['co_tieng'] else 'KHÔNG có tiếng'}")
    print(f"=== MỐC THAY ĐỔI ({len(rawfiles)} khung lấy mẫu → {len(frames)} khung khác nhau) ===")
    for fr in frames:
        print(f"  giây {fr['giay']:>7} : {fr['anh']}")
    if sheet:
        print(f"  CONTACT SHEET (đọc 1 ảnh là hiểu cả clip): {sheet}")
    if audio:
        print(f"  audio tách ra: {audio}")
    print("=== BƯỚC TIẾP ===")
    print(f'  vision_analyze(image_url="{sheet}", question="<cần tìm gì>")')
    print(f"  # nếu cần soi kỹ 1 mốc: vision_analyze(image_url=<khung ở trên>, question=..., region=[x1,y1,x2,y2])")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
