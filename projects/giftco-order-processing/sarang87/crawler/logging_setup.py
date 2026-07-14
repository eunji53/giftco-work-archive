# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 로깅 설정

콘솔에는 페이지 단위 진행상황 + 경고/오류만 보이고,
output/crawl.log 파일에는 상품 단위 상세 로그까지 전부 남습니다.
"""
import logging

from . import config


def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG):
    log_path = config.SAVE_DIR / "crawl.log"
    config.SAVE_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("crawler")
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info(f"로그 파일: {log_path}")

    return log_path
