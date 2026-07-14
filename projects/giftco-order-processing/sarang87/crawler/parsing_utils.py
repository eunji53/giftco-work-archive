# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 텍스트/가격/카테고리 파싱 공통 유틸

네트워크 요청이나 파일 입출력은 하지 않는 순수 함수들만 모아둡니다.
"""
import html
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

from . import config


#목록 페이지 URL에서 page= 값만 바꿔주는 함수
def build_page_url(base_url: str, page: int) -> str:
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["page"] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


#상품코드 및 납품사례ID, 수집키 가져오기
def get_hidden_value(soup_or_tag, input_id: str):
    tag = soup_or_tag.find("input", {"id": input_id})
    return tag.get("value", "").strip() if tag else ""


def clean_label_value(text: str, label: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(rf"^{re.escape(label)}\s*[:：]\s*", "", text).strip()
    return text


def clean_price_to_int(text: str):
    if text is None:
        return None

    text = str(text).strip()

    if not text:
        return None

    if "가격문의" in text:
        return "가격문의"

    num = re.sub(r"[^0-9]", "", text)
    return int(num) if num else None


def parse_html_category_text(cat_html: str) -> str:
    if not cat_html:
        return ""

    decoded = html.unescape(cat_html)
    cat_soup = BeautifulSoup(decoded, "html.parser")
    parts = [a.get_text(" ", strip=True) for a in cat_soup.find_all("a")]
    parts = [p for p in parts if p]

    if parts:
        return " > ".join(parts)

    return cat_soup.get_text(" ", strip=True).replace(">", " > ")


def split_buyer_category(text: str):
    """
    판촉사랑 목록의 업종/행사 값을 구매처분류(중/소/세)로 나눕니다.

    예: 학교/교육기관 > 대학교/대학원 > 행사/홍보
    -> 구매처분류(중)=학교/교육기관, 구매처분류(소)=대학교/대학원, 구매처분류(세)=행사/홍보
    """
    text = str(text or "").strip()

    if not text:
        return "", "", ""

    parts = [p.strip() for p in text.split(">")]
    parts = [p for p in parts if p]
    parts = parts + [""] * 3

    return parts[0], parts[1], parts[2]


def add_buyer_category_to_row(row: dict) -> dict:
    """
    row의 업종/행사 값을 기준으로 구매처분류(중/소/세)를 추가합니다.
    """
    buyer_mid, buyer_small, buyer_detail = split_buyer_category(row.get("업종/행사", ""))
    row["구매처분류(중)"] = buyer_mid
    row["구매처분류(소)"] = buyer_small
    row["구매처분류(세)"] = buyer_detail
    return row


def ensure_buyer_category_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    기존 LIST_ONLY_CSV 또는 CHECKPOINT_CSV에 구매처분류 컬럼이 없더라도
    업종/행사 컬럼을 기준으로 다시 생성해서 이어하기가 가능하게 합니다.
    """
    df = df.copy()

    for col in config.BUYER_CATEGORY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if "업종/행사" in df.columns:
        buyer_values = df["업종/행사"].fillna("").apply(split_buyer_category)
        df["구매처분류(중)"] = buyer_values.apply(lambda x: x[0])
        df["구매처분류(소)"] = buyer_values.apply(lambda x: x[1])
        df["구매처분류(세)"] = buyer_values.apply(lambda x: x[2])

    return df


def make_collect_key(row: dict) -> str:
    case_id = str(row.get("납품사례ID", "") or "").strip()
    if case_id:
        return f"case:{case_id}"

    return "|".join([
        str(row.get("상품코드", "") or "").strip(),
        str(row.get("상품명", "") or "").strip(),
        str(row.get("등록일", "") or "").strip(),
        str(row.get("상세URL", "") or "").strip(),
    ])
