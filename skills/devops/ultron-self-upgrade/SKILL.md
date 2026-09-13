---
name: ultron-self-upgrade
description: "Use when Hoàng gives feedback — turn it into a durable rule."
---

# Tự nâng cấp bản thân — góp ý thành luật

Hoàng chốt 2026-09-13: *"Tiếp theo là việc nâng cấp bản thân để làm việc hiệu quả hơn, ví dụ như việc khi anh góp ý về việc làm việc với tester thì ưu tiên dùng dpdf [PDF] chẳng hạn"*.

Mục tiêu: **một lời góp ý = một luật bền vững**, không phải một câu trả lời rồi quên.

## Pipeline 4 bước (làm NGAY trong lượt đó)

1. **Nhận diện** — đây là góp ý/đính chính/quy tắc mới, không phải câu hỏi thường:
   dấu hiệu: *"ưu tiên…", "nhớ là…", "đừng…", "lần sau…", "anh chốt…"*, hoặc sửa lại điều Ultron vừa làm.
2. **Đối chiếu luật đang có** — đã tồn tại chưa? Đã có mà KHÁC điều mới ⇒ **KHÔNG tự ghi đè**:
   nêu rõ cho Hoàng và escalate. Chỉ bổ sung/chi tiết hoá ⇒ ghi bình thường.
3. **Ghi vào đúng tầng** (quan trọng nhất — sai tầng thì lần sau không tải lại):
   ```
   SOUL.md      luật áp cho MỌI session, bất kể tác vụ   (hiếm khi đổi)
   skill        quy trình/kinh nghiệm theo TÁC VỤ          ← mặc định ghi ở đây
   memory       fact áp mọi session, ngắn, ngân sách chặt
   agentmemory  bài học/khuôn mẫu dài hạn (memory_save type=pattern|workflow)
   people.json  chỉ dành cho con người (skill team-people)
   ```
   Ghi xong phải **đổi hành vi ngay từ lượt sau** — không để Hoàng phải nhắc lại.
4. **Xác nhận 1 câu** trong chat: "Ok em ghi rồi ạ" + luật mới, không kể lể quá trình tra cứu.

## Ghi NGAY hay để 19:00? (Hoàng chốt 2026-09-13)

Hai đường KHÁC nhau — đừng trộn:

```
KÊNH                                     THỜI ĐIỂM GHI
Hoàng nhắc / góp ý (chat, group, DM, Siri)   NGAY trong lượt đó — KHÔNG chờ 19:00
Em TỰ nhận ra trong quá trình làm việc        gom lại, 19:00 job đúc kết cuối ngày
```

- Hoàng nhắc một lần = **đường chính** ⇒ patch skill/memory **ngay**, xác nhận 1 câu, đổi hành vi
  từ lượt sau. Nhắc lại lần 2 mà luật vẫn chưa có = em làm sai.
- **19:00 chỉ lo phần em TỰ rút ra** trong ngày: bài học từ việc đã làm, quan sát lặp lại, điều chỉnh nhỏ.
- Job 19:00 còn là **lưới an toàn**: góp ý nào của Hoàng trong ngày lỡ chưa thành luật thì ghi bù.
  Nó KHÔNG phải đường ghi chính — không được lấy cớ "để tối ghi".

## Vòng rà định kỳ (dùng hạ tầng có sẵn — không dựng job mới)

```
19:00 hằng ngày   job ultron-daily-lessons  → gom góp ý trong ngày, kiểm tra đã thành luật chưa,
                                             cái nào chưa thì GHI NGAY + báo Hoàng 1 dòng
Chủ nhật 09:00    lesson_review.py          → soi bài học rác/trùng/tiền đề đã đổi; CHỈ báo,
                                             không tự xoá; có phát hiện thì escalation
```

## Luật lấy ví dụ chuẩn (Hoàng đã chốt)

- *"đối với team tester, họ ưu tiên pdf hơn"* ⇒ **trả lời tester = nghiệp vụ + FILE PDF**; markdown chỉ
  là bước trung gian nội bộ, không gửi làm bản chính. Áp y hệt cho `DVNH - Daily`. → skill `tester-support`.
- *"DM = kênh hỗ trợ 1:1"*, *"1:1 với ai thì nói với ng ấy"*, *"càng làm việc càng hiểu tính người"* → skill `team-people`.
- *"link log UAT/LIVE là của riêng VBSME"* ⇒ luật per-project → skill `tester-support`.

## Cấm

- KHÔNG tự sửa/xoá luật cũ khi chưa hỏi Hoàng; mâu thuẫn ⇒ escalate.
- KHÔNG ghi token/mật khẩu/PII, không ghi đời tư đồng nghiệp.
- KHÔNG ghi luật "cho có": luật phải đổi được hành vi và kiểm chứng được bằng file thật.
