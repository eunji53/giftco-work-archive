# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 목록 페이지 파싱
"""
import html
import logging
import re
from urllib.parse import urljoin

from . import config
from .fetch import fetch_soup
from .parsing_utils import clean_label_value, get_hidden_value, make_collect_key, parse_html_category_text, split_buyer_category

logger = logging.getLogger(__name__)


def extract_direct_text(tag):
    """태그의 직계 텍스트만 추출합니다. textarea/하위 테이블에 들어있는 숨은 HTML이 섞이는 문제를 방지합니다."""
    if tag is None:
        return ""
    parts = []
    for s in tag.find_all(string=True, recursive=False):
        txt = str(s).strip()
        if txt:
            parts.append(txt)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def find_product_detail_link(card, item_code: str):
    """
    상품명 영역의 a href를 찾아 상세페이지 URL을 반환합니다.

    기준 HTML 예시:
    <a href="/shop/viewitem.asp?mcd=M00000001&ca=168&itemcd=04130299" target="_blank">
        <span>상품명</span>
    </a>
    """
    if not card:
        return "", ""

    # 1순위: itemcd가 href 안에 포함된 상품 상세 링크
    for a in card.find_all("a", href=True):
        href = html.unescape(a.get("href", "")).strip()
        text = a.get_text(" ", strip=True)

        if "viewitem.asp" in href and f"itemcd={item_code}" in href:
            return urljoin(config.BASE_URL, href), text

    # 2순위: viewitem.asp가 포함된 첫 번째 상세 링크
    for a in card.find_all("a", href=True):
        href = html.unescape(a.get("href", "")).strip()
        text = a.get_text(" ", strip=True)

        if "viewitem.asp" in href:
            return urljoin(config.BASE_URL, href), text

    return "", ""


def extract_print_method_from_card(card, item_code: str):
    """
    목록 카드에서 인쇄방법만 정확히 추출합니다.

    기준 구조:
    <tr height="30">
        <td width="40%">상품코드 : 04130299</td>
        <td width="60%">인쇄방법 : 실크인쇄</td>
    </tr>

    기존처럼 card 전체 text를 읽으면 숨겨진 textarea의 HTML까지 섞일 수 있으므로
    반드시 '상품코드 td'의 다음 형제 td에서만 추출합니다.
    """
    if not card:
        return ""

    # 1순위: 상품코드가 들어있는 td를 찾고, 바로 옆 td에서 인쇄방법 추출
    code_patterns = [
        f"상품코드 : {item_code}",
        f"상품코드: {item_code}",
    ]

    for td in card.find_all("td"):
        direct_text = extract_direct_text(td)
        if any(p in direct_text for p in code_patterns):
            next_td = td.find_next_sibling("td")
            if next_td:
                method_text = extract_direct_text(next_td)
                if not method_text:
                    method_text = next_td.get_text(" ", strip=True)

                method = clean_label_value(method_text, "인쇄방법")
                method = re.sub(r"\s+", " ", method).strip()

                # 인쇄방법이 비어있거나 라벨만 있으면 빈값
                if method and method != "인쇄방법":
                    return method
            break

    # 2순위: 직계 텍스트가 '인쇄방법 :'으로 시작하는 td만 스캔
    for td in card.find_all("td"):
        direct_text = extract_direct_text(td)
        m = re.search(r"^인쇄방법\s*[:：]\s*(.+)$", direct_text)
        if m:
            method = m.group(1).strip()
            return method

    return ""


def parse_list_page(list_url: str, page: int):
    soup = fetch_soup(list_url)

    rows = []

    item_inputs = soup.select("input[id^='itemcd_']")

    logger.debug(f"[목록] page={page} / itemcd input 수: {len(item_inputs)}")

    for inp in item_inputs:
        item_input_id = inp.get("id", "")
        idx = item_input_id.replace("itemcd_", "").strip()
        if not idx.isdigit():
            continue

        item_code = inp.get("value", "").strip()
        case_id = get_hidden_value(soup, f"idx_{idx}")
        product_name = get_hidden_value(soup, f"itemnm_{idx}")
        mcd = get_hidden_value(soup, f"mcd_{idx}")
        ca = get_hidden_value(soup, f"ca_{idx}")
        catnm = get_hidden_value(soup, f"catnm_{idx}")
        event_category = parse_html_category_text(catnm)

        # hidden input 바로 뒤의 상품 카드 td
        card = inp.find_next("td", attrs={"width": "33%"})

        registered_date = ""
        list_price_text = ""

        # 상세페이지는 반드시 상품명 a href에서 추출
        detail_url, product_name_from_link = find_product_detail_link(card, item_code)

        if product_name_from_link:
            product_name = product_name_from_link

        # 인쇄방법은 상품코드 td의 다음 td에서만 추출
        print_method = extract_print_method_from_card(card, item_code)

        if card:
            # 등록일
            date_tag = card.find(string=lambda s: s and "등록일" in s)
            if date_tag:
                registered_date = clean_label_value(str(date_tag), "등록일")
            else:
                card_text = card.get_text(" ", strip=True)
                m = re.search(r"등록일\s*[:：]\s*(\d{4}-\d{2}-\d{2})", card_text)
                registered_date = m.group(1) if m else ""

            # 목록 하단 가격
            strongs = [s.get_text(" ", strip=True) for s in card.find_all("strong")]
            if strongs:
                list_price_text = strongs[-1].replace("~", "").strip()

        # a href 추출 실패 시에만 hidden 값으로 상세 URL 보정
        if not detail_url and item_code and mcd and ca:
            detail_url = urljoin(config.BASE_URL, f"/shop/viewitem.asp?mcd={mcd}&ca={ca}&itemcd={item_code}")

        buyer_mid, buyer_small, buyer_detail = split_buyer_category(event_category)

        row = {
            "납품사례ID": case_id,
            "상품코드": item_code,
            "구매처분류(중)": buyer_mid,
            "구매처분류(소)": buyer_small,
            "구매처분류(세)": buyer_detail,
            "상품명": product_name,
            "인쇄방법": print_method,  # 비어있으면 그대로 빈칸 저장
            "업종/행사": event_category,
            "등록일": registered_date,
            "목록가격": list_price_text,
            "상세URL": detail_url,
            "수집페이지": page,
        }
        row["수집키"] = make_collect_key(row)

        rows.append(row)

    return rows
