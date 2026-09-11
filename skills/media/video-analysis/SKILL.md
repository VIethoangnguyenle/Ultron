---
name: video-analysis
description: Use when someone sends a video to analyze.
---

# Phân tích video người dùng gửi

## Khi nào dùng
- Tester/dev gửi clip quay màn hình (mp4/mov/mkv/webm) kèm câu kiểu *"clip lỗi đây anh xem giúp"*.
- Cần biết clip **diễn ra những bước nào, lỗi hiện ở giây thứ mấy, mã lỗi là gì**.
- Có clip trong `~/.hermes/cache/videos/` (adapter Google Chat tự tải mọi attachment `video/*` về đây; nếu không thấy thì soi `~/.hermes/cache/documents/`).

**Model chính không xem được video.** Muốn "xem" phải biến clip thành ẢNH + LỜI THOẠI rồi đọc bằng 2 đường: `vision_analyze` (đọc ảnh) và `audio_transcribe.py` (bóc tiếng, chạy local).

## Quy trình 4 bước

```bash
# 0) luôn unset HERMES_HOME khi chạy script tay (tránh lẫn profile khác)
unset HERMES_HOME
CLIP=~/.hermes/cache/videos/<file>.mp4

# 1) metadata + lọc khung hình khác nhau + contact sheet + tách tiếng
python3 ~/.hermes/scripts/video_inspect.py "$CLIP" --audio
#    -> in ra: thời lượng/độ phân giải/fps/có tiếng không, danh sách khung theo giây,
#       contact_sheet.jpg (đọc 1 ảnh là hiểu cả clip), audio.wav, manifest.json

# 2) bóc lời thoại (nếu clip có thuyết minh) — LOCAL, không gửi cloud
/home/zane/.hermes/venvs/whisper/bin/python ~/.hermes/scripts/audio_transcribe.py \
    /tmp/video_<tên>/audio.wav --model medium

# 3) đọc ảnh: contact sheet trước, rồi soi từng khung nếu cần
#    vision_analyze(image_url="/tmp/video_<tên>/contact_sheet.jpg", question="...")
#    vision_analyze(image_url=<khung>, question="...", region=[x1,y1,x2,y2])  # zoom chữ nhỏ

# 4) trả lời bằng NGÔN NGỮ NGHIỆP VỤ: các bước tester làm, mốc lỗi, mã lỗi, nghi vấn nguyên nhân
```

## Đọc kết quả cho đúng
- Contact sheet có nhãn `giây mm:ss` ở góc mỗi khung → luôn nói lỗi ở **giây thứ mấy**.
- Clip quay màn hình: chữ trong khung nhỏ → gọi `vision_analyze` với `region=[...]` để phóng to vùng thông báo lỗi trước khi kết luận.
- Lời thoại và hình khớp nhau thì trích cả hai; chỉ có hình thì mô tả thao tác.
- **Với giọng tiếng Việt thật, `medium` bóc đúng gần hết** (đo thật: câu "Bước 1, em đăng nhập vào hệ thống bình thường…" ra đúng từng chữ) → có thể trích nguyên văn khi câu rõ ràng; còn audio méo/nhiễu thì chỉ hiểu ý, đừng trích.
- Có mã lỗi trong clip → tra mã lỗi theo `scope-map.json` của skill `tester-support` (đúng dự án của group), không đoán.

## Pitfalls (đã dính thật)
- **`drawtext` KHÔNG có** trong bản ffmpeg static → đừng vẽ chữ bằng ffmpeg; cần chèn chữ thì dùng PIL.
- **`select=gt(scene,x)` cho ra 0 khung với clip quay màn hình** (nền đứng yên, chỉ đổi chữ) → dùng cách lọc ảnh-hash trong `video_inspect.py` (giữ khung khi hash 32×32 lệch ≥4 hoặc sai khác điểm ảnh ≥2.5).
- **`agy`/Gemini hay bị chặn filter** (nhất là khi prompt có audio + từ khoá bảo mật) → đường chính là `vision_analyze`; agy chỉ là phương án dự phòng.
- **Groq/OpenAI STT: key trong `.env` chỉ là biến rỗng** (401) → dùng venv whisper local.
- **Đừng đẩy clip/khung hình lên cloud**: clip tester có thể chứa số tài khoản/tên khách hàng. Chỉ gửi ra **báo cáo chữ**.
- **Đừng dán transcript/cả trăm khung vào ngữ cảnh** — ghi ra file, chỉ giữ tóm tắt.
- Clip dài (>5 phút): giảm `--rate` (vd `--rate 0.5`) cho khỏi trích quá nhiều khung.

- **Chất lượng bóc tiếng tiếng Việt còn thô** (đo thật trên clip 24s có thuyết minh): `small` sai nhiều, `medium` đọc được ý (vẫn sai dấu/từ), `large-v3` int8 trên CPU **bịa hẳn** ("Hãy đăng ký kênh…") → mặc định `medium`, và **chỉ dùng transcript để hiểu ý, KHÔNG trích nguyên văn** trong câu trả lời cho tester.
- **TTS giọng tiếng Anh đọc chữ tiếng Việt → nghe méo, và ASR bóc ra rác.** Đã dính thật: `tts.edge.voice` để mặc định `en-US-AriaNeural` → clip nghe không ra chữ; đổi sang `vi-VN-NamMinhNeural` (`hermes config set tts.edge.voice vi-VN-NamMinhNeural`) thì cùng câu đó bóc đúng gần hết. **Nếu clip nhà mình tự tạo (demo/thuyết minh) mà ASR ra rác → nghi giọng TTS trước, đừng nghi model.**
- **Chỉ chạy bước 2 khi clip thật sự có tiếng** (`video_inspect.py` in "tiếng: có/không"); clip quay màn hình thường im lặng → bỏ qua cho nhanh.
- **Âm thanh clip tự tạo nên chuẩn hoá độ to**: `-af loudnorm=I=-16:TP=-1.5` (mean_volume từ -21dB lên -16.6dB, max -1.3dB) cho dễ nghe.

## Đã kiểm chứng
- `ffmpeg`/`ffprobe` 7.0.2 static ở `~/.local/bin` (không cần sudo).
- Clip test 24s 1280×720 có thuyết minh: lọc đúng 3 mốc (0s/8s/16s), contact sheet được `vision_analyze` đọc đúng từng bước + mã lỗi.
- Whisper local: venv `~/.hermes/venvs/whisper` (`uv venv` + `uv pip install faster-whisper`), model `medium` int8, CPU 8 luồng.
- Clip v2 (giọng Việt `vi-VN-NamMinhNeural` + loudnorm): bóc tiếng ra đúng: *"Alo, em gửi anh clip lỗi nhé. Bước 1, em đăng nhập vào hệ thống bình thường… Giao dịch không thực hiện được."*
