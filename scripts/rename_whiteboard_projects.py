#!/usr/bin/env python3
"""Gán project_id và đổi tên thư mục copy vào assets/whiteboard."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WHITEBOARD_ROOT = ROOT / "assets" / "whiteboard"


def log(message: str) -> None:
    print(f"[rename] {message}")


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(f"Không thể đọc {path}: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"JSON không hợp lệ tại {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"Nội dung {path} phải là một JSON object")
    return data


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError:
        return None


def language_code(manifest: dict[str, Any]) -> str:
    raw = manifest.get("language")
    if not isinstance(raw, str):
        return "project"
    code = re.sub(r"[^a-z0-9]+", "", raw.lower())
    return code or "project"


def folder_name(language: str, project_id: str) -> str:
    return f"{language}-{project_id}"


def discover(selected: str | None) -> list[Path]:
    if not WHITEBOARD_ROOT.is_dir():
        fail(f"Không thấy thư mục {WHITEBOARD_ROOT}")
    projects = sorted(
        path.parent
        for path in WHITEBOARD_ROOT.glob("*/scenes.manifest.json")
        if path.is_file()
    )
    if selected is None:
        return projects
    token = selected.strip()
    matches = [
        project
        for project in projects
        if project.name == token or project.name == Path(token).name
    ]
    if len(matches) == 1:
        return matches
    listing = "\n".join(f"  {project.name}" for project in projects) or "  (không có)"
    fail(f"Không tìm thấy thư mục {selected}\nCác project hiện có:\n{listing}")


def prepare_project(project_dir: Path, dry_run: bool) -> None:
    manifest_path = project_dir / "scenes.manifest.json"
    manifest = load_manifest(manifest_path)
    project_id = valid_uuid(manifest.get("project_id"))
    assigned = False
    if project_id is None:
        project_id = str(uuid.uuid4())
        manifest["project_id"] = project_id
        assigned = True
        log(f"Gán ID mới cho {project_dir.name}: {project_id}")
        if not dry_run:
            save_manifest(manifest_path, manifest)
    else:
        log(f"Giữ ID của {project_dir.name}: {project_id}")

    target_name = folder_name(language_code(manifest), project_id)
    target = project_dir.with_name(target_name)
    if project_dir.name == target_name:
        log(f"Tên thư mục đã đúng: {target_name}")
        return
    if target.exists():
        fail(f"Không thể đổi {project_dir.name} thành {target_name} vì thư mục đích đã tồn tại")
    log(f"{project_dir.name} -> {target_name}")
    if not dry_run:
        project_dir.rename(target)
    if assigned and dry_run:
        log("Chưa ghi file vì đang chạy --dry-run")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gán project_id và đổi tên thư mục trong assets/whiteboard thành {ngôn ngữ}-{project_id}."
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="Tên một thư mục trong assets/whiteboard. Bỏ trống để xử lý mọi project.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in việc sẽ làm, không đổi tên hay ghi file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        projects = discover(args.folder)
        if not projects:
            fail("Không có project nào chứa scenes.manifest.json trong assets/whiteboard")
        for project_dir in projects:
            prepare_project(project_dir, args.dry_run)
        return 0
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
