from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_v4_mockup import setup_scene


def ease(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--start-year", type=int, default=1984)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--skip-existing", action="store_true")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def main() -> None:
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    for year in range(args.start_year, args.end_year):
        first = np.load(args.classes / f"{year}-classes.npy")
        second = np.load(args.classes / f"{year + 1}-classes.npy")
        for step in range(1, args.steps + 1):
            target = args.output / f"{year}-{year + 1}-{step:02d}.png"
            if args.skip_existing and target.is_file():
                print(f"[{year} step {step}] exists, skipping", flush=True)
                continue
            amount = ease(step / (args.steps + 1))
            setup_scene(
                "transition",
                first,
                year=year,
                output=args.output,
                width=args.width,
                height=args.height,
                render_samples=args.samples,
                transition_to=second,
                transition_amount=amount,
            )
            bpy.context.scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True)
            elapsed = time.monotonic() - started
            print(
                f"[{year}→{year + 1} step {step}/{args.steps}] "
                f"rendered · elapsed {elapsed:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()
