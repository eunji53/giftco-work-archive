# giftco-order-processing

지금까지의 발주서를 정리하는 작업 모음. 조아기프트, 고려기프트, 기타 이메일로 들어오는 발주서를 정리하고, 그 외 거래데이터를 정리하는 폴더도 포함합니다.

## 폴더 구조

- `joagift/` — 조아기프트 발주서 메일을 IMAP으로 수집해 필드를 파싱하고 엑셀로 변환하는 파이프라인
  - `01_collect_and_clean_mail.ipynb` — IMAP으로 메일함에서 발주서 메일을 수집하고 본문(HTML/plain)을 정제
    - IMAP은 폴더 하나당 한 번에 최대 400건까지만 조회가 되어, 연도별 폴더(2018~2023)로 나눠 수집하도록 구성
    - 결과물: `output/01-10_mail_clean_final.xlsx` (본문이 정제된 메일 목록, 02_의 입력으로 사용)
  - `02_parse_and_merge_test.ipynb` — 정제된 메일 본문에서 품명/수량/단가 등 필드를 파싱해 엑셀로 변환하는 로직을 검증하는 테스트 노트북
    - 결과물: `output/joagift_transaction_data_test.xlsx`
  - `02_parse_and_merge.py` — `02_parse_and_merge_test.ipynb`와 동일한 파싱 로직을 담은 운영용 스크립트
    - 결과물: `output/joagift_transaction_data.xlsx`
