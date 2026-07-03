# data/

`crawler/`가 생성하는 결과 엑셀과 `viewer/`가 읽어들이는 입력 엑셀이 모두 여기에 모입니다. 이렇게 하면 `viewer/`가 `crawler/`의 내부 구조를 몰라도 되고, 데이터 위치가 한 곳으로 통일됩니다.

- `partner_goods_full.xlsx` — 01 노트북/`giftco_supplier_crawler.py` 1단계 출력 (상품 전체)
- `partner_goods_checkpoint.xlsx` — 1단계 중간 저장 (중단/재개용)
- `supplier_detail_result.xlsx` — 02 노트북/`giftco_supplier_crawler.py` 2단계 출력 (업체별 공급사 정보)
- `products_with_supplier_info.xlsx` — 02 노트북/`giftco_supplier_crawler.py` 3단계(조인) 출력, `viewer/`의 필수 입력 파일
- `supplier_product_viewer_config.json` — `viewer/`(v3, v4) 실행 시 마지막으로 선택한 공급사 파일 경로를 기억해두는 설정 파일. 로컬 PC 절대경로가 담기므로 git에 올리지 않음

실제 업체 연락처·사업자번호가 담기므로 이 폴더 안의 `.xlsx`는 저장소 루트 `.gitignore`(`*.xlsx`)에 의해 git에 올라가지 않습니다. `supplier_product_viewer_config.json`도 별도 규칙으로 제외됩니다.
