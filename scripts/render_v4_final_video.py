from __future__ import annotations

import argparse
import math
import subprocess
from collections.abc import Iterator
from pathlib import Path

from design_v4_assets import (
    CANVAS,
    MUTED,
    OUTPUT,
    TEXT,
    draw_legend,
    draw_overlay_graph,
    font,
    gradient_background,
    summary_rows,
)
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRAME_RATE = 60


def ease(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def short_transition_amount(amount: float) -> float:
    if amount <= 0.38:
        return 0.0
    if amount >= 0.62:
        return 1.0
    return ease((amount - 0.38) / 0.24)


def short_map_transition(
    first: Image.Image,
    second: Image.Image,
    amount: float,
) -> Image.Image:
    if amount <= 0.0:
        return first
    if amount >= 1.0:
        return second
    return Image.blend(first, second, amount)


def alpha_envelope(
    progress: float,
    *,
    fade_in_end: float,
    fade_out_start: float,
) -> int:
    fade_in = min(max(progress / fade_in_end, 0.0), 1.0)
    fade_out = 1.0
    if progress > fade_out_start:
        fade_out = 1.0 - ease(
            min((progress - fade_out_start) / (1.0 - fade_out_start), 1.0)
        )
    return round(255 * ease(fade_in) * fade_out)


def compose_intro_frame(
    first_map: Image.Image,
    rows: list[dict[str, str]],
    progress: float,
    base_background: Image.Image,
) -> Image.Image:
    final_frame = compose_frame(
        first_map,
        rows,
        float(rows[0]["year"]),
        base_background,
    ).convert("RGBA")
    reveal = ease(min(max((progress - 0.82) / 0.18, 0.0), 1.0))

    canvas = base_background.copy()
    stars = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    star_draw = ImageDraw.Draw(stars)
    star_alpha = round(150 * (1.0 - reveal))
    for index in range(90):
        x = (index * 389 + 173) % CANVAS[0]
        y = (index * 211 + 97) % CANVAS[1]
        radius = 1 if index % 7 else 2
        star_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(135, 190, 205, star_alpha),
        )
    canvas.alpha_composite(stars)

    zoom = ease(min(max((progress - 0.20) / 0.55, 0.0), 1.0))
    diameter = round(470 + 2230 * zoom)
    map_scale = min((diameter / CANVAS[1]) * 1.02, 1.0)
    map_size = (
        round(CANVAS[0] * map_scale),
        round(CANVAS[1] * map_scale),
    )
    globe = first_map.resize(map_size, Image.Resampling.LANCZOS)
    center_y = round(470 + 70 * zoom)
    map_left = CANVAS[0] // 2 - map_size[0] // 2
    map_top = center_y - map_size[1] // 2
    map_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    map_layer.alpha_composite(globe, dest=(map_left, map_top))

    left = CANVAS[0] // 2 - diameter // 2
    top = center_y - diameter // 2
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse(
        (left, top, left + diameter, top + diameter),
        fill=255,
    )
    map_layer.putalpha(
        Image.composite(map_layer.getchannel("A"), Image.new("L", CANVAS, 0), mask)
    )
    canvas.alpha_composite(map_layer)

    ring = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    ring_alpha = round(190 * (1.0 - reveal))
    box = (left, top, left + diameter, top + diameter)
    ring_draw.ellipse(box, outline=(70, 214, 224, ring_alpha), width=3)
    if diameter < 1600:
        for inset in (round(diameter * 0.20), round(diameter * 0.36)):
            ring_draw.ellipse(
                (
                    left + inset,
                    top,
                    left + diameter - inset,
                    top + diameter,
                ),
                outline=(70, 214, 224, ring_alpha // 3),
                width=1,
            )
        ring_draw.line(
            (left, center_y, left + diameter, center_y),
            fill=(70, 214, 224, ring_alpha // 3),
            width=1,
        )
    ring = ring.filter(ImageFilter.GaussianBlur(radius=0.35))
    canvas.alpha_composite(ring)

    labels = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(labels)
    title_alpha = alpha_envelope(
        progress,
        fade_in_end=0.12,
        fade_out_start=0.42,
    )
    label_draw.text(
        (CANVAS[0] // 2, 88),
        "북극의 기억층",
        font=font(58, bold=True),
        fill=(*TEXT, title_alpha),
        anchor="ma",
    )
    label_draw.text(
        (CANVAS[0] // 2, 158),
        "1984—2024 · 같은 제11주 · 해빙 연령 추정",
        font=font(22, bold=True),
        fill=(118, 174, 188, title_alpha),
        anchor="ma",
    )
    label_draw.text(
        (CANVAS[0] // 2, 742),
        "ARCTIC · 90°N",
        font=font(17, bold=True),
        fill=(100, 206, 216, title_alpha),
        anchor="ma",
    )
    if progress < 0.58:
        legend_alpha = alpha_envelope(
            progress,
            fade_in_end=0.22,
            fade_out_start=0.46,
        )
        legend_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        draw_legend(ImageDraw.Draw(legend_layer), 680, 925)
        legend_layer.putalpha(
            legend_layer.getchannel("A").point(
                lambda value: round(value * legend_alpha / 255)
            )
        )
        labels.alpha_composite(legend_layer)
    canvas.alpha_composite(labels)

    if reveal > 0.0:
        canvas = Image.blend(canvas, final_frame, reveal)
    return canvas.convert("RGB")


def compose_frame(
    map_image: Image.Image,
    rows: list[dict[str, str]],
    year_position: float,
    base_background: Image.Image | None = None,
) -> Image.Image:
    background = (
        base_background.copy()
        if base_background is not None
        else gradient_background().convert("RGBA")
    )
    background.alpha_composite(map_image)
    canvas = background
    draw = ImageDraw.Draw(canvas)

    first_year = int(rows[0]["year"])
    lower_index = min(max(int(year_position) - first_year, 0), len(rows) - 1)
    transition = year_position - int(year_position)
    upper_index = min(lower_index + 1, len(rows) - 1)
    lower_value = float(rows[lower_index]["multiyear_fraction"])
    upper_value = float(rows[upper_index]["multiyear_fraction"])
    percentage = (lower_value * (1 - transition) + upper_value * transition) * 100
    display_year = math.floor(year_position + 0.5)

    draw.text((64, 38), str(display_year), font=font(82, bold=True), fill=TEXT)

    draw_legend(draw, 68, 944)
    draw.text(
        (68, 1024),
        "높이는 실제 두께가 아닌 해빙 연령 · 연도 사이는 시각적 보간",
        font=font(16),
        fill=(91, 123, 134),
    )

    draw_overlay_graph(canvas, rows, year_position)
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
    return canvas.convert("RGB")


def compose_comparison_frame(
    first_map: Image.Image,
    last_map: Image.Image,
    rows: list[dict[str, str]],
    split_x: int,
    base_background: Image.Image,
) -> Image.Image:
    canvas = base_background.copy()
    canvas.alpha_composite(last_map)
    if split_x > 0:
        first_crop = first_map.crop((0, 0, split_x, CANVAS[1]))
        canvas.alpha_composite(first_crop, dest=(0, 0))

    draw = ImageDraw.Draw(canvas)
    if split_x > 0:
        draw.line(
            (split_x, 0, split_x, CANVAS[1]),
            fill=(44, 200, 217, 205),
            width=2,
        )

    first_value = float(rows[0]["multiyear_fraction"]) * 100
    last_value = float(rows[-1]["multiyear_fraction"]) * 100
    if split_x >= 380:
        draw.text((64, 38), "1984", font=font(62, bold=True), fill=TEXT)
        draw.text(
            (64, 119),
            f"{first_value:.1f}%",
            font=font(42, bold=True),
            fill=(255, 233, 164),
            stroke_width=3,
            stroke_fill=(4, 13, 19),
        )
        draw.text(
            (64, 176),
            "여름을 견딘 얼음",
            font=font(18, bold=True),
            fill=TEXT,
            stroke_width=2,
            stroke_fill=(4, 13, 19),
        )

    draw.text(
        (1855, 38),
        "2024",
        font=font(62, bold=True),
        fill=TEXT,
        anchor="ra",
    )
    draw.text(
        (1855, 119),
        f"{last_value:.1f}%",
        font=font(42, bold=True),
        fill=(255, 233, 164),
        stroke_width=3,
        stroke_fill=(4, 13, 19),
        anchor="ra",
    )
    draw.text(
        (1855, 176),
        "여름을 견딘 얼음",
        font=font(18, bold=True),
        fill=TEXT,
        stroke_width=2,
        stroke_fill=(4, 13, 19),
        anchor="ra",
    )

    draw_legend(draw, 68, 949)
    draw.text(
        (68, 1012),
        "같은 제11주 · 같은 좌표 · 높이는 연령 표현",
        font=font(15),
        fill=(73, 106, 118),
    )
    draw.text(
        (1855, 1054),
        "Data · NSIDC-0611 V4.1",
        font=font(14),
        fill=(66, 96, 107),
        anchor="ra",
    )
    return canvas.convert("RGB")


def frame_stream(
    maps: list[Image.Image],
    rows: list[dict[str, str]],
    *,
    intro_frames: int,
    transition_frames: int,
    opening_hold: int,
    closing_hold: int,
    transition_maps: Path | None = None,
    transition_steps: int = 5,
    frames_per_state: int = 4,
    comparison_reveal: int = 30,
    comparison_hold: int = 150,
) -> Iterator[Image.Image]:
    first_year = int(rows[0]["year"])
    base_background = gradient_background().convert("RGBA")
    for step in range(intro_frames):
        progress = step / max(intro_frames - 1, 1)
        yield compose_intro_frame(
            maps[0],
            rows,
            progress,
            base_background,
        )

    first = compose_frame(
        maps[0],
        rows,
        float(first_year),
        base_background,
    )
    for _ in range(opening_hold):
        yield first

    for index in range(len(maps) - 1):
        year = first_year + index
        if transition_maps is None:
            for step in range(1, transition_frames + 1):
                amount = ease(step / transition_frames)
                transition_amount = short_transition_amount(amount)
                transitioned_map = short_map_transition(
                    maps[index],
                    maps[index + 1],
                    transition_amount,
                )
                yield compose_frame(
                    transitioned_map,
                    rows,
                    year + transition_amount,
                    base_background,
                )
            continue

        states = [maps[index]]
        states.extend(
            Image.open(
                transition_maps / f"{year}-{year + 1}-{step:02d}.png"
            ).convert("RGBA")
            for step in range(1, transition_steps + 1)
        )
        states.append(maps[index + 1])
        positions = [0.0]
        positions.extend(
            ease(step / (transition_steps + 1))
            for step in range(1, transition_steps + 1)
        )
        positions.append(1.0)

        for state_index in range(len(states) - 1):
            for step in range(1, frames_per_state + 1):
                amount = ease(step / frames_per_state)
                transitioned_map = Image.blend(
                    states[state_index],
                    states[state_index + 1],
                    amount,
                )
                position = (
                    positions[state_index] * (1 - amount)
                    + positions[state_index + 1] * amount
                )
                yield compose_frame(
                    transitioned_map,
                    rows,
                    year + position,
                    base_background,
                )

    last_year = int(rows[-1]["year"])
    last = compose_frame(
        maps[-1],
        rows,
        float(last_year),
        base_background,
    )
    for _ in range(closing_hold):
        yield last

    for step in range(1, comparison_reveal + 1):
        amount = ease(step / comparison_reveal)
        split_x = round(CANVAS[0] * 0.5 * amount)
        yield compose_comparison_frame(
            maps[0],
            maps[-1],
            rows,
            split_x,
            base_background,
        )
    comparison = compose_comparison_frame(
        maps[0],
        maps[-1],
        rows,
        CANVAS[0] // 2,
        base_background,
    )
    for _ in range(comparison_hold):
        yield comparison


def encode(
    frames: Iterator[Image.Image],
    output: Path,
    *,
    frame_rate: int,
) -> int:
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
            "slow",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    if process.stdin is None:
        raise RuntimeError("FFmpeg input pipe was not created")

    frame_count = 0
    try:
        for frame in frames:
            process.stdin.write(frame.tobytes())
            frame_count += 1
            if frame_count % 90 == 0:
                print(f"encoded {frame_count} frames", flush=True)
    finally:
        process.stdin.close()
    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, process.args)
    return frame_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--maps",
        type=Path,
        default=OUTPUT / "annual-maps",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/final/polar-memory-final-v7.mp4",
    )
    parser.add_argument("--frame-rate", type=int, default=DEFAULT_FRAME_RATE)
    parser.add_argument("--intro-frames", type=int, default=210)
    parser.add_argument("--transition-frames", type=int, default=36)
    parser.add_argument("--opening-hold", type=int, default=60)
    parser.add_argument("--closing-hold", type=int, default=120)
    parser.add_argument("--transition-maps", type=Path)
    parser.add_argument("--transition-steps", type=int, default=5)
    parser.add_argument("--frames-per-state", type=int, default=8)
    parser.add_argument("--comparison-reveal", type=int, default=60)
    parser.add_argument("--comparison-hold", type=int, default=300)
    parser.add_argument("--start-year", type=int, default=1984)
    parser.add_argument("--end-year", type=int, default=2024)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = [
        row
        for row in summary_rows()
        if args.start_year <= int(row["year"]) <= args.end_year
    ]
    if not rows:
        raise ValueError("No summary rows in the requested year range")
    years = [int(row["year"]) for row in rows]
    maps = [
        Image.open(args.maps / f"map-3d-{year}.png").convert("RGBA")
        for year in years
    ]
    missing_size = [year for year, image in zip(years, maps) if image.size != CANVAS]
    if missing_size:
        raise ValueError(f"Unexpected map dimensions: {missing_size}")

    frame_count = encode(
        frame_stream(
            maps,
            rows,
            intro_frames=args.intro_frames,
            transition_frames=args.transition_frames,
            opening_hold=args.opening_hold,
            closing_hold=args.closing_hold,
            transition_maps=args.transition_maps,
            transition_steps=args.transition_steps,
            frames_per_state=args.frames_per_state,
            comparison_reveal=args.comparison_reveal,
            comparison_hold=args.comparison_hold,
        ),
        args.output,
        frame_rate=args.frame_rate,
    )
    cover = compose_comparison_frame(
        maps[0],
        maps[-1],
        rows,
        CANVAS[0] // 2,
        gradient_background().convert("RGBA"),
    )
    cover_name = args.output.stem.replace("polar-memory-final", "cover") + ".png"
    cover.save(args.output.with_name(cover_name))
    print(
        f"wrote {args.output} · {frame_count} frames · "
        f"{frame_count / args.frame_rate:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
