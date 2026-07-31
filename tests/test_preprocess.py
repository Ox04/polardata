from __future__ import annotations

import csv

import numpy as np
import xarray as xr
from PIL import Image

from polar_memory.nsidc import (
    annual_filename,
    is_netcdf_file,
    validate_collection,
    write_file_manifest,
)
from polar_memory.preprocess import (
    LAND,
    UNCALCULATED_OCEAN,
    choose_week,
    classify_age,
    find_ice_age_variable,
    save_frame,
    summarize,
    write_summary,
)
from polar_memory.video import write_concat_manifest


def test_classify_age_codes() -> None:
    source = np.array([[0, 1, 2, 3, 4, 5, 16, 20, 21, 99]])
    result = classify_age(source)
    expected = np.array(
        [[0, 1, 2, 3, 4, 5, 5, LAND, UNCALCULATED_OCEAN, UNCALCULATED_OCEAN]],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(result, expected)


def test_find_variable_and_choose_week() -> None:
    data = xr.Dataset(
        {
            "projection": xr.DataArray(np.array(1)),
            "age_of_sea_ice": xr.DataArray(
                np.zeros((52, 4, 5), dtype=np.uint8),
                dims=("week", "y", "x"),
            ),
        }
    )
    assert find_ice_age_variable(data) == "age_of_sea_ice"
    selected = choose_week(data["age_of_sea_ice"], 11)
    assert selected.shape == (4, 5)


def test_summary_uses_only_ice_cells() -> None:
    classes = np.array([[0, 1, 2], [3, 5, LAND]], dtype=np.uint8)
    result = summarize(classes, year=1984, week=11, pixel_size_m=1000)
    assert result.ice_cells == 4
    assert result.first_year_cells == 1
    assert result.multiyear_cells == 3
    assert result.fifth_year_plus_cells == 1
    assert result.ice_area_km2 == 4
    assert result.multiyear_fraction == 0.75


def test_save_frame_and_summary(tmp_path) -> None:
    classes = np.array([[0, 1], [5, LAND]], dtype=np.uint8)
    paths = save_frame(classes, tmp_path / "frames", "1984")
    assert Image.open(paths["height"]).mode in {"I;16", "I"}
    assert Image.open(paths["mask"]).getpixel((1, 0)) == 255
    assert Image.open(paths["preview"]).size == (2, 2)

    row = summarize(classes, year=1984, week=11, pixel_size_m=1000)
    summary_path = write_summary([row], tmp_path / "summary.csv")
    with summary_path.open(encoding="utf-8") as file:
        records = list(csv.DictReader(file))
    assert records[0]["year"] == "1984"
    assert records[0]["multiyear_fraction"] == "0.5"


def test_netcdf_magic_detection(tmp_path) -> None:
    classic = tmp_path / "classic.nc"
    classic.write_bytes(b"CDF\x02" + b"\x00" * 16)
    netcdf4 = tmp_path / "netcdf4.nc"
    netcdf4.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 16)
    html = tmp_path / "login.nc"
    html.write_text("<!doctype html>", encoding="utf-8")

    assert is_netcdf_file(classic)
    assert is_netcdf_file(netcdf4)
    assert not is_netcdf_file(html)


def test_validate_collection(tmp_path) -> None:
    for year in (1984, 1985):
        path = tmp_path / annual_filename(year)
        path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 16)

    files = validate_collection(tmp_path, 1984, 1985)
    assert [path.name for path in files] == [
        annual_filename(1984),
        annual_filename(1985),
    ]
    manifest = write_file_manifest(files, tmp_path / "manifest.csv")
    with manifest.open(encoding="utf-8") as file:
        records = list(csv.DictReader(file))
    assert records[0]["year"] == "1984"
    assert len(records[0]["sha256"]) == 64


def test_write_concat_manifest_repeats_last_frame(tmp_path) -> None:
    frames = [tmp_path / "1984.png", tmp_path / "1985.png"]
    manifest = write_concat_manifest(
        frames,
        tmp_path / "timeline.ffconcat",
        seconds_per_frame=0.6,
    )
    text = manifest.read_text(encoding="utf-8")
    assert text.count("duration 0.600000") == 2
    assert text.count("1985.png") == 2
