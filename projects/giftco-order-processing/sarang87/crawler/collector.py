# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 1단계 목록 수집 / 2단계 상세 수집 오케스트레이션

fetch(요청) + list_page/detail_page(파싱) + checkpoint_io(저장/이어하기)를
엮어서 실제 크롤링 루프를 돌리는 부분입니다.
"""
import logging
import random
import time
import traceback
from pathlib import Path

import pandas as pd

from . import config
from .checkpoint_io import ALL_SAVE_COLUMNS, append_error_log, load_checkpoint, safe_write_csv
from .detail_page import parse_detail_page
from .excel_export import save_excel_from_checkpoint
from .fetch import close_selenium_driver
from .list_page import parse_list_page
from .parsing_utils import build_page_url, ensure_buyer_category_columns, make_collect_key, split_buyer_category

logger = logging.getLogger(__name__)


def load_list_only() -> pd.DataFrame:
    """
    1단계 목록 수집 파일을 로드합니다.
    """
    if Path(config.LIST_ONLY_CSV).exists():
        df = pd.read_csv(config.LIST_ONLY_CSV, dtype=str).fillna("")
        df = ensure_buyer_category_columns(df)
        for col in config.LIST_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        logger.info(f"[목록 이어하기] 기존 목록 파일 로드: {len(df)}건")
        return df[config.LIST_COLUMNS]
    else:
        logger.info("[목록 새 작업] 기존 목록 파일 없음")
        return pd.DataFrame(columns=config.LIST_COLUMNS)


def save_list_only(df: pd.DataFrame):
    """
    목록 수집 결과를 안전하게 저장합니다.
    """
    df = ensure_buyer_category_columns(df)

    for col in config.LIST_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[config.LIST_COLUMNS].copy()

    if not df.empty:
        df = df.drop_duplicates(subset=["수집키"], keep="first")

    safe_write_csv(df, config.LIST_ONLY_CSV)


def save_checkpoint_files(df: pd.DataFrame):
    """
    상세페이지 체크포인트를 CSV와 XLSX로 함께 저장합니다.
    CSV는 이어하기 기준 파일이고,
    XLSX는 확인용 파일입니다.
    """
    df = ensure_buyer_category_columns(df)

    for col in ALL_SAVE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[ALL_SAVE_COLUMNS].copy()

    # CSV 저장
    safe_write_csv(df, config.CHECKPOINT_CSV)

    # XLSX 확인용 저장
    df.to_excel(config.CHECKPOINT_XLSX, index=False, engine="openpyxl")

    # XLSX도 output 폴더에 복사
    config.sync_to_dir(config.CHECKPOINT_XLSX)


def collect_list_only():
    """
    1단계:
    목록페이지에서 상품코드, 상품명, 인쇄방법, 업종/행사, 등록일, 상세URL만 먼저 수집합니다.
    상세페이지에는 들어가지 않습니다.
    """

    list_df = load_list_only()
    done_list_keys = set(list_df["수집키"].dropna().astype(str).tolist()) if not list_df.empty else set()

    new_rows = []

    try:
        for page in range(config.START_PAGE, config.END_PAGE + 1):
            page_url = build_page_url(config.START_URL, page)

            logger.debug(f"[1단계 목록 수집] page={page}")
            logger.debug(f"  URL: {page_url}")

            try:
                page_rows = parse_list_page(page_url, page)

            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}"
                logger.warning(f"[목록 오류] page={page} / {err_msg}")
                append_error_log(page, "", "", page_url, f"목록 페이지 오류: {err_msg}")
                continue

            if not page_rows:
                logger.info(f"[중단] page={page}에서 수집 항목이 없습니다.")
                break

            page_new_count = 0

            for row in page_rows:
                collect_key = str(row.get("수집키", "") or "").strip()

                if not collect_key:
                    collect_key = make_collect_key(row)

                if collect_key in done_list_keys:
                    logger.debug(f"[목록 건너뜀] 이미 목록 수집됨: {row.get('상품코드')} / {str(row.get('상품명', ''))[:35]}")
                    continue

                buyer_mid, buyer_small, buyer_detail = split_buyer_category(row.get("업종/행사", ""))

                list_row = {
                    "수집키": collect_key,
                    "납품사례ID": row.get("납품사례ID", ""),
                    "수집페이지": page,
                    "상품코드": row.get("상품코드", ""),
                    "구매처분류(중)": buyer_mid,
                    "구매처분류(소)": buyer_small,
                    "구매처분류(세)": buyer_detail,
                    "상품명": row.get("상품명", ""),
                    "인쇄방법": row.get("인쇄방법", ""),
                    "업종/행사": row.get("업종/행사", ""),
                    "등록일": row.get("등록일", ""),
                    "상세URL": row.get("상세URL", ""),
                    "목록수집상태": "완료",
                }

                new_rows.append(list_row)
                done_list_keys.add(collect_key)
                page_new_count += 1

            if new_rows:
                list_df = pd.concat([list_df, pd.DataFrame(new_rows)], ignore_index=True)
                list_df = list_df.drop_duplicates(subset=["수집키"], keep="first")
                save_list_only(list_df)
                new_rows = []

            logger.info(f"[1단계] page={page} 완료 - 신규 {page_new_count}건 / 누적 {len(list_df)}건")

    except KeyboardInterrupt:
        logger.warning("[목록 수집 중지] 현재까지 목록 데이터를 저장합니다.")
        if new_rows:
            list_df = pd.concat([list_df, pd.DataFrame(new_rows)], ignore_index=True)
        save_list_only(list_df)
        logger.info("[목록 중지 저장 완료]")
        return list_df

    if new_rows:
        list_df = pd.concat([list_df, pd.DataFrame(new_rows)], ignore_index=True)

    save_list_only(list_df)

    logger.info(f"[1단계 목록 수집 완료] 총 {len(list_df)}건 저장")
    logger.info(f"저장 파일: {config.LIST_ONLY_CSV}")

    return list_df


def make_error_detail_row(row, collect_key, item_code, product_name, detail_url, page):
    """
    상세페이지 오류가 나도 목록에서 확보한 기본정보를 최종 체크포인트에 남기기 위한 행입니다.
    """
    buyer_mid, buyer_small, buyer_detail = split_buyer_category(row.get("업종/행사", ""))

    return {
        "No": "",
        "상품코드": item_code,
        "구매처분류(중)": buyer_mid,
        "구매처분류(소)": buyer_small,
        "구매처분류(세)": buyer_detail,
        "상품명": product_name,
        "상품분류(대)": "",
        "상품분류(중)": "",
        "상품분류(소)": "",
        "최소인쇄수량": "",
        "최소주문수량": "",
        "대량가격(원)": "",
        "중간가격(원)": "",
        "소량가격(원)": "",
        "인쇄방법": row.get("인쇄방법", ""),
        "업종/행사": row.get("업종/행사", ""),
        "등록일": row.get("등록일", ""),
        "수집키": collect_key,
        "납품사례ID": row.get("납품사례ID", ""),
        "수집페이지": page,
        "상세URL": detail_url,
        "수집상태": "상세페이지 오류",
    }


def run_detail_from_list():
    """
    2단계:
    1단계에서 저장한 LIST_ONLY_CSV를 읽고,
    상세URL에 하나씩 접속해서 상품분류, 최소수량, 가격을 수집합니다.
    """

    if not Path(config.LIST_ONLY_CSV).exists():
        raise FileNotFoundError(
            f"{config.LIST_ONLY_CSV} 파일이 없습니다. 먼저 collect_list_only()를 실행하세요."
        )

    list_df = pd.read_csv(config.LIST_ONLY_CSV, dtype=str).fillna("")
    list_df = ensure_buyer_category_columns(list_df)

    for col in config.LIST_COLUMNS:
        if col not in list_df.columns:
            list_df[col] = ""

    list_df = list_df[config.LIST_COLUMNS].copy()

    checkpoint_df = load_checkpoint()

    # RETRY_DETAIL_ERRORS=True이면 기존 상세페이지 오류 행은 다시 시도할 수 있도록 제거
    if config.RETRY_DETAIL_ERRORS and not checkpoint_df.empty:
        error_keys = set(
            checkpoint_df.loc[
                checkpoint_df["수집상태"].astype(str) == "상세페이지 오류",
                "수집키"
            ].dropna().astype(str).tolist()
        )

        if error_keys:
            logger.info(f"[오류 재시도] 기존 상세페이지 오류 {len(error_keys)}건을 재시도 대상으로 전환")
            checkpoint_df = checkpoint_df[~checkpoint_df["수집키"].astype(str).isin(error_keys)].copy()
            save_checkpoint_files(checkpoint_df)
    # RETRY_BLANK_DETAIL_ROWS=True이면 상세값이 거의 비어 있는 완료/오류 행도 다시 시도
    if config.RETRY_BLANK_DETAIL_ROWS and not checkpoint_df.empty:
        price_cols = ["대량가격(원)", "중간가격(원)", "소량가격(원)"]
        detail_cols = ["상품분류(대)", "상품분류(중)", "상품분류(소)", "최소인쇄수량", "최소주문수량"] + price_cols

        for col in detail_cols + ["수집상태"]:
            if col not in checkpoint_df.columns:
                checkpoint_df[col] = ""

        def is_blank_or_error_detail(row):
            status = str(row.get("수집상태", "") or "").strip()
            if status == "상세페이지 오류":
                return True

            values = [str(row.get(col, "") or "").strip() for col in detail_cols]
            # 가격문의는 실제 가격문의일 수 있으므로 단독으로는 재시도 조건으로 쓰지 않음
            # 다만 분류/최소수량/가격이 전부 빈칸이면 재시도
            return all(v == "" for v in values)

        blank_keys = set(
            checkpoint_df.loc[
                checkpoint_df.apply(is_blank_or_error_detail, axis=1),
                "수집키"
            ].dropna().astype(str).tolist()
        )

        if blank_keys:
            logger.info(f"[빈 상세값 재시도] 기존 상세 오류/빈값 {len(blank_keys)}건을 재시도 대상으로 전환")
            checkpoint_df = checkpoint_df[~checkpoint_df["수집키"].astype(str).isin(blank_keys)].copy()
            save_checkpoint_files(checkpoint_df)

    done_keys = set()
    if not checkpoint_df.empty and "수집키" in checkpoint_df.columns:
        done_keys = set(checkpoint_df["수집키"].dropna().astype(str).tolist())

    total_new_count = 0
    processed_since_excel_save = 0

    try:
        for idx, row in list_df.iterrows():
            collect_key = str(row.get("수집키", "") or "").strip()
            item_code = str(row.get("상품코드", "") or "").strip()
            product_name = str(row.get("상품명", "") or "").strip()
            detail_url = str(row.get("상세URL", "") or "").strip()
            page = str(row.get("수집페이지", "") or "").strip()

            if not collect_key:
                collect_key = make_collect_key(row.to_dict())

            if not detail_url or "viewitem.asp" not in detail_url:
                err_msg = "상세URL 없음 또는 viewitem.asp URL 아님"
                logger.warning(f"[상세URL 오류] {item_code} / {product_name} / {err_msg}")
                append_error_log(page, item_code, product_name, detail_url, err_msg)
                continue

            if collect_key in done_keys:
                logger.debug(f"[상세 건너뜀] 이미 상세 수집됨: {item_code} / {product_name[:35]}")
                continue

            logger.debug(f"[2단계 상세 수집] page={page} / {item_code} / {product_name[:50]}")
            logger.debug(f"  상세URL: {detail_url}")

            try:
                # I열 상세URL을 Selenium으로 직접 접속해서 상세정보를 추출합니다.
                # 납품사례 목록주소를 먼저 열거나 링크를 타고 들어가지 않습니다.
                detail_data = parse_detail_page(detail_url, referer=None)

                buyer_mid, buyer_small, buyer_detail = split_buyer_category(row.get("업종/행사", ""))

                final_row = {
                    "No": "",
                    "상품코드": item_code,
                    "구매처분류(중)": buyer_mid,
                    "구매처분류(소)": buyer_small,
                    "구매처분류(세)": buyer_detail,
                    "상품명": product_name,
                    "상품분류(대)": detail_data.get("상품분류(대)", ""),
                    "상품분류(중)": detail_data.get("상품분류(중)", ""),
                    "상품분류(소)": detail_data.get("상품분류(소)", ""),
                    "최소인쇄수량": detail_data.get("최소인쇄수량", ""),
                    "최소주문수량": detail_data.get("최소주문수량", ""),
                    "대량가격(원)": detail_data.get("대량가격(원)", ""),
                    "중간가격(원)": detail_data.get("중간가격(원)", ""),
                    "소량가격(원)": detail_data.get("소량가격(원)", ""),
                    "인쇄방법": row.get("인쇄방법", ""),
                    "업종/행사": row.get("업종/행사", ""),
                    "등록일": row.get("등록일", ""),
                    "수집키": collect_key,
                    "납품사례ID": row.get("납품사례ID", ""),
                    "수집페이지": page,
                    "상세URL": detail_url,
                    "수집상태": "완료",
                }

            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}"
                logger.warning(f"[상세 오류] {item_code} / {product_name} / {err_msg}")
                append_error_log(page, item_code, product_name, detail_url, err_msg)

                if config.DETAIL_ERROR_SAVE_AS_ROW:
                    final_row = make_error_detail_row(row, collect_key, item_code, product_name, detail_url, page)
                else:
                    continue

            checkpoint_df = pd.concat(
                [checkpoint_df, pd.DataFrame([final_row])],
                ignore_index=True
            )

            done_keys.add(collect_key)
            save_checkpoint_files(checkpoint_df)

            total_new_count += 1
            processed_since_excel_save += 1

            logger.debug(f"  -> 상세 체크포인트 저장 완료: 누적 {len(checkpoint_df)}건")

            if total_new_count % 100 == 0:
                logger.info(f"[2단계] 진행 중 - 누적 {len(checkpoint_df)}건 처리")

            if processed_since_excel_save >= config.SAVE_EXCEL_EVERY_ROWS:
                save_excel_from_checkpoint(config.OUTPUT_XLSX)
                processed_since_excel_save = 0

            if total_new_count > 0 and total_new_count % config.COOLDOWN_EVERY_ITEMS == 0:
                cooldown = random.uniform(config.COOLDOWN_SLEEP_MIN, config.COOLDOWN_SLEEP_MAX)
                logger.debug(f"[쿨다운] {total_new_count}건 처리 완료, {cooldown:.1f}초 대기")
                time.sleep(cooldown)

    except KeyboardInterrupt:
        logger.warning("[상세 수집 중지] 현재까지 수집한 데이터 저장 중입니다.")
        save_checkpoint_files(checkpoint_df)
        save_excel_from_checkpoint(config.OUTPUT_XLSX)
        close_selenium_driver()
        logger.info("[상세 중지 저장 완료] 다음 실행 시 이어서 진행됩니다.")
        return checkpoint_df

    except Exception:
        logger.exception("[상세 수집 예상 외 오류] 현재까지 수집한 데이터 저장 중입니다.")
        save_checkpoint_files(checkpoint_df)
        save_excel_from_checkpoint(config.OUTPUT_XLSX)
        close_selenium_driver()
        logger.info("[상세 오류 저장 완료] 다음 실행 시 이어서 진행됩니다.")
        return checkpoint_df

    save_excel_from_checkpoint(config.OUTPUT_XLSX)
    close_selenium_driver()

    logger.info(f"[2단계 상세 수집 완료] 신규 상세 수집 {total_new_count}건 / 총 저장 {len(checkpoint_df)}건")
    logger.info(f"최종 엑셀: {config.OUTPUT_XLSX}")

    return checkpoint_df
