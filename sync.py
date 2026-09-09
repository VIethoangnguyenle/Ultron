#!/usr/bin/env python3
"""Sync curated Hermes state (memory, custom skills, scripts, config, SOUL,
cron job definitions) from ~/.hermes into this repo.

Deliberately EXCLUDES anything secret or machine-specific:
  .env, auth.json, state.db(+wal/shm), sessions/, logs/, caches, gateway
  runtime files, kanban.db, pairing/, platforms/, hooks/, the source tree.

Run via sync.sh (which also commits and pushes), or standalone.
"""
import os
import shutil
import sys
from pathlib import Path

HERMES = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
REPO = Path(__file__).resolve().parent

if len(sys.argv) > 1:
    HERMES = Path(sys.argv[1])
if len(sys.argv) > 2:
    REPO = Path(sys.argv[2])

SKILL_META = {".bundled_manifest", ".curator_ledger.jsonl", ".curator_state",
              ".usage.json", ".usage.json.lock"}


def read_bundled_skills() -> set:
    """Names of skills shipped with the install (re-created on a fresh setup)."""
    manifest = HERMES / "skills" / ".bundled_manifest"
    bundled = set()
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            line = line.strip()
            if line and ":" in line:
                bundled.add(line.split(":", 1)[0])
    return bundled


def mirror_dir(src: Path, dst: Path, skip=frozenset()) -> None:
    """Copy src/* into dst/ exactly (delete stale entries in dst)."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in dst.iterdir():
        if child.name in skip:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in src.iterdir():
        if child.name in skip:
            continue
        if child.is_dir():
            shutil.copytree(child, dst / child.name)
        else:
            shutil.copy2(child, dst / child.name)


def main() -> None:
    # 1. Memory + user profile (the "who you are" core)
    mirror_dir(HERMES / "memories", REPO / "memories")

    # 2. Custom scripts (e.g. check_resources.py)
    mirror_dir(HERMES / "scripts", REPO / "scripts")

    # 3. Persona + settings (config.yaml carries no secrets — only ${ENV} refs)
    for name in ("SOUL.md", "config.yaml"):
        src = HERMES / name
        if src.exists():
            shutil.copy2(src, REPO / name)

    # 4. Cron job definitions (so scheduled jobs survive a machine switch)
    jobs = HERMES / "cron" / "jobs.json"
    if jobs.exists():
        (REPO / "cron").mkdir(exist_ok=True)
        shutil.copy2(jobs, REPO / "cron" / "jobs.json")

    # 5. Custom skills only (bundled skills are re-shipped by the installer)
    bundled = read_bundled_skills()
    src_skills = HERMES / "skills"
    dst_skills = REPO / "skills"
    if dst_skills.exists():
        shutil.rmtree(dst_skills)
    if src_skills.is_dir():
        for category in src_skills.iterdir():
            if not category.is_dir() or category.name.startswith("."):
                continue
            for skill in category.iterdir():
                if not skill.is_dir() or skill.name in bundled:
                    continue
                dest = dst_skills / category.name / skill.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(skill, dest)

    print(f"synced: {HERMES} -> {REPO}")


if __name__ == "__main__":
    main()
