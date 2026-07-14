# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 상세 페이지 파싱
"""
import html
import re

from bs4 import BeautifulSoup

from . import config
from .fetch import fetch_soup, fetch_soup_selenium, fetch_soup_selenium_direct
from .parsing_utils import clean_price_to_int


def parse_product_categories(detail_soup: BeautifulSoup):
    """
    상세페이지 현재위치 영역에서 상품분류(대/중/소)를 추출합니다.

    기준:
    현재위치 : HOME > 부채 > 부채 > 부채(전통,한지부채)
    """

    position_td = None

    # 1순위: 현재위치 아이콘 arr01.gif가 들어있는 td
    img = detail_soup.find("img", src=lambda s: s and "/image/sub/arr01.gif" in s)
    if img:
        position_td = img.find_parent("td")

    # 2순위: 텍스트에 '현재위치'가 있는 td
    if position_td is None:
        for td in detail_soup.find_all("td"):
            td_text = td.get_text(" ", strip=True)
            if "현재위치" in td_text:
                position_td = td
                break

    categories = []

    if position_td is not None:
        for a in position_td.find_all("a", href=True):
            href = html.unescape(a.get("href", "")).strip()
            name = a.get_text(" ", strip=True)

            if not name or name.upper() == "HOME":
                continue

            if (
                "/shop/main.asp" in href
                or "/shop/middle.asp" in href
                or "/shop/small.asp" in href
            ):
                categories.append(name)

    # 3순위: 현재위치 텍스트만 있는 경우 보조 추출
    if not categories:
        page_text = detail_soup.get_text(" ", strip=True)
        m = re.search(r"현재위치\s*:\s*HOME\s*>\s*([^>\n]+)\s*>\s*([^>\n]+)\s*>\s*([^>\n]+)", page_text)
        if m:
            categories = [m.group(1).strip(), m.group(2).strip(), m.group(3).strip()]

    large = categories[0] if len(categories) >= 1 else ""
    middle = categories[1] if len(categories) >= 2 else ""
    small = categories[2] if len(categories) >= 3 else ""

    return large, middle, small


def parse_minimum_quantities(detail_soup: BeautifulSoup):
    """
    상세페이지에서 최소인쇄수량 / 최소주문수량을 각각 독립적으로 추출합니다.

    예:
    - 최소인쇄수량 : 100개
    - 최소주문수량 : 100개
    - 최소인쇄수량 : 20세트
    - 최소주문수량 : 10세트
    """

    min_print_qty = ""
    min_order_qty = ""

    page_text = detail_soup.get_text("\n", strip=True)
    page_text = html.unescape(page_text)
    page_text = re.sub(r"\s+", " ", page_text)

    # 숫자 + 단위 추출
    # 단위는 다음 라벨 전까지 너무 많이 먹지 않도록 짧게 제한
    qty_pattern = r"([0-9,]+)\s*([가-힣A-Za-z0-9()\/·\-\+]+)?"

    m_print = re.search(
        rf"최소\s*인쇄\s*수량\s*[:：]\s*{qty_pattern}",
        page_text
    )
    if m_print:
        number = m_print.group(1)
        unit = m_print.group(2) or ""
        min_print_qty = f"{number}{unit}"

    m_order = re.search(
        rf"최소\s*주문\s*수량\s*[:：]\s*{qty_pattern}",
        page_text
    )
    if m_order:
        number = m_order.group(1)
        unit = m_order.group(2) or ""
        min_order_qty = f"{number}{unit}"

    if not min_order_qty:
        m_order_alt = re.search(
            rf"최소\s*주문\s*[:：]\s*{qty_pattern}",
            page_text
        )
        if m_order_alt:
            number = m_order_alt.group(1)
            unit = m_order_alt.group(2) or ""
            min_order_qty = f"{number}{unit}"

    return min_print_qty, min_order_qty


def decode_percent_u_escaped(text: str) -> str:
    """
    가격표가 document.write(unescape("...")) 안에 들어있는 경우를 처리합니다.
    Python의 urllib.parse.unquote는 %uC218 같은 JS escape를 처리하지 못하므로 별도 처리합니다.
    """
    from urllib.parse import unquote

    if not text:
        return ""

    def repl_unicode(m):
        return chr(int(m.group(1), 16))

    text = re.sub(r"%u([0-9A-Fa-f]{4})", repl_unicode, text)
    text = unquote(text)

    return text


def find_price_tables_in_soup(soup: BeautifulSoup):
    """
    상세페이지에서 가격표 table 후보를 찾습니다.

    기준:
    - table 텍스트에 '즉시 할인가' 또는 '일반 판매가'가 있는 경우
    - 또는 table 내부에 input name='rateprice'가 있는 경우
    """
    tables = []

    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True)
        has_price_label = ("즉시 할인가" in table_text) or ("즉시할인가" in table_text) or ("일반 판매가" in table_text) or ("일반판매가" in table_text)
        has_rateprice = table.find("input", {"name": "rateprice"}) is not None

        if has_price_label or has_rateprice:
            tables.append(table)

    return tables


def extract_price_values_from_table(table):
    """
    가격표 table에서 가격을 추출합니다.

    우선순위:
    1. '즉시 할인가' 행
    2. '일반 판매가' 행
    3. table 내부 hidden input name='rateprice'

    기준:
    - 1번째 가격 = 소량가격
    - 4번째 가격 = 중간가격
    - 마지막 가격 = 대량가격

    가격 컬럼이 7개든 8개든 마지막 가격을 대량가격으로 사용합니다.
    """
    table_text = table.get_text(" ", strip=True)

    price_rows = {}

    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue

        row_name = re.sub(r"\s+", "", cells[0])

        if "즉시할인가" in row_name:
            price_rows["즉시할인가"] = cells[1:]
        elif "일반판매가" in row_name:
            price_rows["일반판매가"] = cells[1:]

    raw_prices = price_rows.get("즉시할인가") or price_rows.get("일반판매가") or []

    # 가격 행에 가격문의가 명시된 경우만 가격문의로 처리
    if raw_prices and any("가격문의" in str(x) for x in raw_prices):
        return "가격문의", "가격문의", "가격문의"

    prices = [clean_price_to_int(x) for x in raw_prices]
    prices = [p for p in prices if isinstance(p, int)]

    # table 내부 hidden rateprice 보조 추출
    if not prices:
        for inp in table.find_all("input", {"name": "rateprice"}):
            value = inp.get("value", "")
            price = clean_price_to_int(value)
            if isinstance(price, int):
                prices.append(price)

    if prices:
        small_price = prices[0]
        middle_price = prices[3] if len(prices) >= 4 else prices[len(prices) // 2]
        large_price = prices[-1]
        return large_price, middle_price, small_price

    # 진짜 가격문의 테이블인 경우만 가격문의 처리
    if "가격문의" in table_text and not re.search(r"[0-9][0-9,]*\s*원", table_text):
        return "가격문의", "가격문의", "가격문의"

    return None, None, None


def parse_price_columns(detail_soup: BeautifulSoup):
    """
    상세페이지 가격표에서 가격을 추출합니다.

    기준:
    - 즉시 할인가 행 우선
    - 없으면 일반 판매가 행 사용
    - 1번째 가격 = 소량가격
    - 4번째 가격 = 중간가격
    - 마지막 가격 = 대량가격

    주의:
    페이지 어딘가에 '가격문의' 문구가 있어도,
    가격표나 rateprice 값이 있으면 실제 가격을 우선 사용합니다.
    """
    page_text = detail_soup.get_text(" ", strip=True)
    html_text = str(detail_soup)

    # 1순위: HTML에 이미 렌더링된 table이 있는 경우
    for table in find_price_tables_in_soup(detail_soup):
        large_price, middle_price, small_price = extract_price_values_from_table(table)
        if any(v is not None for v in [large_price, middle_price, small_price]):
            return large_price, middle_price, small_price

    # 2순위: document.write(unescape("...")) script 내부에 가격표가 있는 경우
    patterns = [
        r'document\.write\s*\(\s*unescape\s*\(\s*"([^"]+)"\s*\)\s*\)',
        r"document\.write\s*\(\s*unescape\s*\(\s*'([^']+)'\s*\)\s*\)",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
            encoded_html = m.group(1)
            decoded_html = decode_percent_u_escaped(encoded_html)

            if not decoded_html:
                continue

            price_soup = BeautifulSoup(decoded_html, "html.parser")

            for table in find_price_tables_in_soup(price_soup):
                large_price, middle_price, small_price = extract_price_values_from_table(table)
                if any(v is not None for v in [large_price, middle_price, small_price]):
                    return large_price, middle_price, small_price

            # decoded 내부에 진짜 가격문의만 있는 경우
            decoded_text = price_soup.get_text(" ", strip=True)
            if "가격문의" in decoded_text and not re.search(r"[0-9][0-9,]*\s*원", decoded_text):
                return "가격문의", "가격문의", "가격문의"

    # 3순위: 상세페이지에 rateprice hidden만 있는 경우
    rate_prices = []
    for inp in detail_soup.find_all("input", {"name": "rateprice"}):
        value = inp.get("value", "")
        price = clean_price_to_int(value)

        if isinstance(price, int):
            rate_prices.append(price)

    # 3-1순위: raw HTML 문자열에서 rateprice 직접 추출
    if not rate_prices:
        for m in re.finditer(r'name=["\']rateprice["\']\s+value=["\']([^"\']+)["\']', html_text, flags=re.IGNORECASE):
            price = clean_price_to_int(m.group(1))
            if isinstance(price, int):
                rate_prices.append(price)

    if rate_prices:
        small_price = rate_prices[0]
        middle_price = rate_prices[3] if len(rate_prices) >= 4 else rate_prices[len(rate_prices) // 2]
        large_price = rate_prices[-1]
        return large_price, middle_price, small_price

    # 4순위: 진짜 가격문의 페이지인 경우만 가격문의 처리
    # 단순히 페이지 어딘가에 가격문의 문구가 있는 것만으로는 가격문의 처리하지 않음
    has_price_number = bool(re.search(r"[0-9][0-9,]*\s*원", page_text))
    if "가격문의" in page_text and not has_price_number:
        return "가격문의", "가격문의", "가격문의"

    return None, None, None


def parse_detail_page(detail_url: str, referer: str = None):
    if not detail_url:
        return {
            "상품분류(대)": "",
            "상품분류(중)": "",
            "상품분류(소)": "",
            "최소인쇄수량": "",
            "최소주문수량": "",
            "대량가격(원)": None,
            "중간가격(원)": None,
            "소량가격(원)": None,
        }

    if config.DETAIL_FETCH_MODE == "selenium":
        if config.DETAIL_DIRECT_URL_ONLY:
            soup = fetch_soup_selenium_direct(detail_url)
        else:
            soup = fetch_soup_selenium(detail_url, referer=referer)
    else:
        soup = fetch_soup(detail_url, referer=referer)

    large_cat, middle_cat, small_cat = parse_product_categories(soup)
    min_print_qty, min_order_qty = parse_minimum_quantities(soup)
    large_price, middle_price, small_price = parse_price_columns(soup)

    return {
        "상품분류(대)": large_cat,
        "상품분류(중)": middle_cat,
        "상품분류(소)": small_cat,
        "최소인쇄수량": min_print_qty,
        "최소주문수량": min_order_qty,
        "대량가격(원)": large_price,
        "중간가격(원)": middle_price,
        "소량가격(원)": small_price,
    }
