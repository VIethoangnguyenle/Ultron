#!/usr/bin/env python3
"""Đo toolset + prompt size THẬT cho MỘT profile Hermes, mô phỏng đúng đường cron.

Vì sao cần script này: toolset là kết quả của 3 tầng cấu hình chồng nhau (platform_toolsets
→ resolver cron → merge MCP), còn system prompt thì không đọc được từ file. Đọc config bằng mắt
là đoán sai. Script dựng agent offline (không gọi API) theo ĐÚNG thứ tự cron/scheduler.py:

    _init_cron_mcp_tools()  -> tools.mcp_tool_discovery.discover_mcp_tools()
    _resolve_cron_enabled_toolsets(job, cfg)
    _resolve_cron_disabled_toolsets(cfg)
    AIAgent(...)            -> agent.tools  (schema gửi lên model)
    build_system_prompt(agent)

CÁCH CHẠY (BẮT BUỘC kèm HERMES_HOME, nếu không sẽ đo nhầm profile default):

    VENV=~/.hermes/hermes-agent/venv/bin/python
    HERMES_HOME=~/.hermes/profiles/<tên> $VENV measure_cron_prompt.py <label>
    HERMES_HOME=~/.hermes                 $VENV measure_cron_prompt.py default

Đổ ra file để khỏi bị cắt:  ... measure_cron_prompt.py <label> > /tmp/measure_<label>.txt 2>&1

MCP discovery spawn server thật (mcp-atlassian qua uvx có thể mất 10-60s/server) -> cho timeout rộng.

Đọc kết quả:
  * "SO TOOL trong schema" nhỏ (3) mà "SO TOOL raw" lớn (80) là BÌNH THƯỜNG: MCP catalog lớn bị deferred
    vào description của tool `tool_search`, không nhét thẳng vào system prompt. So sánh độ phình phải so
    CẢ bytes tool-schema, không chỉ số tool.
  * "RAW TOOL NAMES" là danh sách thật của MCP server sau khi áp `tools.exclude` -> dùng để kiểm xem
    mình đã loại đúng tool ghi chưa (danh sách loại tay thường thiếu).
  * Số tool native có thể chênh giữa 2 lần đo vì check_fn của toolset (browser, image_gen...) trả False
    trong tiến trình đo. Ghi rõ "đo được ở lần chạy khi toolset khả dụng" + lý do chênh.

Nếu resolver đổi tên/tham số: đọc lại `cron/scheduler.py` (các hàm _resolve_cron_*_toolsets,
_init_cron_mcp_tools) và `hermes_cli/tools_config.py:_get_platform_tools` rồi sửa import tương ứng.
"""
import json
import os
import sys

HERMES_AGENT = os.environ.get("HERMES_AGENT_DIR", os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, HERMES_AGENT)
os.chdir(HERMES_AGENT)

label = sys.argv[1] if len(sys.argv) > 1 else "profile"

from hermes_constants import get_hermes_home  # noqa: E402

print("### LABEL:", label)
print("HERMES_HOME =", os.environ.get("HERMES_HOME"))
print("get_hermes_home() =", get_hermes_home())

# 1) giống _init_cron_mcp_tools(): MCP phải được đăng ký TRƯỚC khi dựng agent.
from tools.mcp_tool_discovery import discover_mcp_tools  # noqa: E402

mcp_tools = discover_mcp_tools()
print("MCP tools registered:", len(mcp_tools))

from hermes_cli.config import load_config  # noqa: E402

cfg = load_config()
print("mcp_servers trong config:", sorted((cfg.get("mcp_servers") or {}).keys()))
print("platform_toolsets.cron:", (cfg.get("platform_toolsets") or {}).get("cron"))
print("memory:", cfg.get("memory"))

from cron.scheduler import (  # noqa: E402
    _resolve_cron_disabled_toolsets,
    _resolve_cron_enabled_toolsets,
)

# job rỗng = mô phỏng job KHÔNG khai enabled_toolsets per-job (khuyến nghị).
# Muốn mô phỏng job có khai: job = {"enabled_toolsets": ["atlassian"]}
job = {"enabled_toolsets": None}
enabled = sorted(_resolve_cron_enabled_toolsets(job, cfg))
disabled = _resolve_cron_disabled_toolsets(cfg)
print("RESOLVED enabled_toolsets:", enabled)
print("RESOLVED disabled_toolsets:", disabled)

from run_agent import AIAgent  # noqa: E402
from agent.system_prompt import build_system_prompt, build_system_prompt_parts  # noqa: E402

model_cfg = cfg.get("model") or {}
agent = AIAgent(
    model=model_cfg.get("default") or model_cfg.get("model") or "",
    api_key="inspect-only",
    base_url="https://example.invalid/v1",
    quiet_mode=True,
    save_trajectories=False,
    platform="cron",
    enabled_toolsets=enabled,
    disabled_toolsets=disabled,
)
prompt = build_system_prompt(agent)
parts = build_system_prompt_parts(agent) or {}
tools = agent.tools or []
tool_names = sorted((t.get("function") or {}).get("name") or t.get("name") for t in tools)

from model_tools import get_tool_definitions  # noqa: E402

raw = get_tool_definitions(
    enabled_toolsets=enabled, disabled_toolsets=disabled,
    quiet_mode=True, skip_tool_search_assembly=True,
)
raw_names = sorted({(t.get("function") or {}).get("name") or t.get("name") for t in raw})

print()
print("MODEL:", model_cfg.get("default"))
print("SO TOOL trong schema (deferred/bridge):", len(tools))
print("SO TOOL raw (bo tool_search bridge):", len(raw_names))
print("RAW TOOL NAMES:", ", ".join(raw_names))
print("tool-schema JSON bytes:", len(json.dumps({"tools": tools}, ensure_ascii=False)))
print(f"SYSTEM PROMPT chars: {len(prompt)}  bytes: {len(prompt.encode('utf-8'))}")
print("SECTIONS:", json.dumps(
    {k: (len(v) if isinstance(v, str) else v) for k, v in parts.items()}, ensure_ascii=False))
print("TOOL NAMES:", ", ".join(tool_names))

dump = f"/tmp/prompt_{label}.txt"
with open(dump, "w", encoding="utf-8") as fh:
    fh.write(prompt)
print("da ghi prompt ->", dump)
