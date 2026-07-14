# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 납품사례 크롤링 - 운영 실행용 진입점

실제 로직은 crawler/ 패키지에 있습니다.
로직 검증/디버그는 notebooks/01_crawl_supply_cases_test.ipynb(테스트 노트북)를 사용하고,
실제 운영 실행은 이 스크립트로 합니다.

콘솔에는 페이지 단위 진행상황 + 경고/오류만 보이고,
상품 단위 상세 로그는 output/crawl.log 파일에 남습니다.
데이터 미리보기가 필요하면 결과 csv/xlsx 파일을 직접 열어서 확인하세요.

실행 방법 (sarang87/ 폴더 기준):
    python scripts/01_crawl_supply_cases.py
"""
import logging
import sys
from pathlib import Path

# crawler 패키지(sarang87/crawler)를 어디서 실행하든 import할 수 있도록 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from crawler import config  # noqa: E402
from crawler.collector import collect_list_only, run_detail_from_list  # noqa: E402
from crawler.excel_export import save_excel_from_checkpoint  # noqa: E402
from crawler.logging_setup import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)


def log_checkpoint_status():
    """이어하기 상태 확인 (테스트 노트북의 '상태 확인' 셀과 동일, 건수만 로그로 남김)."""
    if Path(config.CHECKPOINT_CSV).exists():
        ck = pd.read_csv(config.CHECKPOINT_CSV, dtype=str)
        logger.info(f"체크포인트 저장 건수: {len(ck)}")
    else:
        logger.info("체크포인트 파일이 없습니다.")

    if Path(config.ERROR_LOG_CSV).exists():
        err = pd.read_csv(config.ERROR_LOG_CSV, dtype=str)
        logger.info(f"오류 로그 건수: {len(err)}")
    else:
        logger.info("오류 로그 파일이 없습니다.")


def main():
    setup_logging()

    logger.info(f"현재 폴더: {config.BASE_DIR}")
    logger.info(f"복사 저장 폴더: {config.SAVE_DIR}")

    # 1단계: 목록 정보 + 상세링크만 먼저 수집
    list_df = collect_list_only()
    logger.info(f"목록 수집 건수: {len(list_df)}")

    # 2단계: 저장된 상세링크를 하나씩 열어서 상세정보 수집
    result_df = run_detail_from_list()
    logger.info(f"최종 체크포인트 건수: {len(result_df)}")

    # 최종 엑셀 저장 (2단계 안에서도 저장되지만, 마지막에 한 번 더 확정 저장)
    save_excel_from_checkpoint(config.OUTPUT_XLSX)

    log_checkpoint_status()


if __name__ == "__main__":
    main()
