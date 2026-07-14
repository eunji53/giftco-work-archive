# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 기본 설정

파일 경로는 이 crawler 패키지가 있는 sarang87/ 폴더를 기준으로 합니다.
(스크립트를 어느 폴더에서 실행하든 결과 파일 위치가 바뀌지 않도록,
cwd가 아니라 이 파일의 실제 위치를 기준으로 삼습니다.)
"""
import shutil
from pathlib import Path

import requests

BASE_URL = "https://www.87sarang.com"

START_URL = (
    "https://www.87sarang.com/customercenter/supplycaselist.asp?"
    "page=1&lcode=&mcode=&scode=&iscolor=&isSamllQty=&origin=&isOrderMade="
    "&freed=&freep=&orderby=12&orderbytype=desc&printtype=&price01=&price02="
    "&mcd=&stype=N&srch="
)
#START_PAGE = 크롤링 시작 페이지
#END_PAGE = 크롤링 끝나는 페이지

START_PAGE = 1
END_PAGE = 5#9999


# =========================
# 저장 파일 설정
# 파일명 변경 가능

#TEMPLATE_XLSX	결과 엑셀의 기본 양식 파일
#OUTPUT_XLSX	최종 크롤링 결과 엑셀
#CHECKPOINT_CSV	중간 저장 파일, 재시작할 때 이어서 하기 위함
#ERROR_LOG_CSV	오류 발생 내역 저장
#LIST_ONLY_CSV	목록 페이지만 먼저 수집한 결과 저장
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
SAVE_DIR = BASE_DIR / "output"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_XLSX = str(BASE_DIR / "data" / "supply_case_template.xlsx")

# 기본 저장 파일: BASE_DIR(sarang87/)에 저장
OUTPUT_XLSX = str(BASE_DIR / "crawl_result.xlsx")

CHECKPOINT_CSV = str(BASE_DIR / "detail_checkpoint.csv")
CHECKPOINT_XLSX = str(BASE_DIR / "detail_checkpoint.xlsx")
ERROR_LOG_CSV = str(BASE_DIR / "error_log.csv")
LIST_ONLY_CSV = str(BASE_DIR / "list_checkpoint.csv")

# 복사 저장 위치: BASE_DIR 하위 output 폴더
OUTPUT_XLSX_DIR = SAVE_DIR / Path(OUTPUT_XLSX).name
CHECKPOINT_CSV_DIR = SAVE_DIR / Path(CHECKPOINT_CSV).name
CHECKPOINT_XLSX_DIR = SAVE_DIR / Path(CHECKPOINT_XLSX).name
ERROR_LOG_CSV_DIR = SAVE_DIR / Path(ERROR_LOG_CSV).name
LIST_ONLY_CSV_DIR = SAVE_DIR / Path(LIST_ONLY_CSV).name


def sync_to_dir(path):
    """
    BASE_DIR에 저장된 결과 파일을 output 폴더에도 같은 이름으로 복사합니다.
    """
    src = Path(path)
    if not src.exists():
        return

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    dst = SAVE_DIR / src.name

    # 원본과 대상이 같은 경우는 복사하지 않음
    try:
        if src.resolve() == dst.resolve():
            return
    except FileNotFoundError:
        pass

    shutil.copy2(src, dst)


# =========================
# 저장 주기 설정
# =========================
SAVE_EXCEL_EVERY_ROWS = 5000


# =========================
# 요청 간격 설정
# 최소 5초 ~ 최대 12초 사이 랜덤 대기
# =========================

REQUEST_SLEEP_MIN = 5.0
REQUEST_SLEEP_MAX = 12.0

# =========================
# 재시도 설정
# =========================

MAX_RETRIES = 2
RETRY_SLEEP = 15

# =========================
# 요청 헤더 설정
# =========================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.87sarang.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

session = requests.Session()
session.headers.update(HEADERS)

# =========================
# 분리 수집 설정
# =========================

BUYER_CATEGORY_COLUMNS = ["구매처분류(중)", "구매처분류(소)", "구매처분류(세)"]

LIST_COLUMNS = [
    "수집키", "납품사례ID", "수집페이지",
    "상품코드", *BUYER_CATEGORY_COLUMNS, "상품명",
    "인쇄방법", "업종/행사", "등록일", "상세URL",
    "목록수집상태"
]

# 페이지 오류 400 / 403 / 429 응답 발생 시 추가 대기 시간
# 실제 대기시간 = BLOCK_STATUS_SLEEP * 재시도횟수
BLOCK_STATUS_SLEEP = 60

# 상세페이지 요청 전에 목록페이지를 한 번 열어서 Referer / 세션 흐름을 맞출지 여부
WARMUP_REFERER_BEFORE_DETAIL = True

# 상세페이지가 끝까지 열리지 않아도 목록에서 가져온 기본정보는 엑셀에 저장할지 여부
DETAIL_ERROR_SAVE_AS_ROW = True

# 기존 체크포인트에 '상세페이지 오류'로 저장된 상품을 다시 시도할지 여부
# True로 바꾸면 오류 행을 체크포인트에서 제거하고 다시 상세 수집합니다.
RETRY_DETAIL_ERRORS = False

# 일정 건수마다 긴 휴식 시간을 줘서 400 오류 가능성을 줄임
COOLDOWN_EVERY_ITEMS = 999999
COOLDOWN_SLEEP_MIN = 0
COOLDOWN_SLEEP_MAX = 0


# =========================
# 상세페이지 수집 방식
# =========================
# list 단계: 기존 requests + BeautifulSoup
# detail 단계: 기본 Selenium 사용
# requests: 빠르지만 상세페이지에서 400 오류가 날 수 있음
# selenium: 느리지만 실제 브라우저로 열기 때문에 400 오류가 줄어듦
DETAIL_FETCH_MODE = "selenium"

# Selenium 브라우저 표시 여부
# False: 크롬 창이 보임
# True: 창 없이 실행. 단, 사이트에 따라 headless에서 다르게 동작할 수 있음
SELENIUM_HEADLESS = False

# Selenium 페이지 로딩 대기
SELENIUM_WAIT_SECONDS = 5.0
SELENIUM_PAGELOAD_TIMEOUT = 20

# Selenium 상세페이지 요청 간격
SELENIUM_SLEEP_MIN = 0.4
SELENIUM_SLEEP_MAX = 1.2

# 일정 건수마다 브라우저 재시작. 장시간 실행 안정성용
# Selenium 창이 자동으로 닫았다가 다시 열림
# ex): 500개 저장이 되면 다시 닫았다가 열림
SELENIUM_RESTART_EVERY = 500


# =========================
# 직접 URL 수집 설정
# =========================
# True: 납품사례 목록주소를 먼저 열지 않고, LIST_ONLY_CSV의 상세URL(I열)로 바로 접속
DETAIL_DIRECT_URL_ONLY = True

# 기존 체크포인트에서 상세 오류 또는 상세값이 비어 있는 행을 다시 시도할지 여부
RETRY_BLANK_DETAIL_ROWS = True


# =========================
# Selenium 빠르게추출
# =========================
# True: 이미지 로딩을 막고, 페이지 전체 로딩 완료를 기다리지 않음
# False: 이미지 로딩이 되어, 페이지 로딩 시간이 있음
# HTML 텍스트 기반 추출이므로 일반적으로 True 권장
FAST_SELENIUM_MODE = True

# 상세페이지 핵심 텍스트가 나오면 고정 대기시간을 다 기다리지 않고 바로 파싱
DETAIL_READY_MARKERS = [
    "현재위치",
    "즉시 할인가",
    "즉시할인가",
    "일반 판매가",
    "일반판매가",
    "최소인쇄수량",
    "최소주문수량",
    "가격문의",
]
