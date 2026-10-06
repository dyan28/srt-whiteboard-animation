#!/usr/bin/env python3
"""Build a manifest-based whiteboard project into a complete MP4.

The builder preserves existing annotations, initializes missing annotations,
renders every scene, concatenates scene videos, pads narration WAV files to the
manifest timeline, muxes AAC audio, and optionally embeds soft subtitles.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT = ROOT / "assets" / "whiteboard" / "whiteboard-vi"
RENDER_SCRIPT = ROOT / "scripts" / "render_stream_whiteboard.py"
MERGE_SCRIPT = ROOT / "scripts" / "merge_scenes.py"
DEFAULT_HAND = ROOT / "assets" / "drawing-hand.png"


def log(message: str) -> None:
    print(f"[build] {message}")


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(f"Không thể đọc {path}: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"JSON không hợp lệ tại {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"Nội dung {path} phải là một JSON object")
    return data


def load_manifest(project_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = project_dir / "scenes.manifest.json"
    manifest = load_json(manifest_path)
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        fail(f"Không có scenes hợp lệ trong {manifest_path}")
    scenes = sorted(scenes, key=lambda scene: int(scene.get("scene_order", 0)))
    return manifest, scenes


def scene_paths(project_dir: Path, scene: dict[str, Any]) -> dict[str, Path]:
    stem = str(scene["stem"])
    return {
        "image": project_dir / str(scene["image"]),
        "audio": project_dir / str(scene["audio"]),
        "annotation": project_dir / str(scene.get("annotation_todo") or f"{stem}.annotation.json"),
        "video": project_dir / f"{stem}-whiteboard.mp4",
    }


def slot_duration_ms(scenes: list[dict[str, Any]], index: int) -> int:
    scene = scenes[index]
    start = float(scene.get("start_sec", 0.0))
    if index + 1 < len(scenes):
        end = float(scenes[index + 1].get("start_sec", scene.get("end_sec", start)))
    else:
        end = float(scene.get("end_sec", start + float(scene.get("duration_sec", 0.0))))
    duration = int(round((end - start) * 1000))
    if duration <= 0:
        fail(f"Thời lượng timeline không hợp lệ cho scene {scene.get('stem')}")
    return duration


def image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError:
        fail("Thiếu Pillow. Hãy chạy: python3 scripts/prepare_env.py")
    try:
        with Image.open(path) as image:
            return image.size
    except OSError as exc:
        fail(f"Không thể đọc kích thước ảnh {path}: {exc}")


def starter_annotation(scene: dict[str, Any], image_path: Path) -> dict[str, Any]:
    width, height = image_size(image_path)
    duration_ms = max(1000, int(round(float(scene.get("duration_sec", 8.0)) * 1000)))
    start_ms = 300
    draw_duration_ms = max(100, duration_ms - start_ms - 500)
    narration = str(scene.get("narration", ""))
    return {
        "sceneId": str(scene["stem"]),
        "canvas": {"width": width, "height": height},
        "storyBasis": narration or str(scene.get("visual_description", "")),
        "sceneDurationMs": duration_ms,
        "elements": [
            {
                "id": "full-scene",
                "label": "Toàn cảnh",
                "sequence": 1,
                "narrativeRole": "Nội dung chính của cảnh",
                "subtitle": narration,
                "type": "structure",
                "region": {"x": 0, "y": 0, "width": width, "height": height},
                "reveal": {
                    "direction": "left_to_right",
                    "startMs": start_ms,
                    "durationMs": draw_duration_ms,
                    "maskPaddingPx": 22,
                    "protectedRegions": [],
                },
                "handPath": {
                    "start": [0, height // 2],
                    "end": [width, height // 2],
                    "easing": "easeInOut",
                },
            }
        ],
    }


def ensure_annotations(
    project_dir: Path,
    scenes: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        paths = scene_paths(project_dir, scene)
        if not paths["image"].is_file():
            fail(f"Thiếu ảnh: {paths['image']}")
        if not paths["audio"].is_file():
            fail(f"Thiếu audio: {paths['audio']}")
        if paths["annotation"].is_file():
            annotation = load_json(paths["annotation"])
        else:
            annotation = starter_annotation(scene, paths["image"])
            log(f"Tạo annotation toàn cảnh: {paths['annotation'].name}")
            if not dry_run:
                paths["annotation"].write_text(
                    json.dumps(annotation, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        validate_annotation(paths["annotation"], annotation, scenes, scene)
        annotations[str(scene["stem"])] = annotation
    return annotations


def validate_annotation(
    annotation_path: Path,
    annotation: dict[str, Any],
    scenes: list[dict[str, Any]],
    scene: dict[str, Any],
) -> None:
    canvas = annotation.get("canvas")
    elements = annotation.get("elements")
    if not isinstance(canvas, dict) or not canvas.get("width") or not canvas.get("height"):
        fail(f"Annotation thiếu canvas hợp lệ: {annotation_path}")
    if not isinstance(elements, list) or not elements:
        fail(f"Annotation chưa có mô-đun vẽ: {annotation_path}")
    scene_index = scenes.index(scene)
    slot_ms = slot_duration_ms(scenes, scene_index)
    max_end = 0
    for element in elements:
        try:
            reveal = element["reveal"]
            end_ms = int(reveal["startMs"]) + int(reveal["durationMs"])
            region = element["region"]
            if int(region["width"]) <= 0 or int(region["height"]) <= 0:
                fail(f"Region không hợp lệ trong {annotation_path}")
            max_end = max(max_end, end_ms)
        except (KeyError, TypeError, ValueError) as exc:
            fail(f"Element không hợp lệ trong {annotation_path}: {exc}")
    if max_end + 500 > slot_ms:
        fail(
            f"Timing trong {annotation_path.name} kết thúc tại {max_end}ms; "
            f"cần kết thúc không muộn hơn {slot_ms - 500}ms để khớp timeline"
        )


def run(command: list[str], dry_run: bool) -> None:
    print("$ " + shlex.join(command))
    if dry_run:
        return
    subprocess.run(command, cwd=ROOT, check=True)


def is_fresh(output: Path, inputs: list[Path]) -> bool:
    if not output.is_file():
        return False
    output_mtime = output.stat().st_mtime
    return all(path.is_file() and path.stat().st_mtime <= output_mtime for path in inputs)


def render_scenes(
    project_dir: Path,
    scenes: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[Path]:
    videos: list[Path] = []
    for index, scene in enumerate(scenes):
        paths = scene_paths(project_dir, scene)
        videos.append(paths["video"])
        inputs = [paths["image"], paths["annotation"], Path(args.hand)]
        if not args.force_render and is_fresh(paths["video"], inputs):
            log(f"Dùng lại scene đã render: {paths['video'].name}")
            continue
        log(f"Render {index + 1}/{len(scenes)}: {scene['stem']}")
        command = [
            sys.executable,
            str(RENDER_SCRIPT),
            str(paths["image"]),
            str(paths["annotation"]),
            str(paths["video"]),
            str(args.hand),
            "--ink-path",
            args.ink_path,
            "--color-fill",
            args.color_fill,
            "--fps",
            str(args.fps),
            "--cap-long-edge",
            str(args.cap_long_edge),
            "--total-ms",
            str(slot_duration_ms(scenes, index)),
        ]
        if args.bare_tip:
            command.append("--bare-tip")
        run(command, args.dry_run)
    return videos


def merge_videos(videos: list[Path], output: Path, dry_run: bool) -> None:
    log("Ghép các scene thành video không tiếng")
    run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--inputs",
            *[str(path) for path in videos],
            "--output",
            str(output),
        ],
        dry_run,
    )


def build_narration_track(
    project_dir: Path,
    scenes: list[dict[str, Any]],
    output: Path,
    dry_run: bool,
) -> None:
    log(f"Căn audio theo timeline: {output.name}")
    if dry_run:
        for index, scene in enumerate(scenes):
            log(f"  {scene['audio']}: slot {slot_duration_ms(scenes, index)}ms")
        return

    reference_params: tuple[int, int, int, str] | None = None
    with wave.open(str(output), "wb") as target:
        for index, scene in enumerate(scenes):
            audio_path = project_dir / str(scene["audio"])
            with wave.open(str(audio_path), "rb") as source:
                params = (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                )
                if reference_params is None:
                    reference_params = params
                    target.setnchannels(params[0])
                    target.setsampwidth(params[1])
                    target.setframerate(params[2])
                    target.setcomptype(params[3], "not compressed")
                elif params != reference_params:
                    fail(
                        f"Audio {audio_path.name} khác định dạng. Tất cả WAV phải cùng "
                        "số kênh, sample width, sample rate và compression"
                    )
                channels, sample_width, sample_rate, _ = params
                target_frames = int(round(slot_duration_ms(scenes, index) * sample_rate / 1000))
                payload = source.readframes(target_frames)
                bytes_per_frame = channels * sample_width
                actual_frames = len(payload) // bytes_per_frame
                target.writeframesraw(payload)
                if actual_frames < target_frames:
                    target.writeframesraw(b"\x00" * ((target_frames - actual_frames) * bytes_per_frame))


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        fail(
            "Không tìm thấy FFmpeg. Trên macOS, hãy chạy 'brew install ffmpeg', "
            "sau đó chạy lại script. Dùng --video-only nếu chỉ cần video không tiếng."
        )
    return ffmpeg


def mux_audio(
    ffmpeg: str,
    silent_video: Path,
    narration: Path,
    output: Path,
    dry_run: bool,
) -> None:
    log("Ghép audio AAC vào video")
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-i",
            str(silent_video),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ],
        dry_run,
    )


def add_subtitles(
    ffmpeg: str,
    input_video: Path,
    subtitle: Path,
    output: Path,
    dry_run: bool,
) -> None:
    log("Nhúng phụ đề mềm tiếng Việt")
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-i",
            str(input_video),
            "-i",
            str(subtitle),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-map",
            "1:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=vie",
            str(output),
        ],
        dry_run,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tự động build project whiteboard từ manifest thành MP4 có audio/phụ đề."
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_PROJECT,
        help="Thư mục chứa scenes.manifest.json (mặc định: whiteboard-vi)",
    )
    parser.add_argument("--init-only", action="store_true", help="Chỉ tạo annotation còn thiếu rồi dừng")
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra và in lệnh, không tạo video")
    parser.add_argument("--force-render", action="store_true", help="Render lại kể cả khi scene MP4 còn mới")
    parser.add_argument("--video-only", action="store_true", help="Chỉ tạo final-silent.mp4, không cần FFmpeg")
    parser.add_argument("--no-subtitles", action="store_true", help="Tạo video có audio nhưng không nhúng SRT")
    parser.add_argument("--ink-path", choices=["grid", "skeleton"], default="grid")
    parser.add_argument("--color-fill", choices=["contour-wipe", "brush"], default="contour-wipe")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--cap-long-edge", type=int, default=1080)
    parser.add_argument("--bare-tip", action="store_true", help="Không hiển thị bàn tay/bút")
    parser.add_argument("--hand", type=Path, default=DEFAULT_HAND, help="Ảnh bàn tay PNG")
    parser.add_argument("--output", type=Path, default=None, help="Đường dẫn MP4 cuối")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.project_dir = args.project_dir.expanduser().resolve()
    args.hand = args.hand.expanduser().resolve()
    try:
        manifest, scenes = load_manifest(args.project_dir)
        log(f"Project: {manifest.get('topic') or manifest.get('project_slug') or args.project_dir.name}")
        log(f"Số scene: {len(scenes)}")
        ensure_annotations(args.project_dir, scenes, args.dry_run)
        if args.init_only:
            log("Đã khởi tạo annotation. Mở assets/preview.html bằng Chrome để chỉnh trước khi build.")
            return 0

        ffmpeg = None if args.video_only or args.dry_run else require_ffmpeg()
        if args.dry_run and not args.video_only and not shutil.which("ffmpeg"):
            log("Cảnh báo: build có audio cần FFmpeg; cài bằng 'brew install ffmpeg'")

        videos = render_scenes(args.project_dir, scenes, args)
        silent_video = args.project_dir / "final-silent.mp4"
        merge_videos(videos, silent_video, args.dry_run)
        if args.video_only:
            log(f"Hoàn thành: {silent_video}")
            return 0

        narration = args.project_dir / "narration-full.wav"
        with_audio = args.project_dir / "final-with-audio.mp4"
        build_narration_track(args.project_dir, scenes, narration, args.dry_run)
        mux_audio(ffmpeg or "ffmpeg", silent_video, narration, with_audio, args.dry_run)

        subtitle = args.project_dir / "narration.srt"
        output = (args.output.expanduser().resolve() if args.output else args.project_dir / "final-complete.mp4")
        if args.no_subtitles or not subtitle.is_file():
            if args.dry_run:
                log(f"Sẽ sao chép {with_audio.name} thành {output.name}")
            else:
                shutil.copy2(with_audio, output)
        else:
            add_subtitles(ffmpeg or "ffmpeg", with_audio, subtitle, output, args.dry_run)

        log(f"Hoàn thành: {output}")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
