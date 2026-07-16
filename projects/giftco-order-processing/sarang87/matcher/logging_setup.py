# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 - 로깅 설정

콘솔과 output/match.log 파일에 동일하게 기록합니다.
"""
import logging

from . import config


def setup_logging(console_level=logging.INFO, file_level=logging.INFO):
    log_path = config.OUTPUT_DIR / "match.log"
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("match_buyer_names")
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
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

    return root_logger


logger = setup_logging()


def log(*args):
    """print(a, b, c)와 동일하게 여러 인자를 공백으로 이어붙여 logger.info로 기록합니다."""
    logger.info(" ".join(str(a) for a in args))
