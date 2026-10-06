#!/usr/bin/env python3
"""Generate a deterministic whiteboard source image and annotation about rain."""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

WIDTH = 1920
HEIGHT = 1080
BACKGROUND = "#F5EBD7"
INK = "#3F4145"
BLUE = "#4F86A6"
LIGHT_BLUE = "#A9CAD8"
ORANGE = "#D98245"
CLOUD = "#E6E1D7"
DARK_CLOUD = "#B9BEC2"


def jittered_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: str,
    width: int,
    seed: int,
    jitter: float = 1.8,
) -> None:
    """Draw a restrained double-pass line to resemble a pencil sketch."""
    rng = random.Random(seed)
    for pass_index in range(2):
        varied = [
            (
                int(round(x + rng.uniform(-jitter, jitter) + pass_index * 0.6)),
                int(round(y + rng.uniform(-jitter, jitter) + pass_index * 0.4)),
            )
            for x, y in points
        ]
        draw.line(varied, fill=fill, width=max(2, width - pass_index * 2), joint="curve")


def ellipse_outline(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    width: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    for pass_index in range(2):
        delta = rng.randint(-2, 2)
        shifted = tuple(v + delta + pass_index for v in box)
        draw.ellipse(shifted, outline=fill, width=max(2, width - pass_index * 2))


def arrow_head(
    draw: ImageDraw.ImageDraw,
    tip: tuple[int, int],
    angle: float,
    color: str,
    seed: int,
    size: int = 24,
) -> None:
    wings = []
    for offset in (2.55, -2.55):
        wings.append(
            (
                tip[0] + math.cos(angle + offset) * size,
                tip[1] + math.sin(angle + offset) * size,
            )
        )
    jittered_line(draw, [wings[0], tip, wings[1]], color, 8, seed)


def draw_sun(draw: ImageDraw.ImageDraw) -> None:
    ellipse_outline(draw, (120, 115, 270, 265), ORANGE, 10, 10)
    cx, cy = 195, 190
    for index, angle in enumerate([i * math.pi / 4 for i in range(8)]):
        start = (cx + math.cos(angle) * 100, cy + math.sin(angle) * 100)
        end = (cx + math.cos(angle) * 142, cy + math.sin(angle) * 142)
        jittered_line(draw, [start, end], ORANGE, 8, 20 + index)


def draw_water_and_evaporation(draw: ImageDraw.ImageDraw) -> None:
    # Warm shoreline and three restrained water bands.
    jittered_line(draw, [(60, 875), (260, 842), (475, 855), (690, 820)], INK, 9, 40)
    for index, y in enumerate((900, 944, 988)):
        points = []
        for x in range(75, 710, 24):
            points.append((x, y + math.sin(x / 55 + index) * 12))
        jittered_line(draw, points, BLUE, 9, 50 + index)

    # Water molecules rise toward the central cloud.
    paths = [
        [(275, 820), (245, 730), (285, 645), (330, 565), (405, 485)],
        [(430, 825), (455, 735), (430, 650), (490, 565), (550, 490)],
        [(585, 800), (625, 720), (600, 635), (660, 555), (735, 480)],
    ]
    for index, path in enumerate(paths):
        jittered_line(draw, path, BLUE, 9, 70 + index)
        a, b = path[-2], path[-1]
        arrow_head(draw, b, math.atan2(b[1] - a[1], b[0] - a[0]), BLUE, 80 + index)
        for dot_index, (x, y) in enumerate(path[1:4]):
            ellipse_outline(draw, (x - 8, y - 12, x + 8, y + 12), LIGHT_BLUE, 5, 90 + index * 10 + dot_index)


def cloud_shape(
    draw: ImageDraw.ImageDraw,
    lobes: list[tuple[int, int, int]],
    baseline: tuple[int, int, int],
    fill: str,
    seed: int,
) -> None:
    for x, y, radius in lobes:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    left, right, y = baseline
    draw.rounded_rectangle((left, y - 85, right, y + 55), radius=65, fill=fill)

    # A single sketch outline around the cloud silhouette.
    outline_points = []
    for x, y, radius in lobes:
        for step in range(9):
            angle = math.pi + step * math.pi / 8
            outline_points.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
    outline_points.extend([(right, y + 52), (left, y + 52), (left, y - 25)])
    jittered_line(draw, outline_points, INK, 9, seed, jitter=2.2)


def draw_condensation_cloud(draw: ImageDraw.ImageDraw) -> None:
    cloud_shape(
        draw,
        [(735, 345, 105), (870, 285, 145), (1025, 335, 115), (1135, 365, 92)],
        (660, 1205, 410),
        CLOUD,
        120,
    )
    # Small droplets collect inside the cloud.
    for index, (x, y) in enumerate([(790, 365), (875, 335), (965, 375), (1055, 350)]):
        ellipse_outline(draw, (x - 10, y - 15, x + 10, y + 15), BLUE, 5, 130 + index)


def draw_rain_cloud(draw: ImageDraw.ImageDraw) -> None:
    cloud_shape(
        draw,
        [(1360, 330, 98), (1480, 270, 135), (1625, 310, 125), (1740, 360, 90)],
        (1280, 1820, 405),
        DARK_CLOUD,
        160,
    )
    # Air-flow arrow links condensation to the rain cloud.
    flow = [(1110, 220), (1220, 170), (1330, 215)]
    jittered_line(draw, flow, BLUE, 8, 170)
    a, b = flow[-2], flow[-1]
    arrow_head(draw, b, math.atan2(b[1] - a[1], b[0] - a[0]), BLUE, 171)


def draw_rain_and_ground(draw: ImageDraw.ImageDraw) -> None:
    drops = [
        (1325, 500, 610), (1405, 485, 655), (1490, 505, 625),
        (1575, 480, 680), (1660, 510, 640), (1740, 490, 690),
        (1360, 675, 790), (1470, 700, 820), (1610, 705, 835), (1715, 720, 830),
    ]
    for index, (x, y0, y1) in enumerate(drops):
        jittered_line(draw, [(x, y0), (x - 18, y1)], BLUE, 9, 200 + index)

    # Ground, puddle and a small plant receiving the rain.
    jittered_line(draw, [(1180, 920), (1350, 890), (1530, 915), (1730, 875), (1880, 900)], INK, 9, 230)
    puddle = [(1320, 955), (1390, 935), (1510, 940), (1595, 965), (1490, 985), (1370, 980), (1320, 955)]
    jittered_line(draw, puddle, BLUE, 8, 231)
    jittered_line(draw, [(1710, 895), (1705, 805), (1680, 750)], INK, 8, 232)
    jittered_line(draw, [(1705, 815), (1755, 770), (1795, 785)], INK, 8, 233)
    draw.ellipse((1652, 725, 1695, 772), fill=LIGHT_BLUE, outline=INK, width=6)
    draw.ellipse((1768, 755, 1810, 800), fill=LIGHT_BLUE, outline=INK, width=6)


def build_annotation() -> dict:
    return {
        "sceneId": "rain-cycle-demo",
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "storyBasis": "Nắng làm nước bốc hơi, hơi nước ngưng tụ thành mây, giọt nước lớn dần rồi rơi xuống thành mưa.",
        "sceneDurationMs": 15000,
        "elements": [
            {
                "id": "evaporation",
                "label": "Nước bốc hơi dưới ánh nắng",
                "sequence": 1,
                "narrativeRole": "Mở đầu nguyên nhân: nhiệt từ Mặt Trời làm nước bốc hơi.",
                "subtitle": "Ánh nắng làm nước ở sông, hồ và biển bốc hơi lên cao.",
                "type": "action",
                "region": {"x": 45, "y": 45, "width": 720, "height": 990},
                "reveal": {
                    "direction": "bottom_to_top",
                    "startMs": 300,
                    "durationMs": 3300,
                    "maskPaddingPx": 20,
                    "protectedRegions": [],
                },
                "handPath": {"start": [360, 950], "end": [610, 450], "easing": "easeInOut"},
            },
            {
                "id": "condensation",
                "label": "Hơi nước ngưng tụ thành mây",
                "sequence": 2,
                "narrativeRole": "Hơi nước lạnh đi và tụ thành những giọt nước nhỏ trong mây.",
                "subtitle": "Lên cao, hơi nước lạnh đi và ngưng tụ thành những đám mây.",
                "type": "structure",
                "region": {"x": 635, "y": 100, "width": 610, "height": 470},
                "reveal": {
                    "direction": "left_to_right",
                    "startMs": 3800,
                    "durationMs": 2800,
                    "maskPaddingPx": 20,
                    "protectedRegions": [],
                },
                "handPath": {"start": [670, 390], "end": [1190, 390], "easing": "easeInOut"},
            },
            {
                "id": "heavy-cloud",
                "label": "Mây chứa nhiều giọt nước",
                "sequence": 3,
                "narrativeRole": "Các giọt nước kết hợp và trở nên quá nặng để ở lại trong mây.",
                "subtitle": "Các giọt nước kết hợp với nhau, khiến đám mây ngày càng nặng.",
                "type": "transition",
                "region": {"x": 1240, "y": 95, "width": 625, "height": 440},
                "reveal": {
                    "direction": "left_to_right",
                    "startMs": 6800,
                    "durationMs": 2800,
                    "maskPaddingPx": 20,
                    "protectedRegions": [],
                },
                "handPath": {"start": [1270, 360], "end": [1810, 360], "easing": "easeInOut"},
            },
            {
                "id": "rainfall",
                "label": "Nước rơi xuống thành mưa",
                "sequence": 4,
                "narrativeRole": "Kết quả: trọng lực kéo các giọt nước xuống mặt đất thành mưa.",
                "subtitle": "Khi đủ nặng, các giọt nước rơi xuống mặt đất và tạo thành mưa.",
                "type": "result",
                "region": {"x": 1160, "y": 455, "width": 720, "height": 575},
                "reveal": {
                    "direction": "top_to_bottom",
                    "startMs": 9800,
                    "durationMs": 4200,
                    "maskPaddingPx": 20,
                    "protectedRegions": [],
                },
                "handPath": {"start": [1510, 480], "end": [1510, 980], "easing": "easeInOut"},
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("assets/whiteboard/rain-demo"),
        help="Directory for the generated PNG and annotation JSON.",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw_sun(draw)
    draw_water_and_evaporation(draw)
    draw_condensation_cloud(draw)
    draw_rain_cloud(draw)
    draw_rain_and_ground(draw)

    image_path = args.output_dir / "scene-01-why-rain.png"
    annotation_path = args.output_dir / "scene-01-why-rain.annotation.json"
    image.save(image_path, quality=95)
    annotation_path.write_text(
        json.dumps(build_annotation(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"IMAGE={image_path.resolve()}")
    print(f"ANNOTATION={annotation_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
