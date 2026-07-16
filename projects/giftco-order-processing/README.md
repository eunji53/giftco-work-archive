# giftco-order-processing

지금까지의 발주서를 정리하는 작업 모음. 조아기프트, 고려기프트, 기타 이메일로 들어오는 발주서를 정리하고, 그 외 거래데이터를 정리하는 폴더도 포함합니다.

## 폴더 구조

### `joagift/`

조아기프트 발주서 메일을 IMAP으로 수집해 필드를 파싱하고 엑셀로 변환하는 파이프라인

- `01_collect_and_clean_mail.ipynb` — IMAP으로 메일함에서 발주서 메일을 수집하고 본문(HTML/plain)을 정제
  - IMAP은 폴더 하나당 한 번에 최대 400건까지만 조회가 되어, 연도별 폴더(2018~2023)로 나눠 수집하도록 구성
  - 결과물: `output/01-10_mail_clean_final.xlsx` (본문이 정제된 메일 목록, 02_의 입력으로 사용)
- `02_parse_and_merge_test.ipynb` — 정제된 메일 본문에서 품명/수량/단가 등 필드를 파싱해 엑셀로 변환하는 로직을 검증하는 테스트 노트북
  - 결과물: `output/joagift_transaction_data_test.xlsx`
- `02_parse_and_merge.py` — `02_parse_and_merge_test.ipynb`와 동일한 파싱 로직을 담은 운영용 스크립트
  - 결과물: `output/joagift_transaction_data.xlsx`

### `goryeogift/`

고려기프트 파트너 사이트(adpanchok.co.kr)에서 발주서 PDF를 수집해 파싱하고 엑셀로 정리하는 파이프라인. 번호 순서(`00_`~`05_`)대로 실행

- `00_crawl_orders.ipynb` — Selenium으로 발주목록에서 "승인" 클릭 → PDF 다운로드를 반복. 로그인은 매번 보안코드(OTP)가 필요해 수동으로 하고 이후는 자동 진행. `progress_checkpoint.json`에 진행 페이지를 저장해서 중간에 멈춰도(로그인만 다시 하면) 이어서 진행됨
- `01_diagnose_pdf_text.ipynb` — PDF 1개를 지정해 원문 추출 → 품목 블록 추출 → 줄 파싱까지 단계별로 확인하는 디버깅용 노트북
- `02_extract_and_convert.py` — PDF를 전부 순회하며 발주일/납기일/거래처/발송처/품목(수량·단가·공급가액·부가세·합계)을 파싱해 엑셀로 저장 (메인 파이프라인). 파싱 로직은 `pdf_parser.py` 사용
  - 결과물: `config.ORDERS_XLSX`
- `03_analyze_multi_item_orders.ipynb` — 파일 하나에 메인 상품이 여러 개 들어있는 경우가 몇 건인지 분석하는 진단용 노트북
  - 결과물: `config.MULTI_ITEM_ANALYSIS_PATH`
- `04_flatten_to_one_row_per_item.ipynb` — 메인 상품 1개 = 1행으로 정리하는 실제 생산 단계. 옵션 행(택배비 등)은 직전 메인 상품의 부대비용으로 합산. 끝에 "품목 합계+부대비용 ≠ PDF 총합계" 파일을 찾는 검증 셀 포함
  - 결과물: `config.FLATTENED_ORDERS_PATH`
- `05_detect_broken_item_names.ipynb` — PDF 추출 과정에서 잘리거나 깨진 것으로 의심되는 상품명을 패턴별로 찾는 QA용 노트북
  - 결과물: `config.BROKEN_NAMES_PATH`
- `config.py` — 파이프라인 전체가 쓰는 경로(`PDF_DIR`, 각 단계 결과 파일 등)를 한 곳에 모아둠. 경로를 바꿀 일이 있으면 여기만 수정. 결과 저장 폴더(`output/`)는 없으면 자동 생성. 로컬 절대경로라 gitignore 대상 — 아래 "설정" 참고
- `pdf_parser.py` — PDF 텍스트에서 품목/발송처/사양을 파싱하는 공통 함수 모음 (`01_`, `02_`가 사용). PyPDF2 추출 시 숫자 사이 공백이 불규칙하게 누락되는 문제를 단계적으로 처리하고, 그래도 숫자를 못 나누면 품목코드/상품명만 남기고 숫자는 비워서 반환 (엑셀에서 빈 칸으로 눈에 띄어 수동 확인 가능)

#### 설정

`config.py`는 로컬 절대경로가 들어있어 커밋하지 않습니다. 처음 실행하기 전에:

1. `config.example.py`를 같은 폴더에 `config.py`로 복사
2. `config.py`를 열어 각 경로 값(`PDF_DIR`, `CRAWL_DOWNLOAD_DIR`, `ORDERS_XLSX`, `RESULT_DIR`)을 본인 PC 경로로 채우기

### `email-attachments/`

이메일(POP3)에서 제목에 "발주서/발주" 키워드가 있는 메일을 찾아 첨부파일만 추출하는 작업. 고려기프트/조아기프트는 각각 별도 파이프라인이 있어 제외.

- `00_extract_order_attachments.ipynb` — 메일함을 순회하며 키워드에 맞는 메일의 첨부파일을 다운로드 (시안/사업자등록증/로고 등 관련 없는 첨부는 제외). SSL 끊김 자동 재연결 + 체크포인트 재개 지원
  - 결과물: `attachments/` (첨부파일), `order_mail_list.xlsx` (메일 목록)

**진행 상태**: 첨부파일 추출까지 완료. 추출된 첨부파일을 실제 발주서 데이터로 정리하는 다음 단계는 별도로 진행됨(타 담당자). 향후 TODO — 첨부파일 없이 본문에만 "발주" 관련 텍스트가 있는 메일도 캡처해서 추출하는 방법 검토 필요.

### `sarang87/`

판촉사랑(87sarang.com)에서 납품사례를 크롤링하고, 기존에 수작업으로 모아둔 거래데이터와 대조해 구매처명을 복원하는 파이프라인.

- `scripts/01_crawl_supply_cases.py` — 운영용 크롤링 진입점(`def main()`). 실제 로직은 `crawler/` 패키지에 있음
  - `crawler/config.py` — URL/파일명/헤더/기능 플래그 등 설정
  - `crawler/parsing_utils.py` — 텍스트·가격·카테고리 파싱 공통 유틸
  - `crawler/checkpoint_io.py` — 체크포인트/에러로그 파일 입출력
  - `crawler/fetch.py` — requests + Selenium 페이지 요청
  - `crawler/list_page.py`, `crawler/detail_page.py` — 목록/상세페이지 파싱
  - `crawler/excel_export.py` — 체크포인트 결과를 엑셀로 저장
  - `crawler/collector.py` — 위 모듈을 엮는 1단계(목록)/2단계(상세) 수집 오케스트레이션
  - `crawler/logging_setup.py` — 콘솔(페이지 단위 진행상황 + 경고/오류만)과 파일(`output/crawl.log`, 상품 단위 상세 로그) 로깅 분리 설정
  - 결과물: `crawl_result.xlsx`, `list_checkpoint.csv`, `detail_checkpoint.csv/xlsx`, `output/crawl.log` (전부 gitignore 대상)
- `scripts/02_match_buyer_names.py` — 운영용 매칭 진입점. 크롤링 결과와 `data/transaction_data_merged.xlsx`(기존 거래데이터)를 구매처분류(중/소) → 날짜 → 상품명(완전일치 → exact 정규화 → relaxed 정규화 → KR-SBERT 유사도) 순서로 1:1 매칭해 구매처명을 복원. 실제 로직은 `matcher/` 패키지에 있음
  - `matcher/config.py` — 파일 경로/매칭 조건/BERT 설정 등 전체 설정값
  - `matcher/normalize.py` — 텍스트·상품명·분류명 정규화, 날짜 파싱, 컬럼 자동탐색 유틸
  - `matcher/category_exceptions.py` — 구매처분류(중/소)가 판촉사랑·거래데이터 간에 이름이 다르게 붙은 경우의 예외 매핑 (예: 전시회/박람회 ↔ 기념행사별, 관광지 ↔ 골프관련)
  - `matcher/bert.py` — CUDA 환경 점검, KR-SBERT 임베딩 계산·캐시(`output/embedding_cache.pkl`), 상품명 유사도 매칭
  - `matcher/category_fix.py` — `data/category_reference.xlsx` 기준 상품분류(대/중/소) 보정
  - `matcher/logging_setup.py` — 콘솔과 `output/match.log` 파일에 동시 기록하는 `log()` 헬퍼
  - GPU(CUDA) 필요 (`REQUIRE_CUDA_GPU = True`)
  - 결과물: `output/buyer_name_matched.xlsx`(매칭 결과), `output/match.log`(실행 로그), `output/embedding_cache.pkl`(BERT 임베딩 캐시, 전부 gitignore 대상)
- `data/` — 입력 데이터 (전부 gitignore 대상, 로컬에 직접 채워야 함)
  - `supply_case_template.xlsx` — 크롤링 결과 엑셀 서식 기준 파일
  - `transaction_data_merged.xlsx` — 기존에 수작업으로 수집한 거래데이터(6만여 건) 병합본
  - `category_reference.xlsx` — 상품분류(대/중/소) 보정용 매핑표

#### 실행 방법 (sarang87/ 폴더 기준)

```
python scripts/01_crawl_supply_cases.py
python scripts/02_match_buyer_names.py
```
