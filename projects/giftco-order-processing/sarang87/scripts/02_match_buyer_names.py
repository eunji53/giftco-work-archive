# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 — 운영 실행용 스크립트

로직 검증/디버그는 02_match_buyer_names_test.ipynb(테스트 노트북)를 사용하고,
실제 운영 실행은 이 스크립트로 합니다.

실행 방법 (sarang87/ 폴더 기준):
    python scripts/02_match_buyer_names.py
"""


# ---- 판촉사랑 구매처명 복원 노트북 - pandas + relaxed + KR-SBERT GPU ----


# ---- 변경사항 ----


# ---- 판촉사랑 구매처 매칭 1대1 - relaxed + KR-SBERT 상품명 유사도 버전 ----

import sys
from pathlib import Path

# matcher 패키지(sarang87/matcher)를 어디서 실행하든 import할 수 있도록 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from matcher.config import *  # noqa: F401,F403,E402 (설정값은 matcher/config.py에서 관리)
from matcher.logging_setup import log  # noqa: E402
from matcher.normalize import (  # noqa: E402
    clean_text,
    normalize_product_raw,
    normalize_product_exact,
    normalize_product_relaxed,
    normalize_category,
    parse_one_date,
    find_col,
    find_best_col_by_nonblank,
)
from matcher.category_exceptions import (  # noqa: E402
    norm_mid,
    norm_small,
    unique_keep_order,
    get_trade_filter_pairs_for_promo,
    get_promo_filter_pairs_for_trade,
)
from matcher.bert import (  # noqa: E402
    check_cuda_or_raise,
    _embedding_cache,
    save_embedding_cache,
    find_bert_product_candidates,
)
from matcher.category_fix import apply_product_category_fix  # noqa: E402

log("Python:", sys.version)
log("pandas version:", pd.__version__)


def display(obj):
    """Jupyter의 display()를 스크립트에서도 쓸 수 있게 하는 얕은 대체 함수."""
    try:
        log(obj.to_string())
    except AttributeError:
        log(obj)


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

log("sarang87 폴더:", BASE_DIR)
log("output 폴더:", OUTPUT_DIR)
log(f"{SOURCE_LABEL} 파일:", FILE_87)
log("거래데이터 파일:", FILE_TR)
log("상품분류 카테고리 파일:", FILE_CATEGORY)
log("결과 파일:", OUTPUT_FILE)

assert FILE_87.exists(), f"파일이 없습니다: {FILE_87}"
assert FILE_TR.exists(), f"파일이 없습니다: {FILE_TR}"
assert FILE_CATEGORY.exists(), f"파일이 없습니다: {FILE_CATEGORY}"

log("거래데이터 배정 순서:", TRADE_ORDER_MODE)
log("인쇄방법 조건: 제외 / 상세시트 확인용으로만 유지")
log("공통 필터 순서: 구매처분류(중) → 구매처분류(소) → 날짜")
log("상품명 비교 순서: 완전일치 → exact 기본정규화 → relaxed 보정정규화 → BERT 유사도")
log("BERT 사용:", USE_BERT_PRODUCT_SIMILARITY)
log("BERT 모델:", BERT_MODEL_NAME)
log("BERT 자동매칭 기준:", BERT_SIM_THRESHOLD)
log("BERT 후보 수 제한: 없음")
log("전체 배정 순서: 상품명완전일치 전체 → exact 전체 → relaxed 전체 → BERT 최고유사도")
log("BERT 배정 기준: 중분류+소분류+날짜 후보 중 미사용 후보의 최고 유사도 1개 배정")
log("분류 예외 7번: 거래데이터 전시회/박람회/축제/행사 중분류는 판촉사랑 기념행사별+전시회 중분류 후보로 확인")
log("분류 예외 추가: 판촉사랑 관광지/국립공원/놀이공원 하위 소분류는 거래데이터 골프관련/관광지 후보도 확인")
log("BERT_DEVICE:", BERT_DEVICE)
log("REQUIRE_CUDA_GPU:", REQUIRE_CUDA_GPU)


# ---- 0. BERT 사용 환경 사전 점검 ----
# 실제 매칭(파일 읽기 ~ relaxed 단계)을 다 돌리고 나서 맨 마지막 BERT 단계에서야
# sentence-transformers 미설치 / CUDA 미사용 문제를 알게 되면 그 앞 단계를 처음부터 다시
# 돌려야 하므로, 무거운 모델 로딩(get_bert_model)은 그대로 지연시키되 환경 점검만 여기서
# 미리 해서 문제가 있으면 매칭을 시작하기 전에 바로 중단합니다.



if USE_BERT_PRODUCT_SIMILARITY:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "BERT 상품명 유사도를 사용하려면 sentence-transformers 설치가 필요합니다. "
            "노트북/터미널에서 `pip install sentence-transformers` 실행 후 다시 실행하세요."
        ) from exc

    if BERT_DEVICE == "cuda":
        check_cuda_or_raise()

    log("BERT 사용 환경 사전 점검 통과")


# ---- 1. 파일 읽기 ----

def read_csv_auto(path):
    """CSV 인코딩 자동 시도. 판촉사랑 파일은 utf-8-sig가 우선입니다."""
    encodings = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]
    last_error = None

    for enc in encodings:
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False), enc
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"CSV 파일을 읽지 못했습니다: {path}\n마지막 오류: {last_error}")


def read_table_auto(path):
    """확장자에 따라 CSV 또는 Excel을 자동으로 읽습니다. Excel은 첫 번째 시트를 읽습니다."""
    suffix = str(path).lower()
    if suffix.endswith(".csv"):
        df, enc = read_csv_auto(path)
        log(f"{SOURCE_LABEL} CSV 인코딩:", enc)
        return df
    if suffix.endswith((".xlsx", ".xls")):
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise ValueError(f"지원하지 않는 파일 형식입니다: {path}")


# 판촉사랑 Excel / 거래데이터 Excel 읽기
log("pandas 방식으로 파일을 읽습니다.")
# 변수명 df87은 기존 코드 재사용을 위해 그대로 둡니다.
df87 = read_table_auto(FILE_87)
dftr = pd.read_excel(FILE_TR, dtype=str, keep_default_na=False)

# 컬럼명 문자열화 및 앞뒤 공백 정리
# 거래데이터에는 '구매처 명 '처럼 뒤 공백이 있는 컬럼도 있어 원본명은 최대한 유지하되 문자열화합니다.
df87.columns = [str(c).strip() for c in df87.columns]
dftr.columns = [str(c) for c in dftr.columns]

# 상품코드는 앞자리 0이 중요하므로 문자열 상태로 유지합니다.
# 여기서는 zfill을 하지 않고, 입력 파일에 있는 상품코드를 그대로 사용합니다.
if "상품코드" in df87.columns:
    df87["상품코드"] = df87["상품코드"].map(lambda x: "" if pd.isna(x) else str(x).strip())

log(f"{SOURCE_LABEL} 행 수:", len(df87))
log("거래데이터 행 수:", len(dftr))
log(f"{SOURCE_LABEL} 컬럼:", list(df87.columns))
log("거래데이터 컬럼:", list(dftr.columns))


# ---- 2. 정규화 함수 ----



# ---- 3. 컬럼 자동 탐색 ----

# 판촉사랑 컬럼
COL_87_KEY = find_col(df87, ["수집키"], required=False)
COL_87_CASE_ID = find_col(df87, ["납품사례ID"], required=False)
COL_87_PRODUCT_CODE = find_col(df87, ["상품코드"], required=False)
COL_87_PRODUCT = find_col(df87, ["상품명"])
COL_87_PRINT = find_col(df87, ["인쇄방법"], required=False)
COL_87_DATE = find_col(df87, ["등록일", "날짜"])
COL_87_LARGE = find_col(df87, ["구매처분류(대)", "구매처 분류(대)"], required=False)
COL_87_MID = find_col(df87, ["구매처분류(중)", "구매처 분류(중)"])
COL_87_SMALL = find_col(df87, ["구매처분류(소)", "구매처 분류(소)"], required=False)
COL_87_URL = find_col(df87, ["상세URL"], required=False)

# 거래데이터 컬럼
COL_TR_NO = find_col(dftr, ["번호"])
COL_TR_LARGE = find_col(dftr, ["구매처 분류(대)", "구매처분류(대)"])
COL_TR_MID = find_col(dftr, ["구매처 분류(중)", "구매처분류(중)"])
COL_TR_SMALL = find_col(dftr, ["구매처 분류(소)", "구매처분류(소)"], required=False)
COL_TR_DETAIL = find_col(dftr, ["구매처 분류(세)", "구매처분류(세)"], required=False)
COL_TR_PRODUCT = find_col(dftr, ["상품", "상품명"])
COL_TR_DATE = find_col(dftr, ["날짜", "등록일"])
COL_TR_PRINT = find_col(dftr, ["인쇄 방법", "인쇄방법"], required=False)
COL_TR_BUYER, buyer_col_matches = find_best_col_by_nonblank(
    dftr,
    ["구매처 명 ", "구매처 명", "구매처명"],
    exclude_values=("-",)
)

log(f"[{SOURCE_LABEL}]")
for name, col in [
    ("수집키", COL_87_KEY),
    ("납품사례ID", COL_87_CASE_ID),
    ("상품코드", COL_87_PRODUCT_CODE),
    ("상품명", COL_87_PRODUCT),
    ("인쇄방법", COL_87_PRINT),
    ("등록일", COL_87_DATE),
    ("구매처분류(대)", COL_87_LARGE),
    ("구매처분류(중)", COL_87_MID),
    ("구매처분류(소)", COL_87_SMALL),
    ("상세URL", COL_87_URL),
]:
    log(f"- {name}: {col}")


# 컬럼 위치 검수: 위치가 달라도 아래처럼 컬럼명으로 찾아서 사용합니다.
# 현재 업로드 파일 기준 예시: 상품코드=B열, 상품명=C열, 구매처분류(중)=M열, 구매처분류(소)=N열입니다.
log("\n[판촉사랑 컬럼 자동 탐색 완료]")
log("- 상품코드 컬럼:", COL_87_PRODUCT_CODE)
log("- 상품명 컬럼:", COL_87_PRODUCT)
log("- 구매처분류(중) 컬럼:", COL_87_MID)
log("- 구매처분류(소) 컬럼:", COL_87_SMALL)
if COL_87_PRODUCT_CODE:
    log("- 상품코드 앞자리 0 포함 예시:")
    display(df87[[COL_87_PRODUCT_CODE, COL_87_PRODUCT]].head(10))

log("\n[거래데이터]")
for name, col in [
    ("번호", COL_TR_NO),
    ("구매처 분류(대)", COL_TR_LARGE),
    ("구매처 분류(중)", COL_TR_MID),
    ("구매처 분류(소)", COL_TR_SMALL),
    ("구매처 분류(세)", COL_TR_DETAIL),
    ("구매처 명", COL_TR_BUYER),
    ("날짜", COL_TR_DATE),
    ("상품", COL_TR_PRODUCT),
    ("인쇄 방법", COL_TR_PRINT),
]:
    log(f"- {name}: {col}")

log("\n구매처명 후보 컬럼별 유효값 수:", buyer_col_matches)


# ---- 4. 키 생성 ----

df87_work = df87.copy().astype("object")
dftr_work = dftr.copy().astype("object")

# 원본 행 정보: 엑셀 데이터 행은 header 다음부터 시작하므로 index + 2
df87_work["_87_order"] = range(len(df87_work))
df87_work["_87_excel_row"] = df87_work.index + 2
dftr_work["_trade_order"] = range(len(dftr_work))
dftr_work["_trade_excel_row"] = dftr_work.index + 2

# 날짜/상품명 키
df87_work["_key_date"] = df87_work[COL_87_DATE].map(parse_one_date)
dftr_work["_key_date"] = dftr_work[COL_TR_DATE].map(parse_one_date)

df87_work["_key_product_raw"] = df87_work[COL_87_PRODUCT].map(normalize_product_raw)
dftr_work["_key_product_raw"] = dftr_work[COL_TR_PRODUCT].map(normalize_product_raw)

df87_work["_key_product_exact"] = df87_work[COL_87_PRODUCT].map(normalize_product_exact)
dftr_work["_key_product_exact"] = dftr_work[COL_TR_PRODUCT].map(normalize_product_exact)

# relaxed 보정정규화 키
# 상품명 exact가 실패했을 때, 상태/이벤트 문구·사이즈·1P·우산 살대 수 등
# 상품 식별에 직접적이지 않은 반복 표현을 보정한 뒤 비교합니다.
df87_work["_key_product_relaxed"] = df87_work[COL_87_PRODUCT].map(normalize_product_relaxed)
dftr_work["_key_product_relaxed"] = dftr_work[COL_TR_PRODUCT].map(normalize_product_relaxed)

# 인쇄방법 키
df87_work["_key_print"] = df87_work[COL_87_PRINT].map(normalize_category) if COL_87_PRINT else ""
dftr_work["_key_print"] = dftr_work[COL_TR_PRINT].map(normalize_category) if COL_TR_PRINT else ""

# 분류 경로 키용 원본 경로 저장
def get_87_path(row):
    items = []
    if USE_87_LARGE_IN_CATEGORY_PATH and COL_87_LARGE:
        items.append(row[COL_87_LARGE])
    items.append(row[COL_87_MID])
    if COL_87_SMALL:
        items.append(row[COL_87_SMALL])
    return items


def get_trade_path(row):
    items = [row[COL_TR_LARGE], row[COL_TR_MID]]
    if COL_TR_SMALL:
        items.append(row[COL_TR_SMALL])
    if COL_TR_DETAIL:
        items.append(row[COL_TR_DETAIL])
    return items


df87_work["_category_path"] = df87_work.apply(get_87_path, axis=1)
dftr_work["_category_path"] = dftr_work.apply(get_trade_path, axis=1)

# 거래데이터 번호 숫자화. 정렬 보조용이며, 1대1 검증은 index 기준으로 함.
dftr_work["_trade_no_num"] = pd.to_numeric(dftr_work[COL_TR_NO].map(clean_text), errors="coerce")

# 날짜 기준 거래데이터 그룹.
# 날짜는 무조건 일치해야 하므로, 매칭과 미매칭 진단 모두 같은 날짜 그룹 안에서만 수행합니다.
trade_groups_by_date = {}

for idx, row in dftr_work.iterrows():
    date_key = row["_key_date"]
    if date_key:
        trade_groups_by_date.setdefault(date_key, []).append(idx)

log(f"{SOURCE_LABEL} 날짜 빈값:", int((df87_work["_key_date"] == "").sum()))
log("거래데이터 날짜 빈값:", int((dftr_work["_key_date"] == "").sum()))
log("거래데이터 날짜 그룹 수:", len(trade_groups_by_date))
log(f"{SOURCE_LABEL} 상품명 exact 빈값:", int((df87_work["_key_product_exact"] == "").sum()))
log("거래데이터 상품명 exact 빈값:", int((dftr_work["_key_product_exact"] == "").sum()))
log(f"{SOURCE_LABEL} 상품명 exact 정규화 변경 행 수:", int((df87_work["_key_product_raw"] != df87_work["_key_product_exact"]).sum()))
log("거래데이터 상품명 exact 정규화 변경 행 수:", int((dftr_work["_key_product_raw"] != dftr_work["_key_product_exact"]).sum()))
log(f"{SOURCE_LABEL} 상품명 relaxed 보정 변경 행 수:", int((df87_work["_key_product_exact"] != df87_work["_key_product_relaxed"]).sum()))
log("거래데이터 상품명 relaxed 보정 변경 행 수:", int((dftr_work["_key_product_exact"] != dftr_work["_key_product_relaxed"]).sum()))
log(f"{SOURCE_LABEL} 분류경로 예시:")
display(df87_work[[COL_87_MID] + ([COL_87_SMALL] if COL_87_SMALL else []) + ["_category_path"]].head(10))


# ---- 5-1. 배정 순서 · 분류 예외 · 거래데이터 인덱스 준비 ----

# 거래데이터 후보 정렬 함수
if TRADE_ORDER_MODE == "번호순서":
    def sort_trade_indexes(indexes):
        return sorted(
            list(indexes),
            key=lambda i: (
                pd.isna(dftr_work.at[i, "_trade_no_num"]),
                dftr_work.at[i, "_trade_no_num"] if not pd.isna(dftr_work.at[i, "_trade_no_num"]) else 10**18,
                dftr_work.at[i, "_trade_order"],
            )
        )
else:
    def sort_trade_indexes(indexes):
        return sorted(list(indexes), key=lambda i: dftr_work.at[i, "_trade_order"])


# ------------------------------------------------------------
# 빠른 단계별 필터용 키 생성
# ------------------------------------------------------------
# 사람의 엑셀 필터 방식과 동일하게 처리합니다.
# 공통 조건:
# 1) 거래데이터 구매처 분류(중) 컬럼에서 찾기
# 2) 중분류가 맞은 거래데이터 안에서 구매처 분류(소) 컬럼 찾기
# 3) 중+소분류가 맞은 거래데이터 안에서 판촉사랑 등록일만 확인
#
# 상품명 비교 순서:
# 4-1) 상품명 완전일치(raw)
# 4-2) 상품명 exact 기본정규화
# 4-3) 상품명 relaxed 보정정규화
# 4-4) BERT 상품명 의미 유사도
#
# 전부 맞으면 미사용 거래데이터를 거래데이터 행 순서대로 1대1 배정합니다.



# 87 / 거래데이터의 중분류, 소분류 비교 키
# 원본 컬럼은 건드리지 않고 비교용 키만 추가합니다.
df87_work["_key_mid"] = df87_work[COL_87_MID].map(norm_mid)
df87_work["_key_small"] = df87_work[COL_87_SMALL].map(norm_small) if COL_87_SMALL else ""

dftr_work["_key_mid"] = dftr_work[COL_TR_MID].map(norm_mid)
dftr_work["_key_small"] = dftr_work[COL_TR_SMALL].map(norm_small) if COL_TR_SMALL else ""





def collect_sorted_indexes(indexes):
    """여러 후보 index를 중복 제거 후 거래데이터 기준 순서로 정렬."""
    return sort_trade_indexes(unique_keep_order(indexes))












def collect_from_mapping(mapping, keys):
    """여러 key에 해당하는 후보 index를 합친 뒤 정렬."""
    out = []
    for key in keys:
        out.extend(mapping.get(key, []))
    return collect_sorted_indexes(out)


# ------------------------------------------------------------
# 거래데이터를 단계별 필터 키로 미리 그룹화합니다.
# ------------------------------------------------------------
# 날짜 목록 전체를 만들지 않습니다.
# 필요한 것은 "해당 날짜가 있는지"와 "해당 날짜 후보 index"뿐입니다.

trade_indexes_sorted = sort_trade_indexes(dftr_work.index.tolist())

trade_by_mid = {}
trade_by_mid_small = {}
trade_by_mid_small_date = {}
trade_by_mid_small_date_raw = {}
trade_by_mid_small_date_exact = {}
trade_by_mid_small_date_relaxed = {}

for idxtr in trade_indexes_sorted:
    mid = clean_text(dftr_work.at[idxtr, "_key_mid"])
    small = clean_text(dftr_work.at[idxtr, "_key_small"])
    date_key = clean_text(dftr_work.at[idxtr, "_key_date"])
    p_raw = clean_text(dftr_work.at[idxtr, "_key_product_raw"])
    p_exact = clean_text(dftr_work.at[idxtr, "_key_product_exact"])
    p_relaxed = clean_text(dftr_work.at[idxtr, "_key_product_relaxed"])

    if not mid:
        continue

    # 1단계: 중분류 필터
    trade_by_mid.setdefault(mid, []).append(idxtr)

    # 2단계: 중분류 + 소분류 필터
    ms_key = (mid, small)
    trade_by_mid_small.setdefault(ms_key, []).append(idxtr)

    # 3단계: 중분류 + 소분류 + 해당 날짜 필터
    if date_key:
        msd_key = (mid, small, date_key)
        trade_by_mid_small_date.setdefault(msd_key, []).append(idxtr)

        # 4단계: 상품명 필터용 색인
        if p_raw:
            trade_by_mid_small_date_raw.setdefault((mid, small, date_key, p_raw), []).append(idxtr)

        if p_exact:
            trade_by_mid_small_date_exact.setdefault((mid, small, date_key, p_exact), []).append(idxtr)

        if p_relaxed:
            trade_by_mid_small_date_relaxed.setdefault((mid, small, date_key, p_relaxed), []).append(idxtr)


# ---- 5-2. BERT 유사도 함수 정의 ----

# ------------------------------------------------------------
# BERT 상품명 의미 유사도 함수 - GPU 사용
# ------------------------------------------------------------
# check_cuda_or_raise는 위쪽 "0. BERT 사용 환경 사전 점검" 단계로 옮겼습니다.
# 여기서는 이미 정의된 그 함수를 그대로 사용합니다.














# ------------------------------------------------------------
# 진단용 문자열 함수
# ------------------------------------------------------------
def limited_join(values, limit=30):
    """진단용 문자열이 너무 길어지지 않도록 제한해서 표시합니다."""
    vals = [clean_text(v) for v in values if clean_text(v)]
    seen = []
    for v in vals:
        if v not in seen:
            seen.append(v)
    if len(seen) > limit:
        return " / ".join(seen[:limit]) + f" / ...외 {len(seen) - limit}개"
    return " / ".join(seen)


def join_trade_no(indexes, limit=30):
    """거래데이터 번호를 / 로 묶어 표시합니다."""
    indexes = sort_trade_indexes(list(dict.fromkeys(indexes)))
    if not indexes:
        return ""
    return limited_join(dftr_work.loc[indexes, COL_TR_NO].map(clean_text).tolist(), limit=limit)


def get_bert_score_text(indexes, score_map, limit=30):
    """후보별 BERT 점수를 사람이 보기 쉽게 표시합니다."""
    items = []
    for idxtr in indexes[:limit]:
        no = clean_text(dftr_work.at[idxtr, COL_TR_NO])
        score = score_map.get(idxtr, "")
        if score == "":
            items.append(no)
        else:
            items.append(f"{no}:{score:.4f}")
    if len(indexes) > limit:
        items.append(f"...외 {len(indexes) - limit}개")
    return " / ".join(items)


# ---- 5-3. 매칭 함수 정의 및 결과 컬럼 준비 ----

# ------------------------------------------------------------
# 판촉사랑 1행 기준 후보 추출
# ------------------------------------------------------------
def get_trade_candidates_by_stage(idx87, enable_bert=True):
    """
    판촉사랑 1행에 대해 사람의 필터 방식으로 단계별 후보를 반환합니다.

    상태값 판단 기준:
    - 중분류 후보가 없으면: 미매칭_구매처분류(중)_매칭안됨
    - 중분류는 있으나 소분류 후보가 없으면: 미매칭_구매처분류(소)_매칭안됨
    - 중/소분류는 있으나 해당 날짜 후보가 없으면: 미매칭_날짜없음
    - 중/소분류+날짜는 있으나 상품명 후보가 없으면: 미매칭_상품명매칭안됨
    - 전부 맞으면: 1대1 매칭
    """
    row87 = df87_work.loc[idx87]

    mid = clean_text(row87["_key_mid"])
    small = clean_text(row87["_key_small"])
    date_key = clean_text(row87["_key_date"])
    p_raw = clean_text(row87["_key_product_raw"])
    p_exact = clean_text(row87["_key_product_exact"])
    p_relaxed = clean_text(row87["_key_product_relaxed"])

    # 7번 수정: 특정 거래데이터 중분류가 판촉사랑에서 여러 중분류로 나뉜 경우를 처리합니다.
    # 예: 거래데이터 중분류 "전시회/박람회/축제/행사"는
    #     판촉사랑 중분류 "기념행사별", "전시회" 후보와 호환 처리합니다.
    filter_pairs = get_trade_filter_pairs_for_promo(mid, small) if mid else []
    mid_candidates = unique_keep_order([pair[0] for pair in filter_pairs])

    mid_indexes = collect_from_mapping(trade_by_mid, mid_candidates) if mid_candidates else []
    mid_small_indexes = collect_from_mapping(trade_by_mid_small, filter_pairs) if filter_pairs else []
    mid_small_date_keys = [(m, s, date_key) for m, s in filter_pairs] if (filter_pairs and date_key) else []
    mid_small_date_indexes = collect_from_mapping(trade_by_mid_small_date, mid_small_date_keys) if mid_small_date_keys else []

    # 1순위: 상품명 완전일치(raw)
    raw_keys = [(m, s, date_key, p_raw) for m, s in filter_pairs] if (filter_pairs and date_key and p_raw) else []
    raw_indexes = collect_from_mapping(trade_by_mid_small_date_raw, raw_keys) if raw_keys else []

    # 2순위: 상품명 exact 기본정규화
    exact_indexes = []
    if not raw_indexes and p_exact:
        exact_keys = [(m, s, date_key, p_exact) for m, s in filter_pairs] if (filter_pairs and date_key) else []
        exact_indexes = collect_from_mapping(trade_by_mid_small_date_exact, exact_keys) if exact_keys else []

    # 3순위: 상품명 relaxed 보정정규화
    relaxed_indexes = []
    if not raw_indexes and not exact_indexes and p_relaxed:
        relaxed_keys = [(m, s, date_key, p_relaxed) for m, s in filter_pairs] if (filter_pairs and date_key) else []
        relaxed_indexes = collect_from_mapping(trade_by_mid_small_date_relaxed, relaxed_keys) if relaxed_keys else []

    # 4순위: BERT 상품명 의미 유사도
    bert_indexes = []
    bert_scores = {}
    if enable_bert and not raw_indexes and not exact_indexes and not relaxed_indexes and mid_small_date_indexes:
        # BERT는 상품명 완전일치/exact/relaxed가 모두 실패한 경우에만 실행합니다.
        # 비교 텍스트는 relaxed 보정키를 우선 사용하고, 없으면 exact/raw로 fallback합니다.
        bert_indexes, bert_scores = find_bert_product_candidates(
            query_product=p_relaxed or p_exact or p_raw,
            candidate_indexes=mid_small_date_indexes,
            dftr_work=dftr_work,
            sort_trade_indexes=sort_trade_indexes,
            threshold=BERT_SIM_THRESHOLD,
        )

    # 상품명 후보 전체: raw → exact → relaxed → BERT 순서
    product_indexes = sort_trade_indexes(set(raw_indexes) | set(exact_indexes) | set(relaxed_indexes) | set(bert_indexes))

    return {
        "mid": mid,
        "small": small,
        "date_key": date_key,
        "filter_pairs": filter_pairs,
        "mid_candidates": mid_candidates,
        "mid_indexes": mid_indexes,
        "mid_small_indexes": mid_small_indexes,
        "mid_small_date_indexes": mid_small_date_indexes,
        "raw_indexes": raw_indexes,
        "exact_indexes": exact_indexes,
        "relaxed_indexes": relaxed_indexes,
        "bert_indexes": bert_indexes,
        "bert_scores": bert_scores,
        "product_indexes": product_indexes,
        "mid_count": len(mid_indexes),
        "mid_small_count": len(mid_small_indexes),
        "mid_small_date_count": len(mid_small_date_indexes),
        "product_count": len(product_indexes),
    }


def choose_trade_index(stage_info, used_trade_indexes, allowed_modes=None):
    """
    실제 1대1 배정 후보를 선택합니다.

    핵심 변경점:
    - 전체 판촉사랑 행에 대해 raw → exact → relaxed 확정 매칭을 먼저 끝냅니다.
    - BERT는 마지막 단계에서만 실행합니다.
    - BERT 단계에서는 구매처분류(중)+구매처분류(소)+날짜 필터를 통과한 미사용 후보 중
      BERT 유사도 점수가 가장 높은 1개 거래데이터만 선택합니다.
    - 같은 점수일 때만 거래데이터 원본순서로 보조 정렬합니다.

    이렇게 해야 낮은 BERT 점수 후보가 뒤쪽의 상품명 완전일치/정규화 일치 후보를 먼저 빼앗지 않습니다.
    """
    if allowed_modes is None:
        allowed_modes = ("raw", "exact", "relaxed", "bert")
    allowed_modes = set(allowed_modes)

    raw_unused = [i for i in stage_info["raw_indexes"] if i not in used_trade_indexes]
    exact_unused = [i for i in stage_info["exact_indexes"] if i not in used_trade_indexes]
    relaxed_unused = [i for i in stage_info["relaxed_indexes"] if i not in used_trade_indexes]
    bert_unused = [i for i in stage_info["bert_indexes"] if i not in used_trade_indexes]

    if "raw" in allowed_modes and raw_unused:
        return sort_trade_indexes(raw_unused), "상품명완전일치", "raw"

    if "exact" in allowed_modes and exact_unused:
        return sort_trade_indexes(exact_unused), "상품명exact일치", "exact"

    if "relaxed" in allowed_modes and relaxed_unused:
        return sort_trade_indexes(relaxed_unused), "상품명relaxed일치", "relaxed"

    if "bert" in allowed_modes and bert_unused:
        score_map = stage_info.get("bert_scores", {})
        bert_unused = sorted(
            bert_unused,
            key=lambda i: (-score_map.get(i, 0), dftr_work.at[i, "_trade_order"])
        )
        # 실제 배정은 1건(passed_idxs[0])만 하되, 임계값을 넘는 나머지 후보도 함께
        # 반환해서 apply_success_match가 "후보다수_검토" 시트에 남기도록 합니다.
        return bert_unused, "BERT상품명유사도", "bert"

    return [], "", ""


# ------------------------------------------------------------
# 1대1 매칭 실행
# ------------------------------------------------------------
result_df = df87.copy().astype("object")

# 메인 시트에는 요청한 결과 컬럼을 추가/갱신합니다.
result_df["구매처분류(대)"] = ""
result_df["구매처명"] = ""
result_df["매칭상태"] = ""
result_df["매칭건수"] = 0
result_df["상품명매칭방식"] = ""
result_df["BERT유사도"] = pd.Series([""] * len(result_df), index=result_df.index, dtype="object")

# 미매칭 원인 진단용 컬럼
# 모든 후보 날짜/후보 번호를 전부 나열하지 않습니다.
# 사람의 필터 방식처럼 현재 확인하는 값과 해당 단계 후보 수만 남깁니다.
result_df["미매칭진단_확인단계"] = ""
result_df["미매칭진단_확인중분류"] = ""
result_df["미매칭진단_확인소분류"] = ""
result_df["미매칭진단_확인날짜"] = ""
result_df["미매칭진단_해당단계후보수"] = 0
result_df["미매칭진단_해당단계후보번호"] = pd.Series([""] * len(result_df), index=result_df.index, dtype="object")

# pandas 3.x 계열에서 빈 문자열 컬럼이 string dtype으로 고정되면,
# 나중에 BERT 점수(float)나 기타 값 입력 시 TypeError가 날 수 있으므로
# 결과 추가 컬럼은 명시적으로 object dtype으로 고정합니다.
for _col in [
    "구매처분류(대)", "구매처명", "매칭상태", "상품명매칭방식", "BERT유사도",
    "미매칭진단_확인단계", "미매칭진단_확인중분류", "미매칭진단_확인소분류",
    "미매칭진단_확인날짜", "미매칭진단_해당단계후보번호",
]:
    if _col in result_df.columns:
        result_df[_col] = result_df[_col].astype("object")

matched_detail_rows = []
unmatched_87_indexes = []
review_rows = []
used_trade_indexes = set()
matched_87_indexes = set()


def apply_success_match(idx87, stage_info, passed_idxs, product_reason, chosen_mode):
    """선택된 거래데이터 1건을 result_df와 상세시트에 반영합니다."""
    row87 = df87_work.loc[idx87]
    idxtr = passed_idxs[0]
    used_trade_indexes.add(idxtr)
    matched_87_indexes.add(idx87)

    result_df.at[idx87, "매칭건수"] = len(passed_idxs)
    result_df.at[idx87, "상품명매칭방식"] = product_reason

    buyer = clean_text(dftr_work.at[idxtr, COL_TR_BUYER])
    large = clean_text(dftr_work.at[idxtr, COL_TR_LARGE])

    bert_score = ""
    if chosen_mode == "bert":
        bert_score = stage_info.get("bert_scores", {}).get(idxtr, "")
        result_df.at[idx87, "BERT유사도"] = f"{float(bert_score):.4f}" if bert_score != "" else ""

    result_df.at[idx87, "구매처분류(대)"] = large
    if buyer not in EMPTY_BUYER_VALUES:
        result_df.at[idx87, "구매처명"] = buyer
        if chosen_mode == "raw":
            result_df.at[idx87, "매칭상태"] = "매칭_1대1_상품명완전일치"
        elif chosen_mode == "exact":
            result_df.at[idx87, "매칭상태"] = "매칭_1대1_상품명exact일치"
        elif chosen_mode == "relaxed":
            result_df.at[idx87, "매칭상태"] = "매칭_1대일_상품명relaxed일치".replace("1대일", "1대1")
        elif chosen_mode == "bert":
            result_df.at[idx87, "매칭상태"] = "매칭_1대1_BERT상품명유사도"
        else:
            result_df.at[idx87, "매칭상태"] = "매칭_1대1_기타"
    else:
        result_df.at[idx87, "구매처명"] = ""
        result_df.at[idx87, "매칭상태"] = "매칭_1대1_구매처명없음"

    # 후보가 2개 이상이면 검토 시트에 남김
    if len(passed_idxs) >= 2:
        review_rows.append({
            "판촉사랑_엑셀행": int(df87_work.at[idx87, "_87_excel_row"]),
            "판촉사랑_수집키": clean_text(df87_work.at[idx87, COL_87_KEY]) if COL_87_KEY else "",
            "판촉사랑_납품사례ID": clean_text(df87_work.at[idx87, COL_87_CASE_ID]) if COL_87_CASE_ID else "",
            "판촉사랑_상품명": clean_text(df87_work.at[idx87, COL_87_PRODUCT]),
            "판촉사랑_인쇄방법": clean_text(df87_work.at[idx87, COL_87_PRINT]) if COL_87_PRINT else "",
            "판촉사랑_구매처분류(중)": clean_text(df87_work.at[idx87, COL_87_MID]),
            "판촉사랑_구매처분류(소)": clean_text(df87_work.at[idx87, COL_87_SMALL]) if COL_87_SMALL else "",
            "판촉사랑_등록일": clean_text(df87_work.at[idx87, COL_87_DATE]),
            "상품명매칭방식": product_reason,
            "BERT유사도": round(float(bert_score), 4) if bert_score != "" else "",
            "분류통과후보수": len(passed_idxs),
            "후보_거래데이터번호": " / ".join(dftr_work.loc[passed_idxs, COL_TR_NO].map(clean_text).tolist()),
            "후보_구매처명": " / ".join(dftr_work.loc[passed_idxs, COL_TR_BUYER].map(clean_text).tolist()),
            "후보_BERT점수": get_bert_score_text(passed_idxs, stage_info.get("bert_scores", {})) if chosen_mode == "bert" else "",
            "선택_거래데이터번호": clean_text(dftr_work.at[idxtr, COL_TR_NO]),
            "선택_구매처명": buyer,
        })

    # 상세 시트용: 판촉사랑 식별값 + 거래데이터 원본 전체
    rec = {
        "판촉사랑_엑셀행": int(df87_work.at[idx87, "_87_excel_row"]),
        "판촉사랑_수집키": clean_text(df87_work.at[idx87, COL_87_KEY]) if COL_87_KEY else "",
        "판촉사랑_납품사례ID": clean_text(df87_work.at[idx87, COL_87_CASE_ID]) if COL_87_CASE_ID else "",
        "판촉사랑_상품코드": clean_text(df87_work.at[idx87, COL_87_PRODUCT_CODE]) if COL_87_PRODUCT_CODE else "",
        "판촉사랑_상품명": clean_text(df87_work.at[idx87, COL_87_PRODUCT]),
        "판촉사랑_상품명_raw키": row87["_key_product_raw"],
        "판촉사랑_상품명_exact키": row87["_key_product_exact"],
        "판촉사랑_상품명_relaxed키": row87["_key_product_relaxed"],
        "판촉사랑_인쇄방법": clean_text(df87_work.at[idx87, COL_87_PRINT]) if COL_87_PRINT else "",
        "판촉사랑_구매처분류(대)": clean_text(df87_work.at[idx87, COL_87_LARGE]) if (COL_87_LARGE and USE_87_LARGE_IN_CATEGORY_PATH) else "",
        "판촉사랑_구매처분류(중)": clean_text(df87_work.at[idx87, COL_87_MID]),
        "판촉사랑_구매처분류(소)": clean_text(df87_work.at[idx87, COL_87_SMALL]) if COL_87_SMALL else "",
        "판촉사랑_등록일": clean_text(df87_work.at[idx87, COL_87_DATE]),
        "판촉사랑_상세URL": clean_text(df87_work.at[idx87, COL_87_URL]) if COL_87_URL else "",
        "매칭_상품명방식": product_reason,
        "매칭_BERT유사도": round(float(bert_score), 4) if bert_score != "" else "",
        "매칭_분류방식": "구매처분류(중소)_예외포함" if stage_info.get("filter_pairs") and len(stage_info.get("mid_candidates", [])) >= 2 else "구매처분류(중소)_컬럼일치",
        "매칭_분류통과후보수": len(passed_idxs),
        "거래데이터_엑셀행": int(dftr_work.at[idxtr, "_trade_excel_row"]),
    }
    for col in dftr.columns:
        rec[col] = dftr_work.at[idxtr, col]
    matched_detail_rows.append(rec)


def apply_unmatched_status(idx87, stage_info):
    """최종 미매칭 행의 매칭상태를 단계별로 1개만 입력합니다."""
    row87 = df87_work.loc[idx87]

    result_df.at[idx87, "미매칭진단_확인중분류"] = clean_text(row87[COL_87_MID])
    result_df.at[idx87, "미매칭진단_확인소분류"] = clean_text(row87[COL_87_SMALL]) if COL_87_SMALL else ""
    result_df.at[idx87, "미매칭진단_확인날짜"] = clean_text(row87["_key_date"])
    result_df.at[idx87, "매칭건수"] = 0
    result_df.at[idx87, "상품명매칭방식"] = ""

    if stage_info["mid_count"] == 0:
        status = "미매칭_구매처분류(중)_매칭안됨"
        result_df.at[idx87, "미매칭진단_확인단계"] = "구매처분류(중)"
        result_df.at[idx87, "미매칭진단_해당단계후보수"] = 0
        result_df.at[idx87, "미매칭진단_해당단계후보번호"] = ""

    elif stage_info["mid_small_count"] == 0:
        status = "미매칭_구매처분류(소)_매칭안됨"
        result_df.at[idx87, "미매칭진단_확인단계"] = "구매처분류(소)"
        result_df.at[idx87, "미매칭진단_해당단계후보수"] = stage_info["mid_count"]
        result_df.at[idx87, "미매칭진단_해당단계후보번호"] = join_trade_no(stage_info["mid_indexes"])

    elif stage_info["mid_small_date_count"] == 0:
        status = "미매칭_날짜없음"
        result_df.at[idx87, "미매칭진단_확인단계"] = "날짜"
        result_df.at[idx87, "미매칭진단_해당단계후보수"] = 0
        result_df.at[idx87, "미매칭진단_해당단계후보번호"] = ""

    else:
        status = "미매칭_상품명매칭안됨"
        result_df.at[idx87, "미매칭진단_확인단계"] = "상품명"
        result_df.at[idx87, "미매칭진단_해당단계후보수"] = stage_info["mid_small_date_count"]
        result_df.at[idx87, "미매칭진단_해당단계후보번호"] = join_trade_no(stage_info["mid_small_date_indexes"])

    result_df.at[idx87, "매칭상태"] = status
    unmatched_87_indexes.append(idx87)


# ---- 5-4. raw/exact/relaxed 매칭 실행 ----

# ------------------------------------------------------------
# 전체 우선순위 1~3단계: 정확/정규화 매칭을 전체 행에서 먼저 확정
# ------------------------------------------------------------
# 중요:
# 기존처럼 한 행씩 raw→exact→relaxed→BERT를 모두 처리하면,
# 낮은 BERT 점수 후보가 뒤쪽 행의 완전일치 거래데이터를 먼저 가져가는 문제가 생깁니다.
# 따라서 BERT는 모든 완전일치/exact/relaxed 배정이 끝난 뒤 마지막에만 실행합니다.

for mode in ["raw", "exact", "relaxed"]:
    for idx87 in df87_work.index:
        if idx87 in matched_87_indexes:
            continue

        stage_info = get_trade_candidates_by_stage(idx87, enable_bert=False)
        passed_idxs, product_reason, chosen_mode = choose_trade_index(
            stage_info,
            used_trade_indexes,
            allowed_modes=(mode,),
        )

        if passed_idxs:
            apply_success_match(idx87, stage_info, passed_idxs, product_reason, chosen_mode)


# ---- 5-5. BERT 매칭 실행 ----
# 노트북에서 이 셀만 다시 실행해도, sentence-transformers/CUDA 문제를 5-4(raw/exact/relaxed)를
# 다시 돌리지 않고 바로 알 수 있도록 여기서 한 번 더 점검합니다(0번 사전 점검과 동일한 점검).
if USE_BERT_PRODUCT_SIMILARITY:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "BERT 상품명 유사도를 사용하려면 sentence-transformers 설치가 필요합니다. "
            "노트북/터미널에서 `pip install sentence-transformers` 실행 후 다시 실행하세요."
        ) from exc

    if BERT_DEVICE == "cuda":
        check_cuda_or_raise()


# ------------------------------------------------------------
# 전체 우선순위 4단계: 남은 행만 BERT 최고 유사도 매칭
# ------------------------------------------------------------
# 임베딩 계산이 오래 걸리므로, 중간에 멈추더라도(오류/중단) 그때까지 계산한 임베딩은
# 잃어버리지 않도록 일정 건수마다 + 끝나면(성공/실패 상관없이) 캐시를 저장합니다.
_BERT_CACHE_SAVE_EVERY = 200

try:
    for _bert_i, idx87 in enumerate(df87_work.index):
        if idx87 in matched_87_indexes:
            continue

        stage_info = get_trade_candidates_by_stage(idx87, enable_bert=True)
        passed_idxs, product_reason, chosen_mode = choose_trade_index(
            stage_info,
            used_trade_indexes,
            allowed_modes=("bert",),
        )

        if passed_idxs:
            apply_success_match(idx87, stage_info, passed_idxs, product_reason, chosen_mode)

        if (_bert_i + 1) % _BERT_CACHE_SAVE_EVERY == 0:
            save_embedding_cache()
finally:
    save_embedding_cache()
    log(
        "임베딩 캐시 저장 완료:", EMBEDDING_CACHE_FILE,
        f"(모델 {BERT_MODEL_NAME} 캐시 {len(_embedding_cache.get(BERT_MODEL_NAME, {}))}건)",
    )


# ---- 5-6. 최종 미매칭 상태 입력 · 미사용 거래데이터 진단 · 요약 ----

# ------------------------------------------------------------
# 최종 미매칭 상태 입력
# ------------------------------------------------------------
for idx87 in df87_work.index:
    if idx87 in matched_87_indexes:
        continue

    stage_info = get_trade_candidates_by_stage(idx87, enable_bert=True)
    apply_unmatched_status(idx87, stage_info)


matched_detail_df = pd.DataFrame(matched_detail_rows)
unmatched_87_df = result_df.loc[unmatched_87_indexes].copy() if unmatched_87_indexes else pd.DataFrame(columns=result_df.columns)


# ------------------------------------------------------------
# 미사용_거래데이터원본 시트용 매칭상태 1개 컬럼만 생성
# ------------------------------------------------------------
# 방향은 반대입니다.
# - 메인 매칭: 판촉사랑 행 -> 거래데이터 후보 찾기
# - 미사용 진단: 미사용 거래데이터 행 -> 판촉사랑 파일에 어느 단계까지 존재하는지 확인
#
# 표시 순서:
# 구매처분류(중) 없음 -> 구매처분류(소) 없음 -> 날짜없음 -> 상품명매칭안됨
# 조건이 모두 존재하지만 1대1 배정에서 선택되지 않은 거래데이터는 별도 상태 1개로만 표시합니다.

promo_by_mid = {}
promo_by_mid_small = {}
promo_by_mid_small_date = {}
promo_by_mid_small_date_raw = {}
promo_by_mid_small_date_exact = {}
promo_by_mid_small_date_relaxed = {}

for _idx87 in df87_work.index:
    _mid = norm_mid(df87_work.at[_idx87, COL_87_MID])
    _small = norm_small(df87_work.at[_idx87, COL_87_SMALL]) if COL_87_SMALL else ""
    _date = clean_text(df87_work.at[_idx87, "_key_date"])
    _raw = clean_text(df87_work.at[_idx87, "_key_product_raw"])
    _exact = clean_text(df87_work.at[_idx87, "_key_product_exact"])
    _relaxed = clean_text(df87_work.at[_idx87, "_key_product_relaxed"])

    if _mid:
        promo_by_mid.setdefault(_mid, []).append(_idx87)
    if _mid and _small:
        promo_by_mid_small.setdefault((_mid, _small), []).append(_idx87)
    if _mid and _small and _date:
        promo_by_mid_small_date.setdefault((_mid, _small, _date), []).append(_idx87)
    if _mid and _small and _date and _raw:
        promo_by_mid_small_date_raw.setdefault((_mid, _small, _date, _raw), []).append(_idx87)
    if _mid and _small and _date and _exact:
        promo_by_mid_small_date_exact.setdefault((_mid, _small, _date, _exact), []).append(_idx87)
    if _mid and _small and _date and _relaxed:
        promo_by_mid_small_date_relaxed.setdefault((_mid, _small, _date, _relaxed), []).append(_idx87)


def get_unused_trade_status(_idxtr):
    _mid = norm_mid(dftr_work.at[_idxtr, COL_TR_MID])
    _small = norm_small(dftr_work.at[_idxtr, COL_TR_SMALL]) if COL_TR_SMALL else ""
    _date = clean_text(dftr_work.at[_idxtr, "_key_date"])
    _raw = clean_text(dftr_work.at[_idxtr, "_key_product_raw"])
    _exact = clean_text(dftr_work.at[_idxtr, "_key_product_exact"])
    _relaxed = clean_text(dftr_work.at[_idxtr, "_key_product_relaxed"])

    # 7번 수정 + 관광지/골프관련 예외: 미사용 거래데이터 진단은 역방향이므로,
    # get_trade_filter_pairs_for_promo(정방향)가 허용하는 (중분류, 소분류) 조합을
    # get_promo_filter_pairs_for_trade로 반대 방향에서도 동일하게 확인합니다.
    _filter_pairs = get_promo_filter_pairs_for_trade(_mid, _small)
    _promo_mid_candidates = unique_keep_order([m for m, _ in _filter_pairs])
    _promo_ms_keys = _filter_pairs
    _promo_msd_keys = [(m, s, _date) for m, s in _filter_pairs]

    if not any(promo_by_mid.get(m) for m in _promo_mid_candidates):
        return "미사용_구매처분류(중)_매칭안됨"
    if not any(promo_by_mid_small.get(key) for key in _promo_ms_keys):
        return "미사용_구매처분류(소)_매칭안됨"
    if not any(promo_by_mid_small_date.get(key) for key in _promo_msd_keys):
        return "미사용_날짜없음"

    # 상품명은 메인 매칭과 동일하게 raw -> exact -> relaxed 순서로만 확인합니다.
    # 여기서는 미사용 거래데이터 시트에 상태 1개만 남기기 위해 BERT 재계산은 하지 않습니다.
    if _raw and any(promo_by_mid_small_date_raw.get((m, s, _date, _raw)) for m, s in _filter_pairs):
        return "미사용_조건일치_1대1미배정"
    if _exact and any(promo_by_mid_small_date_exact.get((m, s, _date, _exact)) for m, s in _filter_pairs):
        return "미사용_조건일치_1대1미배정"
    if _relaxed and any(promo_by_mid_small_date_relaxed.get((m, s, _date, _relaxed)) for m, s in _filter_pairs):
        return "미사용_조건일치_1대1미배정"

    return "미사용_상품명매칭안됨"


_unused_trade_indexes = [i for i in dftr_work.index if i not in used_trade_indexes]
unused_trade_df = dftr_work.loc[_unused_trade_indexes, dftr.columns].copy()
unused_trade_df.insert(0, "거래데이터_엑셀행", [int(i + 2) for i in unused_trade_df.index])
unused_trade_df.insert(1, "매칭상태", [get_unused_trade_status(i) for i in unused_trade_df.index])

review_df = pd.DataFrame(review_rows)

summary = pd.DataFrame([
    [f"{SOURCE_LABEL} 전체 행 수", len(df87)],
    ["거래데이터 전체 행 수", len(dftr)],
    ["1대1 매칭 완료 행 수", int(result_df["매칭상태"].astype(str).str.startswith("매칭_1대1").sum())],
    ["상품명완전일치 매칭 행 수", int((result_df["상품명매칭방식"] == "상품명완전일치").sum())],
    ["상품명exact 매칭 행 수", int((result_df["상품명매칭방식"] == "상품명exact일치").sum())],
    ["상품명relaxed 매칭 행 수", int((result_df["상품명매칭방식"] == "상품명relaxed일치").sum())],
    ["BERT 유사도 매칭 행 수", int((result_df["상품명매칭방식"] == "BERT상품명유사도").sum())],
    ["구매처명 입력 행 수", int(result_df["구매처명"].map(clean_text).ne("").sum())],
    ["매칭됐지만 구매처명 없음 행 수", int((result_df["매칭상태"] == "매칭_1대1_구매처명없음").sum())],
    [f"미매칭 {SOURCE_LABEL} 행 수", len(unmatched_87_df)],
    ["미매칭_구매처분류(중)_매칭안됨 행 수", int((result_df["매칭상태"] == "미매칭_구매처분류(중)_매칭안됨").sum())],
    ["미매칭_구매처분류(소)_매칭안됨 행 수", int((result_df["매칭상태"] == "미매칭_구매처분류(소)_매칭안됨").sum())],
    ["미매칭_날짜없음 행 수", int((result_df["매칭상태"] == "미매칭_날짜없음").sum())],
    ["미매칭_상품명매칭안됨 행 수", int((result_df["매칭상태"] == "미매칭_상품명매칭안됨").sum())],
    ["사용된 거래데이터 행 수", len(used_trade_indexes)],
    ["미사용 거래데이터 행 수", len(unused_trade_df)],
    ["후보다수 검토 행 수", len(review_df)],
    ["거래데이터 배정 순서", TRADE_ORDER_MODE],
    ["인쇄방법 조건", "제외 / 상세시트 확인용"],
    ["공통 필터 순서", "구매처분류(중) 컬럼 → 구매처분류(소) 컬럼 → 해당 날짜"],
    ["상품명 비교 순서", "상품명 완전일치 → 상품명 exact 기본정규화 → 상품명 relaxed 보정정규화 → BERT 유사도"],
    ["BERT 사용", USE_BERT_PRODUCT_SIMILARITY],
    ["BERT 모델", BERT_MODEL_NAME],
    ["BERT 자동매칭 기준", BERT_SIM_THRESHOLD],
    ["BERT 후보 수 제한", "없음"],
    ["사용하지 않는 상태값", "미매칭_1대1후보이미사용됨 / 미매칭_거래데이터수부족"],
    ["구매처명으로 선택된 거래데이터 컬럼", COL_TR_BUYER],
], columns=["항목", "값"])

log(summary.to_string(index=False))
log("\n매칭상태 분포:")
log(result_df["매칭상태"].value_counts(dropna=False).to_string())
log("\n상품명매칭방식 분포:")
log(result_df["상품명매칭방식"].replace("", "미매칭").value_counts(dropna=False).to_string())


# ---- 6. 상품분류 보정 함수 ----



log("상품분류 보정 함수 준비 완료: 소분류 실패 시 중분류 기준 대분류 보정 포함 / 주문제작 제외")


# ---- 7. 상품분류 보정 및 저장 ----


try:
    import xlsxwriter  # noqa: F401
    EXCEL_ENGINE = "xlsxwriter"
    ENGINE_KWARGS = {"options": {"strings_to_urls": False}}
except ImportError:
    EXCEL_ENGINE = "openpyxl"
    ENGINE_KWARGS = {}

log("Excel 저장 엔진:", EXCEL_ENGINE)

# ------------------------------------------------------------
# 상품분류(대)/(중) 보정
# ------------------------------------------------------------
# 구매처명 매칭이 끝난 result_df에 상품분류 수정까지 함께 반영합니다.
result_df, category_summary, category_unmatched, category_count_dfs = apply_product_category_fix(
    result_df,
    FILE_CATEGORY
)

# 미매칭 판촉사랑 시트도 보정된 result_df 기준으로 다시 생성합니다.
unmatched_87_df = result_df.loc[unmatched_87_indexes].copy() if unmatched_87_indexes else pd.DataFrame(columns=result_df.columns)

with pd.ExcelWriter(OUTPUT_FILE, engine=EXCEL_ENGINE, engine_kwargs=ENGINE_KWARGS) as writer:
    result_df.to_excel(writer, sheet_name=f"{SOURCE_LABEL}_구매처추가_1대1", index=False)
    matched_detail_df.to_excel(writer, sheet_name="매칭상세_거래데이터원본", index=False)
    unmatched_87_df.to_excel(writer, sheet_name=f"미매칭_{SOURCE_LABEL}", index=False)
    unused_trade_df.to_excel(writer, sheet_name="미사용_거래데이터원본", index=False)
    review_df.to_excel(writer, sheet_name="후보다수_검토", index=False)
    summary.to_excel(writer, sheet_name="요약", index=False)

    # 상품분류 보정 결과 확인용 시트
    category_summary.to_excel(writer, sheet_name="상품분류_수정요약", index=False)
    category_unmatched.to_excel(writer, sheet_name="상품분류_미매칭", index=False)
    category_count_dfs["상품분류_대분류개수"].to_excel(writer, sheet_name="상품분류_대분류개수", index=False)
    category_count_dfs["상품분류_중분류개수"].to_excel(writer, sheet_name="상품분류_중분류개수", index=False)
    category_count_dfs["상품분류_소분류개수"].to_excel(writer, sheet_name="상품분류_소분류개수", index=False)

log("상품분류 수정 반영 완료:", FILE_CATEGORY)
log("저장 완료:", OUTPUT_FILE)
log("\n상품분류 수정 요약:")
log(category_summary.to_string(index=False))


# ---- 8. 검증 ----

log("결과 파일 존재:", OUTPUT_FILE.exists())
log("전체 행 수 유지:", len(result_df), "=", len(df87))
log("사용된 거래데이터 행 수:", len(used_trade_indexes))
log("중복 사용된 거래데이터 index 수:", len(used_trade_indexes) - len(set(used_trade_indexes)))

# 예시 확인: 태권도/운동학원 물티슈 케이스가 있으면 표시
sample_mask = result_df[COL_87_PRODUCT].map(clean_text).str.contains("화이트\(백색\) 10매 물티슈", regex=True, na=False)
if sample_mask.any():
    cols = [c for c in [COL_87_KEY, COL_87_CASE_ID, COL_87_PRODUCT, COL_87_DATE, COL_87_MID, COL_87_SMALL, "구매처분류(대)", "구매처명", "매칭상태", "상품명매칭방식", "BERT유사도", "매칭건수"] if c]
    display(result_df.loc[sample_mask, cols].head(20))

# 예시 확인: 코리아5링 니들3색 터치펜 / 중.고등학교 케이스가 있으면 표시
sample_mask2 = result_df[COL_87_PRODUCT].map(clean_text).str.contains("코리아5링 니들3색 터치펜", regex=False, na=False)
if sample_mask2.any():
    cols = [c for c in [COL_87_KEY, COL_87_CASE_ID, COL_87_PRODUCT, COL_87_DATE, COL_87_MID, COL_87_SMALL, "구매처분류(대)", "구매처명", "매칭상태", "상품명매칭방식", "BERT유사도", "매칭건수"] if c]
    display(result_df.loc[sample_mask2, cols].head(20))

if not matched_detail_df.empty:
    display(matched_detail_df.head(20))
# 예시 확인: 포켓에코백 A형 사이즈 표기 보정 케이스가 있으면 표시
sample_mask3 = result_df[COL_87_PRODUCT].map(clean_text).str.contains("포켓에코백 A형", regex=False, na=False)
if sample_mask3.any():
    cols = [c for c in [COL_87_KEY, COL_87_CASE_ID, COL_87_PRODUCT, COL_87_DATE, COL_87_MID, COL_87_SMALL, "구매처분류(대)", "구매처명", "매칭상태", "상품명매칭방식", "BERT유사도", "매칭건수"] if c]
    display(result_df.loc[sample_mask3, cols].head(20))


# ---- BERT 버전 실행 참고 ----
