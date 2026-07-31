# 북극의 기억층

NSIDC 해빙 연령 자료를 높이, 투명도와 색상으로 변환해 3D 애니메이션을 만드는 프로젝트다.

구현 기준은 [파이프라인 문서](sea-ice-age-animation-pipeline.md)에 정리되어 있다.

## 현재 구현 범위

- NSIDC-0611 연간 NetCDF 다운로드
- 데이터 구조와 코드값 검사
- 동일 주차 연도별 높이 맵·마스크·미리보기 생성
- 2024년 주간 계절 프레임 생성
- 연도별 해빙 연령 요약 CSV 생성
- 합성 데이터 기반 자동 테스트

Blender 장면과 최종 영상 렌더링은 전처리 결과 검토 후 추가한다.

## 설치

WSL Fedora에서 실행한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Earthdata 인증

[NASA Earthdata Login](https://urs.earthdata.nasa.gov/) 계정과 자료 접근 승인이 필요하다.

`~/.netrc` 사용을 권장한다.

```bash
machine urs.earthdata.nasa.gov
  login 아이디
  password 비밀번호
chmod 600 ~/.netrc
```

또는 `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` 환경변수를 사용할 수 있다.
인증 정보는 Git에 저장하지 않는다. 로그인 HTML이 반환되면 다운로드를
중단하므로 잘못된 파일이 NetCDF로 저장되지 않는다.

## 실행

Earthdata 인증 전에는 합성 자료로 전체 전처리 흐름을 확인한다.

```bash
polar-memory demo
```

결과는 `outputs/demo`에 생성된다. 합성 자료는 작동 확인용이며 관측값이나
대회 작품의 근거 자료로 사용하지 않는다.

1984년 파일 한 개를 먼저 받는다.

```bash
polar-memory download --start-year 1984 --end-year 1984
```

파일 구조를 확인한다.

```bash
polar-memory validate-downloads

polar-memory inspect data/raw/nsidc0611/iceage_nh_12.5km_19840101_19841231_v4.1.nc
```

고정 주차 프레임을 생성한다.

```bash
polar-memory process-all
```

2024년 52주 계절 프레임도 함께 생성하려면:

```bash
polar-memory process-all --seasonal-year 2024
```

Blender 설치 후 640×640 프리뷰 프레임을 렌더링한다.

```bash
blender --background --python blender/render.py -- \
  --input data/processed/snapshots \
  --output outputs/frames
```

연도·다년생 해빙 비율·범례를 렌더 프레임에 합성한다.

```bash
polar-memory compose \
  --input outputs/frames \
  --output outputs/composed
```

합성된 연도별 프레임을 약 25초짜리 H.264 영상으로 묶는다.

```bash
polar-memory encode \
  --input outputs/composed \
  --output outputs/final/memory-timeline.mp4 \
  --seconds-per-frame 0.6
```

지도와 그래프를 분리하고 연도 사이를 부드럽게 전환한 편집 디자인 영상을
바로 생성한다.

```bash
polar-memory editorial
```

도입·계절 변화·장기 변화·과거/현재 비교·마무리를 연결한 통합 프리뷰를
생성한다.

```bash
polar-memory story
```

테스트:

```bash
pytest
ruff check .
```

## 출력

```text
data/processed/
├── snapshots/
│   ├── height/
│   ├── mask/
│   └── preview/
├── seasonal/
│   └── 2024/
└── summary.csv
```

`height`는 16비트 정규화 높이 맵이며 실제 얼음 두께가 아니다.
