from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from polar_memory.editorial import (
    BACKGROUND,
    CANVAS,
    FONT_BOLD,
    FONT_REGULAR,
    MAP_POSITION,
    SIDEBAR_LEFT,
    _base_canvas,
    _font,
    _remap_preview,
)

FRAME_RATE = 30


@dataclass(frozen=True)
class SeasonalPoint:
    week: int
    ice_area_km2: float
    multiyear_fraction: float


def _encode_frames(frames, output: Path, frame_rate: int = FRAME_RATE) -> float:
    output.parent.mkdir(parents=True, exist_ok=True)
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
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    if process.stdin is None:
        raise RuntimeError("FFmpeg 입력 파이프를 열지 못했습니다.")

    frame_count = 0
    for frame in frames:
        process.stdin.write(frame.convert("RGB").tobytes())
        frame_count += 1
    process.stdin.close()
    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, process.args)
    return frame_count / frame_rate


def _repeat(frame: Image.Image, count: int):
    for _ in range(count):
        yield frame


def _intro_frame() -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    eyebrow = _font(FONT_REGULAR, 22)
    title = _font(FONT_BOLD, 92)
    subtitle = _font(FONT_REGULAR, 32)
    small = _font(FONT_REGULAR, 18)

    draw.text(
        (112, 260),
        "ARCTIC SEA ICE AGE · 1984—2024",
        font=eyebrow,
        fill=(104, 138, 151),
    )
    draw.text((102, 320), "북극의 기억층", font=title, fill=(235, 241, 241))
    draw.line((110, 460, 770, 460), fill=(104, 202, 226), width=4)
    draw.text(
        (112, 515),
        "같은 넓이 속에서 사라지는 오래된 얼음의 시간",
        font=subtitle,
        fill=(151, 181, 192),
    )
    draw.text(
        (112, 995),
        "NSIDC-0611 Sea Ice Age V4.1",
        font=small,
        fill=(65, 94, 106),
    )
    return canvas


def _outro_frame() -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    eyebrow = _font(FONT_REGULAR, 22)
    title = _font(FONT_BOLD, 66)
    subtitle = _font(FONT_REGULAR, 30)
    small = _font(FONT_REGULAR, 17)

    draw.text(
        (112, 250),
        "THE ARCTIC IS LOSING MORE THAN AREA",
        font=eyebrow,
        fill=(104, 202, 226),
    )
    draw.text(
        (104, 320),
        "사라진 것은 얼음의 넓이만이 아니다.",
        font=title,
        fill=(235, 241, 241),
    )
    draw.text(
        (112, 450),
        "여러 여름을 견딘 얼음이 사라질수록\n"
        "북극 생태계가 의지해 온 오래된 환경도 함께 약해진다.",
        font=subtitle,
        fill=(151, 181, 192),
        spacing=18,
    )
    draw.line((112, 650, 840, 650), fill=(247, 239, 211), width=3)
    draw.text(
        (112, 990),
        "Data · NSIDC-0611 V4.1   |   DOI · 10.5067/UTAV7490FEPB",
        font=small,
        fill=(65, 94, 106),
    )
    return canvas


def _load_seasonal_points(path: Path) -> list[SeasonalPoint]:
    with path.open(encoding="utf-8") as file:
        return [
            SeasonalPoint(
                week=int(row["week"]),
                ice_area_km2=float(row["ice_area_km2"]),
                multiyear_fraction=float(row["multiyear_fraction"]),
            )
            for row in csv.DictReader(file)
        ]


def _seasonal_frame(
    base: Image.Image,
    map_image: Image.Image,
    points: list[SeasonalPoint],
    index: int,
    transition: float,
) -> Image.Image:
    canvas = base.copy()
    canvas.paste(map_image, MAP_POSITION, map_image)
    draw = ImageDraw.Draw(canvas)
    heading = _font(FONT_BOLD, 22)
    week_font = _font(FONT_BOLD, 98)
    metric_font = _font(FONT_BOLD, 66)
    body = _font(FONT_REGULAR, 18)
    small = _font(FONT_REGULAR, 15)

    current = points[index]
    following = points[min(index + 1, len(points) - 1)]
    week = current.week if transition < 0.5 else following.week
    area = (
        current.ice_area_km2 * (1 - transition)
        + following.ice_area_km2 * transition
    )
    multiyear = (
        current.multiyear_fraction * (1 - transition)
        + following.multiyear_fraction * transition
    )

    draw.text((SIDEBAR_LEFT, 140), "2024", font=week_font, fill=(235, 241, 241))
    draw.text(
        (SIDEBAR_LEFT, 270),
        f"WEEK {week:02d}",
        font=heading,
        fill=(104, 202, 226),
    )
    draw.text(
        (SIDEBAR_LEFT, 340),
        "북극 해빙 범위",
        font=heading,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT, 382),
        f"{area / 1_000_000:.2f}",
        font=metric_font,
        fill=(235, 241, 241),
    )
    draw.text(
        (SIDEBAR_LEFT + 205, 420),
        "백만 km²",
        font=body,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT + 365, 401),
        f"다년생 얼음\n{multiyear * 100:.1f}%",
        font=body,
        fill=(175, 196, 201),
        spacing=6,
    )

    left, top, right, bottom = 1290, 535, 1845, 745
    values = [point.ice_area_km2 / 1_000_000 for point in points]
    minimum = min(values) - 0.4
    maximum = max(values) + 0.4

    def coordinate(position: float, value: float) -> tuple[float, float]:
        x = left + position / (len(points) - 1) * (right - left)
        y = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
        return x, y

    all_coordinates = [
        coordinate(position, value) for position, value in enumerate(values)
    ]
    progress = all_coordinates[: index + 1]
    marker = progress[-1]
    if index < len(points) - 1 and transition > 0:
        interpolated = values[index] * (1 - transition) + values[index + 1] * transition
        marker = coordinate(index + transition, interpolated)
        progress.append(marker)

    for fraction in (0.0, 0.5, 1.0):
        y = bottom - fraction * (bottom - top)
        label = minimum + fraction * (maximum - minimum)
        draw.line((left, y, right, y), fill=(24, 48, 61), width=1)
        draw.text(
            (left - 58, y - 10),
            f"{label:.1f}",
            font=small,
            fill=(78, 108, 120),
        )
    draw.line(all_coordinates, fill=(44, 67, 78), width=3, joint="curve")
    if len(progress) > 1:
        draw.line(progress, fill=(104, 202, 226), width=4, joint="curve")
    draw.ellipse(
        (marker[0] - 6, marker[1] - 6, marker[0] + 6, marker[1] + 6),
        fill=(247, 239, 211),
    )
    for x, label in ((left, "1주"), (1555, "26주"), (1800, "52주")):
        draw.text((x, bottom + 18), label, font=small, fill=(78, 108, 120))

    draw.text(
        (SIDEBAR_LEFT, 815),
        "계절의 호흡",
        font=heading,
        fill=(135, 172, 186),
    )
    draw.text(
        (SIDEBAR_LEFT, 865),
        "얼음은 겨울마다 넓어지고 여름마다 줄어든다.",
        font=body,
        fill=(235, 241, 241),
    )
    draw.text(
        (SIDEBAR_LEFT, 905),
        "하지만 한 번 사라진 오래된 얼음의 시간은\n"
        "다음 겨울에 곧바로 돌아오지 않는다.",
        font=body,
        fill=(135, 172, 186),
        spacing=7,
    )
    draw.text(
        (SIDEBAR_LEFT, 1030),
        "NSIDC-0611 V4.1 · 주차 사이 화면은 시각적 보간",
        font=small,
        fill=(70, 99, 111),
    )
    return canvas


def _comparison_frame(
    first_map: Image.Image,
    last_map: Image.Image,
    first_fraction: float,
    last_fraction: float,
) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title = _font(FONT_BOLD, 42)
    year_font = _font(FONT_BOLD, 54)
    metric = _font(FONT_BOLD, 34)
    body = _font(FONT_REGULAR, 18)

    draw.text(
        (62, 42),
        "40년 사이, 오래된 얼음은 어디로 갔는가",
        font=title,
        fill=(235, 241, 241),
    )
    draw.line((62, 105, 1858, 105), fill=(38, 61, 72), width=1)
    draw.line((960, 142, 960, 920), fill=(38, 61, 72), width=1)

    size = 720
    first = first_map.resize((size, size), Image.Resampling.LANCZOS)
    last = last_map.resize((size, size), Image.Resampling.LANCZOS)
    canvas.paste(first, (120, 175), first)
    canvas.paste(last, (1080, 175), last)

    draw.text((92, 135), "1984", font=year_font, fill=(235, 241, 241))
    draw.text((1052, 135), "2024", font=year_font, fill=(235, 241, 241))
    draw.text(
        (92, 870),
        f"다년생 해빙 {first_fraction * 100:.1f}%",
        font=metric,
        fill=(247, 239, 211),
    )
    draw.text(
        (1052, 870),
        f"다년생 해빙 {last_fraction * 100:.1f}%",
        font=metric,
        fill=(247, 239, 211),
    )
    draw.text(
        (92, 950),
        "같은 계절, 같은 투영, 같은 색상 기준",
        font=body,
        fill=(104, 138, 151),
    )
    draw.text(
        (1052, 950),
        "넓이보다 먼저 사라진 것은 오래된 얼음의 층이다",
        font=body,
        fill=(104, 138, 151),
    )
    return canvas


def _seasonal_frames(
    preview_directory: Path,
    summary_csv: Path,
    stills: Path,
):
    points = _load_seasonal_points(summary_csv)
    maps = [
        _remap_preview(preview_directory / f"week-{point.week:02d}.png")
        for point in points
    ]
    base = _base_canvas(
        metadata="ARCTIC SEA ICE AGE  ·  2024 WEEKLY CYCLE",
    )
    stills.mkdir(parents=True, exist_ok=True)
    for index in (0, 25, 51):
        frame = _seasonal_frame(base, maps[index], points, index, 0.0)
        frame.save(stills / f"seasonal-week-{index + 1:02d}.png")

    first = _seasonal_frame(base, maps[0], points, 0, 0.0)
    yield from _repeat(first, FRAME_RATE)
    transition_frames = 4
    for index in range(len(points) - 1):
        for step in range(1, transition_frames + 1):
            linear = step / transition_frames
            eased = linear * linear * (3 - 2 * linear)
            blended = Image.blend(maps[index], maps[index + 1], eased)
            yield _seasonal_frame(base, blended, points, index, eased)
    last = _seasonal_frame(base, maps[-1], points, len(points) - 1, 0.0)
    yield from _repeat(last, FRAME_RATE)


def _assemble(
    segments: list[Path],
    durations: list[float],
    output: Path,
    crossfade: float = 0.6,
) -> Path:
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
    for segment in segments:
        command.extend(["-i", str(segment)])

    filters = []
    cumulative = durations[0]
    previous = "0:v"
    for index in range(1, len(segments)):
        output_label = f"v{index}"
        offset = cumulative - crossfade
        filters.append(
            f"[{previous}][{index}:v]xfade=transition=fadeblack:"
            f"duration={crossfade}:offset={offset:.6f}[{output_label}]"
        )
        previous = output_label
        cumulative += durations[index] - crossfade

    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            f"[{previous}]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    subprocess.run(command, check=True)
    return output


def build_story(
    project_root: str | Path,
    output: str | Path,
) -> Path:
    root = Path(project_root)
    story_root = root / "outputs" / "story"
    segments_root = story_root / "segments"
    stills_root = story_root / "stills"
    segments_root.mkdir(parents=True, exist_ok=True)
    stills_root.mkdir(parents=True, exist_ok=True)

    intro = _intro_frame()
    outro = _outro_frame()
    intro.save(stills_root / "intro.png")
    outro.save(stills_root / "outro.png")
    intro_duration = _encode_frames(
        _repeat(intro, FRAME_RATE * 4),
        segments_root / "01-intro.mp4",
    )
    seasonal_duration = _encode_frames(
        _seasonal_frames(
            root / "data/processed/seasonal/2024/preview",
            root / "data/processed/seasonal/2024/summary.csv",
            stills_root,
        ),
        segments_root / "02-seasonal.mp4",
    )

    annual = root / "outputs/design-v2/polar-memory-editorial.mp4"
    if not annual.is_file():
        raise FileNotFoundError(f"연도별 본편이 없습니다: {annual}")
    annual_duration = 26.0

    summaries = []
    with (root / "data/processed/summary.csv").open(encoding="utf-8") as file:
        summaries = list(csv.DictReader(file))
    first_map = _remap_preview(
        root / "data/processed/snapshots/preview/1984.png"
    )
    last_map = _remap_preview(
        root / "data/processed/snapshots/preview/2024.png"
    )
    comparison = _comparison_frame(
        first_map,
        last_map,
        float(summaries[0]["multiyear_fraction"]),
        float(summaries[-1]["multiyear_fraction"]),
    )
    comparison.save(stills_root / "comparison-1984-2024.png")
    comparison_duration = _encode_frames(
        _repeat(comparison, FRAME_RATE * 6),
        segments_root / "04-comparison.mp4",
    )
    outro_duration = _encode_frames(
        _repeat(outro, FRAME_RATE * 5),
        segments_root / "05-outro.mp4",
    )

    return _assemble(
        [
            segments_root / "01-intro.mp4",
            segments_root / "02-seasonal.mp4",
            annual,
            segments_root / "04-comparison.mp4",
            segments_root / "05-outro.mp4",
        ],
        [
            intro_duration,
            seasonal_duration,
            annual_duration,
            comparison_duration,
            outro_duration,
        ],
        Path(output),
    )
