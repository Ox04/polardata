from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_v4_mockup import setup_scene


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--start-year", type=int, default=1984)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--skip-existing", action="store_true")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def main() -> None:
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    for year in range(args.start_year, args.end_year + 1):
        target = args.output / f"map-3d-{year}.png"
        if args.skip_existing and target.is_file():
            print(f"[{year}] exists, skipping", flush=True)
            continue

        classes_path = args.classes / f"{year}-classes.npy"
        if not classes_path.is_file():
            raise FileNotFoundError(classes_path)
        classes = np.load(classes_path)
        setup_scene(
            "block",
            classes,
            year=year,
            output=args.output,
            width=args.width,
            height=args.height,
            render_samples=args.samples,
        )
        bpy.context.scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
        elapsed = time.monotonic() - started
        print(f"[{year}] rendered · elapsed {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
