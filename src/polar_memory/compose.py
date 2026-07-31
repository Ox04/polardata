from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_FONT = Path(
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Regular.ttc"
)
LEGEND = (
    ("1년생", (158, 216, 235)),
    ("2년생", (191, 226, 239)),
    ("3년생", (220, 239, 245)),
    ("4년생", (239, 247, 249)),
    ("5년차 이상", (255, 255, 255)),
)


def read_summary(path: str | Path) -> dict[str, dict[str, str]]:
    with Path(path).open(encoding="utf-8") as file:
        return {row["year"]: row for row in csv.DictReader(file)}


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.is_file():
        raise FileNotFoundError(f"한글 폰트를 찾지 못했습니다: {path}")
    return ImageFont.truetype(str(path), size=size)


def compose_frame(
    source: str | Path,
    destination: str | Path,
    *,
    summary: dict[str, str],
    history: dict[str, dict[str, str]] | None = None,
    font_path: Path = DEFAULT_FONT,
) -> Path:
    image = Image.open(source).convert("RGB")
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    scale = width / 960

    title_font = _font(font_path, round(34 * scale))
    year_font = _font(font_path, round(70 * scale))
    body_font = _font(font_path, round(20 * scale))
    small_font = _font(font_path, round(14 * scale))

    margin = round(42 * scale)
    draw.rounded_rectangle(
        (margin, margin, round(390 * scale), round(190 * scale)),
        radius=round(14 * scale),
        fill=(2, 10, 20, 205),
        outline=(112, 178, 205, 100),
        width=max(1, round(1 * scale)),
    )
    draw.text((margin + 20 * scale, margin + 15 * scale), "북극의 기억층", font=title_font)
    draw.text(
        (margin + 20 * scale, margin + 58 * scale),
        f"{summary['year']}",
        font=year_font,
        fill=(235, 248, 252),
    )
    draw.text(
        (margin + 205 * scale, margin + 85 * scale),
        f"제 {summary['week']}주",
        font=body_font,
        fill=(159, 203, 220),
    )

    fraction = float(summary["multiyear_fraction"]) * 100
    metric = f"다년생 해빙 비율  {fraction:.1f}%"
    chart_left = width - margin - 270 * scale
    chart_right = width - margin - 20 * scale
    chart_top = margin + 60 * scale
    chart_bottom = margin + 118 * scale
    draw.rounded_rectangle(
        (
            width - margin - 290 * scale,
            margin,
            width - margin,
            margin + 138 * scale,
        ),
        radius=round(12 * scale),
        fill=(2, 10, 20, 205),
    )
    draw.text(
        (chart_left, margin + 12 * scale),
        metric,
        font=body_font,
        fill=(235, 248, 252),
    )
    if history:
        current_year = int(summary["year"])
        points = sorted(
            (
                int(year),
                float(row["multiyear_fraction"]),
            )
            for year, row in history.items()
            if int(year) <= current_year
        )
        if points:
            min_year = min(int(year) for year in history)
            max_year = max(int(year) for year in history)
            max_fraction = 0.5

            def chart_point(year: int, value: float) -> tuple[float, float]:
                year_span = max(max_year - min_year, 1)
                x = chart_left + (year - min_year) / year_span * (
                    chart_right - chart_left
                )
                y = chart_bottom - min(value / max_fraction, 1.0) * (
                    chart_bottom - chart_top
                )
                return x, y

            draw.line(
                (chart_left, chart_bottom, chart_right, chart_bottom),
                fill=(97, 132, 148, 130),
                width=max(1, round(scale)),
            )
            plotted = [chart_point(year, value) for year, value in points]
            if len(plotted) > 1:
                draw.line(
                    plotted,
                    fill=(118, 210, 235, 255),
                    width=max(2, round(3 * scale)),
                    joint="curve",
                )
            x, y = plotted[-1]
            radius = 4 * scale
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(245, 252, 255, 255),
            )
            draw.text(
                (chart_left, chart_bottom + 4 * scale),
                str(min_year),
                font=small_font,
                fill=(118, 153, 168),
            )
            current_label = str(current_year)
            label_box = draw.textbbox((0, 0), current_label, font=small_font)
            draw.text(
                (
                    chart_right - (label_box[2] - label_box[0]),
                    chart_bottom + 4 * scale,
                ),
                current_label,
                font=small_font,
                fill=(118, 153, 168),
            )

    panel_top = height - margin - 92 * scale
    legend_y = panel_top + 17 * scale
    draw.rounded_rectangle(
        (
            margin,
            panel_top,
            width - margin,
            height - margin + 8 * scale,
        ),
        radius=round(12 * scale),
        fill=(2, 10, 20, 205),
    )
    x = margin + 20 * scale
    for label, color in LEGEND:
        draw.rounded_rectangle(
            (x, legend_y, x + 24 * scale, legend_y + 24 * scale),
            radius=round(4 * scale),
            fill=(*color, 255),
        )
        draw.text(
            (x + 32 * scale, legend_y),
            label,
            font=small_font,
            fill=(220, 235, 241),
        )
        x += 120 * scale

    footer = "높이 = 실제 두께가 아닌 해빙 연령 · NSIDC-0611 V4.1"
    footer_box = draw.textbbox((0, 0), footer, font=small_font)
    footer_width = footer_box[2] - footer_box[0]
    draw.text(
        (
            width - margin - footer_width - 20 * scale,
            panel_top + 56 * scale,
        ),
        footer,
        font=small_font,
        fill=(137, 171, 184),
    )

    result = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target, quality=95)
    return target


def compose_directory(
    source: str | Path,
    destination: str | Path,
    summary_csv: str | Path,
    *,
    font_path: Path = DEFAULT_FONT,
) -> list[Path]:
    summaries = read_summary(summary_csv)
    output = []
    for image_path in sorted(Path(source).glob("*.png")):
        summary = summaries.get(image_path.stem)
        if summary is not None:
            output.append(
                compose_frame(
                    image_path,
                    Path(destination) / image_path.name,
                    summary=summary,
                    history=summaries,
                    font_path=font_path,
                )
            )
    return output
