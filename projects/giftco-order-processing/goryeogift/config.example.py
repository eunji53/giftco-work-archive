import os

# 이 파일은 예시입니다. 복사해서 config.py로 저장한 뒤 본인 PC 경로로 값을 채우세요.
# (config.py는 gitignore 대상이라 커밋되지 않습니다.)

# 발주서 원본 PDF 아카이브 폴더 (01_, 02_가 여기서 읽음)
PDF_DIR = r""

# 00_이 크롤링한 PDF를 새로 저장하는 폴더 (확인 후 PDF_DIR로 옮기는 걸 권장)
CRAWL_DOWNLOAD_DIR = r""

# [02_extract_and_convert.py 생성] PDF에서 뽑은 품목별 원본 데이터 (파일당 여러 행).
# 03_/04_가 이 파일을 읽어서 다음 단계로 가공함.
ORDERS_XLSX = r""

# 03_/04_/05_ 결과 파일 저장 폴더
RESULT_DIR = r""
os.makedirs(RESULT_DIR, exist_ok=True)

# [03_analyze_multi_item_orders.ipynb 생성]
# 파일 하나에 상품이 여러 개 들어있는 발주서 목록 + 메인상품별 부대비용 정리.
MULTI_ITEM_ANALYSIS_PATH = os.path.join(RESULT_DIR, "goryeogift_multi_item_analysis.xlsx")

# [04_flatten_to_one_row_per_item.ipynb 생성]
# 메인상품 1개 = 1행으로 정리하고 옵션(택배비 등) 금액을 부대비용/총비용으로 합산한 최종 결과.
FLATTENED_ORDERS_PATH = os.path.join(RESULT_DIR, "goryeogift_orders_flattened.xlsx")

# [05_detect_broken_item_names.ipynb 생성]
# PDF 추출 과정에서 잘리거나 깨진 것으로 의심되는 상품명 목록 (패턴별 시트 구분).
BROKEN_NAMES_PATH = os.path.join(RESULT_DIR, "goryeogift_broken_item_names.xlsx")
