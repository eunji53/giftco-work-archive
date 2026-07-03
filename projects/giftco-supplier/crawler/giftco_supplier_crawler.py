# -*- coding: utf-8 -*-
"""
giftco.co.kr 입점업체 상품목록 + 공급사 사업자정보 통합 크롤러
------------------------------------------------------------
01_crawl_product_list.ipynb 와
02_crawl_supplier_info.ipynb 의 로직을 하나로 합쳐,
스크립트 한 번 실행으로 아래 두 단계를 순서대로 끝까지 수행합니다.

1단계 (상품목록 크롤링)
  giftco.co.kr 관리자 페이지(partner_goods_admlist)를 페이지 단위로 순회하며
  상품코드/업체명/이미지URL/상품링크 등을 수집 → partner_goods_full.xlsx

2단계 (공급사 사업자정보 크롤링)
  1단계 결과에서 업체명별 '가장 최근 상품' 1건의 상세페이지에 접속해
  공급사 연락처(전화/휴대폰/이메일/주소)와 발주링크를 추출한 뒤,
  같은 세션으로 발주링크에 접속해 사업자번호/대표자/업태/종목까지 수집
  → supplier_detail_result.xlsx

필요 환경변수(.env): GIFTCO_SUPPLIER_COOKIE (giftco.co.kr 로그인 세션 쿠키)
실행: python giftco_supplier_crawler.py
"""

import os
import re
import time
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

load_dotenv()

# ============================================================
# 0. 설정 (여기만 바꾸면 됩니다)
# ============================================================
GIFTCO_SUPPLIER_COOKIE = os.environ.get("GIFTCO_SUPPLIER_COOKIE", "").strip()
if not GIFTCO_SUPPLIER_COOKIE:
    raise RuntimeError(
        ".env에 GIFTCO_SUPPLIER_COOKIE가 설정되지 않았습니다. "
        "giftco.co.kr 로그인 후 F12 > Network 탭에서 아무 요청이나 클릭 > "
        "Request Headers의 Cookie 값을 통째로 복사해 .env에 넣어주세요."
    )

# 실행할 단계 (모두 True면 상품목록부터 사업자정보, 조인까지 한 번에 실행)
RUN_STAGE1_PRODUCT_LIST = True
RUN_STAGE2_SUPPLIER_INFO = True
RUN_STAGE3_JOIN = True

TIMEOUT = 15
SLEEP_SEC = 0.5

HEADERS = {
    "Cookie": GIFTCO_SUPPLIER_COOKIE,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

# ----- 데이터 폴더 (crawler/02/03과 viewer/가 공유) -----
DATA_DIR = "../data"
os.makedirs(DATA_DIR, exist_ok=True)

# ----- 1단계 설정 -----
STAGE1_BASE_URL = "https://giftco.co.kr/mypage/page.php?code=partner_goods_admlist&page={}"
STAGE1_CHECKPOINT_PATH = f"{DATA_DIR}/partner_goods_checkpoint.xlsx"   # 중간 저장 (중단/재개용)
STAGE1_OUTPUT_PATH = f"{DATA_DIR}/partner_goods_full.xlsx"             # 1단계 최종 결과 = 2단계 입력
STAGE1_PAGE_START_DEFAULT = 1
STAGE1_PAGE_END = 5000               # 안전 상한선 (실제 마지막 페이지에서 자동으로 멈춤)
STAGE1_PAGE_END = 30                 # 테스트
STAGE1_CHECKPOINT_EVERY = 20         # 몇 페이지마다 체크포인트 저장할지

# ----- 2단계 설정 -----
STAGE2_EXCEL_IN = STAGE1_OUTPUT_PATH
STAGE2_EXCEL_OUT = f"{DATA_DIR}/supplier_detail_result.xlsx"
STAGE2_CRAWL_ORDER_PAGE = True   # 발주페이지(사업자번호 등)까지 크롤링할지 여부

STAGE2_WANT_FIELDS = [
    "전화번호", "휴대폰번호", "팩스", "이메일", "주소",
    "상품등록일", "상품최근수정일",
    "인쇄가능여부", "한박스당수량", "한박스당배송비", "이미지사용",
    "발주링크", "gs_id",
]
STAGE2_WANT_NORM = {
    "전화번호": "전화번호",
    "휴대폰번호": "휴대폰번호",
    "팩스": "팩스",
    "이메일": "이메일",
    "주소": "주소",
    "상품등록일": "상품등록일",
    "상품최근수정일": "상품최근수정일",
    "인쇄가능여부": "인쇄가능여부",
    "한박스당수량": "한박스당수량",
    "한박스당배송비": "한박스당배송비",
    "이미지사용": "이미지사용",
}
STAGE2_SUPPLIER_FIELDS = ["상호", "사업자번호", "대표자", "업태", "종목", "전화", "팩스", "이메일", "주소"]
STAGE2_SUPPLIER_NORM = {k: k for k in STAGE2_SUPPLIER_FIELDS}

# ----- 3단계 설정 -----
STAGE3_JOIN_OUTPUT_PATH = f"{DATA_DIR}/products_with_supplier_info.xlsx"   # 상품조회툴(supplier_product_viewer) 입력 파일

# 세션 + 재시도 (두 단계에서 공용으로 사용)
session = requests.Session()
session.headers.update(HEADERS)
retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))


def save_excel(df, path):
    """문자열을 URL로 자동변환하지 않도록 저장 (대량 링크 저장 시 엑셀 한도 경고 방지)."""
    with pd.ExcelWriter(
        path, engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}},
    ) as writer:
        df.to_excel(writer, index=False)


# ============================================================
# 1단계. 상품목록 + 이미지링크 + 상품링크 크롤링
# ============================================================
def _clean(s):
    return re.sub(r"\s+", " ", s).strip()


def _parse_product_list_page(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="sodr_list")
    if not table or not table.find("tbody"):
        return []

    trs = table.find("tbody").find_all("tr", recursive=False)
    records, i = [], 0
    while i < len(trs):
        if trs[i].find("input", {"name": "chk[]"}) and i + 1 < len(trs):
            top = trs[i].find_all("td", recursive=False)
            bot = trs[i + 1].find_all("td", recursive=False)
            if len(top) >= 12 and len(bot) >= 5:
                hid = top[0].find("input", {"type": "hidden"})
                gs_id = hid["value"] if hid else ""

                a = top[2].find("a")
                shop_url = a["href"].strip() if (a and a.has_attr("href")) else ""
                m = re.search(r"index_no=(\d+)", shop_url) if shop_url else None
                index_no = m.group(1) if m else ""
                if shop_url and not shop_url.startswith("http"):
                    shop_url = "https://giftco.co.kr" + (shop_url if shop_url.startswith("/") else "/" + shop_url)
                if not shop_url and index_no:
                    shop_url = f"https://giftco.co.kr/shop/view.php?index_no={index_no}"

                img = top[2].find("img")
                img_url = img["src"] if img else ""

                parts = list(top[1].stripped_strings)
                no = parts[0] if parts else ""
                expose = parts[1] if len(parts) > 1 else ""

                name_cell = top[4]
                badge = name_cell.find("span")
                ban = "Y" if (badge and "퍼가기" in badge.get_text()) else "N"
                if badge:
                    badge.extract()

                records.append({
                    "번호": no,
                    "노출": expose,
                    "상품코드": _clean(top[3].get_text()),
                    "업체코드": _clean(bot[0].get_text()),
                    "상품명": _clean(name_cell.get_text()),
                    "퍼가기금지": ban,
                    "업체명": _clean(bot[1].get_text()),
                    "카테고리": _clean(bot[2].get_text()),
                    "최초등록일": _clean(top[5].get_text()),
                    "최근수정일": _clean(bot[3].get_text()),
                    "진열": _clean(top[6].get_text()),
                    "과세": _clean(bot[4].get_text()),
                    "기본수량": _clean(top[7].get_text()),
                    "공급가": _clean(top[8].get_text()),
                    "판매가1": _clean(top[9].get_text()),
                    "판매가7": _clean(top[10].get_text()),
                    "마진율": _clean(top[11].get_text()),
                    "gs_id": gs_id,
                    "index_no": index_no,
                    "상품링크": shop_url,
                    "이미지URL": img_url,
                })
            i += 2
        else:
            i += 1
    return records


def crawl_product_list():
    if os.path.exists(STAGE1_CHECKPOINT_PATH):
        prev = pd.read_excel(STAGE1_CHECKPOINT_PATH)
        all_records = prev.to_dict("records")
        start_page = int(prev["page"].max()) + 1 if "page" in prev.columns and len(prev) else STAGE1_PAGE_START_DEFAULT
        print(f"[1단계][info] 체크포인트에서 {len(all_records)}건 불러옴 → {start_page}페이지부터 이어서 진행")
    else:
        all_records = []
        start_page = STAGE1_PAGE_START_DEFAULT

    for page in tqdm(range(start_page, STAGE1_PAGE_END), desc="1단계: 상품목록"):
        try:
            res = session.get(STAGE1_BASE_URL.format(page), timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"\n[1단계] {page}페이지 실패({e}) → 5초 후 재시도")
            time.sleep(5)
            try:
                res = session.get(STAGE1_BASE_URL.format(page), timeout=TIMEOUT)
            except requests.exceptions.RequestException:
                print(f"[1단계] {page}페이지 재시도 실패 → 중단")
                break

        res.encoding = res.apparent_encoding
        recs = _parse_product_list_page(res.text)
        for r in recs:
            r["page"] = page

        if not recs:
            if "sodr_list" not in res.text:
                print(f"\n⚠️ [1단계] {page}페이지: 로그인 페이지로 보임 → 세션 만료 가능. GIFTCO_SUPPLIER_COOKIE 갱신 필요")
            else:
                print(f"\n[1단계] {page}페이지: 마지막 페이지로 보임 → 정상 종료")
            break

        all_records.extend(recs)
        if page % STAGE1_CHECKPOINT_EVERY == 0:
            save_excel(pd.DataFrame(all_records), STAGE1_CHECKPOINT_PATH)
        time.sleep(SLEEP_SEC)

    df = pd.DataFrame(all_records).drop_duplicates(subset="gs_id", keep="first")
    save_excel(df, STAGE1_OUTPUT_PATH)
    print(f"[1단계][done] 전체 {len(df)}건 저장 완료 → {STAGE1_OUTPUT_PATH}")
    return df


# ============================================================
# 2단계. 상품링크 기반 공급사 · 사업자정보 크롤링
# ============================================================
def _norm(s):
    """공백/줄바꿈 모두 제거해서 비교용 키로."""
    return re.sub(r"\s+", "", s or "")


def _clean_text(node):
    """td 안의 텍스트만 깔끔하게. 버튼/공백/줄바꿈 정리."""
    txt = node.get_text(" ", strip=True)
    txt = re.sub(r"\s*(공급사)?발주하기\s*", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _cell_value(td):
    """공급처 td 값 추출. 보이는 텍스트 우선, 없으면 hidden input value."""
    txt = re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
    if txt:
        return txt
    inp = td.find("input")
    if inp and inp.get("value"):
        return inp["value"].strip()
    return ""


def _parse_supplier_table(html, base_url=""):
    """상세페이지에서 공급사 표(연락처)와 발주링크를 추출."""
    soup = BeautifulSoup(html, "html.parser")

    target_table = None
    for table in soup.find_all("table", class_=lambda c: c and "wfull" in c):
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        if "공급사" in ths:
            target_table = table
            break

    result = {f: "" for f in STAGE2_WANT_FIELDS}
    if target_table is None:
        return result, False  # 표 못 찾음(로그인 필요/구조 변경 가능)

    for tr in target_table.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue

        th_text = th.get_text(strip=True)

        key = STAGE2_WANT_NORM.get(_norm(th_text))
        if key:
            result[key] = _clean_text(td)

        if th_text == "공급사":
            a = td.find("a", href=True)
            if a:
                href = a["href"]
                result["발주링크"] = urljoin(base_url, href) if base_url else href
                m = re.search(r"gs_id=(\d+)", href)
                if m:
                    result["gs_id"] = m.group(1)

    return result, True


def _parse_order_page(html):
    """발주페이지에서 '공급처'(오른쪽 칸)의 사업자번호/대표자/업태/종목 등을 추출.
    각 행 구조: th(라벨) td(가맹점값) th(라벨) td(공급처값) → 두 번째 th/td 쌍이 공급처.
    """
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    container = soup.find("div", class_=lambda c: c and "tbl_frm03" in c)
    scope = container if container else soup
    table = scope.find("table", class_=lambda c: c and "wfull" in c)
    if table is None:
        return data

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) >= 4 and cells[2].name == "th" and cells[3].name == "td":
            label = _norm(cells[2].get_text(strip=True))
            key = STAGE2_SUPPLIER_NORM.get(label)
            if key:
                data[f"공급처_{key}"] = _cell_value(cells[3])
    return data


def _build_targets(excel_path):
    df = pd.read_excel(excel_path, dtype=str)
    df["번호_int"] = df["번호"].astype(int)

    counts = df.groupby("업체명").size().rename("상품수")

    idx = df.groupby("업체명")["번호_int"].idxmax()
    latest = df.loc[idx].sort_values("번호_int", ascending=False)
    targets = latest[["업체명", "업체코드", "번호", "상품링크"]].reset_index(drop=True)
    targets = targets.merge(counts, on="업체명", how="left")

    print(f"[2단계][info] 대상 업체 수: {len(targets)}")
    return targets


def crawl_supplier_info():
    targets = _build_targets(STAGE2_EXCEL_IN)

    rows = []
    for i, r in tqdm(targets.iterrows(), total=len(targets), desc="2단계: 공급사정보"):
        url = r["상품링크"]
        rec = {
            "업체명": r["업체명"],
            "업체코드": r["업체코드"],
            "상품수": r["상품수"],
            "상품링크": url,
        }

        # --- 상세페이지 ---
        try:
            resp = session.get(url, timeout=TIMEOUT)
            resp.encoding = resp.apparent_encoding or resp.encoding
            data, found = _parse_supplier_table(resp.text, base_url=url)
            rec.update(data)
            rec["상태"] = "OK" if found else "표없음(로그인필요?)"
        except Exception as e:
            for f in STAGE2_WANT_FIELDS:
                rec[f] = ""
            rec["상태"] = f"에러: {e}"

        # --- 발주페이지 (같은 session으로 쿠키 유지) ---
        if STAGE2_CRAWL_ORDER_PAGE and rec.get("발주링크"):
            try:
                time.sleep(SLEEP_SEC)
                r2 = session.get(rec["발주링크"], timeout=TIMEOUT)
                r2.encoding = r2.apparent_encoding or r2.encoding
                rec.update(_parse_order_page(r2.text))
                rec["발주_상태"] = "OK"
            except Exception as e:
                rec["발주_상태"] = f"에러: {e}"

        rows.append(rec)
        # if len(rows) % 50 == 0:
        #     print(f"[2단계][{i+1}/{len(targets)}] {rec['업체명']:<20} | "
        #           f"{rec.get('휴대폰번호', ''):<15} | {rec['상태']}")
        time.sleep(SLEEP_SEC)

    supplier_cols = [f"공급처_{f}" for f in STAGE2_SUPPLIER_FIELDS]
    fixed = (["업체명", "업체코드", "상품수"] + STAGE2_WANT_FIELDS
             + supplier_cols + ["상품링크", "상태", "발주_상태"])

    df_out = pd.DataFrame(rows)
    ordered = [c for c in fixed if c in df_out.columns]
    extra = [c for c in df_out.columns if c not in ordered]
    df_out = df_out[ordered + extra]

    df_out.to_excel(STAGE2_EXCEL_OUT, index=False)
    print(f"[2단계][done] 저장 완료 → {STAGE2_EXCEL_OUT}  ({len(df_out)}개 업체)")
    return df_out


# ============================================================
# 3단계. 상품목록 + 공급사정보 조인 (상품조회툴 입력 파일 생성)
# ============================================================
def build_full_join():
    """1단계 결과(상품 전체)에 2단계 결과(업체별 공급사정보)를 업체명 기준으로 left join."""
    goods = pd.read_excel(STAGE1_OUTPUT_PATH, dtype=str)     # 상품 전체 (1단계 출력)
    supplier = pd.read_excel(STAGE2_EXCEL_OUT, dtype=str)    # 업체별 1행 (2단계 출력)

    key = "업체명"
    supplier_extra_cols = [key] + [c for c in supplier.columns if c not in goods.columns]
    joined = goods.merge(supplier[supplier_extra_cols], on=key, how="left", indicator=True)

    matched = int((joined["_merge"] == "both").sum())
    joined = joined.drop(columns="_merge")

    joined.to_excel(STAGE3_JOIN_OUTPUT_PATH, index=False)
    print(f"[3단계][done] 조인 완료 → {STAGE3_JOIN_OUTPUT_PATH}  ({len(joined)}행, 공급사 정보 매칭 {matched}건)")
    return joined


# ============================================================
# 실행
# ============================================================
def run_all():
    if RUN_STAGE1_PRODUCT_LIST:
        crawl_product_list()
    else:
        print("[1단계] RUN_STAGE1_PRODUCT_LIST=False → 건너뜀 (기존 partner_goods_full.xlsx 사용)")

    if RUN_STAGE2_SUPPLIER_INFO:
        crawl_supplier_info()
    else:
        print("[2단계] RUN_STAGE2_SUPPLIER_INFO=False → 건너뜀")

    if RUN_STAGE3_JOIN:
        build_full_join()
    else:
        print("[3단계] RUN_STAGE3_JOIN=False → 건너뜀")


if __name__ == "__main__":
    run_all()
