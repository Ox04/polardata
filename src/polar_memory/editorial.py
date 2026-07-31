from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from polar_memory.compose import read_summary
from polar_memory.preprocess import LAND, PREVIEW_RGBA, UNCALCULATED_OCEAN

CANVAS = (1920, 1080)
BACKGROUND = (7, 16, 24)
MAP_SIZE = 900
MAP_POSITION = (160, 130)
SIDEBAR_LEFT = 1260

FONT_REGULAR = Path(
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Regular.ttc"
)
FONT_BOLD = Path(
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Bold.ttc"
)

TARGET_COLORS = {
    1: (84, 145, 170, 255),
    2: (119, 172, 190, 255),
    3: (158, 198, 208, 255),
    4: (202, 222, 224, 255),
    5: (247, 239, 211, 255),
    LAND: (31, 43, 51, 255),
    UNCALCULATED_OCEAN: (0, 0, 0, 0),
    0: (0, 0, 0, 0),
}


@dataclass(frozen=True)
class TimelinePoint:
    year: int
    multiyear_fraction: float
    fifth_year_plus_cells: int


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _load_points(summary_csv: str | Path) -> list[TimelinePoint]:
    rows = read_summary(summary_csv)
    return [
        TimelinePoint(
            year=int(year),
            multiyear_fraction=float(row["multiyear_fraction"]),
            fifth_year_plus_cells=int(row["fifth_year_plus_cells"]),
        )
        for year, row in sorted(rows.items())
    ]


def _remap_preview(path: Path) -> Image.Image:
    source = np.asarray(Image.open(path).convert("RGB"))
    rgba = np.zeros((*source.shape[:2], 4), dtype=np.uint8)
    for age_class, source_color in PREVIEW_RGBA.items():
        mask = np.all(source == source_color[:3], axis=-1)
        rgba[mask] = TARGET_COLORS[age_class]
    return Image.fromarray(rgba, mode="RGBA").resize(
        (MAP_SIZE, MAP_SIZE),
        Image.Resampling.LANCZOS,
    )


def _base_canvas(
    *,
    metadata: str = "ARCTIC SEA ICE AGE  ·  MARCH / WEEK 11  ·  1984—2024",
) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title = _font(FONT_BOLD, 44)
    label = _font(FONT_REGULAR, 18)

    draw.text((62, 40), "북극의 기억층", font=title, fill=(235, 241, 241))
    draw.text(
        (430, 58),
        metadata,
        font=label,
        fill=(104, 138, 151),
    )
    draw.line((62, 105, 1858, 105), fill=(38, 61, 72), width=1)
    draw.line((1225, 130, 1225, 1022), fill=(38, 61, 72), width=1)

    center_x = MAP_POSITION[0] + MAP_SIZE / 2
    center_y = MAP_POSITION[1] + MAP_SIZE / 2
    grid_color = (24, 48, 61)
    for radius in (150, 300, 445):
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            outline=grid_color,
            width=1,
        )
    for angle in range(0, 180, 30):
        radians = np.deg2rad(angle)
        dx = np.cos(radians) * 445
        dy = np.sin(radians) * 445
        draw.line(
            (center_x - dx, center_y - dy, center_x + dx, center_y + dy),
            fill=grid_color,
            width=1,
        )
    return canvas


def _chart_coordinates(
    points: list[TimelinePoint],
    index: int,
    transition: float,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], tuple[float, float]]:
    left, top, right, bottom = 1290, 535, 1845, 745
    minimum, maximum = 0.18, 0.50

    def coordinate(position: float, value: float) -> tuple[float, float]:
        x = left + position / (len(points) - 1) * (right - left)
        y = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
        return x, y

    all_points = [
        coordinate(position, point.multiyear_fraction)
        for position, point in enumerate(points)
    ]
    progress = all_points[: index + 1]
    marker = progress[-1]
    if index < len(points) - 1 and transition > 0:
        value = (
            points[index].multiyear_fraction * (1 - transition)
            + points[index + 1].multiyear_fraction * transition
        )
        marker = coordinate(index + transition, value)
        progress.append(marker)
    return all_points, progress, marker


def _draw_sidebar(
    canvas: Image.Image,
    points: list[TimelinePoint],
    index: int,
    transition: float,
) -> None:
    draw = ImageDraw.Draw(canvas)
    year_font = _font(FONT_BOLD, 126)
    metric_font = _font(FONT_BOLD, 74)
    heading_font = _font(FONT_BOLD, 21)
    body_font = _font(FONT_REGULAR, 18)
    small_font = _font(FONT_REGULAR, 15)

    current = points[index]
    following = points[min(index + 1, len(points) - 1)]
    interpolated_fraction = (
        current.multiyear_fraction * (1 - transition)
        + following.multiyear_fraction * transition
    )
    interpolated_old_ice = round(
        current.fifth_year_plus_cells * (1 - transition)
        + following.fifth_year_plus_cells * transition
    )
    display_year = current.year if transition < 0.5 else following.year

    draw.text(
        (SIDEBAR_LEFT, 130),
        str(display_year),
        font=year_font,
        fill=(235, 241, 241),
    )
    draw.text(
        (SIDEBAR_LEFT + 6, 280),
        "동일한 계절 · 제11주",
        font=body_font,
        fill=(104, 138, 151),
    )

    draw.text(
        (SIDEBAR_LEFT, 350),
        "다년생 해빙 비율",
        font=heading_font,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT, 382),
        f"{interpolated_fraction * 100:.1f}",
        font=metric_font,
        fill=(235, 241, 241),
    )
    draw.text(
        (SIDEBAR_LEFT + 190, 421),
        "%",
        font=heading_font,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT + 300, 407),
        f"5년 이상 얼음\n{interpolated_old_ice:,} 격자",
        font=body_font,
        fill=(175, 196, 201),
        spacing=6,
    )

    chart_left, chart_top, chart_right, chart_bottom = 1290, 535, 1845, 745
    for percentage in (20, 30, 40, 50):
        y = chart_bottom - (percentage / 100 - 0.18) / 0.32 * (
            chart_bottom - chart_top
        )
        draw.line(
            (chart_left, y, chart_right, y),
            fill=(24, 48, 61),
            width=1,
        )
        draw.text(
            (chart_left - 46, y - 10),
            f"{percentage}%",
            font=small_font,
            fill=(78, 108, 120),
        )

    all_points, progress, marker = _chart_coordinates(points, index, transition)
    draw.line(all_points, fill=(44, 67, 78), width=3, joint="curve")
    if len(progress) > 1:
        draw.line(progress, fill=(104, 202, 226), width=4, joint="curve")
    radius = 6
    draw.ellipse(
        (
            marker[0] - radius,
            marker[1] - radius,
            marker[0] + radius,
            marker[1] + radius,
        ),
        fill=(247, 239, 211),
    )
    for position, label in ((chart_left, "1984"), (1568, "2004"), (1802, "2024")):
        draw.text(
            (position, chart_bottom + 18),
            label,
            font=small_font,
            fill=(78, 108, 120),
        )

    legend_y = 835
    draw.text(
        (SIDEBAR_LEFT, legend_y - 42),
        "해빙 연령",
        font=heading_font,
        fill=(135, 172, 186),
    )
    labels = ("1년", "2년", "3년", "4년", "5년+")
    for offset, (age_class, label) in enumerate(zip(range(1, 6), labels)):
        x = SIDEBAR_LEFT + offset * 112
        color = TARGET_COLORS[age_class][:3]
        draw.rectangle((x, legend_y, x + 54, legend_y + 12), fill=color)
        draw.text(
            (x, legend_y + 22),
            label,
            font=small_font,
            fill=(150, 174, 183),
        )

    draw.text(
        (SIDEBAR_LEFT, 930),
        "사라지는 것은 얼음의 넓이만이 아니다.",
        font=heading_font,
        fill=(235, 241, 241),
    )
    draw.text(
        (SIDEBAR_LEFT, 968),
        "여러 여름을 견딘 북극의 시간이 사라지고 있다.",
        font=body_font,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT, 1030),
        "NSIDC-0611 V4.1 · 연도 사이 화면은 시각적 보간",
        font=small_font,
        fill=(70, 99, 111),
    )


def render_editorial_frame(
    base: Image.Image,
    map_image: Image.Image,
    points: list[TimelinePoint],
    index: int,
    transition: float,
) -> Image.Image:
    canvas = base.copy()
    canvas.paste(map_image, MAP_POSITION, map_image)
    _draw_sidebar(canvas, points, index, transition)
    return canvas


def render_editorial_video(
    preview_directory: str | Path,
    summary_csv: str | Path,
    output: str | Path,
    stills_directory: str | Path,
    *,
    frame_rate: int = 30,
    transition_frames: int = 14,
    hold_frames: int = 4,
) -> Path:
    points = _load_points(summary_csv)
    preview_root = Path(preview_directory)
    maps = {
        point.year: _remap_preview(preview_root / f"{point.year}.png")
        for point in points
    }
    base = _base_canvas()

    stills_root = Path(stills_directory)
    stills_root.mkdir(parents=True, exist_ok=True)
    for year in (points[0].year, points[len(points) // 2].year, points[-1].year):
        index = next(i for i, point in enumerate(points) if point.year == year)
        frame = render_editorial_frame(base, maps[year], points, index, 0.0)
        frame.save(stills_root / f"{year}.png")

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{CANVAS[0]}x{CANVAS[1]}",
            "-r",
            str(frame_rate),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ],
        stdin=subprocess.PIPE,
    )
    if process.stdin is None:
        raise RuntimeError("FFmpeg 입력 파이프를 열지 못했습니다.")

    def write(frame: Image.Image, count: int = 1) -> None:
        payload = frame.tobytes()
        for _ in range(count):
            process.stdin.write(payload)

    first = render_editorial_frame(base, maps[points[0].year], points, 0, 0.0)
    write(first, frame_rate)
    for index in range(len(points) - 1):
        current = render_editorial_frame(
            base,
            maps[points[index].year],
            points,
            index,
            0.0,
        )
        write(current, hold_frames)
        for step in range(1, transition_frames + 1):
            linear = step / transition_frames
            eased = linear * linear * (3 - 2 * linear)
            blended_map = Image.blend(
                maps[points[index].year],
                maps[points[index + 1].year],
                eased,
            )
            write(
                render_editorial_frame(
                    base,
                    blended_map,
                    points,
                    index,
                    eased,
                )
            )
    last = render_editorial_frame(
        base,
        maps[points[-1].year],
        points,
        len(points) - 1,
        0.0,
    )
    write(last, frame_rate)
    process.stdin.close()
    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, process.args)
    return target
