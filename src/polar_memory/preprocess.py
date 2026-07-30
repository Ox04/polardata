from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import xarray as xr
from PIL import Image

OPEN_WATER = 0
LAND = 20
UNCALCULATED_OCEAN = 21
MIN_ICE_AGE = 1
MAX_ICE_AGE = 16

HEIGHT_BY_CLASS = {
    0: 0.00,
    1: 0.10,
    2: 0.25,
    3: 0.45,
    4: 0.70,
    5: 1.00,
}

PREVIEW_RGBA = {
    0: (8, 20, 35, 255),
    1: (158, 216, 235, 120),
    2: (191, 226, 239, 170),
    3: (220, 239, 245, 205),
    4: (239, 247, 249, 230),
    5: (255, 255, 255, 255),
    LAND: (42, 46, 52, 255),
    UNCALCULATED_OCEAN: (24, 47, 65, 255),
}


@dataclass(frozen=True)
class FrameSummary:
    year: int
    week: int
    ice_cells: int
    first_year_cells: int
    multiyear_cells: int
    fifth_year_plus_cells: int
    ice_area_km2: float
    multiyear_fraction: float


def find_ice_age_variable(dataset: xr.Dataset) -> str:
    candidates: list[tuple[int, str]] = []
    for name, variable in dataset.data_vars.items():
        if variable.ndim != 3 or not np.issubdtype(variable.dtype, np.number):
            continue
        score = 0
        lowered = name.lower()
        if "age" in lowered:
            score += 10
        if variable.shape[0] in {52, 53}:
            score += 4
        if variable.shape[-2:] == (722, 722):
            score += 4
        candidates.append((score, name))

    if not candidates:
        raise ValueError("3차원 해빙 연령 변수를 찾지 못했습니다.")
    candidates.sort(reverse=True)
    return candidates[0][1]


def load_ice_age(path: str | Path, variable: str | None = None) -> xr.DataArray:
    with xr.open_dataset(path, mask_and_scale=False) as dataset:
        variable_name = variable or find_ice_age_variable(dataset)
        return dataset[variable_name].load()


def classify_age(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values)
    classes = np.full(source.shape, UNCALCULATED_OCEAN, dtype=np.uint8)
    classes[source == OPEN_WATER] = OPEN_WATER
    classes[source == LAND] = LAND
    classes[source == UNCALCULATED_OCEAN] = UNCALCULATED_OCEAN
    for age in range(1, 5):
        classes[source == age] = age
    classes[(source >= 5) & (source <= MAX_ICE_AGE)] = 5
    return classes


def choose_week(data: xr.DataArray, week: int) -> np.ndarray:
    if data.ndim != 3:
        raise ValueError(f"해빙 연령 자료는 3차원이어야 합니다. 현재: {data.ndim}차원")
    if week < 1 or week > data.shape[0]:
        raise ValueError(f"주차는 1~{data.shape[0]} 범위여야 합니다: {week}")
    return np.asarray(data.isel({data.dims[0]: week - 1}).values)


def height_map(classes: np.ndarray) -> np.ndarray:
    heights = np.zeros(classes.shape, dtype=np.float32)
    for age_class, height in HEIGHT_BY_CLASS.items():
        heights[classes == age_class] = height
    return heights


def ice_mask(classes: np.ndarray) -> np.ndarray:
    return ((classes >= 1) & (classes <= 5)).astype(np.uint8) * 255


def preview_rgba(classes: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*classes.shape, 4), dtype=np.uint8)
    for age_class, color in PREVIEW_RGBA.items():
        rgba[classes == age_class] = color
    return rgba


def summarize(
    classes: np.ndarray,
    *,
    year: int,
    week: int,
    pixel_size_m: int,
) -> FrameSummary:
    is_ice = (classes >= 1) & (classes <= 5)
    ice_cells = int(np.count_nonzero(is_ice))
    first_year = int(np.count_nonzero(classes == 1))
    multiyear = int(np.count_nonzero((classes >= 2) & (classes <= 5)))
    old_ice = int(np.count_nonzero(classes == 5))
    area_per_cell_km2 = (pixel_size_m / 1000.0) ** 2
    fraction = multiyear / ice_cells if ice_cells else 0.0

    return FrameSummary(
        year=year,
        week=week,
        ice_cells=ice_cells,
        first_year_cells=first_year,
        multiyear_cells=multiyear,
        fifth_year_plus_cells=old_ice,
        ice_area_km2=round(ice_cells * area_per_cell_km2, 3),
        multiyear_fraction=round(fraction, 6),
    )


def save_frame(
    classes: np.ndarray,
    output_root: str | Path,
    stem: str,
) -> dict[str, Path]:
    root = Path(output_root)
    destinations = {
        "height": root / "height" / f"{stem}.png",
        "mask": root / "mask" / f"{stem}.png",
        "preview": root / "preview" / f"{stem}.png",
    }
    for destination in destinations.values():
        destination.parent.mkdir(parents=True, exist_ok=True)

    height_u16 = np.round(height_map(classes) * 65535).astype(np.uint16)
    Image.fromarray(height_u16).save(destinations["height"])
    Image.fromarray(ice_mask(classes), mode="L").save(destinations["mask"])
    Image.fromarray(preview_rgba(classes), mode="RGBA").save(destinations["preview"])
    return destinations


def write_summary(rows: Iterable[FrameSummary], output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    materialized = [asdict(row) for row in rows]
    fieldnames = list(FrameSummary.__dataclass_fields__)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return output_path


def inspect_dataset(path: str | Path) -> dict[str, object]:
    with xr.open_dataset(path, mask_and_scale=False) as dataset:
        return {
            "path": str(path),
            "dimensions": dict(dataset.sizes),
            "variables": {
                name: {
                    "dimensions": list(variable.dims),
                    "shape": list(variable.shape),
                    "dtype": str(variable.dtype),
                    "attributes": {
                        key: str(value) for key, value in variable.attrs.items()
                    },
                }
                for name, variable in dataset.data_vars.items()
            },
            "selected_variable": find_ice_age_variable(dataset),
            "attributes": {key: str(value) for key, value in dataset.attrs.items()},
        }


def write_inspection(path: str | Path, output: str | Path | None = None) -> str:
    document = json.dumps(inspect_dataset(path), ensure_ascii=False, indent=2)
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document + "\n", encoding="utf-8")
    return document
