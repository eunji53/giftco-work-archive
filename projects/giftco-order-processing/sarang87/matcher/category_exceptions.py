# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 - 구매처분류(중/소) 예외 매핑 및 후보 필터 함수.

02_match_buyer_names.py(운영 스크립트)에서 분리되었습니다.
전역 상태(df87_work/dftr_work 등)에 의존하지 않는 순수 함수/상수만 모아둡니다.
"""

import pandas as pd

from .normalize import clean_text, normalize_category


def norm_mid(value):
    return normalize_category(value)


def norm_small(value):
    return normalize_category(value)


# ------------------------------------------------------------
# 분류 예외 매핑 - 7번 수정
# ------------------------------------------------------------
# 원본 분류값은 절대 수정하지 않고, 매칭용 후보 키에만 예외를 적용합니다.
#
# 거래데이터:
#   구매처분류(중) = 전시회/박람회/축제/행사
#
# 판촉사랑:
#   구매처분류(중) = 기념행사별 또는 전시회
#
# 위 구조에서는 판촉사랑의 두 중분류 아래 구매처분류(소)를 합쳐서
# 거래데이터의 구매처분류(소)와 비교해야 하므로 1:N 중분류 예외로 처리합니다.
TRADE_TO_PROMO_MID_EXCEPTIONS = {
    norm_mid("전시회/박람회/축제/행사"): [norm_mid("기념행사별"), norm_mid("전시회")],
}

PROMO_TO_TRADE_MID_EXCEPTIONS = {}
for _trade_mid, _promo_mid_list in TRADE_TO_PROMO_MID_EXCEPTIONS.items():
    for _promo_mid in _promo_mid_list:
        PROMO_TO_TRADE_MID_EXCEPTIONS.setdefault(_promo_mid, []).append(_trade_mid)


def unique_keep_order(values):
    """순서를 유지하면서 중복 제거. 문자열은 공백 정리, 숫자 index는 원형 유지."""
    out = []
    seen = set()
    for value in values:
        if pd.isna(value):
            continue
        key = clean_text(value) if isinstance(value, str) else value
        if key == "" or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out

def get_trade_mid_candidates_for_promo(promo_mid):
    """판촉사랑 중분류 1개가 거래데이터에서 확인해야 할 중분류 후보 목록."""
    promo_mid = clean_text(promo_mid)
    return unique_keep_order([promo_mid] + PROMO_TO_TRADE_MID_EXCEPTIONS.get(promo_mid, []))

# ------------------------------------------------------------
# 분류 예외 추가: 관광지/국립공원/놀이공원 ↔ 골프관련
# ------------------------------------------------------------
# 원본 분류값은 절대 수정하지 않고, 매칭용 후보 키에만 예외를 적용합니다.
#
# 거래데이터:
#   구매처분류(중) = 골프관련
#   구매처분류(소) = 관광지/국립공원/놀이공원
#
# 판촉사랑:
#   구매처분류(중) = 관광지/국립공원/놀이공원
#   구매처분류(소) = 관광지/유적지, 국립공원/수목원, 놀이공원, 기타
#
# 위 구조에서는 판촉사랑의 관광지 하위 소분류를
# 거래데이터의 골프관련 / 관광지/국립공원/놀이공원 후보와도 비교합니다.
# 날짜 조건과 상품명 매칭 순서는 기존 로직 그대로 유지합니다.
TOUR_PROMO_MID = norm_mid("관광지/국립공원/놀이공원")
TOUR_TRADE_MID = norm_mid("골프관련")
TOUR_TRADE_SMALL = norm_small("관광지/국립공원/놀이공원")

TOUR_PROMO_SMALLS = {
    norm_small("관광지/유적지"),
    norm_small("국립공원/수목원"),
    norm_small("놀이공원"),
    norm_small("기타"),
}

def get_trade_filter_pairs_for_promo(promo_mid, promo_small):
    """판촉사랑 행 기준으로 거래데이터에서 확인할 (중분류, 소분류) 후보 목록."""
    promo_mid = clean_text(promo_mid)
    promo_small = clean_text(promo_small)

    pairs = [(mid, promo_small) for mid in get_trade_mid_candidates_for_promo(promo_mid)]

    # 관광지/골프관련 예외 추가
    # 판촉사랑: 관광지/국립공원/놀이공원 / 관광지/유적지, 국립공원/수목원, 놀이공원, 기타
    # 거래데이터: 골프관련 / 관광지/국립공원/놀이공원
    if promo_mid == TOUR_PROMO_MID and promo_small in TOUR_PROMO_SMALLS:
        pairs.append((TOUR_TRADE_MID, TOUR_TRADE_SMALL))

    return unique_keep_order(pairs)

def get_promo_mid_candidates_for_trade(trade_mid):
    """미사용 거래데이터 진단용: 거래데이터 중분류가 판촉사랑에서 확인해야 할 중분류 후보 목록."""
    trade_mid = clean_text(trade_mid)
    return unique_keep_order([trade_mid] + TRADE_TO_PROMO_MID_EXCEPTIONS.get(trade_mid, []))

def get_promo_filter_pairs_for_trade(trade_mid, trade_small):
    """미사용 거래데이터 진단용: 거래데이터 행 기준으로 판촉사랑에서 확인할 (중분류, 소분류) 후보 목록.

    get_trade_filter_pairs_for_promo의 역방향입니다. 관광지/골프관련 예외도 반대 방향으로
    동일하게 반영해야, 정방향에서는 매칭 가능한 조합인데 미사용 진단에서만
    "매칭안됨"으로 잘못 표시되는 것을 막을 수 있습니다.
    """
    trade_mid = clean_text(trade_mid)
    trade_small = clean_text(trade_small)

    pairs = [(mid, trade_small) for mid in get_promo_mid_candidates_for_trade(trade_mid)]

    # 관광지/골프관련 예외 역방향
    if trade_mid == TOUR_TRADE_MID and trade_small == TOUR_TRADE_SMALL:
        pairs.extend((TOUR_PROMO_MID, small) for small in TOUR_PROMO_SMALLS)

    return unique_keep_order(pairs)
