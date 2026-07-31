from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from polar_memory.preprocess import LAND, PREVIEW_RGBA, UNCALCULATED_OCEAN

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/design-v3"
FONT_ROOT = Path("/usr/share/fonts/google-noto-sans-cjk-fonts")
FONT_REGULAR = FONT_ROOT / "NotoSansCJK-Regular.ttc"
FONT_BOLD = FONT_ROOT / "NotoSansCJK-Bold.ttc"

CANVAS = (1920, 1080)
BACKGROUND = (5, 14, 21)
TEXT = (237, 243, 243)
MUTED = (113, 145, 156)
GRID = (24, 47, 57)
LAND_COLOR = (31, 42, 49, 255)

AGE_COLORS = {
    1: (47, 107, 255, 255),
    2: (44, 200, 217, 255),
    3: (53, 196, 122, 255),
    4: (242, 193, 78, 255),
    5: (255, 107, 53, 255),
}
AGE_LABELS = ("0–1년", "1–2년", "2–3년", "3–4년", "4년 초과")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def load_rows() -> list[dict[str, str]]:
    with (ROOT / "data/processed/summary.csv").open(encoding="utf-8") as source:
        return list(csv.DictReader(source))


def remap(year: int, size: int) -> Image.Image:
    path = ROOT / f"data/processed/snapshots/preview/{year}.png"
    source = np.asarray(Image.open(path).convert("RGB"))
    rgba = np.zeros((*source.shape[:2], 4), dtype=np.uint8)
    for age_class, source_color in PREVIEW_RGBA.items():
        mask = np.all(source == source_color[:3], axis=-1)
        if age_class in AGE_COLORS:
            rgba[mask] = AGE_COLORS[age_class]
        elif age_class == LAND:
            rgba[mask] = LAND_COLOR
        elif age_class in {0, UNCALCULATED_OCEAN}:
            rgba[mask] = (0, 0, 0, 0)
    return Image.fromarray(rgba, mode="RGBA").resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )


def draw_polar_grid(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    radius = (right - left) / 2
    for fraction in (0.33, 0.66, 0.98):
        current = radius * fraction
        draw.ellipse(
            (
                center_x - current,
                center_y - current,
                center_x + current,
                center_y + current,
            ),
            outline=GRID,
            width=1,
        )
    for angle in range(0, 180, 30):
        radians = np.deg2rad(angle)
        dx = np.cos(radians) * radius
        dy = np.sin(radians) * radius
        draw.line(
            (center_x - dx, center_y - dy, center_x + dx, center_y + dy),
            fill=GRID,
            width=1,
        )


def draw_legend(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    compact: bool = False,
) -> None:
    draw.text((x, y - 38), "색은 해빙 연령", font=font(18, bold=True), fill=TEXT)
    width = 112 if compact else 132
    for index, label in enumerate(AGE_LABELS):
        left = x + index * width
        draw.rounded_rectangle(
            (left, y, left + 76, y + 14),
            radius=7,
            fill=AGE_COLORS[index + 1][:3],
        )
        draw.text((left, y + 24), label, font=font(15), fill=MUTED)


def draw_graph(
    draw: ImageDraw.ImageDraw,
    rows: list[dict[str, str]],
    current_index: int,
    *,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    values = [float(row["multiyear_fraction"]) for row in rows]
    low, high = 0.18, 0.50

    def point(index: int, value: float) -> tuple[float, float]:
        x = left + index / (len(rows) - 1) * (right - left)
        y = bottom - (value - low) / (high - low) * (bottom - top)
        return x, y

    points = [point(index, value) for index, value in enumerate(values)]
    for level in (0.2, 0.3, 0.4, 0.5):
        y = bottom - (level - low) / (high - low) * (bottom - top)
        draw.line((left, y, right, y), fill=GRID, width=1)
    draw.line(points, fill=(47, 73, 84), width=3, joint="curve")
    progress = points[: current_index + 1]
    if len(progress) > 1:
        draw.line(progress, fill=(44, 200, 217), width=5, joint="curve")
    marker = points[current_index]
    draw.ellipse(
        (marker[0] - 8, marker[1] - 8, marker[0] + 8, marker[1] + 8),
        fill=(255, 233, 164),
    )
    for x, label in ((left, "1984"), ((left + right) / 2, "2004"), (right - 44, "2024")):
        draw.text((x, bottom + 16), label, font=font(15), fill=MUTED)


def annual_frame(rows: list[dict[str, str]], year: int) -> Image.Image:
    index = next(i for i, row in enumerate(rows) if int(row["year"]) == year)
    row = rows[index]
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    draw.text((62, 34), str(year), font=font(82, bold=True), fill=TEXT)
    draw.text((282, 77), "/ 11주차", font=font(27, bold=True), fill=(44, 200, 217))

    map_box = (55, 125, 995, 1065)
    draw_polar_grid(draw, map_box)
    map_image = remap(year, 940)
    canvas.paste(map_image, map_box[:2], map_image)

    right = 1100
    draw.text((right, 160), "여름을 견딘 얼음", font=font(32, bold=True), fill=TEXT)
    draw.text(
        (right, 210),
        "2년차 이상 / 전체 해빙 범위",
        font=font(19),
        fill=MUTED,
    )
    draw.text(
        (right - 6, 245),
        f"{float(row['multiyear_fraction']) * 100:.1f}",
        font=font(112, bold=True),
        fill=TEXT,
    )
    draw.text((right + 275, 324), "%", font=font(32, bold=True), fill=MUTED)

    draw.text((right, 520), "1984—2024 변화", font=font(22, bold=True), fill=TEXT)
    draw_graph(draw, rows, index, box=(right, 580, 1840, 820))
    draw_legend(draw, x=right, y=925, compact=True)
    draw.text(
        (right, 1030),
        "NSIDC-0611 V4.1 · 연도 사이는 시각적 보간",
        font=font(14),
        fill=(67, 96, 107),
    )
    return canvas


def comparison_frame(rows: list[dict[str, str]]) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    first = rows[0]
    last = rows[-1]

    draw.text(
        (70, 45),
        "범위가 비슷해도, 얼음의 시간은 다르다",
        font=font(46, bold=True),
        fill=TEXT,
    )
    draw.text(
        (72, 112),
        "같은 제11주 · 같은 투영 · 같은 색상 기준",
        font=font(19),
        fill=MUTED,
    )

    for x, year, row in ((100, 1984, first), (1030, 2024, last)):
        draw.text((x, 175), str(year), font=font(50, bold=True), fill=TEXT)
        image = remap(year, 700)
        canvas.paste(image, (x, 245), image)
        value = float(row["multiyear_fraction"]) * 100
        draw.text(
            (x, 920),
            f"여름을 견딘 얼음  {value:.1f}%",
            font=font(28, bold=True),
            fill=(255, 233, 164),
        )
    draw.line((960, 190, 960, 990), fill=GRID, width=1)
    draw_legend(draw, x=660, y=1010, compact=True)
    return canvas


def outro_frame() -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    draw.text(
        (78, 190),
        "해빙은 북극 생물이 살아가는 공간이자",
        font=font(48, bold=True),
        fill=TEXT,
    )
    draw.text(
        (78, 260),
        "바다와 대기를 잇는 경계다.",
        font=font(48, bold=True),
        fill=TEXT,
    )
    draw.line((80, 355, 710, 355), fill=(44, 200, 217), width=4)
    draw.text(
        (82, 415),
        "오래된 얼음의 감소는 단순히 흰 범위가 줄어든 것이 아니라\n"
        "그 환경의 구조가 바뀌고 있음을 보여준다.",
        font=font(27),
        fill=(157, 183, 191),
        spacing=16,
    )

    for x, year in ((1080, 1984), (1500, 2024)):
        image = remap(year, 380)
        canvas.paste(image, (x, 250), image)
        draw.text((x, 205), str(year), font=font(34, bold=True), fill=TEXT)
    draw.text(
        (1080, 665),
        "여러 여름을 견딘 얼음",
        font=font(21, bold=True),
        fill=(255, 233, 164),
    )
    draw_legend(draw, x=1080, y=745, compact=True)
    draw.text(
        (82, 1005),
        "근거 · NOAA Arctic Report Card 2024  |  Data · NSIDC-0611 V4.1",
        font=font(16),
        fill=(70, 101, 112),
    )
    return canvas


def storyboard(frames: list[tuple[str, Image.Image]]) -> Image.Image:
    canvas = Image.new("RGB", (1920, 700), (11, 21, 28))
    draw = ImageDraw.Draw(canvas)
    notes = (
        "연도·주차 중심 화면",
        "과거와 현재 비교",
        "근거가 있는 환경 메시지",
    )
    for index, ((label, frame), note) in enumerate(zip(frames, notes)):
        x = index * 640
        draw.text((x + 24, 28), label, font=font(24, bold=True), fill=TEXT)
        preview = frame.resize((600, 338), Image.Resampling.LANCZOS)
        canvas.paste(preview, (x + 20, 85))
        draw.text((x + 24, 455), note, font=font(20, bold=True), fill=TEXT)
    draw.text(
        (24, 625),
        "DESIGN V3 · HEADER 제거 · 고대비 연령색 · 우측 하단 추세 · 연속 전환",
        font=font(18),
        fill=MUTED,
    )
    return canvas


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    annual = annual_frame(rows, 2013)
    comparison = comparison_frame(rows)
    outro = outro_frame()
    annual.save(OUTPUT / "mockup-2013.png")
    comparison.save(OUTPUT / "mockup-comparison.png")
    outro.save(OUTPUT / "mockup-outro.png")
    storyboard(
        [
            ("01 · 2013 / 11주차", annual),
            ("02 · 1984 ↔ 2024", comparison),
            ("03 · 환경·생태 메시지", outro),
        ]
    ).save(OUTPUT / "storyboard.png")
    print(OUTPUT)


if __name__ == "__main__":
    main()
