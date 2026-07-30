from __future__ import annotations

import netrc
import os
import re
from pathlib import Path

import requests
from tqdm import tqdm

YEAR_PATTERN = re.compile(r"iceage_nh_12\.5km_(\d{4})0101_\1(?:1231)_v4\.1\.nc$")
NETCDF_CLASSIC_MAGIC = b"CDF"
NETCDF4_MAGIC = b"\x89HDF\r\n\x1a\n"


def annual_filename(year: int) -> str:
    return f"iceage_nh_12.5km_{year}0101_{year}1231_v4.1.nc"


def annual_url(base_url: str, year: int) -> str:
    return f"{base_url.rstrip('/')}/{annual_filename(year)}"


def parse_year(path: str | Path) -> int:
    match = YEAR_PATTERN.search(Path(path).name)
    if not match:
        raise ValueError(f"NSIDC-0611 연간 파일명이 아닙니다: {Path(path).name}")
    return int(match.group(1))


def _credentials(host: str) -> tuple[str, str] | None:
    username = os.getenv("EARTHDATA_USERNAME")
    password = os.getenv("EARTHDATA_PASSWORD")
    if username and password:
        return username, password

    try:
        auth = netrc.netrc().authenticators(host)
        if auth is None:
            auth = netrc.netrc().authenticators("urs.earthdata.nasa.gov")
    except (FileNotFoundError, netrc.NetrcParseError, OSError):
        auth = None

    if auth:
        login, _, password = auth
        return login, password
    return None


def is_netcdf_file(path: str | Path) -> bool:
    source = Path(path)
    if not source.is_file():
        return False
    with source.open("rb") as file:
        magic = file.read(8)
    return magic.startswith(NETCDF_CLASSIC_MAGIC) or magic == NETCDF4_MAGIC


def download_year(
    base_url: str,
    year: int,
    destination: str | Path,
    *,
    overwrite: bool = False,
    chunk_size: int = 1024 * 1024,
) -> Path:
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    target = destination_path / annual_filename(year)
    partial = target.with_suffix(target.suffix + ".part")

    if target.exists() and not overwrite:
        if is_netcdf_file(target):
            return target
        raise RuntimeError(
            f"기존 파일이 NetCDF 형식이 아닙니다: {target}. "
            "--overwrite로 다시 내려받으세요."
        )

    url = annual_url(base_url, year)
    headers: dict[str, str] = {}
    token = os.getenv("EARTHDATA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    credentials = _credentials("daacdata.apps.nsidc.org")
    auth = credentials if not token else None
    if not token and not credentials:
        raise RuntimeError(
            "Earthdata 인증 정보가 없습니다. EARTHDATA_USERNAME/"
            "EARTHDATA_PASSWORD 환경 변수 또는 ~/.netrc를 설정하세요."
        )

    try:
        with requests.get(
            url,
            headers=headers,
            auth=auth,
            stream=True,
            timeout=(30, 120),
            allow_redirects=True,
        ) as response:
            if response.status_code == 401:
                raise RuntimeError(
                    "Earthdata 인증에 실패했습니다. 계정 승인과 인증 정보를 확인하세요."
                )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise RuntimeError(
                    "Earthdata 로그인 페이지가 반환되었습니다. "
                    "계정 승인과 인증 정보를 확인하세요."
                )

            total = int(response.headers.get("content-length", 0))
            with partial.open("wb") as output, tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc=target.name,
            ) as progress:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        output.write(chunk)
                        progress.update(len(chunk))

        if not is_netcdf_file(partial):
            raise RuntimeError(
                "받은 파일이 NetCDF 형식이 아닙니다. Earthdata 인증 상태를 확인하세요."
            )
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    return target
