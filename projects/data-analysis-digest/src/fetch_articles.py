"""데이터 분석 관련 사이트 최신/인기 글 다이제스트 생성 스크립트.

Analytics Vidhya, Machine Learning Mastery, KDnuggets의 RSS 피드에서 최근 글을,
Hacker News(키워드 검색 + 포인트순)와 Reddit(주간 인기글)에서 인기 글을 가져와
본문 전체를 추출한 뒤, 무료 추출 요약(LexRank)으로 핵심만 정리한다.
영문 요약은 articles_digest_YYYY-MM-DD.md에, 한글 번역은 articles_digest_YYYY-MM-DD_korean.md에 각각 저장한다.
(Towards Data Science는 봇 차단/멤버십 페이월 문제로 제외, Data Elixir는 RSS 봇 차단,
Kaggle은 RSS 미제공으로 제외)
"""

import argparse
import calendar
import datetime
import re
import sys
import time
from pathlib import Path

import feedparser
import requests
import trafilatura
from deep_translator import GoogleTranslator
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FEEDS = [
    {"name": "Analytics Vidhya", "url": "https://www.analyticsvidhya.com/feed/"},
    {"name": "Machine Learning Mastery", "url": "https://machinelearningmastery.com/feed/"},
    {"name": "KDnuggets", "url": "https://www.kdnuggets.com/feed"},
]

HN_KEYWORDS = ["machine learning", "LLM", "data analysis", "deep learning", "AI agent"]
REDDIT_SUBS = ["MachineLearning", "datascience"]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
USER_AGENT = "Mozilla/5.0 (compatible; data-analysis-digest/1.0)"
MAX_TRANSLATE_CHUNK = 4500


def split_long_line(line: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?]) +", line)
    chunks = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > MAX_TRANSLATE_CHUNK:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def translate_long_text(text: str) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(line) > MAX_TRANSLATE_CHUNK:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_line(line))
            continue
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > MAX_TRANSLATE_CHUNK:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    translated_chunks = []
    for chunk in chunks:
        try:
            translated_chunks.append(GoogleTranslator(source="en", target="ko").translate(chunk))
        except Exception as exc:
            translated_chunks.append(f"(번역 실패: {exc})")
        time.sleep(0.5)
    return "\n\n".join(translated_chunks)


BOILERPLATE_RE = re.compile(r"\s*The post .+? appeared first on .+?\.\s*$", re.DOTALL)


def strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text or "").strip()
    cleaned = BOILERPLATE_RE.sub("", cleaned).strip()
    return cleaned


def fetch_full_text(url: str) -> str | None:
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return None
    return trafilatura.extract(response.text)


CODE_LINE_NUMBERS_RE = re.compile(r"^(\d+\s*){2,}$")


def clean_extracted_text(text: str) -> str:
    """표/코드/목록 기호처럼 요약을 망치는 비-본문 줄을 제거한다.

    trafilatura가 기사 본문과 함께 표(pipe table), 코드 블록의 줄번호,
    "A." 같은 목록 기호까지 통째로 뽑아오는 경우가 있는데, 이런 조각이
    LexRank 요약에서 반복 등장하면 (특히 짧고 동일한 줄일수록 서로
    유사도가 높아 중심성이 커져) 진짜 문장 대신 요약으로 뽑히는 문제가 있다.
    """
    if not text:
        return text
    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        if stripped.count("|") >= 2:
            continue
        if CODE_LINE_NUMBERS_RE.match(stripped):
            continue
        if len(stripped.split()) < 3:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def summarize_text(text: str, sentence_count: int) -> str:
    if not text:
        return ""
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        candidates = LexRankSummarizer()(parser.document, sentence_count * 4)
        good = [s for s in candidates if len(str(s).split()) >= 4]
        chosen = good[:sentence_count] if good else list(candidates)[:sentence_count]
        result = "\n\n".join(str(s) for s in chosen).strip()
        if result:
            return result
    except Exception:
        pass
    sentences = re.split(r"(?<=[.!?]) +", text)
    sentences = [s for s in sentences if len(s.split()) >= 4] or sentences
    return "\n\n".join(sentences[:sentence_count]).strip()


def fetch_latest_entries(feed_url: str, count: int) -> list[dict]:
    """발행 시각과 무관하게, 사이트별 최근 글을 항상 count개 가져온다."""
    parsed = feedparser.parse(feed_url)
    entries = []
    for entry in parsed.entries:
        if not getattr(entry, "published_parsed", None):
            continue
        published = datetime.datetime.fromtimestamp(
            calendar.timegm(entry.published_parsed), tz=datetime.timezone.utc
        )
        entries.append(
            {
                "title": entry.get("title", "제목 없음"),
                "link": entry.get("link", ""),
                "author": entry.get("author", ""),
                "published": published,
                "rss_summary": strip_html(entry.get("summary", "")),
            }
        )
    entries.sort(key=lambda e: e["published"], reverse=True)
    return entries[:count]


def fetch_hn_popular(keywords: list[str], days: int, count: int) -> list[dict]:
    """Hacker News(Algolia 검색 API)에서 키워드 관련 글을 모아 포인트(추천수) 높은 순으로 count개 반환."""
    since = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp())
    seen: dict[str, dict] = {}
    for keyword in keywords:
        try:
            response = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": keyword,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{since},points>=15",
                    "hitsPerPage": 50,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Hacker News '{keyword}' 검색에 실패했습니다: {exc}", file=sys.stderr)
            continue
        for hit in response.json().get("hits", []):
            seen[hit["objectID"]] = hit

    ranked = sorted(seen.values(), key=lambda h: h.get("points", 0), reverse=True)
    entries = []
    for hit in ranked[:count]:
        published = None
        if hit.get("created_at"):
            published = datetime.datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
        entries.append(
            {
                "title": hit.get("title") or "제목 없음",
                "link": hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                "author": hit.get("author", ""),
                "published": published,
                "rss_summary": strip_html(hit.get("story_text") or ""),
                "points": hit.get("points"),
            }
        )
    return entries


def fetch_reddit_popular(subreddit: str, count: int) -> list[dict]:
    """r/{subreddit}의 이번 주 인기글(업보트 기준) 상위 count개 반환."""
    url = f"https://www.reddit.com/r/{subreddit}/top.rss?t=week&limit={count}"
    response = None
    for attempt in range(2):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException as exc:
            print(f"r/{subreddit} 인기글을 가져오는 데 실패했습니다: {exc}", file=sys.stderr)
            return []
        if response.status_code == 429 and attempt == 0:
            time.sleep(15)
            continue
        break

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"r/{subreddit} 인기글을 가져오는 데 실패했습니다: {exc}", file=sys.stderr)
        return []

    parsed = feedparser.parse(response.content)
    entries = []
    for entry in parsed.entries[:count]:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime.datetime.fromtimestamp(
                calendar.timegm(entry.published_parsed), tz=datetime.timezone.utc
            )
        entries.append(
            {
                "title": entry.get("title", "제목 없음"),
                "link": entry.get("link", ""),
                "author": (entry.get("author") or "").replace("/u/", ""),
                "published": published,
                "rss_summary": strip_html(entry.get("summary", "")),
                "points": None,
            }
        )
    return entries


def build_digest(
    all_entries: dict[str, list[dict]], date_label: str, sentence_count: int, translate: bool
) -> tuple[str, str]:
    """(영문 요약 마크다운, 한글 번역 마크다운) 튜플을 반환."""
    en_lines = [f"# 데이터 분석 아티클 다이제스트 - {date_label}", ""]
    ko_lines = [f"# 데이터 분석 아티클 다이제스트 (한글 번역) - {date_label}", ""]

    for site_name, entries in all_entries.items():
        en_lines.append(f"## {site_name}")
        en_lines.append("")
        ko_lines.append(f"## {site_name}")
        ko_lines.append("")
        if not entries:
            en_lines.extend(["최근 기간 내 새 글 없음.", ""])
            ko_lines.extend(["최근 기간 내 새 글 없음.", ""])
            continue

        for rank, entry in enumerate(entries, start=1):
            print(f"  [{site_name}] {rank}/{len(entries)}: {entry['title'][:60]}")

            full_text = fetch_full_text(entry["link"])
            source_text = full_text.strip() if full_text else entry["rss_summary"]
            source_text = clean_extracted_text(source_text)
            summary = summarize_text(source_text, sentence_count) if source_text else ""
            if not summary:
                summary = entry["rss_summary"] or "(요약할 내용 없음)"

            heading = f"### {rank}. [{entry['title']}]({entry['link']})"
            if entry["published"]:
                meta = f"- 발행: {entry['published'].strftime('%Y-%m-%d %H:%M UTC')}"
            else:
                meta = "- 발행 시각 정보 없음"
            if entry["author"]:
                meta += f" / 작성자: {entry['author']}"
            if entry.get("points") is not None:
                meta += f" / 포인트: {entry['points']}"
            if not full_text:
                meta += "\n- _(본문 전체 추출 실패, RSS 요약 기반 요약)_"

            en_lines.extend([heading, meta, "", summary, ""])

            if translate:
                translated_summary = translate_long_text(summary)
                ko_lines.extend([heading, meta, "", translated_summary, ""])

            time.sleep(0.5)

    footer = (
        "참고: Towards Data Science는 기사 페이지 접속이 Cloudflare 봇 차단에 걸리고 "
        "일부 글은 Medium 멤버십 페이월이 있어 제외했습니다. "
        "Data Elixir는 RSS 요청이 봇 차단(403)되어 제외했습니다 "
        "(https://dataelixir.com 에서 직접 구독/열람 가능). "
        "Kaggle Discussions/Notebooks는 RSS를 제공하지 않아 제외했습니다."
    )
    en_lines.extend(["---", footer])
    ko_lines.extend(["---", footer])

    return "\n".join(en_lines), "\n".join(ko_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="데이터 분석 아티클 다이제스트 생성")
    parser.add_argument("--count", type=int, default=7, help="사이트당 가져올 최근 글 개수 (기본 7, 발행 시각과 무관하게 항상 이 개수만큼 보장)")
    parser.add_argument("--popular-count", type=int, default=5, help="인기글 소스(Hacker News/Reddit)별로 가져올 개수 (기본 5)")
    parser.add_argument("--sentences", type=int, default=6, help="글당 요약 문장 수 (기본 6)")
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="한글 번역 파일(_korean.md)을 생성하지 않음",
    )
    parser.add_argument(
        "--no-popular",
        action="store_true",
        help="인기글 섹션(Hacker News/Reddit)을 생성하지 않음",
    )
    args = parser.parse_args()

    date_label = datetime.date.today().isoformat()

    all_entries = {}
    for feed in FEEDS:
        try:
            all_entries[feed["name"]] = fetch_latest_entries(feed["url"], args.count)
        except Exception as exc:
            print(f"{feed['name']} 피드를 가져오는 데 실패했습니다: {exc}", file=sys.stderr)
            all_entries[feed["name"]] = []

    if not args.no_popular:
        all_entries["Hacker News (이주의 인기글)"] = fetch_hn_popular(HN_KEYWORDS, days=7, count=args.popular_count)
        for sub in REDDIT_SUBS:
            all_entries[f"r/{sub} (이주의 인기글)"] = fetch_reddit_popular(sub, args.popular_count)
            time.sleep(5)

    en_markdown, ko_markdown = build_digest(all_entries, date_label, args.sentences, translate=not args.no_translate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    en_path = OUTPUT_DIR / f"articles_digest_{date_label}.md"
    en_path.write_text(en_markdown, encoding="utf-8")
    print(f"저장 완료: {en_path}")

    if not args.no_translate:
        ko_path = OUTPUT_DIR / f"articles_digest_{date_label}_korean.md"
        ko_path.write_text(ko_markdown, encoding="utf-8")
        print(f"저장 완료: {ko_path}")


if __name__ == "__main__":
    main()
