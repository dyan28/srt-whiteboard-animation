#!/usr/bin/env python3
"""Build a manifest-based whiteboard project into a complete MP4.

The builder preserves existing annotations, initializes missing annotations,
renders every scene, concatenates scene videos, pads narration WAV files to the
manifest timeline, muxes AAC audio, and optionally embeds soft subtitles.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WHITEBOARD_ROOT = ROOT / "assets" / "whiteboard"
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


def discover_projects() -> list[Path]:
    if not WHITEBOARD_ROOT.is_dir():
        return []
    return sorted(
        path.parent
        for path in WHITEBOARD_ROOT.glob("*/scenes.manifest.json")
        if path.is_file()
    )


def read_project_id(project_dir: Path) -> str:
    project_id = load_json(project_dir / "scenes.manifest.json").get("project_id")
    if isinstance(project_id, str) and project_id.strip():
        return project_id.strip()
    return project_dir.name


def describe_projects(projects: list[Path]) -> str:
    return "\n".join(
        f"  {read_project_id(project_dir)}    {project_dir.name}"
        for project_dir in projects
    )


def resolve_projects(raw: Path | None) -> list[Path]:
    """Chọn một project theo ID, tên thư mục hoặc đường dẫn."""
    projects = discover_projects()
    if not projects:
        fail(
            "Không có project nào trong assets/whiteboard. "
            "Mỗi thư mục project cần scenes.manifest.json."
        )
    if raw is None:
        if len(projects) == 1:
            return projects
        fail(
            "assets/whiteboard có nhiều project. Hãy truyền project_id:\n"
            f"{describe_projects(projects)}\n"
            "Ví dụ: ./build_video.sh <project_id> --subtitles"
        )

    token = str(raw.expanduser())
    exact_ids = [project for project in projects if read_project_id(project) == token]
    if len(exact_ids) == 1:
        return [exact_ids[0].resolve()]
    if len(exact_ids) > 1:
        fail(f"project_id {token} trùng nhiều thư mục:\n{describe_projects(exact_ids)}")

    folder_matches = [project for project in projects if project.name == Path(token).name and "/" not in token and "\\" not in token]
    if len(folder_matches) == 1 and not Path(token).is_absolute() and len(Path(token).parts) == 1:
        return [folder_matches[0].resolve()]

    expanded = raw.expanduser()
    candidates = [expanded] if expanded.is_absolute() else [
        Path.cwd() / expanded,
        ROOT / expanded,
        WHITEBOARD_ROOT / expanded,
    ]
    for candidate in candidates:
        if (candidate / "scenes.manifest.json").is_file():
            return [candidate.resolve()]

    if len(token) >= 8:
        prefix_matches = [
            project for project in projects if read_project_id(project).startswith(token)
        ]
        if len(prefix_matches) == 1:
            return [prefix_matches[0].resolve()]
        if len(prefix_matches) > 1:
            fail(
                f"ID {token} khớp nhiều project. Hãy truyền đủ project_id:\n"
                f"{describe_projects(prefix_matches)}"
            )

    fail(
        f"Không tìm thấy project cho: {raw}\n"
        f"Project trong assets/whiteboard:\n{describe_projects(projects)}"
    )


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


def srt_timestamp(value: str) -> float:
    hours, minutes, seconds = value.strip().replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_text, end_text = lines[timing_index].split("-->", 1)
        text = " ".join(lines[timing_index + 1 :]).strip()
        if text.startswith("# "):
            text = text[2:].strip()
        if not text:
            continue
        start = srt_timestamp(start_text)
        end = srt_timestamp(end_text.split()[0])
        if end > start:
            cues.append((start, end, text))
    return cues


def video_dimensions(path: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        fail("Không tìm thấy ffprobe để đọc kích thước video")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    width_text, height_text = result.stdout.strip().split("x")
    return int(width_text), int(height_text)


def wrap_caption(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_caption_png(
    text: str,
    width: int,
    height: int,
    destination: Path,
    font_size: int,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        fail("Thiếu Pillow. Hãy chạy: python3 scripts/prepare_env.py")

    font_path = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    if not font_path.is_file():
        font_path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    if not font_path.is_file():
        fail(f"Không tìm thấy font phụ đề: {font_path}")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    max_width = width - 80
    minimum_size = max(16, int(font_size * 0.7))
    font = ImageFont.truetype(str(font_path), font_size)
    lines = wrap_caption(draw, text, font, max_width)
    while len(lines) > 3 and font_size > minimum_size:
        font_size -= 2
        font = ImageFont.truetype(str(font_path), font_size)
        lines = wrap_caption(draw, text, font, max_width)

    line_gap = 8
    line_height = font_size + line_gap
    block_height = line_height * len(lines) - line_gap
    y = height - 28 - block_height
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(35, 35, 35, 255),
            stroke_width=3,
            stroke_fill=(245, 235, 215, 255),
        )
        y += line_height
    image.save(destination)


def add_subtitles(
    ffmpeg: str,
    input_video: Path,
    subtitle: Path,
    output: Path,
    dry_run: bool,
    font_size: int,
) -> None:
    cues = parse_srt(subtitle)
    if not cues:
        fail(f"Không có câu phụ đề trong {subtitle}")
    log(f"Đốt {len(cues)} câu phụ đề lên hình, cỡ chữ {font_size}px")
    if dry_run:
        log(f"Sẽ ghi phụ đề từ {subtitle.name} vào {output.name}")
        return

    width, height = video_dimensions(input_video)
    with tempfile.TemporaryDirectory(prefix="whiteboard-subs-") as temp_dir:
        temp_path = Path(temp_dir)
        blank = temp_path / "blank.png"
        render_caption_png("", width, height, blank, font_size)
        concat_lines = ["ffconcat version 1.0"]
        cursor = 0.0
        for index, (start, end, text) in enumerate(cues, start=1):
            if start > cursor:
                concat_lines.extend([f"file '{blank.name}'", f"duration {start - cursor:.3f}"])
            caption = temp_path / f"cue-{index:03d}.png"
            render_caption_png(text, width, height, caption, font_size)
            concat_lines.extend([f"file '{caption.name}'", f"duration {end - start:.3f}"])
            cursor = end
        concat_lines.extend([f"file '{blank.name}'", "duration 1.000", f"file '{blank.name}'"])
        concat_path = temp_path / "captions.ffconcat"
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "warning",
                "-i",
                str(input_video),
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-filter_complex",
                "[0:v][1:v]overlay=0:0:shortest=1[v]",
                "-map",
                "[v]",
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                str(output),
            ],
            dry_run=False,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tự động build project whiteboard từ manifest thành MP4 có audio/phụ đề."
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        type=Path,
        default=None,
        help="project_id, tên thư mục hoặc đường dẫn. Bắt buộc khi assets/whiteboard có nhiều project.",
    )
    parser.add_argument("--init-only", action="store_true", help="Chỉ tạo annotation còn thiếu rồi dừng")
    parser.add_argument("--dry-run", action="store_true", help="Kiểm tra và in lệnh, không tạo video")
    parser.add_argument("--force-render", action="store_true", help="Render lại kể cả khi scene MP4 còn mới")
    parser.add_argument("--video-only", action="store_true", help="Chỉ tạo final-silent.mp4, không cần FFmpeg")
    subtitles = parser.add_mutually_exclusive_group()
    subtitles.add_argument(
        "--subtitles",
        dest="subtitles",
        action="store_true",
        help="Đốt phụ đề narration.srt lên hình (mặc định)",
    )
    subtitles.add_argument(
        "--no-subtitles",
        dest="subtitles",
        action="store_false",
        help="Xuất video có tiếng, không đốt phụ đề",
    )
    parser.set_defaults(subtitles=True)
    parser.add_argument(
        "--subtitle-size",
        type=int,
        default=34,
        help="Cỡ chữ phụ đề, tính bằng pixel (mặc định: 34)",
    )
    parser.add_argument("--ink-path", choices=["grid", "skeleton"], default="grid")
    parser.add_argument("--color-fill", choices=["contour-wipe", "brush"], default="contour-wipe")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--cap-long-edge", type=int, default=1080)
    parser.add_argument("--bare-tip", action="store_true", help="Không hiển thị bàn tay/bút")
    parser.add_argument("--hand", type=Path, default=DEFAULT_HAND, help="Ảnh bàn tay PNG")
    parser.add_argument("--output", type=Path, default=None, help="Đường dẫn MP4 cuối")
    return parser.parse_args()


def build_project(project_dir: Path, args: argparse.Namespace) -> None:
    manifest, scenes = load_manifest(project_dir)
    try:
        folder_label = str(project_dir.relative_to(ROOT))
    except ValueError:
        folder_label = str(project_dir)
    log(f"ID: {read_project_id(project_dir)}")
    log(f"Thư mục: {folder_label}")
    log(f"Project: {manifest.get('topic') or manifest.get('project_slug') or project_dir.name}")
    log(f"Số scene: {len(scenes)}")
    ensure_annotations(project_dir, scenes, args.dry_run)
    if args.init_only:
        log("Đã khởi tạo annotation. Mở assets/preview.html bằng Chrome để chỉnh trước khi build.")
        return

    ffmpeg = None if args.video_only or args.dry_run else require_ffmpeg()
    if args.dry_run and not args.video_only and not shutil.which("ffmpeg"):
        log("Cảnh báo: build có audio cần FFmpeg; cài bằng 'brew install ffmpeg'")

    videos = render_scenes(project_dir, scenes, args)
    silent_video = project_dir / "final-silent.mp4"
    merge_videos(videos, silent_video, args.dry_run)
    if args.video_only:
        log(f"Hoàn thành: {silent_video}")
        return

    narration = project_dir / "narration-full.wav"
    with_audio = project_dir / "final-with-audio.mp4"
    build_narration_track(project_dir, scenes, narration, args.dry_run)
    mux_audio(ffmpeg or "ffmpeg", silent_video, narration, with_audio, args.dry_run)

    subtitle = project_dir / "narration.srt"
    if args.output:
        output = args.output.expanduser().resolve()
    elif args.subtitles:
        output = project_dir / "final-complete.mp4"
    else:
        output = project_dir / "final-without-subtitles.mp4"
    if args.subtitle_size < 12:
        fail("--subtitle-size phải từ 12 trở lên")
    if not args.subtitles or not subtitle.is_file():
        if args.subtitles and not subtitle.is_file():
            log(f"Không thấy {subtitle.name}, xuất video không phụ đề")
        if args.dry_run:
            log(f"Sẽ sao chép {with_audio.name} thành {output.name}")
        else:
            shutil.copy2(with_audio, output)
    else:
        add_subtitles(
            ffmpeg or "ffmpeg",
            with_audio,
            subtitle,
            output,
            args.dry_run,
            args.subtitle_size,
        )

    log(f"Hoàn thành: {output}")


def main() -> int:
    args = parse_args()
    args.hand = args.hand.expanduser().resolve()
    try:
        projects = resolve_projects(args.project_dir)
        if len(projects) > 1 and args.output is not None:
            fail("--output chỉ dùng khi chỉ định một thư mục project.")
        if len(projects) > 1:
            log(f"Tìm thấy {len(projects)} project trong assets/whiteboard")
        for project_dir in projects:
            build_project(project_dir, args)
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
