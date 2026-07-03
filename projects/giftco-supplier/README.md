# giftco-supplier 실행 가이드

giftco.co.kr 입점업체 상품목록 + 공급사 연락처/사업자정보를 크롤링하고, 분석하고, 조회하는 프로젝트입니다.

## 폴더 구조

```
giftco-supplier/
├─ crawler/
│  ├─ 01_crawl_product_list.ipynb    # 1단계: 상품목록 크롤링
│  ├─ 02_crawl_supplier_info.ipynb   # 2단계: 공급사/사업자정보 크롤링 + 조인
│  ├─ giftco_supplier_crawler.py     # 01+02를 한 번에 실행하는 스크립트
│  └─ 03_analyze_data.ipynb          # 크롤링 결과 분석 (업체분석 + 상품분석)
│
├─ data/                             # crawler 출력 + viewer 입력이 모이는 공용 폴더
│
└─ viewer/
   ├─ supplier_product_viewer_v1.py
   ├─ supplier_product_viewer_v2.py
   ├─ supplier_product_viewer_v3.py
   └─ supplier_product_viewer_v4.py
```

**모든 경로는 `../data/` 기준입니다.** `crawler/`의 노트북·스크립트는 `../data/`(즉 `giftco-supplier/data/`)에 결과를 저장하고, `viewer/`의 4개 파일도 같은 `../data/`를 읽습니다. 파일을 직접 옮길 필요가 없습니다 — crawler 실행 후 바로 viewer를 실행하면 됩니다.

## 0. 환경 준비

```bash
pip install pandas requests beautifulsoup4 python-dotenv tqdm xlsxwriter openpyxl matplotlib koreanize-matplotlib
```

저장소 루트의 `.env.example`을 복사해 `.env`를 만들고, `GIFTCO_SUPPLIER_COOKIE` 값을 채웁니다.

```
# .env
GIFTCO_SUPPLIER_COOKIE=여기에_실제_쿠키값
```

쿠키 값 얻는 방법: giftco.co.kr에 로그인 → F12(개발자도구) → **Network** 탭 → 아무 요청이나 클릭 → **Request Headers**의 `Cookie:` 값을 통째로 복사.

값이 비어 있으면 아래 노트북/스크립트 모두 실행 즉시 에러 메시지를 띄우고 멈춥니다.

## 1. 실행 순서

**옵션 A — 노트북으로 단계별 실행 (처음 실행할 때 추천)**

1. `crawler/01_crawl_product_list.ipynb` 실행 → `../data/partner_goods_full.xlsx` 생성 확인
2. `crawler/02_crawl_supplier_info.ipynb` 실행 → `../data/supplier_detail_result.xlsx`, `../data/products_with_supplier_info.xlsx` 생성 확인
3. `crawler/03_analyze_data.ipynb` 실행 → 표/그래프로 분석 결과 확인

**옵션 B — 스크립트로 한 번에 실행**

```bash
cd projects/giftco-supplier/crawler
python giftco_supplier_crawler.py
```

`01`, `02` 두 단계(상품목록 → 공급사/사업자정보 → 조인)를 순서대로 자동 실행합니다. 파일 상단의 플래그로 단계를 개별 제어할 수 있습니다.

```python
RUN_STAGE1_PRODUCT_LIST = True   # 상품목록 크롤링
RUN_STAGE2_SUPPLIER_INFO = True  # 공급사/사업자정보 크롤링
RUN_STAGE3_JOIN = True           # 조인(상품조회툴 입력 파일 생성)
```

예: 1단계 결과가 이미 있고 2단계부터 다시 하고 싶다면 `RUN_STAGE1_PRODUCT_LIST = False`로 바꾸고 실행.

## 2. 파일별 입력/출력

모든 경로는 `../data/`(=`giftco-supplier/data/`) 기준입니다.

| 파일 | 입력 | 출력 |
|---|---|---|
| `01_crawl_product_list.ipynb` | 없음 (giftco.co.kr 직접 크롤링) | `../data/partner_goods_full.xlsx`, `../data/partner_goods_checkpoint.xlsx`(중간 저장) |
| `02_crawl_supplier_info.ipynb` | `../data/partner_goods_full.xlsx` | `../data/supplier_detail_result.xlsx`, `../data/products_with_supplier_info.xlsx` |
| `giftco_supplier_crawler.py` | 없음 (01+02를 순서대로 실행) | 위 3개 파일 전부 |
| `03_analyze_data.ipynb` | `../data/supplier_detail_result.xlsx`, `../data/partner_goods_full.xlsx`, (있으면) `../data/products_with_supplier_info.xlsx` | 없음 (화면 출력) |
| `viewer/supplier_product_viewer_v4.py` | `../data/products_with_supplier_info.xlsx`, `../data/supplier_detail_result.xlsx` | 실행 중 GUI에서 조회 |

모든 크롤링/조인 결과 엑셀은 `.gitignore`(`*.xlsx`)에 의해 git에는 올라가지 않습니다. 실제 업체 연락처·사업자번호가 담기므로 커밋하지 마세요.

## 3. 중단 후 재실행

- `01_crawl_product_list.ipynb`: `../data/partner_goods_checkpoint.xlsx`가 있으면 마지막으로 수집된 페이지 다음부터 자동으로 이어받습니다. 삭제 후 재실행하면 처음부터 다시 수집합니다.
- 페이지 범위(`STAGE1_PAGE_END`)나 발주페이지 크롤링 여부(`CRAWL_ORDER_PAGE`)는 각 노트북 상단 설정 셀에서 바꿀 수 있습니다.
- `data/` 폴더는 코드에서 `os.makedirs(..., exist_ok=True)`로 자동 생성하므로, 처음 실행할 때 폴더가 없어도 됩니다.

## 4. 흔한 오류

| 증상 | 원인 | 조치 |
|---|---|---|
| `RuntimeError: .env에 GIFTCO_SUPPLIER_COOKIE가 설정되지 않았습니다` | `.env` 파일이 없거나 값이 비어있음 | 위 "0. 환경 준비" 참고해 `.env` 채우기 |
| `⚠️ N페이지: 로그인 페이지로 보임 → 세션 만료 가능` | 쿠키 세션 만료 | giftco.co.kr 재로그인 후 `.env`의 쿠키 값 갱신 |
| `표없음(로그인필요?)` 상태 다수 | 쿠키가 유효하지 않거나 권한 없는 계정 | 쿠키 값 재확인 |

## 5. viewer 실행 (상품조회툴)

```bash
cd projects/giftco-supplier/viewer
python supplier_product_viewer_v4.py
```

`../data/products_with_supplier_info.xlsx`가 있어야 자동으로 열리고, `supplier_detail_result.xlsx`는 실행 후 GUI에서 "공급사 파일 선택/재로드" 버튼으로 직접 선택합니다 (기본으로 `../data/`를 보되, 다른 위치를 선택할 수도 있습니다).

### 버전 히스토리 (2026-07-03 정리)

| 단계 | 대표 파일 | 실제로 달라진 것 (diff 근거) |
|---|---|---|
| 1단계 | `supplier_product_viewer_v1.py` | 최초 버전. 조인 파일(`products_with_supplier_info.xlsx`) 하나만 있으면 동작 |
| 2단계 | `supplier_product_viewer_v2.py` | v1 대비 **가장 큰 변화**: 공급사 파일(`supplier_detail_result.xlsx`)을 별도로 받는 2파일 체계로 전환. 이후 레이아웃 고정, 카테고리/대분류 표시, 미분류 제외, 상품 검색/필터, 긴 텍스트 줄바꿈 등 수정 |
| 3단계 | `supplier_product_viewer_v3.py` | 신규 기능 : 설정 저장/불러오기(`load_config`/`save_config`), 공급사별 연락 상태 관리(`update_contact_status` 등), PyInstaller exe 빌드 지원 |
| 4단계 (최신) | `supplier_product_viewer_v4.py` | 신규 기능: 담당자(매니저) 배정(`update_manager`), 상품 등록상태 관리(`update_product_status`), 창 분할 위치 저장/복원(`_apply_sash`) |

