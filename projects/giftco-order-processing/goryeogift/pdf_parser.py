import re

# =========================
# 숫자 정리
# =========================
def clean_number(x):
    if x is None:
        return None
    s = re.sub(r"[^\d]", "", str(x))
    return int(s) if s else None


# =========================
# blob 금액 파싱 (핵심)
# =========================
def parse_amount_blob(line):
    """공백이 일부 또는 전부 누락돼 숫자들이 붙어버린 줄을 파싱한다.

    PyPDF2로 PDF를 추출하면 공급가액/부가세/합계 사이 공백이 종종 누락되고,
    심하면 수량부터 합계까지 전부 붙어버리는 경우도 있다. 쉼표 3자리 구분
    패턴(예: 557,368)을 단서로 삼아 뒤에서부터 합계 후보를 찾고,
    VAT+합계가 실제로 붙어있는지 검증한 뒤 남은 자리수를 수량/단가로 나눈다.
    """

    if "무료" in line:
        return None

    line = line.replace("\n", " ")

    if "-" not in line:
        return None

    tail = line.split("-")[-1]

    money_candidates = re.findall(r'\d{1,3}(?:,\d{3})+', tail)
    if not money_candidates:
        return None

    for total_str in reversed(money_candidates):

        total = int(total_str.replace(",", ""))

        supply = round(total / 1.1)
        vat = total - supply

        vat_str = f"{vat:,}"
        check_tail = vat_str + total_str

        tail_no_space = tail.replace(" ", "")

        # VAT + 합계 붙어있는지 확인
        if check_tail not in tail_no_space:
            continue

        prefix = tail_no_space.split(check_tail)[0]

        digits = re.sub(r"[^\d]", "", prefix)

        supply_digits = str(supply)
        if digits.endswith(supply_digits):
            digits = digits[:-len(supply_digits)]

        if len(digits) < 2:
            continue

        for i in range(1, len(digits)):
            qty = int(digits[:i])
            unit = int(digits[i:])

            # VAT 미포함 단가
            if qty * unit == supply:
                return {
                    "수량": qty,
                    "단가": unit,
                    "공급가액": supply,
                    "부가세": vat,
                    "합계": total,
                }

            # VAT 포함 단가
            if qty * unit == total:
                real_supply = round(total / 1.1)
                real_vat = total - real_supply
                return {
                    "수량": qty,
                    "단가": unit,
                    "공급가액": real_supply,
                    "부가세": real_vat,
                    "합계": total,
                }

    return None


# =========================
# 품목 영역 추출
# =========================
def extract_item_block(text):
    m = re.search(
        r"품목코드.*?합계\s*\n(.*?)\n공급가액\s*[\d,]+\s*VAT\s*[\d,]+\s*합계\s*[\d,]+",
        text,
        re.S,
    )
    if not m:
        return None

    block = m.group(1)

    # 상품명 뒤 숫자 blob 앞에 붙은 '-'만 분리 (USB-C 등 상품명 내 하이픈은 보존)
    processed_lines = []
    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "-" in line:
            left, right = line.rsplit("-", 1)
            if re.match(r"^\s*[\d,]", right):
                line = left.strip() + " - " + right.strip()
        processed_lines.append(line)

    return "\n".join(processed_lines)


# =========================
# 줄 분리
# =========================
def split_item_lines(item_block):
    """줄 분리 + PDF 줄 깨짐 병합

    세 가지 경우에만 직전 줄에 이어붙임:
    1. 직전 줄이 '-' 로 끝남 → PDF 하이픈 줄바꿈
    2. 현재 줄이 ',' 로 시작 → 숫자 중간 줄바꿈
    3. 직전 줄이 한글로 끝나고 현재 줄이 품목코드로 시작하지 않음 → 한글 단어 중간 줄바꿈
    """
    def ends_with_korean(s):
        return bool(s) and "가" <= s[-1] <= "힣"

    def starts_with_code(s):
        return bool(re.match(r"^[A-Z][A-Z0-9]*", s))

    merged = []
    for line in item_block.split("\n"):
        line = line.strip()
        if not line:
            continue

        if merged and merged[-1].endswith("-"):
            merged[-1] = merged[-1] + line
        elif line.startswith(",") and merged:
            merged[-1] = merged[-1] + line
        elif merged and ends_with_korean(merged[-1]) and not starts_with_code(line):
            merged[-1] = merged[-1] + line
        elif merged and not starts_with_code(line):
            # 품목코드로 시작하지 않는 줄은 새 상품이 아니라 직전 줄이 중간에
            # 끊겨 넘어온 것 (예: 상품명 끝의 모델번호 뒤에서 줄바꿈).
            # 이 경우는 원래 공백이 있던 자리에서 줄이 나뉜 것이므로 공백을 살려줌
            merged[-1] = merged[-1] + " " + line
        else:
            merged.append(line)
    return merged


# =========================
# 사양 분리
# =========================
def parse_spec(text):
    spec_match = re.search(r"사\s*양(.*?)발\s*송\s*처", text, re.S)
    if not spec_match:
        return None
    spec_text = spec_match.group(1)
    lines = [l.strip() for l in spec_text.split("\n") if l.strip()]
    return ", ".join(lines)


# =========================
# 한 줄 파싱
# =========================
def parse_line(line):
    # 1) 공백이 다 살아있는 정상 케이스
    normal_match = re.search(
        r"([A-Z0-9]+)\s*(.+?)\s+-\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)",
        line,
    )
    if normal_match:
        code, name, qty, price, supply, vat, total = normal_match.groups()
        return {
            "품목코드": code,
            "상품명": name.strip(),
            "수량": int(qty.replace(",", "")),
            "단가": clean_number(price),
            "공급가액": clean_number(supply),
            "부가세": clean_number(vat),
            "합계": clean_number(total),
        }

    # 2) 무료/옵션 행 (금액이 전부 0)
    option_match = re.search(
        r"([A-Z0-9]+)\s*(.+?)\s+-\s+([\d,]+)\s+0\s+0\s+0(?:\s+0)?",
        line,
    )
    if option_match:
        code, name, qty = option_match.groups()
        return {
            "품목코드": code,
            "상품명": name.strip(),
            "수량": int(qty.replace(",", "")),
            "단가": 0,
            "공급가액": 0,
            "부가세": 0,
            "합계": 0,
        }

    # 3) 부가세+합계만 붙어버린 경우 (부가세가 1,000원 미만이라 콤마가 없어서
    #    바로 뒤 합계 숫자와 헷갈리는 패턴). 공급가액까지는 깨끗하게 읽히므로
    #    공급가액을 신뢰하고 부가세/합계는 계산으로 역산한다.
    tail_glued_match = re.search(
        r"([A-Z0-9]+)\s*(.+?)\s+-\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s+[\d,]+\s*$",
        line,
    )
    if tail_glued_match:
        code, name, qty_s, price_s, supply_s = tail_glued_match.groups()
        qty = int(qty_s.replace(",", ""))
        price = clean_number(price_s)
        supply = clean_number(supply_s)
        # 검증: 이 값이 진짜 '공급가액'이 맞는지 확인 (아니면 공급가액+부가세가
        # 붙은 다른 패턴일 수 있으므로 이 분기를 쓰지 않고 blob 파싱에 맡김)
        if qty * price == supply:
            vat = round(supply * 0.1)
            return {
                "품목코드": code,
                "상품명": name.strip(),
                "수량": qty,
                "단가": price,
                "공급가액": supply,
                "부가세": vat,
                "합계": supply + vat,
            }

    # 3-2) 수량+단가까지 같이 붙어버린 경우 (수량이 한 자리라 앞자리에 묻힘).
    #    공급가액은 여전히 깨끗하므로, 수량*단가==공급가액이 되도록
    #    앞부분 숫자를 나눠본다.
    glued_qty_price_match = re.search(
        r"([A-Z0-9]+)\s*(.+?)\s+-\s+(\d{1,2})(\d{1,3}(?:,\d{3})+)\s+([\d,]+)\s+[\d,]+\s*$",
        line,
    )
    if glued_qty_price_match:
        code, name, qty_s, price_s, supply_s = glued_qty_price_match.groups()
        qty = int(qty_s)
        price = clean_number(price_s)
        supply = clean_number(supply_s)
        if qty * price == supply:
            vat = round(supply * 0.1)
            return {
                "품목코드": code,
                "상품명": name.strip(),
                "수량": qty,
                "단가": price,
                "공급가액": supply,
                "부가세": vat,
                "합계": supply + vat,
            }

    # 4) 그 외 공백이 불규칙하게 누락된 경우 → blob 파싱
    code_match = re.search(r'^([A-Z0-9]+)', line)
    name_match = re.search(r'[A-Z0-9]+\s*(.+?)\s+-', line)

    blob = parse_amount_blob(line)
    if blob:
        return {
            "품목코드": code_match.group(1) if code_match else None,
            "상품명": name_match.group(1).strip() if name_match else None,
            **blob,
        }

    # 5) 숫자를 끝내 못 나눈 경우 — 품목코드/상품명은 살리고 숫자만 비움
    if code_match:
        return {
            "품목코드": code_match.group(1),
            "상품명": name_match.group(1).strip() if name_match else None,
            "수량": None,
            "단가": None,
            "공급가액": None,
            "부가세": None,
            "합계": None,
        }

    return None


# =========================
# 품목 파싱
# =========================
def parse_items(text):
    item_block = extract_item_block(text)
    if not item_block:
        return []
    lines = split_item_lines(item_block)
    items = []
    for line in lines:
        parsed = parse_line(line)
        if parsed:
            items.append(parsed)
        else:
            # 파싱 실패 — 값은 비워두고 원본 줄을 상품명에 남겨서
            # 엑셀에서 빈 칸으로 눈에 띄게 하고 수동 확인할 수 있게 함
            items.append({
                "품목코드": None,
                "상품명": f"[확인필요] {line}",
                "수량": None,
                "단가": None,
                "공급가액": None,
                "부가세": None,
                "합계": None,
            })
    return items


# =========================
# 발송처
# =========================
def parse_sender(text):
    sender_block = re.search(r"발\s*송\s*처(.*?)(?:배송지|$)", text, re.S)
    sender_block = sender_block.group(1) if sender_block else ""

    company = re.search(r"상호[:\s]*(.+)", sender_block)
    company = company.group(1).strip() if company else None

    name = re.search(r"성명[:\s]*(.+)", sender_block)
    name = name.group(1).strip() if name else None

    phone = re.search(r"전화[:\s]*(.*?)(?:/|$)", sender_block)
    phone = phone.group(1).strip() if phone and phone.group(1).strip() else None

    mobile = re.search(r"휴대폰[:\s]*(.+)", sender_block)
    mobile = mobile.group(1).strip() if mobile else None

    address = re.search(r"주소[:\s]*(.+)", sender_block)
    address = address.group(1).strip() if address else None

    return company, name, phone, mobile, address
