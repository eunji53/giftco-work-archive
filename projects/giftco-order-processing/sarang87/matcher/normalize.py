# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 - 텍스트/상품명/분류명 정규화, 날짜 파싱, 컬럼 탐색 유틸.

02_match_buyer_names.py(운영 스크립트)에서 분리되었습니다.
전역 상태(df87_work/dftr_work 등)에 의존하지 않는 순수 함수만 모아둡니다.
"""

import re
from datetime import datetime, date

import pandas as pd

from .config import USE_PRODUCT_PREFIX_TAG_REMOVAL


def clean_text(value):
    """빈값/공백/NBSP 정리용."""
    if pd.isna(value):
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


# 상품명 앞에 붙을 수 있는 제작/상태 태그만 제거합니다.
# 브랜드 태그([PGA], [쿨린], [스위스밀리터리])는 제거하지 않습니다.
PRODUCT_PREFIX_TAGS = {
    "긴급제작", "급행제작", "빠른제작", "당일제작", "주문제작",
    "긴급", "급행", "당일", "빠른제작상품"
}

# 제작/상태 태그 비교용: 태그 안 공백 차이를 없애고 비교합니다.
# 예: "긴급 제작"과 "긴급제작"을 같은 태그로 처리하기 위한 값입니다.
PRODUCT_PREFIX_TAGS_NORM = {
    re.sub(r"\s+", "", x) for x in PRODUCT_PREFIX_TAGS
}


def normalize_product_raw(value):
    """상품명 완전일치용: 원본 상품명의 앞뒤 공백, 연속 공백만 정리."""
    return clean_text(value)


def normalize_product_exact(value):
    """상품명 exact용: 기본 정규화 후 비교.

    완전일치(raw)보다 한 단계 느슨하지만, relaxed처럼 상품명 의미 요소를 많이 지우지는 않습니다.
    처리 내용:
    - 앞뒤/연속 공백 정리
    - 영문 대소문자 통일
    - 공백 및 일부 구분자 제거
    - 괄호/대괄호 기호는 제거하되 내부 글자는 유지
    """
    text = clean_text(value).lower()
    if not text:
        return ""
    # 괄호/대괄호는 글자는 남기고 기호만 제거되도록 전체 구분자를 제거합니다.
    text = re.sub(r"[\s ]+", "", text)
    text = re.sub(r'''[·ㆍ･\-_/,.()\[\]{}<>:;|"\'`~!@#$%^&*=\\?]+''', "", text)
    return text


def normalize_product_relaxed(value):
    """
    상품명 보조매칭용.

    처리 규칙:
    1. 맨 앞 (완판), (인쇄 무료 이벤트) 같은 상태/이벤트 문구는 제거
       - 예: (완판) 상품명 → 상품명
       - 예: (인쇄 무료 이벤트) 상품명 → 상품명

    2. 맨 앞 [긴급제작], [급행제작] 같은 제작/상태 태그는 제거
       - 예: [긴급제작] 화이트 물티슈 → 화이트 물티슈

    3. 맨 뒤 [102-217591] 같은 코드성 대괄호는 제거
       - 예: 상품명 [102-217591] → 상품명

    4. [쿨린], [PGA], [LION] 같은 브랜드 태그는 []만 제거하고 글자는 유지
       - 예: [쿨린] 리풀 → 쿨린 리풀
       - 예: [LION] 참그린 → LION 참그린

    5. 상품명 안의 단독 1P / 1개 / 1EA 표기는 제거
       - 예: 12cm연필 책갈피자(칼라) 1P → 12cm연필 책갈피자(칼라)

    6. 쇼핑백 증정 문구 제거
       - 예: (쇼핑백 증정) → 제거

    7. 우산 상품의 8K / 10K / 16K 같은 살대 수 표기 제거
       - 단, 상품명에 '우산'이 있을 때만 적용

    8. 우산/양우산 표현 통일
       - 예: 양우산 → 우산

    9. + 기호 제거
       - 예: 롱티스푼+롱포크 → 롱티스푼롱포크

    10. 단독 색상명 '실버' 제거
        - 예: 실버 그레이스 롱티스푼롱포크 → 그레이스 롱티스푼롱포크
        - 단, 다른 단어 안에 붙은 경우는 제거하지 않음

    11. 상품명 앞의 (국산) 제거
        - 예: (국산)코리아5링 니들3색 터치펜 → 코리아5링 니들3색 터치펜

    12. 상품명 안의 사이즈 괄호 제거
        - 예: 포켓에코백 A형 (34x39cm) 1P → 포켓에코백 A형 1P
        - 예: 포켓에코백 A형 (34 x 39 cm) 1P → 포켓에코백 A형 1P

    13. 상품명 뒤의 잉크/저점도 설명 괄호 제거
        - 예: 코리아5링 니들3색 터치펜(독일잉크/초초저점도) → 코리아5링 니들3색 터치펜

    14. 공백 정리
    """
    text = normalize_product_raw(value)

    # 맨 앞의 상태/이벤트 괄호 문구 제거
    # 예: (완판), (품절), (인쇄 무료 이벤트)
    text = re.sub(
        r"^\((완판|품절|일시품절|단종|판매종료|인쇄\s*무료\s*이벤트)\)\s*",
        "",
        text
    )

    # 상품명 앞의 (국산) 제거
    # 예: (국산)코리아5링 니들3색 터치펜 → 코리아5링 니들3색 터치펜
    text = re.sub(r"^\(\s*국산\s*\)\s*", "", text)

    if USE_PRODUCT_PREFIX_TAG_REMOVAL:
        # 맨 앞에 제작상태 태그가 여러 개 붙은 경우도 처리
        # 예: [긴급제작] [당일제작] 상품명 → 상품명
        while True:
            m = re.match(r"^\[([^\]]+)\]\s*(.*)$", text)
            if not m:
                break

            tag = clean_text(m.group(1))
            rest = clean_text(m.group(2))
            tag_norm = re.sub(r"\s+", "", tag)

            # 제작/상태 태그면 태그 자체를 제거
            if tag_norm in PRODUCT_PREFIX_TAGS_NORM and rest:
                text = rest
            else:
                break

    # 맨 뒤에 붙은 코드성 대괄호 제거
    # 예: 상품명 [102-217591] → 상품명
    # 코드는 항상 숫자를 포함하므로, 숫자가 없는 [LION]/[PGA] 같은 브랜드 태그가
    # 이 단계에서 함께 삭제되지 않도록 대괄호 안에 숫자가 있을 때만 제거합니다.
    text = re.sub(r"\s*\[(?=[0-9A-Za-z_-]*\d)[0-9A-Za-z_-]{3,}\]\s*$", "", text)

    # 브랜드/제품 태그는 []만 제거하고 글자는 유지
    # 예: [쿨린] 리풀 → 쿨린 리풀
    # 예: [LION] 참그린 → LION 참그린
    text = re.sub(r"\[([^\]]+)\]", r" \1 ", text)

    # 상품명 안의 사이즈 괄호 제거
    # 예:
    # 포켓에코백 A형 (34x39cm) 1P → 포켓에코백 A형 1P
    # 포켓에코백 A형 (34 x 39 cm) 1P → 포켓에코백 A형 1P
    # 단, 숫자 x 숫자 형태의 크기 표기만 제거합니다.
    text = re.sub(
        r"\(\s*\d+(?:\.\d+)?\s*(?:x|X|×|\*)\s*\d+(?:\.\d+)?\s*(?:cm|CM|mm|MM|m|M)?\s*\)",
        " ",
        text
    )

    # 단독 1P / 1개 / 1EA 제거
    # 단, 10P / 2P / 10000mAh / 3in1 / 1PORT / 1+1 은 제거하지 않음
    text = re.sub(
        r"(?<![0-9A-Za-z가-힣])1\s*(?:p|P|개|ea|EA)(?![0-9A-Za-z가-힣])",
        " ",
        text
    )

    # 사은품/증정 문구 제거
    # 예: (쇼핑백 증정), 쇼핑백증정
    text = re.sub(r"\(?\s*쇼핑백\s*증정\s*\)?", " ", text)

    # 우산 상품의 살대 수 표기 제거
    # 예: 10K 3단 자동 우산 → 3단 자동 우산
    # 단, 상품명에 '우산'이 있을 때만 적용
    if "우산" in text:
        text = re.sub(
            r"(?<![0-9A-Za-z가-힣])\d{1,2}\s*[kK](?![0-9A-Za-z가-힣])",
            " ",
            text
        )

    # 우산/양우산 표현 통일
    # 예: 거꾸로 양우산 → 거꾸로 우산
    text = re.sub(r"양우산", "우산", text)

    # + 기호 제거
    # 예: 롱티스푼+롱포크 → 롱티스푼롱포크
    text = re.sub(r"\s*\+\s*", "", text)

    # 단독 색상명 '실버' 제거
    # 예: 실버 그레이스 롱티스푼롱포크 → 그레이스 롱티스푼롱포크
    text = re.sub(
        r"(?<![0-9A-Za-z가-힣])(?:실버|silver)(?![0-9A-Za-z가-힣])",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # 상품명 뒤의 잉크/저점도 설명 괄호 제거
    # 예: 코리아5링 니들3색 터치펜(독일잉크/초초저점도) → 코리아5링 니들3색 터치펜
    # 괄호가 상품명 끝에 있고, 잉크/저점도 설명일 때만 제거합니다.
    text = re.sub(
        r"\([^)]*(?:잉크|저점도|초저점도|초초저점도)[^)]*\)\s*$",
        " ",
        text
    )

    # 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_category_raw(value):
    """분류명 비교용 기본 정규화.

    예:
    - 중.고등학교 / 중·고등학교 / 중고등학교 → 중고등학교로 비교 가능
    - 학교/교육기관처럼 구분자가 들어간 값은 구분자 제거 후 비교
    """
    text = clean_text(value).lower()
    text = text.replace("·", "").replace("ㆍ", "").replace("･", "")
    text = re.sub(r"[\s\t\n\r]+", "", text)
    text = re.sub(r"[\\/\-_,.()\[\]{}<>:;|]+", "", text)
    return text


# 중/소분류 별칭. 양쪽 모두 같은 canonical로 묶습니다.
CATEGORY_ALIAS_PAIRS = [
    ("교육지원청/wee센터/도서관", "교육청/wee센터/도서관"),
    ("봉사/자선단체/사회복지기금", "봉사/자선단체/사회복지기금,센터기타"),
    ("전문직(변호사/회계사...)", "전문직"),
    ("중.고등학교", "중고등학교"),
    ("중·고등학교", "중고등학교"),
    ("중ㆍ고등학교", "중고등학교"),
    ("중/고등학교", "중고등학교"),
    ("중,고등학교", "중고등학교"),
    ("복지관/복지관련 기관", "복지관/복지관련기관"),
    ("장애인관련기관/센터", "장애인관련기관센터"),
    ("문화부체육관광부", "문화체육관광부"),
    ("첨단기술/AI/빅데이터 관련", "첨단기술/IT/빅데이터 관련"),
    ("산업통상자원부/특허청", "산업통산자원부/특허청"),
    ("리서치/텔레마케팅 회사", "리서치/텔레마케팅"),
    ("미술학원/애니메이션", "마술학원/애니메이션"),
    ("사무기기/컴퓨터 판매/정수기렌탈", "사무기기/컴퓨터 판매/렌탈"),
    ("국제교류/협력관련", "국제교류관련"),
    ("귀금속/악세사리", "귀금속/악세서리"),
    ("보건복지부/질병관리청", "보건복지부/질병관리본부"),
    ("신용카드/캐피탈", "산용카드/캐피탈"),
    ("장애인종합복지관", "장애인복지관"),
    ("국민건강보험공단/평가원", "국민건강보험공단"),
    ("에너지/배터리/태양열/정유", "에너지/태양열/정유"),
    ("애견용품/동물병원/반려관련", "애견용품/동물병원/애견관련"),
    ("영상의학과의원", "영상의학과"),
    ("청와대/국회/정당", "청와대/국회"),
    ("PC방/보드카페/게임방", "PC방/보드카페"),
    ("대학교박물관/기념관", "대학교박물관"),
    ("입학/홍보/기획", "입학/홍보"),
    ("학생처/학생지원센터", "학생지원센터"),
    ("청년회의소(JCI)", "청년회의소"),
    ("교수학습지원센터/교수협의회", "교수학습지원센터"),
    ("보안/경비/건물관리/용역", "보안경비/용역"),
    ("인터넷쇼핑몰/홈쇼핑", "인터넷쇼핑몰/앱"),
    ("학생상담센터/인권센터", "학생상담센터"),
    ("행정복지센터(주민센터)", "행정복지센터"),
    ("학습지/방문교육", "학습지/학습교육"),
    ("한국EMS협회", "한국EMS연맹"),
    ("엔터테인먼트/연예기획사", "엔터테인먼트"),
    ("소방청/소방서", "소방서"),
    ("기타 교육관련기관", "기타교육관련기관"),
    ("근로자의날 기념", "근로자의 날 기념"),
    ("어버이날/스승의날기념", "어버이날/스승의날 기념"),
    ("가족센터(건강가정.다문화가족)", "가족센터(건강가정,다문화가족)"),
    ("여성관련 협회/재단", "여성관련협회/재단"),
    ("여성긴급전화 1366", "여성긴급전화1366"),
    ("여성인력개발센터 (여성새로일하기센터)", "여성인력개발센터(여성새로일하기센터)"),
    ("칠순.팔순.구순기념", "칠순팔순구순기념"),
    ("기타 어린이관련학교", "기타어린이관련학교"),
]

_alias_map = {}
for a, b in CATEGORY_ALIAS_PAIRS:
    na = normalize_category_raw(a)
    nb = normalize_category_raw(b)
    canonical = min(na, nb)
    _alias_map[na] = canonical
    _alias_map[nb] = canonical


def normalize_category(value):
    raw = normalize_category_raw(value)
    return _alias_map.get(raw, raw)


def parse_one_date(value):
    """엑셀 날짜 숫자, datetime, YYYY/MM/DD, YYYY-MM-DD 혼합 처리."""
    if pd.isna(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    text = clean_text(value)
    if not text:
        return ""

    text_num = text.replace(",", "")
    if re.fullmatch(r"\d+(\.0)?", text_num):
        try:
            num = float(text_num)
            if 20000 <= num <= 60000:
                return pd.to_datetime(num, unit="D", origin="1899-12-30").strftime("%Y-%m-%d")
        except Exception:
            pass

    text2 = text.replace(".", "-").replace("/", "-")
    try:
        dt = pd.to_datetime(text2, errors="coerce", format="mixed")
    except TypeError:
        dt = pd.to_datetime(text2, errors="coerce")

    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d")


def find_col(df, candidates, required=True):
    """컬럼명을 공백 제거 기준으로 찾아줌."""
    col_map = {clean_text(c): c for c in df.columns}
    for cand in candidates:
        key = clean_text(cand)
        if key in col_map:
            return col_map[key]
    if required:
        raise KeyError(f"컬럼을 찾지 못했습니다: {candidates}")
    return None


def find_best_col_by_nonblank(df, candidates, exclude_values=("-",)):
    """동일한 이름 후보가 여러 개일 때, 유효값이 가장 많은 컬럼을 선택."""
    clean_candidates = [clean_text(x) for x in candidates]
    matches = []
    for col in df.columns:
        if clean_text(col) in clean_candidates:
            ser = df[col].map(clean_text)
            valid = ser.ne("") & ~ser.isin(exclude_values)
            matches.append((int(valid.sum()), col))
    if not matches:
        raise KeyError(f"컬럼을 찾지 못했습니다: {candidates}")
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][1], matches
