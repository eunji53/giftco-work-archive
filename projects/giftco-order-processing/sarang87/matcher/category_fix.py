# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 - 상품분류(대/중/소) 보정 함수.

02_match_buyer_names.py(운영 스크립트)에서 분리되었습니다.
"""

import re

import pandas as pd


def clean_category_text(x):
    """상품분류 보정용 빈값 정리."""
    if pd.isna(x):
        return pd.NA
    x = str(x).strip()
    if x == "" or x.lower() == "nan":
        return pd.NA
    return x


def make_category_key(x):
    """
    상품분류 매칭용 key
    - 앞뒤 공백 제거
    - 중간 공백 제거
    """
    x = clean_category_text(x)
    if pd.isna(x):
        return pd.NA
    return re.sub(r"\s+", "", str(x))


def get_parenthesis_category_key(x):
    """
    예:
    볼펜(100원~500원미만) -> 100원~500원미만
    USB (스틱타입) -> 스틱타입
    보조배터리(무선충전 보조배터리)) -> 무선충전보조배터리
    """
    x = clean_category_text(x)
    if pd.isna(x):
        return pd.NA

    m = re.search(r"\(([^()]*)\)\)*\s*$", str(x))
    if m:
        return make_category_key(m.group(1))

    return pd.NA


def apply_product_category_fix(df, category_path):
    """
    category_reference.xlsx 기준으로 상품분류를 보정합니다.

    1순위: 상품분류(소) 정확 매칭
      - 상품분류(대), 상품분류(중) 수정

    2순위: 상품분류(소) 괄호 안 텍스트 매칭
      - 상품분류(대), 상품분류(중) 수정

    3순위: 위 2개가 실패한 경우 상품분류(중) 매칭
      - 상품분류(대)만 수정
      - 단, 주문제작 상품은 제외
    """
    need_cols = ["상품분류(대)", "상품분류(중)", "상품분류(소)"]

    for col in need_cols:
        if col not in df.columns:
            raise ValueError(f"결과 데이터에 '{col}' 컬럼이 없습니다.")

    cat = pd.read_excel(category_path, dtype=str, keep_default_na=False)

    for col in need_cols:
        if col not in cat.columns:
            raise ValueError(f"카테고리 파일에 '{col}' 컬럼이 없습니다.")

    work_df = df.copy()

    for col in need_cols:
        work_df[col] = work_df[col].apply(clean_category_text)
        cat[col] = cat[col].apply(clean_category_text)

    # =========================
    # 1. 상품분류(소) 기준 매칭표
    # =========================
    cat["_small_key"] = cat["상품분류(소)"].apply(make_category_key)

    cat_small_map = (
        cat.dropna(subset=["_small_key"])
           .drop_duplicates(subset=["_small_key"], keep="first")
           .set_index("_small_key")[["상품분류(대)", "상품분류(중)"]]
    )

    work_df["_상품분류_key_exact"] = work_df["상품분류(소)"].apply(make_category_key)
    work_df["_상품분류_key_parenthesis"] = work_df["상품분류(소)"].apply(get_parenthesis_category_key)

    exact_mask = work_df["_상품분류_key_exact"].isin(cat_small_map.index)
    parenthesis_mask = (~exact_mask) & work_df["_상품분류_key_parenthesis"].isin(cat_small_map.index)

    work_df["_상품분류_match_key"] = pd.NA
    work_df.loc[exact_mask, "_상품분류_match_key"] = work_df.loc[exact_mask, "_상품분류_key_exact"]
    work_df.loc[parenthesis_mask, "_상품분류_match_key"] = work_df.loc[parenthesis_mask, "_상품분류_key_parenthesis"]

    small_match_mask = work_df["_상품분류_match_key"].notna()

    # 상품분류(소) 매칭 성공 시 상품분류(대), 상품분류(중) 수정
    work_df.loc[small_match_mask, "상품분류(대)"] = (
        work_df.loc[small_match_mask, "_상품분류_match_key"].map(cat_small_map["상품분류(대)"])
    )
    work_df.loc[small_match_mask, "상품분류(중)"] = (
        work_df.loc[small_match_mask, "_상품분류_match_key"].map(cat_small_map["상품분류(중)"])
    )

    # =========================
    # 2. 상품분류(중) 기준 상품분류(대) 보정
    # - 상품분류(소) 매칭 실패한 행만 대상
    # - 주문제작 상품은 제외
    # =========================
    cat["_mid_key"] = cat["상품분류(중)"].apply(make_category_key)

    cat_mid_map = (
        cat.dropna(subset=["_mid_key"])
           .drop_duplicates(subset=["_mid_key"], keep="first")
           .set_index("_mid_key")["상품분류(대)"]
    )

    work_df["_상품분류_mid_key"] = work_df["상품분류(중)"].apply(make_category_key)

    category_text_for_exclude = (
        work_df[need_cols]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
    )

    주문제작_제외_mask = category_text_for_exclude.str.contains("주문제작", na=False)

    mid_fallback_mask = (
        (~small_match_mask)
        & (~주문제작_제외_mask)
        & work_df["_상품분류_mid_key"].isin(cat_mid_map.index)
    )

    # 상품분류(중) 매칭은 상품분류(대)만 수정
    work_df.loc[mid_fallback_mask, "상품분류(대)"] = (
        work_df.loc[mid_fallback_mask, "_상품분류_mid_key"].map(cat_mid_map)
    )

    # 최종 매칭 여부
    final_match_mask = small_match_mask | mid_fallback_mask

    # =========================
    # 3. 요약 / 미매칭 정리
    # =========================
    count_big = (
        work_df["상품분류(대)"]
        .fillna("(빈값)")
        .value_counts()
        .reset_index()
    )
    count_big.columns = ["상품분류(대)", "개수"]

    count_mid = (
        work_df["상품분류(중)"]
        .fillna("(빈값)")
        .value_counts()
        .reset_index()
    )
    count_mid.columns = ["상품분류(중)", "개수"]

    count_small = (
        work_df["상품분류(소)"]
        .fillna("(빈값)")
        .value_counts()
        .reset_index()
    )
    count_small.columns = ["상품분류(소)", "개수"]

    category_unmatched = (
        work_df.loc[~final_match_mask, ["상품분류(대)", "상품분류(중)", "상품분류(소)"]]
        .fillna("(빈값)")
        .value_counts()
        .reset_index(name="개수")
    )

    category_summary = pd.DataFrame({
        "항목": [
            "전체 행수",
            "상품분류(소) 정확 매칭",
            "상품분류(소) 괄호 안 추가 매칭",
            "상품분류(중) 기준 대분류 보정",
            "주문제작 제외 행수",
            "상품분류 총 매칭",
            "상품분류 미매칭",
            "상품분류(소) 빈값"
        ],
        "개수": [
            len(work_df),
            int(exact_mask.sum()),
            int(parenthesis_mask.sum()),
            int(mid_fallback_mask.sum()),
            int(주문제작_제외_mask.sum()),
            int(final_match_mask.sum()),
            int((~final_match_mask).sum()),
            int(work_df["상품분류(소)"].isna().sum())
        ]
    })

    drop_cols = [
        "_상품분류_key_exact",
        "_상품분류_key_parenthesis",
        "_상품분류_match_key",
        "_상품분류_mid_key"
    ]
    work_df = work_df.drop(columns=[c for c in drop_cols if c in work_df.columns])

    category_count_dfs = {
        "상품분류_대분류개수": count_big,
        "상품분류_중분류개수": count_mid,
        "상품분류_소분류개수": count_small,
    }

    return work_df, category_summary, category_unmatched, category_count_dfs
