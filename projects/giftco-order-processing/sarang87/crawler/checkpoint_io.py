# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 체크포인트 / 에러로그 파일 입출력

크롤링 자체(요청, 파싱)가 아니라 중간 결과를 어떻게 저장하고
이어하기용으로 다시 읽어들이는지를 담당합니다.
"""
import logging
import os
from pathlib import Path

import pandas as pd

from . import config
from .parsing_utils import ensure_buyer_category_columns

logger = logging.getLogger(__name__)

#저장할 컬럼 정의
# 구매처분류(중/소/세)는 업종/행사 값을 ">" 기준으로 나누어 크롤링 중 바로 생성합니다.
COLUMNS = [
    "No", "상품코드", *config.BUYER_CATEGORY_COLUMNS, "상품명",
    "상품분류(대)", "상품분류(중)", "상품분류(소)",
    "최소인쇄수량", "최소주문수량",
    "대량가격(원)", "중간가격(원)", "소량가격(원)",
    "인쇄방법", "업종/행사", "등록일",
    "납품사례ID", "수집키"
]
#컬럼	                    의미
#======================================================
#수집키	                중복 방지용 고유값, 최종 엑셀 포함
#납품사례ID	             납품사례 고유 ID, 최종 엑셀 포함
#수집페이지	            몇 페이지에서 가져왔는지
#상세URL	            상세페이지 주소
#수집상태	        완료 / 오류 / 상세페이지 오류 등

INTERNAL_COLUMNS = [
    "수집페이지", "상세URL", "수집상태"
]

ALL_SAVE_COLUMNS = COLUMNS + INTERNAL_COLUMNS


def safe_write_csv(df: pd.DataFrame, path: str):
    """
    CSV를 저장한 뒤, 같은 파일을 output 폴더에도 복사 저장합니다.
    """
    path = Path(path)
    tmp_path = Path(f"{path}.tmp")
    df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
    os.replace(tmp_path, path)

    # 저장 후 output 폴더에도 동일 파일 복사
    config.sync_to_dir(path)


def load_checkpoint() -> pd.DataFrame:
    if Path(config.CHECKPOINT_CSV).exists():
        df = pd.read_csv(config.CHECKPOINT_CSV, dtype=str)
        df = ensure_buyer_category_columns(df)
        for col in ALL_SAVE_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        logger.info(f"[이어하기] 기존 체크포인트 로드: {len(df)}건")
        return df[ALL_SAVE_COLUMNS]
    else:
        logger.info("[새 작업] 기존 체크포인트 없음")
        return pd.DataFrame(columns=ALL_SAVE_COLUMNS)


def append_error_log(page, item_code, product_name, detail_url, error_message):
    error_row = pd.DataFrame([{
        "수집페이지": page,
        "상품코드": item_code,
        "상품명": product_name,
        "상세URL": detail_url,
        "오류내용": error_message,
        "오류시간": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }])

    if Path(config.ERROR_LOG_CSV).exists():
        old = pd.read_csv(config.ERROR_LOG_CSV, dtype=str)
        error_df = pd.concat([old, error_row], ignore_index=True)
    else:
        error_df = error_row

    safe_write_csv(error_df, config.ERROR_LOG_CSV)
