# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 크롤링 - 페이지 요청 (requests + Selenium)

URL을 넣으면 BeautifulSoup을 돌려주는 함수들만 모아둡니다.
HTML을 어떻게 해석할지(파싱)는 list_page.py / detail_page.py에서 담당합니다.
"""
import logging
import random
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from . import config

logger = logging.getLogger(__name__)


def sleep_random():
    time.sleep(random.uniform(config.REQUEST_SLEEP_MIN, config.REQUEST_SLEEP_MAX))


def fetch_soup(url: str, timeout: int = 20, referer: str = None) -> BeautifulSoup:
    """
    URL을 요청해서 BeautifulSoup 객체를 반환합니다.

    referer가 있으면 목록페이지에서 상세페이지로 이동하는 것처럼
    Referer 헤더를 함께 전달합니다.

    400/403/429가 나오면 바로 빠르게 재시도하지 않고
    목록페이지를 한 번 열어 세션 흐름을 맞춘 뒤 대기 후 재시도합니다.
    """
    last_error = None

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            sleep_random()

            headers = config.HEADERS.copy()
            if referer:
                headers["Referer"] = referer

            resp = config.session.get(url, headers=headers, timeout=timeout)

            if resp.status_code in [400, 403, 429]:
                last_error = requests.HTTPError(
                    f"{resp.status_code} Client Error: {resp.reason} for url: {url}"
                )

                logger.debug(f"[요청 거절 {attempt}/{config.MAX_RETRIES}] {url} / status={resp.status_code}")

                # 목록페이지를 먼저 열어 Referer / 세션 흐름을 맞춘 뒤 재시도
                if referer and config.WARMUP_REFERER_BEFORE_DETAIL:
                    try:
                        time.sleep(2)
                        config.session.get(referer, headers=config.HEADERS, timeout=timeout)
                    except Exception:
                        pass

                time.sleep(config.BLOCK_STATUS_SLEEP * attempt)
                continue

            resp.raise_for_status()

            if resp.apparent_encoding:
                resp.encoding = resp.apparent_encoding
            elif not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = "euc-kr"

            return BeautifulSoup(resp.text, "html.parser")

        except Exception as e:
            last_error = e
            logger.debug(f"[요청 재시도 {attempt}/{config.MAX_RETRIES}] {url} / {e}")
            time.sleep(config.RETRY_SLEEP * attempt)

    raise last_error


# =========================
# Selenium 상세페이지 수집 함수
# =========================

driver = None
selenium_detail_count = 0


def init_selenium_driver():
    """
    일반 Chrome Selenium 드라이버를 시작합니다.
    """
    global driver

    if driver is not None:
        return driver

    options = Options()

    if config.FAST_SELENIUM_MODE:
        # 전체 리소스 로딩 완료를 기다리지 않고 DOM이 준비되면 진행
        options.page_load_strategy = "eager"

        # 이미지 로딩 차단: 가격/분류/수량은 HTML 텍스트 기반이라 이미지가 필요 없음
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

    if config.SELENIUM_HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--window-size=1400,1000")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.set_page_load_timeout(config.SELENIUM_PAGELOAD_TIMEOUT)

    return driver


def restart_selenium_driver():
    """
    장시간 실행 안정성을 위해 Selenium 브라우저를 재시작합니다.
    """
    global driver

    try:
        if driver is not None:
            driver.quit()
    except Exception:
        pass

    driver = None
    return init_selenium_driver()


def close_selenium_driver():
    """
    크롤링 종료 후 브라우저를 닫습니다.
    """
    global driver

    try:
        if driver is not None:
            driver.quit()
    except Exception:
        pass

    driver = None


def wait_detail_html_ready(drv, max_wait: float = None) -> str:
    """
    상세페이지 HTML에서 필요한 핵심 문구가 보이면 바로 반환합니다.
    기존처럼 무조건 몇 초씩 기다리지 않기 위한 빠른 대기 함수입니다.
    """
    max_wait = max_wait or config.SELENIUM_WAIT_SECONDS
    end_time = time.time() + max_wait

    last_html = ""

    while time.time() < end_time:
        try:
            html_source = drv.page_source or ""
            last_html = html_source

            if any(marker in html_source for marker in config.DETAIL_READY_MARKERS):
                return html_source

        except Exception:
            pass

        time.sleep(0.2)

    return last_html or (drv.page_source or "")


def fetch_soup_selenium(url: str, referer: str = None) -> BeautifulSoup:
    """
    Selenium으로 상세페이지를 열고 BeautifulSoup 객체로 반환합니다.

    2단계 상세 수집 전용입니다.
    목록페이지를 먼저 열고 상세페이지로 이동하도록 처리해서
    requests에서 발생하던 400 Bad Request를 줄입니다.
    """
    global selenium_detail_count

    drv = init_selenium_driver()
    selenium_detail_count += 1

    if config.SELENIUM_RESTART_EVERY and selenium_detail_count % config.SELENIUM_RESTART_EVERY == 0:
        logger.info(f"[Selenium 재시작] 상세페이지 {selenium_detail_count}건 처리")
        drv = restart_selenium_driver()

    time.sleep(random.uniform(config.SELENIUM_SLEEP_MIN, config.SELENIUM_SLEEP_MAX))

    try:
        if referer:
            drv.get(referer)
            time.sleep(random.uniform(0.8, 1.5))

        drv.get(url)
        html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        if "Bad Request" in html_source or "400" in drv.title:
            logger.debug(f"[Selenium 400 감지] 재시도: {url}")
            if referer:
                drv.get(referer)
                time.sleep(random.uniform(1.0, 2.0))
            drv.get(url)
            html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        return BeautifulSoup(html_source, "html.parser")

    except TimeoutException:
        logger.debug(f"[Selenium Timeout] {url}")
        try:
            drv.execute_script("window.stop();")
        except Exception:
            pass

        html_source = drv.page_source or ""
        if html_source:
            return BeautifulSoup(html_source, "html.parser")

        raise

    except WebDriverException as e:
        logger.debug(f"[Selenium 오류] 브라우저 재시작 후 1회 재시도: {e}")
        drv = restart_selenium_driver()

        if referer:
            drv.get(referer)
            time.sleep(random.uniform(1.0, 2.0))

        drv.get(url)
        html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        return BeautifulSoup(html_source or "", "html.parser")


def fetch_soup_selenium_direct(url: str) -> BeautifulSoup:
    """
    LIST_ONLY_CSV의 상세URL(I열)을 Selenium으로 직접 열고 BeautifulSoup으로 반환합니다.

    납품사례 목록페이지를 먼저 열지 않습니다.
    """
    global selenium_detail_count

    drv = init_selenium_driver()
    selenium_detail_count += 1

    if config.SELENIUM_RESTART_EVERY and selenium_detail_count % config.SELENIUM_RESTART_EVERY == 0:
        logger.info(f"[Selenium 재시작] 상세페이지 {selenium_detail_count}건 처리")
        drv = restart_selenium_driver()

    time.sleep(random.uniform(config.SELENIUM_SLEEP_MIN, config.SELENIUM_SLEEP_MAX))

    try:
        drv.get(url)
        html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        # Selenium에서도 400이 뜨면 1회만 다시 직접 접속
        if "Bad Request" in html_source or "400" in drv.title:
            logger.debug(f"[Selenium 400 감지] 직접 URL 재시도: {url}")
            time.sleep(random.uniform(3.0, 6.0))
            drv.get(url)
            html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        return BeautifulSoup(html_source, "html.parser")

    except TimeoutException:
        logger.debug(f"[Selenium Timeout] {url}")
        try:
            drv.execute_script("window.stop();")
        except Exception:
            pass

        html_source = drv.page_source or ""
        if html_source:
            return BeautifulSoup(html_source, "html.parser")

        raise

    except WebDriverException as e:
        logger.debug(f"[Selenium 오류] 브라우저 재시작 후 직접 URL 1회 재시도: {e}")
        drv = restart_selenium_driver()
        drv.get(url)
        html_source = wait_detail_html_ready(drv, config.SELENIUM_WAIT_SECONDS)

        return BeautifulSoup(html_source or "", "html.parser")
