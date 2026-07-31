from __future__ import annotations

import argparse
import csv
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/design-v4"
FONT_ROOT = ROOT / "assets/fonts/wanted-sans"
FONT_REGULAR = FONT_ROOT / "WantedSans-Regular.ttf"
FONT_BOLD = FONT_ROOT / "WantedSans-Bold.ttf"

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


@cache
def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def read_classes(year: int, stride: int) -> np.ndarray:
    from polar_memory.preprocess import PREVIEW_RGBA, UNCALCULATED_OCEAN

    path = ROOT / f"data/processed/snapshots/preview/{year}.png"
    source = np.asarray(Image.open(path).convert("RGB"))
    classes = np.full(source.shape[:2], UNCALCULATED_OCEAN, dtype=np.uint8)
    for age_class, source_color in PREVIEW_RGBA.items():
        mask = np.all(source == source_color[:3], axis=-1)
        classes[mask] = age_class
    return classes[::stride, ::stride]


def prepare(year: int, stride: int, output: Path = OUTPUT) -> None:
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / f"{year}-classes.npy", read_classes(year, stride))


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


def summary_rows() -> list[dict[str, str]]:
    with (ROOT / "data/processed/summary.csv").open(encoding="utf-8") as source:
        return list(csv.DictReader(source))


def draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
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


def draw_overlay_graph(
    canvas: Image.Image,
    rows: list[dict[str, str]],
    current_year: float,
) -> None:
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    left, top, right, bottom = 1430, 925, 1855, 1020
    values = [float(row["multiyear_fraction"]) for row in rows]
    low, high = 0.0, 0.50
    first_year = int(rows[0]["year"])
    last_year = int(rows[-1]["year"])
    current_year = min(max(current_year, first_year), last_year)
    current_position = current_year - first_year
    current_index = min(int(current_position), len(rows) - 1)
    transition = current_position - current_index

    def point(index: int, value: float) -> tuple[float, float]:
        x = left + index / (len(rows) - 1) * (right - left)
        y = bottom - (value - low) / (high - low) * (bottom - top)
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
    area = [(left, bottom), *points, (right, bottom)]
    draw.polygon(area, fill=(36, 126, 169, 47))
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
        font=font(16),
        fill=(174, 195, 201, 165),
    )
    draw.text(
        (left, bottom + 12),
        "1984—2024",
        font=font(16),
        fill=(174, 195, 201, 150),
    )
    draw.text(
        (right - 24, bottom + 12),
        "0%",
        font=font(16),
        fill=(174, 195, 201, 165),
    )
    canvas.alpha_composite(overlay)


def compose(year: int, variant: str) -> None:
    suffix = "" if variant == "block" else "-smooth"
    render = Image.open(OUTPUT / f"map-3d{suffix}-{year}.png").convert("RGBA")
    background = gradient_background().convert("RGBA")
    background.alpha_composite(render)
    canvas = background
    draw = ImageDraw.Draw(canvas)
    rows = summary_rows()
    row = next(row for row in rows if int(row["year"]) == year)
    percentage = float(row["multiyear_fraction"]) * 100

    draw.text((64, 38), str(year), font=font(82, bold=True), fill=TEXT)

    draw_legend(draw, 68, 944)
    draw.text(
        (68, 1024),
        "높이는 실제 두께가 아닌 해빙 연령 · 연도 사이는 시각적 보간",
        font=font(16),
        fill=(91, 123, 134),
    )

    draw_overlay_graph(canvas, rows, year)
    draw = ImageDraw.Draw(canvas)
    metric_x = 1435
    draw.text(
        (metric_x, 786),
        "전체 해빙 중",
        font=font(18, bold=True),
        fill=(154, 183, 191),
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 812),
        "여름을 견딘 얼음",
        font=font(25, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
    )
    draw.text(
        (metric_x, 844),
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

    target = OUTPUT / f"mockup{suffix}-{year}.png"
    canvas.convert("RGB").save(target)

    if variant == "smooth":
        block = Image.open(OUTPUT / f"mockup-{year}.png").convert("RGB")
        comparison = Image.new("RGB", (1920, 650), (10, 20, 27))
        compare_draw = ImageDraw.Draw(comparison)
        compare_draw.text(
            (32, 24), "A · 블록형", font=font(24, bold=True), fill=TEXT
        )
        compare_draw.text(
            (992, 24), "B · 연속 표면형", font=font(24, bold=True), fill=TEXT
        )
        comparison.paste(block.resize((920, 518), Image.Resampling.LANCZOS), (20, 78))
        comparison.paste(
            canvas.convert("RGB").resize((920, 518), Image.Resampling.LANCZOS),
            (980, 78),
        )
        compare_draw.text(
            (32, 615),
            "같은 데이터 · 같은 색상 · 같은 카메라 | 차이는 3D 표면 연결 방식뿐",
            font=font(17),
            fill=MUTED,
        )
        comparison.save(OUTPUT / "compare-block-smooth.png")
        return

    previous = Image.open(ROOT / "outputs/design-v3/mockup-2013.png").convert("RGB")
    comparison = Image.new("RGB", (1920, 650), (10, 20, 27))
    compare_draw = ImageDraw.Draw(comparison)
    compare_draw.text((32, 24), "V3 · 패널 중심", font=font(24, bold=True), fill=TEXT)
    compare_draw.text((992, 24), "V4 · 데이터 부조 중심", font=font(24, bold=True), fill=TEXT)
    comparison.paste(previous.resize((920, 518), Image.Resampling.LANCZOS), (20, 78))
    comparison.paste(
        canvas.convert("RGB").resize((920, 518), Image.Resampling.LANCZOS),
        (980, 78),
    )
    compare_draw.text(
        (32, 615),
        "지도 점유율 확대 · 상시 그래프 제거 · 낮은 3D 연령층",
        font=font(17),
        fill=MUTED,
    )
    comparison.save(OUTPUT / "compare-v3-v4.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "prepare-range", "compose"))
    parser.add_argument("--year", type=int, default=2013)
    parser.add_argument("--start-year", type=int, default=1984)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--stride", type=int, default=3)
    parser.add_argument("--variant", choices=("block", "smooth"), default="block")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "prepare":
        prepare(args.year, args.stride, args.output)
    elif args.command == "prepare-range":
        for year in range(args.start_year, args.end_year + 1):
            prepare(year, args.stride, args.output)
    else:
        compose(args.year, args.variant)


if __name__ == "__main__":
    main()
