# Profile create sinh ra gì (cấu trúc + ngữ nghĩa cờ)

## Thư mục

`hermes profile create <tên>` tạo `~/.hermes/profiles/<tên>/` với các thư mục con:

```
config.yaml   profile.yaml   SOUL.md   .env
memories/  sessions/  skills/  skins/  logs/  plans/  workspace/  cron/
home/  hooks/  backups/  pairing/  audio_cache/  image_cache/
```

- `cron/` sinh ra **rỗng** (chưa có `jobs.json`) — job đầu tiên của profile sẽ tạo file này.
- `skills/` thường có thêm `.bundled_manifest` (dòng `tên:hash`, hash KHÔNG phải md5 của SKILL.md — đừng dùng
  để kết luận "skill đã bị sửa").
- `.env` sinh ra chỉ có comment: *"Per-profile secrets for this Hermes profile"* ⇒ **không có key nào**; profile
  không thừa hưởng `.env` của default (trừ nhánh clone).
- `SOUL.md` sinh ra là prompt mặc định của Hermes (1 dòng dài) ⇒ thay bằng SOUL riêng nếu cần persona riêng.
- `config.yaml` sinh ra có: `model.default` = model của **profile active lúc tạo** (không phải model lý tưởng cho
  job ⇒ phải sửa), `plugins.enabled: []`, `_config_version: <số>`, `agent: {}` và một khối comment dài.
  **Không** có `platform_toolsets`, **không** có `mcp_servers`, **không** có `memory.*`.

## Cờ của `hermes profile create`

| Cờ | Nghĩa |
|---|---|
| `--description` | 1–2 câu vai trò, dùng cho **decomposer route theo vai trò**. Viết đúng việc, không viết tên profile. |
| `--no-skills` | Profile rỗng, **không** seed bundled skill, opt-out luôn skill-sync của `hermes update`. |
| `--clone` | Copy `config.yaml`, `.env`, `SOUL.md` **và toàn bộ skills** từ profile active. Token/allowlist của bot **không** được copy (xem `--clone-channels`). |
| `--clone-from <src>` | Chọn nguồn clone khác (ngầm bật `--clone`). |
| `--clone-all` | Copy toàn bộ state (trừ history per-profile + messaging channel). |
| `--clone-channels` | Copy cả token/allowlist bot — hai profile giữ cùng một token sẽ **đụng nhau**, bị từ chối nếu profile nguồn đang được serve bởi gateway multiplex. |
| `--no-alias` | Không sinh wrapper. |

**Ràng buộc cứng:** `--no-skills` **loại trừ** `--clone*` (code chặn). Muốn profile hẹp thì chọn `--no-skills`
rồi tự copy đúng skill cần.

`--no-skills` để lại **1 skill bundled luôn-on** (`autonomous-ai-agents/hermes-agent`) + `.bundled_manifest`.
Muốn đúng số skill thì xoá cả thư mục đó lẫn manifest; marker `.no-bundled-skills` ở gốc profile giữ cho
`hermes update` không seed lại.

## Wrapper `hermes -p`

`create` sinh `~/.local/bin/<tên>` chứa `exec hermes -p <profile> "$@"` ⇒ gọi được `<tên> cron list`
hoặc `hermes -p <tên> cron tick`. Cờ `hermes -p <tên>` là đường chuẩn để chạy MỘT lệnh dưới profile khác
mà không cần wrapper.

## Kiểm tra nhanh

```bash
hermes profile list          # bảng: profile · model · gateway · alias · distribution
ls ~/.hermes/profiles/       # thư mục chưa tồn tại = chưa từng tạo profile nào
```
