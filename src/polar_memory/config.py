from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DatasetConfig:
    dataset_id: str
    version: str
    base_url: str
    start_year: int
    end_year: int
    fixed_week: int
    seasonal_year: int
    pixel_size_m: int
    expected_weeks: int
    expected_rows: int
    expected_columns: int


@dataclass(frozen=True)
class PathsConfig:
    raw: Path
    processed: Path


@dataclass(frozen=True)
class ProjectConfig:
    dataset: DatasetConfig
    paths: PathsConfig
    visual: dict[str, Any]


def load_config(path: str | Path = "config/project.yaml") -> ProjectConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset = raw["dataset"]
    paths = raw["paths"]

    return ProjectConfig(
        dataset=DatasetConfig(
            dataset_id=str(dataset["id"]),
            version=str(dataset["version"]),
            base_url=str(dataset["base_url"]).rstrip("/"),
            start_year=int(dataset["start_year"]),
            end_year=int(dataset["end_year"]),
            fixed_week=int(dataset["fixed_week"]),
            seasonal_year=int(dataset["seasonal_year"]),
            pixel_size_m=int(dataset["pixel_size_m"]),
            expected_weeks=int(dataset["expected_weeks"]),
            expected_rows=int(dataset["expected_rows"]),
            expected_columns=int(dataset["expected_columns"]),
        ),
        paths=PathsConfig(
            raw=Path(paths["raw"]),
            processed=Path(paths["processed"]),
        ),
        visual=dict(raw["visual"]),
    )

