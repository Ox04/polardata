from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from polar_memory.config import ProjectConfig, load_config
from polar_memory.nsidc import download_year, parse_year
from polar_memory.preprocess import (
    choose_week,
    classify_age,
    load_ice_age,
    save_frame,
    summarize,
    write_inspection,
    write_summary,
)


def _synthetic_ice_age(size: int, weeks: int = 52) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    radius = np.sqrt(x**2 + y**2)
    angle = np.arctan2(y, x)
    data = np.zeros((weeks, size, size), dtype=np.uint8)

    for index in range(weeks):
        phase = 2 * np.pi * index / weeks
        edge = 0.72 + 0.13 * np.cos(phase)
        edge += 0.035 * np.sin(5 * angle + phase)
        distance_inside = edge - radius
        ice = distance_inside >= 0
        age = np.clip(np.floor(distance_inside / 0.115) + 1, 1, 5)
        data[index, ice] = age[ice].astype(np.uint8)

    return data


def _demo(args: argparse.Namespace, config: ProjectConfig) -> None:
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    source = root / "synthetic-sea-ice-age.nc"
    values = _synthetic_ice_age(args.size)
    xr.Dataset(
        {
            "age_of_sea_ice": xr.DataArray(
                values,
                dims=("week", "y", "x"),
                attrs={"note": "Synthetic data for pipeline testing; not observations."},
            )
        },
        attrs={"title": "Polar Memory synthetic demonstration dataset"},
    ).to_netcdf(source)

    data = load_ice_age(source)
    summaries = []
    for week in range(1, data.shape[0] + 1):
        classes = classify_age(choose_week(data, week))
        save_frame(classes, root / "frames", f"week-{week:02d}")
        summaries.append(
            summarize(
                classes,
                year=0,
                week=week,
                pixel_size_m=config.dataset.pixel_size_m,
            )
        )

    write_summary(summaries, root / "summary.csv")
    write_inspection(source, root / "inspection.json")
    print(root)


def _download(args: argparse.Namespace, config: ProjectConfig) -> None:
    start = args.start_year or config.dataset.start_year
    end = args.end_year or config.dataset.end_year
    if start > end:
        raise ValueError("start-year는 end-year보다 클 수 없습니다.")
    for year in range(start, end + 1):
        path = download_year(
            config.dataset.base_url,
            year,
            config.paths.raw,
            overwrite=args.overwrite,
        )
        print(path)


def _inspect(args: argparse.Namespace, _: ProjectConfig) -> None:
    print(write_inspection(args.file, args.output))


def _process_all(args: argparse.Namespace, config: ProjectConfig) -> None:
    files = sorted(config.paths.raw.glob("iceage_nh_12.5km_*_v4.1.nc"))
    if not files:
        raise FileNotFoundError(
            f"원본 파일이 없습니다: {config.paths.raw}. 먼저 download를 실행하세요."
        )

    summaries = []
    for path in files:
        year = parse_year(path)
        data = load_ice_age(path)
        snapshot = classify_age(choose_week(data, config.dataset.fixed_week))
        save_frame(snapshot, config.paths.processed / "snapshots", str(year))
        summaries.append(
            summarize(
                snapshot,
                year=year,
                week=config.dataset.fixed_week,
                pixel_size_m=config.dataset.pixel_size_m,
            )
        )

        if args.seasonal_year == year:
            seasonal_root = config.paths.processed / "seasonal" / str(year)
            for week in range(1, data.shape[0] + 1):
                classes = classify_age(choose_week(data, week))
                save_frame(classes, seasonal_root, f"week-{week:02d}")

    summary_path = write_summary(summaries, config.paths.processed / "summary.csv")
    print(summary_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polar-memory")
    parser.add_argument("--config", default="config/project.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download")
    download.add_argument("--start-year", type=int)
    download.add_argument("--end-year", type=int)
    download.add_argument("--overwrite", action="store_true")
    download.set_defaults(handler=_download)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--output", type=Path)
    inspect.set_defaults(handler=_inspect)

    process_all = subparsers.add_parser("process-all")
    process_all.add_argument("--seasonal-year", type=int)
    process_all.set_defaults(handler=_process_all)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--size", type=int, default=160)
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"))
    demo.set_defaults(handler=_demo)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    args.handler(args, config)


if __name__ == "__main__":
    main()
