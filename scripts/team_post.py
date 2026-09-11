#!/usr/bin/env python3
"""Post a recurring team message to a Google Chat space AS the bot (service account).

Một script cho mọi tin định kỳ trong ngày, chọn loại bằng `--kind`:
  lunch      — nhắc ăn trưa (12h)
  afternoon  — khai ca chiều (13h)
  evening    — chào cuối ngày (17:30)

Vì sao gom: các tin này chỉ khác nhau ở nội dung. Thêm loại mới = thêm 1 entry trong KINDS,
không phải thêm script thứ N rồi lại phải nhớ xoá.

Giọng: vui vẻ CÀ NHÂY (Hoàng chốt 2026-09-11: "Giọng vui vẻ cà nhây nha. Tạo không khí mà").
Mỗi khung giờ 18 câu, xoay vòng theo ngày ⇒ ~18 ngày mới lặp lại một câu.
Muốn thêm câu: thêm 1 dòng vào list tương ứng trong KINDS (giữ ≥ 15 để lâu lặp).

Câu chọn theo NGÀY (không random) → mỗi ngày một câu khác, và chạy lại trong cùng ngày vẫn ra
đúng câu đó nên test được. Không @mention ai: tin vui vẻ mà réo tên cả team thì thành chuông báo.

Usage:
  team_post.py --kind lunch [--space spaces/...] [--dry-run] [--variant N]
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
SA_PATH = HOME / "google-chat-sa.json"
DEFAULT_SPACE = "spaces/AAAADv4ib6s"  # VBB SME | Nội bộ dự án

# Lệch pha giữa các khung giờ: để 3 tin trong ngày không "trùng số" nhau mỗi lần xoay.
SALT = {"lunch": 0, "afternoon": 7, "evening": 13}

KINDS = {
    "lunch": [
        "12h rồi cả nhà ơi 🍚\nAi đang dính bug thì để đó — cơm nguội ăn không ngon đâu 😄 Em cũng xin phép đi ăn đây.",
        "Trưa rồi nha cả nhà 🕛\nGấp gì thì gấp, ăn đã rồi tính. Não cần năng lượng mới fix nổi bug, đói là nghĩ sai hết =))",
        "12h — giờ ăn trưa ạ 🍜\nMọi người nhớ ăn đúng bữa nhé, em trông máy giúp cho. Ăn xong quay lại mình chạy tiếp.",
        "Chuông báo: 12h — cơm nào 🍽️\nAi đang họp thì cố 5 phút nữa, ai đang code thì cũng cố 5 phút nữa rồi đi ăn nha. Đói mà code là code sai đấy 😄",
        "Tới giờ cơm rồi cả nhà ơi 🍛\nĐừng để task nguội trước cơm nhé =)) Ăn xong nghỉ chút rồi chiều chiến tiếp.",
        "12h rồi, đứng dậy đi ăn đi ạ 🍲\nNgồi thêm 15 phút cũng không fix được bug nào đâu, mà đói thì fix sai hết =))",
        "Trưa tới rồi cả nhà 🥢\nMón hôm nay ăn gì vậy? Khoe em nghe với — em ăn bằng pin nên chỉ biết hóng thôi 😌",
        "12h — nghỉ trưa nha cả nhà 🌾\nAi chưa ăn thì ăn, ai ăn rồi thì ngủ chút. Em giữ máy, có gì ầm lên em réo gọi.",
        "Cơm tới rồi cả nhà ơi 🍱\nAnh chị nào đang định ăn trưa bằng bánh mì trước màn hình thì em nhắc nhẹ nha 😆",
        "12h rồi 🕛\nXin phép nhắc: ăn trưa, uống nước, đứng dậy vươn vai 3 cái. Bug sẽ đợi mình được, còn bụng thì không =))",
        "Giờ ăn trưa ạ 🍚\nAi đang cãi nhau với log thì pause lại đi, ăn xong cãi tiếp. Em không chạy đi đâu đâu 😄",
        "Trưa rồi cả nhà 🕐\nNghỉ ngơi 30 phút cho não nó \"deploy\" lại nha, chiều còn chiến tiếp.",
        "12h — đến bữa rồi 🍽️\nMón gì cũng được, miễn đừng ăn trưa ở bàn phím 😆 Em đứng nhìn đấy.",
        "Cơm thôi cả nhà ơi 🍛\nAi hôm nay ăn một mình thì rủ thêm người cho vui — ăn một mình buồn lắm 😄",
        "12h rồi ạ 🍜\nNhắc khéo: đừng lấy cà phê thay cơm nha mấy anh chị, chiều còn phải tỉnh táo mà chạy =))",
        "Tới giờ ăn rồi cả nhà 🍚\nTạm gác bug, log, task lại. Ăn no rồi mình quay lại gỡ tiếp — em hứa không mách ai đâu 🤐",
        "12h — giải lao thôi 🌤️\nAi xong sớm thì đi ăn trước, ai còn dở thì ăn sau cũng được, miễn đừng bỏ bữa nha.",
        "Trưa tới rồi 🍱\nĂn xong nhớ đứng dậy đi vài vòng cho khỏe nha cả nhà — chiều nay còn nhiều việc thú vị lắm =))",
    ],
    "afternoon": [
        "13h rồi cả nhà ơi 😴➡️😎\nAi còn nằm mơ thấy bug thì dậy đi, bug nó không tự chết đâu =)) Ca chiều bắt đầu, bung sức nào!",
        "Chuông báo: 13h — hết giờ ngủ trưa 📢\nAnh/chị nào vừa ngáp 3 cái liên tiếp thì tự biết mình rồi đó nha 😆 Vào ca chiều thôi!",
        "Ca chiều khai hỏa 🚀\nSáng nay ai làm được gì thì khoe, ai chưa làm gì thì... cứ giả vờ sáng nay không tồn tại =)) Em không mách ai đâu 🤐",
        "13h — điểm danh ca chiều 📋\nAi có mặt gõ \"có\", ai chưa tỉnh gõ \"...\" 🤤 Em ghi sổ hết đó nha 😏",
        "Dậy dậy dậy! 13h rồi 🥱\nGối, chăn với giấc mơ trưa — trả lại em, tới lượt công việc 😌 Có gì tắc thì ném xuống đây, em xử cho.",
        "Ca chiều bắt đầu nha cả nhà ☕\nUống ngụm nước cho tỉnh rồi vào việc. Nếu vẫn buồn ngủ thì mở log bug ra đọc, tỉnh ngay =))",
        "Sáng nay ổn không mọi người? 😏 Chiều mình chạy tiếp nha.\nCòn em thì cả ngày không ngủ rồi — nghe oai chứ em là bot mà =)))",
        "13h rồi 🕐\nSáng nay mọi người đã kiệt sức chưa? Nếu chưa thì em có sẵn danh sách bug đang chờ đó nha 😌 Ai dám nhận?",
        "Khai ca chiều 🎉\nMục tiêu chiều nay: ít bug hơn sáng, nhiều cà phê hơn sáng, deadline... xa hơn sáng =)) Bắt đầu!",
        "13h — ca chiều lên sóng 📺\nAi đang cãi nhau với bug thì cứ kể, em làm trọng tài 😆 Còn ai thắng rồi thì lên khoe cho cả nhà biết.",
        "13h rồi cả nhà ơi ⏰\nBáo thức của em đã réo từ lâu, giờ tới lượt mọi người. Ca chiều bắt đầu — ai sẵn sàng thì gõ một cái.",
        "Hết giờ ngủ trưa 📢\nAi đang mơ giữa chừng thì chịu khó dừng ở khúc hay nhất nha =)) Vào ca chiều thôi!",
        "13h — ca chiều chính thức 🎬\nSáng nay trôi tới đâu rồi cả nhà? Chiều mình đi tiếp từ đó. Cần gì cứ réo em, em đứng ngay đây.",
        "Chào ca chiều 👋\nEm vừa nạp xong pin, tỉnh táo 100% nha. Ai cần tra log, tra dữ liệu, hỏi nghiệp vụ thì gọi em liền.",
        "13h rồi nha ☕\nĐội nào còn ngái ngủ thì đi làm ngụm nước, đội nào tỉnh rồi thì... nổ việc xuống đây =))",
        "Khai ca chiều 🚀\nEm đặt mục tiêu chiều nay ít bug hơn sáng. Mục tiêu của mọi người là gì? Kể em ghi sổ cho 😌",
        "13h — chiều rồi 🌤️\nCà phê, nước, nhạc — gì cũng được miễn mọi người thoải mái mà chạy. Em trực sẵn ở đây.",
        "Ca chiều điểm danh 📋\nAi lên rồi gõ \"có\" cho em vui, ai chưa lên thì em ngồi đợi (em kiên nhẫn lắm =))",
    ],
    "evening": [
        "Hết ngày rồi cả nhà ơi 🌇\nHôm nay mọi người thế nào? Có gì vướng kể em nghe, mai xử tiếp. Em xin phép về ăn dưa 🍉",
        "Tan làm rồi ạ 🌆\nNay anh chị em chạy có trôi không? Ai còn vướng cứ để lại lời nhắn, sáng mai em xử tiếp nhé 🍉",
        "17h30 rồi nha cả nhà 🕠\nAi xong sớm thì khoe, ai còn dở thì kể — em ghi hết vào sổ. Còn em thì chuồn về ăn dưa 🍉",
        "Hết giờ ạ ⏰\nTổng kết nhanh: hôm nay ổn hết chứ ạ? Không ổn thì nhắn em, ổn rồi thì... em về ăn dưa 🍉",
        "Về thôi cả nhà ơi 🏃\nBug nào còn sống sót thì cứ để nó sống qua đêm, sáng mai em xử 😌 Em về ăn dưa trước đây 🍉",
        "17h30 — hết ca 🌇\nAi định ôm bug về nhà thì nhớ thả nó lại đây nha, em giữ hộ. Về nhà thì nghỉ cho não nó \"build\" lại 😄",
        "Hết ngày làm việc rồi 🎉\nHôm nay ai làm tốt thì tự vỗ vai một cái. Ai chưa tốt thì mai làm lại. Còn em thì về ăn dưa 🍉",
        "Tan ca nha cả nhà 👋\nTask còn lại cứ treo ở đây, không ai lấy mất đâu. Sáng mai em mở máy trước, mọi người cứ ngủ ngon 😌",
        "17h30 rồi, đóng máy đi ạ 💻➡️🛌\nNgồi thêm nửa tiếng cũng chẳng fix được gì đâu, mà mai lại mệt =)) Em nói thật lòng đó.",
        "Hết ca chiều — tổng kết nào 📊\nHôm nay mọi người có gì vui kể em nghe với. Còn phần \"bug còn lại\" thì em xin phép nhắm mắt cho qua =))",
        "Về đi cả nhà ơi 🍉\nEm ghi sổ hết rồi: hôm nay ai làm gì, ai còn gì. Mai mình tiếp tục, giờ thì nghỉ ngơi.",
        "17h30 — chuông tan ca 🔔\nMáy tính tắt, đầu óc nghỉ, bug để mai. Em cũng về chuồng đây, chào cả nhà 👋",
        "Hết ngày rồi 🌇\nCảm ơn cả nhà đã chạy hết mình hôm nay. Ai còn vướng thì để mai, ai rảnh thì kể em nghe chuyện vui 😄",
        "Tan làm ạ 🌆\nEm dọn log, dọn sổ, dọn hết rồi — sáng mai mọi người có mặt là chạy tiếp được luôn. Nghỉ ngơi nha!",
        "17h30 nha cả nhà 🕠\nAi hôm nay bị bug hành thì giơ tay, mai em gỡ giúp =)) Ai may mắn thì khoe cho em ghen với.",
        "Hết ca rồi 🎊\nSáng có bug, chiều có bug, mai chắc... vẫn có bug =)) Nhưng hôm nay xong là xong, về nghỉ thôi cả nhà!",
        "Về thôi ạ 🏡\nMọi người nhớ dọn chỗ, tắt máy, uống ngụm nước. Sáng mai em vẫn ở đây, già hơn một ngày thôi =))",
        "Tổng kết cuối ngày 📝\nHôm nay mọi người thế nào? Vui thì khoe, mệt thì kể. Còn em thì xin phép về ăn dưa 🍉",
    ],
}


def build_text(kind: str, variant: int = None) -> str:
    if kind not in KINDS:
        raise SystemExit(f"kind không hợp lệ: {kind!r} (chọn: {', '.join(sorted(KINDS))})")
    opts = KINDS[kind]
    if variant is None:
        variant = (date.today().toordinal() + SALT.get(kind, 0)) % len(opts)
    return opts[variant % len(opts)]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--space", default=DEFAULT_SPACE)
    p.add_argument("--variant", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    text = build_text(a.kind, a.variant).strip()
    if a.dry_run:
        print(f"[dry-run] kind={a.kind} -> {a.space} (pool {len(KINDS[a.kind])} câu)")
        print("-" * 60)
        print(text)
        return 0

    if not SA_PATH.exists():
        print(f"ERROR: service account missing at {SA_PATH}", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_PATH.read_text(encoding="utf-8")),
        scopes=["https://www.googleapis.com/auth/chat.bot"])
    svc = build("chat", "v1", credentials=creds, cache_discovery=False)
    try:
        resp = svc.spaces().messages().create(parent=a.space, body={"text": text}).execute()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK {resp.get('name','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
