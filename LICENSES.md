# 출처 및 라이선스

이 문서는 《북극의 기억층》 최종 영상과 설명서에 사용된 데이터, 폰트,
제작 도구와 참고 자료를 정리한다.

## 최종 결과물에 사용된 자료

### NSIDC 해빙 연령 데이터

- 자료명: EASE-Grid Sea Ice Age, Version 4
- 데이터 ID: NSIDC-0611
- 제공: NASA National Snow and Ice Data Center Distributed Active Archive Center
- DOI: https://doi.org/10.5067/UTAV7490FEPB
- 사용 범위: 1984~2024년 제11주 및 2024년 제1주~제52주 NetCDF
- 접근일: 2026년 7월 29일
- 사용 내용: 해빙 연령 지도, 해빙 범위·비율 계산과 영상 시각화
- 사용 조건: 데이터셋 제작자와 NSIDC 자료 출처 명시

권장 인용문:

> Tschudi, M., Meier, W. N., Stewart, J. S., Fowler, C. & Maslanik, J.
> (2019). EASE-Grid Sea Ice Age. (NSIDC-0611, Version 4). [Data Set].
> Boulder, Colorado USA. NASA National Snow and Ice Data Center
> Distributed Active Archive Center.
> https://doi.org/10.5067/UTAV7490FEPB

원본 NetCDF 파일은 용량과 재배포 범위를 고려하여 Git 저장소에 포함하지
않는다. 실행 방법과 원본 주소, 사용 범위와 해시 목록만 저장한다.

### Wanted Sans

- 폰트명: Wanted Sans 1.0.3
- 제작·배포: 원티드랩
- 라이선스: SIL Open Font License 1.1
- 공식 저장소: https://github.com/wanteddev/wanted-sans
- 사용 내용: 최종 영상의 한국어·영어 제목, 수치, 범례와 출처 표기

재현 가능한 렌더링을 위해 Regular·Bold 글꼴 파일과 원본 OFL 문서를
`assets/fonts/wanted-sans/`에 보관한다. 제출 영상에는 글자가 픽셀로
렌더링되며 폰트 파일 자체는 제출 ZIP에 포함하지 않는다.

작품 설명서 DOCX에는 문서 호환성을 위해 Noto Sans CJK KR을 사용한다.

## 제작 도구

다음 프로그램과 라이브러리는 데이터 처리와 영상 제작 도구로 사용했다.
해당 프로그램의 실행 파일이나 소스 코드를 작품 제출물에 포함하지 않는다.

| 도구 | 사용 목적 | 공식 정보 |
|---|---|---|
| Python | 데이터 처리 코드 실행 | https://www.python.org/ |
| xarray | NetCDF 읽기와 배열 처리 | https://xarray.dev/ |
| NumPy | 수치 계산 | https://numpy.org/ |
| Pillow | 지도·그래프·자막 렌더링 | https://python-pillow.org/ |
| FFmpeg | MP4 영상 인코딩 | https://ffmpeg.org/ |

## 참고했지만 결과물에 포함하지 않은 자료

다음 영상은 데이터 애니메이션의 정보 배치와 시간 흐름을 연구하는 참고
자료로만 보았다. 영상, 이미지, 음원, 자막 또는 코드를 복사하거나 최종
결과물에 포함하지 않았다.

- Daily Polar Sea Ice Area with Monthly Ice Extent  
  https://www.reddit.com/r/dataisbeautiful/comments/jad2fm/
- Animation of Antarctic Sea Ice  
  https://www.reddit.com/r/dataisbeautiful/comments/170leop/

## 사용하지 않은 외부 자산

- 외부 사진 또는 위성 이미지: 사용하지 않음
- 외부 일러스트·아이콘·로고: 사용하지 않음
- 외부 음원·효과음·내레이션: 사용하지 않음
- 생성형 AI 이미지·영상·음성: 사용하지 않음

지도, 그래프와 수치는 NSIDC 원본 데이터와 프로젝트 코드로 생성했다.

## 제출물 표기용 요약

> Data: Tschudi et al., EASE-Grid Sea Ice Age V4,
> NSIDC-0611, NASA NSIDC DAAC,
> https://doi.org/10.5067/UTAV7490FEPB  
> Video font: Wanted Sans 1.0.3, SIL Open Font License 1.1

## 제출 전 확인

- [ ] 최종 영상의 데이터 출처와 DOI가 읽을 수 있는 크기로 표시되어 있다.
- [ ] 작품 설명서의 데이터 사용 기간과 접근일이 이 문서와 일치한다.
- [ ] 최종 영상에 음원을 추가할 경우 출처와 라이선스를 이 문서에 추가한다.
- [ ] 외부 이미지·아이콘을 추가할 경우 원작자와 사용 허가를 기록한다.
- [ ] 소스 코드를 공개 배포할 경우 저장소 자체의 코드 라이선스를 별도로 정한다.
