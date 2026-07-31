from __future__ import annotations

import argparse
import csv
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs/feedback-demo"
MAP_OUTPUT = ROOT / "outputs/design-v6/annual-maps"
CANVAS = (1920, 1080)
TEXT = (238, 244, 244)
MUTED = (111, 145, 156)
AGE_COLORS = {
    1: (45, 92, 183),
    2: (50, 137, 204),
    3: (68, 181, 210),
    4: (137, 216, 216),
    5: (235, 239, 211),
}

FONT_ROOT = ROOT / "assets/fonts/wanted-sans"
FONT_REGULAR = FONT_ROOT / "WantedSans-Regular.ttf"
FONT_BOLD = FONT_ROOT / "WantedSans-Bold.ttf"


@cache
def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def summary_rows() -> list[dict[str, str]]:
    with (ROOT / "data/processed/summary.csv").open(encoding="utf-8") as source:
        return list(csv.DictReader(source))


def gradient_background() -> Image.Image:
    width, height = CANVAS
    y = np.linspace(0.0, 1.0, height)[:, None]
    top = np.array([3, 10, 16], dtype=np.float32)
    bottom = np.array([8, 24, 32], dtype=np.float32)
    gradient = top[None, None, :] * (1 - y[:, :, None])
    gradient += bottom[None, None, :] * y[:, :, None]
    gradient = np.repeat(gradient, width, axis=1)

    axis_x = np.arange(width)[None, :]
    axis_y = np.arange(height)[:, None]
    distance = ((axis_x - 980) / 980) ** 2 + ((axis_y - 520) / 620) ** 2
    glow = np.clip(1 - distance, 0, 1)[:, :, None]
    gradient += glow * np.array([2, 11, 15], dtype=np.float32)
    return Image.fromarray(np.clip(gradient, 0, 255).astype(np.uint8), mode="RGB")


def draw_overlay_graph(
    canvas: Image.Image,
    rows: list[dict[str, str]],
    current_year: float,
    *,
    label_size: int = 13,
) -> None:
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    left, top, right, bottom = 1430, 925, 1855, 1020
    values = [float(row["multiyear_fraction"]) for row in rows]
    first_year = int(rows[0]["year"])
    last_year = int(rows[-1]["year"])
    current_year = min(max(current_year, first_year), last_year)
    current_position = current_year - first_year
    current_index = min(int(current_position), len(rows) - 1)
    transition = current_position - current_index

    def point(index: int, value: float) -> tuple[float, float]:
        x = left + index / (len(rows) - 1) * (right - left)
        y = bottom - value / 0.50 * (bottom - top)
        return x, y

    points = [point(index, value) for index, value in enumerate(values)]
    marker = points[current_index]
    progress = points[: current_index + 1]
    if transition > 0 and current_index < len(points) - 1:
        following = points[current_index + 1]
        marker = (
            marker[0] * (1 - transition) + following[0] * transition,
            marker[1] * (1 - transition) + following[1] * transition,
        )
        progress.append(marker)

    draw.polygon([(left, bottom), *points, (right, bottom)], fill=(36, 126, 169, 47))
    draw.line((left, bottom, right, bottom), fill=(98, 137, 151, 55), width=1)
    draw.line(points, fill=(94, 129, 141, 75), width=3, joint="curve")
    draw.line(progress, fill=(44, 200, 217, 155), width=4, joint="curve")
    draw.ellipse(
        (marker[0] - 7, marker[1] - 7, marker[0] + 7, marker[1] + 7),
        fill=(255, 233, 164, 230),
    )
    draw.text(
        (right - 38, 790),
        "50%",
        font=font(label_size),
        fill=(174, 195, 201, 165),
    )
    draw.text(
        (left, bottom + 12),
        "1984—2024",
        font=font(label_size),
        fill=(174, 195, 201, 150),
    )
    draw.text(
        (right - 24, bottom + 12),
        "0%",
        font=font(label_size),
        fill=(174, 195, 201, 165),
    )
    canvas.alpha_composite(overlay)


def draw_current_legend(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.text(
        (x, y - 58),
        "해빙 연령 추정",
        font=font(19, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (x, y - 31),
        "밝고 높은 블록일수록 오래된 얼음",
        font=font(14),
        fill=(144, 177, 187),
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    labels = ("1년차", "2년차", "3년차", "4년차", "5년차+")
    for index, label in enumerate(labels):
        left = x + index * 112
        draw.rounded_rectangle(
            (left, y, left + 92, y + 14),
            radius=7,
            fill=AGE_COLORS[index + 1],
        )
        draw.text(
            (left, y + 22),
            label,
            font=font(14, bold=True),
            fill=MUTED,
            stroke_width=1,
            stroke_fill=(4, 13, 19),
        )


def compose_current_frame(
    map_image: Image.Image,
    rows: list[dict[str, str]],
    year: int,
) -> Image.Image:
    canvas = gradient_background().convert("RGBA")
    canvas.alpha_composite(map_image)
    draw = ImageDraw.Draw(canvas)
    row = next(item for item in rows if int(item["year"]) == year)
    percentage = float(row["multiyear_fraction"]) * 100

    draw.text((64, 38), str(year), font=font(82, bold=True), fill=TEXT)
    draw.text((283, 82), "/ 11주차", font=font(27, bold=True), fill=(44, 200, 217))
    draw_current_legend(draw, 68, 949)
    draw.text(
        (68, 1012),
        "높이도 해빙 연령 표현 · 실제 두께 아님 · 연도 사이는 시각적 보간",
        font=font(14),
        fill=(73, 106, 118),
    )

    draw_overlay_graph(canvas, rows, float(year))
    draw = ImageDraw.Draw(canvas)
    metric_x = 1435
    draw.text(
        (metric_x, 798),
        "여름을 견딘 얼음",
        font=font(22, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 835),
        f"{percentage:.1f}%",
        font=font(54, bold=True),
        fill=(255, 233, 164),
        stroke_width=3,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 910),
        "2년차 이상 격자 / 전체 해빙 격자",
        font=font(16),
        fill=MUTED,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (1855, 1054),
        "Data · NSIDC-0611 V4.1",
        font=font(14),
        fill=(66, 96, 107),
        anchor="ra",
    )
    return canvas.convert("RGB")


def draw_readable_legend(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.text(
        (x, y - 66),
        "해빙 연령 추정",
        font=font(23, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (x, y - 34),
        "밝고 높은 블록일수록 오래된 얼음",
        font=font(17),
        fill=(157, 187, 196),
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    labels = ("1년차", "2년차", "3년차", "4년차", "5년차+")
    for index, label in enumerate(labels):
        left = x + index * 118
        draw.rounded_rectangle(
            (left, y, left + 98, y + 16),
            radius=8,
            fill=AGE_COLORS[index + 1],
        )
        draw.text(
            (left, y + 23),
            label,
            font=font(16, bold=True),
            fill=(137, 169, 179),
            stroke_width=1,
            stroke_fill=(4, 13, 19),
        )


def compose_feedback_frame(
    map_image: Image.Image,
    rows: list[dict[str, str]],
    year: int,
) -> Image.Image:
    background = gradient_background().convert("RGBA")
    background.alpha_composite(map_image)
    canvas = background
    draw = ImageDraw.Draw(canvas)

    row = next(item for item in rows if int(item["year"]) == year)
    percentage = float(row["multiyear_fraction"]) * 100

    # The intro already establishes that every frame compares the same week.
    draw.text((64, 38), str(year), font=font(82, bold=True), fill=TEXT)

    draw_readable_legend(draw, 68, 944)
    draw.text(
        (68, 1024),
        "높이는 실제 두께가 아닌 해빙 연령 · 연도 사이는 시각적 보간",
        font=font(16),
        fill=(91, 123, 134),
    )

    draw_overlay_graph(canvas, rows, float(year), label_size=16)
    draw = ImageDraw.Draw(canvas)
    metric_x = 1435
    draw.text(
        (metric_x, 790),
        "전체 해빙 중",
        font=font(18, bold=True),
        fill=(154, 183, 191),
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 819),
        "여름을 견딘 얼음",
        font=font(25, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 858),
        f"{percentage:.1f}%",
        font=font(58, bold=True),
        fill=(255, 233, 164),
        stroke_width=3,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (1855, 1052),
        "Data · NSIDC-0611 V4.1",
        font=font(16),
        fill=(82, 113, 123),
        anchor="ra",
    )
    return canvas.convert("RGB")


def build_comparison(current: Image.Image, demo: Image.Image) -> Image.Image:
    comparison = Image.new("RGB", (CANVAS[0] * 2, CANVAS[1] + 80), (3, 10, 16))
    draw = ImageDraw.Draw(comparison)
    draw.text((40, 24), "현재 V6", font=font(24, bold=True), fill=TEXT)
    draw.text(
        (CANVAS[0] + 40, 24),
        "피드백 선별 반영 데모",
        font=font(24, bold=True),
        fill=TEXT,
    )
    comparison.paste(current, (0, 80))
    comparison.paste(demo, (CANVAS[0], 80))
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2013)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = summary_rows()
    map_path = MAP_OUTPUT / f"map-3d-{args.year}.png"
    map_image = Image.open(map_path).convert("RGBA")
    if map_image.size != CANVAS:
        raise ValueError(f"Unexpected map dimensions: {map_image.size}")

    args.output.mkdir(parents=True, exist_ok=True)
    current = compose_current_frame(map_image, rows, args.year)
    demo = compose_feedback_frame(map_image, rows, args.year)
    current.save(args.output / f"current-v6-{args.year}.png")
    demo.save(args.output / f"feedback-demo-{args.year}.png")
    build_comparison(current, demo).save(
        args.output / f"compare-current-feedback-{args.year}.png"
    )
    print(f"wrote feedback demo for {args.year} to {args.output}")


if __name__ == "__main__":
    main()
