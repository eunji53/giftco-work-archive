# -*- coding: utf-8 -*-
"""
02_match_buyer_names(구매처명 매칭) 설정값 모음.

이 파일의 부모 폴더(sarang87/)를 기준으로 경로를 잡습니다.
matcher/ 패키지 안에 있으므로 한 단계 더 올라갑니다.
(스크립트를 어느 폴더에서 실행하든 저장 위치가 바뀌지 않도록,
cwd가 아니라 이 파일의 실제 위치를 기준으로 삼습니다.)
"""
from pathlib import Path

# ------------------------------------------------------------
# 경로 설정
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# 입력 데이터 폴더 (거래데이터, 상품분류 보정 기준 파일)
DATA_DIR = BASE_DIR / "data"

# 01번 크롤링 노트북이 만든 출력물이 쌓이는 폴더
OUTPUT_DIR = BASE_DIR / "output"

# 입력 데이터
# - 01번 노트북 결과(상세페이지 체크포인트)는 output 폴더에서 읽습니다.
# - 거래데이터와 상품분류 보정 기준 파일은 data 폴더에서 읽습니다.
# - 상품분류 보정 기준 파일은 우선 data 폴더에서 찾고, 없으면 sarang87/ 폴더에서 찾습니다.
# - 변수명 FILE_87은 기존 코드 호환을 위해 유지합니다.
SOURCE_LABEL = "판촉사랑"

FILE_87 = OUTPUT_DIR / "crawl_result.xlsx"
FILE_TR = DATA_DIR / "transaction_data_merged.xlsx"

FILE_CATEGORY = DATA_DIR / "category_reference.xlsx"
if not FILE_CATEGORY.exists():
    FILE_CATEGORY = BASE_DIR / "category_reference.xlsx"

# 결과 파일은 output 폴더에 바로 저장합니다.
OUTPUT_FILE = OUTPUT_DIR / "buyer_name_matched.xlsx"

# BERT 임베딩 캐시 파일. 모델명별로 구분해서 저장하므로 모델을 바꿔도 서로 섞이지 않습니다.
# 상품명 텍스트가 같으면 재실행/재시작해도 다시 계산하지 않고 이 파일에서 바로 불러옵니다.
EMBEDDING_CACHE_FILE = OUTPUT_DIR / "embedding_cache.pkl"


# ------------------------------------------------------------
# 매칭 동작 설정
# ------------------------------------------------------------
# 거래데이터 배정 순서
# - 원본순서: 거래데이터 엑셀에 있는 행 순서대로 배정
# - 번호순서: 거래데이터 '번호' 숫자 순서대로 배정 후, 같은 번호는 원본순서
TRADE_ORDER_MODE = "원본순서"

# 인쇄방법은 매칭 조건에서 제외합니다.
# 이유: 거래데이터의 인쇄방법이 빈칸 또는 '-'인 행이 있어, 조건에 넣으면 정상 후보가 빠질 수 있습니다.
# 단, 결과 검수용으로 판촉사랑/거래데이터 인쇄방법 값은 상세 시트에 그대로 남깁니다.
USE_PRINT_METHOD = False

# 판촉사랑 파일에 이미 구매처분류(대)가 있는 경우, 그 값을 분류경로에 포함할지 여부
# 기존 1차 결과 파일을 입력으로 쓰는 경우, 이미 잘못 매칭된 대분류일 수 있으므로 기본값 False 권장
USE_87_LARGE_IN_CATEGORY_PATH = False

# 거래데이터 구매처명이 '-' 또는 빈칸인 경우 구매처명은 빈칸으로 둠
EMPTY_BUYER_VALUES = {"", "-"}

# 상품명 앞 제작상태 태그 제거 여부
# 예: [긴급제작] 화이트(백색) 10매 물티슈 -> 화이트(백색) 10매 물티슈
# 이번 버전에서는 상품명 완전일치 → exact → relaxed → KR-SBERT 순서로 사용합니다.
USE_PRODUCT_PREFIX_TAG_REMOVAL = True

# ------------------------------------------------------------
# BERT 상품명 유사도 설정
# ------------------------------------------------------------
# True면 상품명 완전일치, exact, relaxed가 모두 실패했을 때만 BERT 유사도를 사용합니다.
USE_BERT_PRODUCT_SIMILARITY = True

# 한국어 상품명 비교용 KR-SBERT 모델명입니다.
# 인터넷이 막힌 환경이면 모델을 미리 다운로드한 로컬 경로로 바꿔주세요.
# SBERT성능이 안좋으면 KURE 사용 밑에 BERT_MODEL_NAME = "nlpai-lab/KURE-v1" 으로 수정하면 KURE 사용가능 → SBERT는 주석처리
# BERT_MODEL_NAME = "nlpai-lab/KURE-v1"
BERT_MODEL_NAME = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

# 자동 매칭 기준. 처음에는 보수적으로 0.90 이상 권장.
BERT_SIM_THRESHOLD = 0.60

# BERT 후보 수 제한은 두지 않습니다.
# 공통 필터(중분류 → 소분류 → 날짜)를 통과한 후보 전체를 대상으로 상품명 유사도를 계산합니다.
# 후보가 많은 날짜도 제외하지 않고 모두 비교합니다.

# GPU 사용 설정
# CUDA GPU가 없으면 CPU로 자동 전환하지 않고 오류를 띄웁니다.
BERT_DEVICE = "cuda"
REQUIRE_CUDA_GPU = True
