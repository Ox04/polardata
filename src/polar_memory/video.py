from __future__ import annotations

import subprocess
from pathlib import Path


def _concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def write_concat_manifest(
    frames: list[Path],
    output: str | Path,
    *,
    seconds_per_frame: float,
) -> Path:
    if not frames:
        raise ValueError("인코딩할 PNG 프레임이 없습니다.")
    if seconds_per_frame <= 0:
        raise ValueError("프레임 유지 시간은 0보다 커야 합니다.")

    lines = ["ffconcat version 1.0"]
    for frame in frames:
        lines.append(f"file '{_concat_path(frame)}'")
        lines.append(f"duration {seconds_per_frame:.6f}")
    lines.append(f"file '{_concat_path(frames[-1])}'")

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def encode_timeline(
    input_directory: str | Path,
    output: str | Path,
    *,
    seconds_per_frame: float = 0.6,
    frame_rate: int = 30,
    crf: int = 18,
) -> Path:
    frames = sorted(Path(input_directory).glob("*.png"))
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = write_concat_manifest(
        frames,
        target.with_suffix(".ffconcat"),
        seconds_per_frame=seconds_per_frame,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-vf",
            f"fps={frame_rate},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            str(crf),
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
    )
    return target
