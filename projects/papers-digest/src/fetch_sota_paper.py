"""SOTA Papers(sotapapers.com) 다이제스트 생성 스크립트.

sotapapers.com/trending(참여도 기준, 전체 분야 통틀어 소수만 노출)에서 지정한 분야의
논문을 우선 가져오고, 개수가 부족하면 sotapapers.com/field/<분야> 1페이지(최신순)에서
나머지를 채운다. 상위 N개는 arXiv 공식 API로 abstract 전문을 추가로 가져와
한글 번역과 함께 마크다운으로 저장한다. (조회수 정렬 자체는 사이트에 없음)
"""

import argparse
import datetime
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TRENDING_URL = "https://www.sotapapers.com/trending"
FIELD_URL_TEMPLATE = "https://www.sotapapers.com/field/{field}"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_ATOM_NS = "{http://www.w3.org/2005/Atom}"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def translate_to_korean(text: str) -> str:
    try:
        return GoogleTranslator(source="en", target="ko").translate(text)
    except Exception as exc:
        return f"(번역 실패: {exc})"


def fetch_trending_html() -> str:
    response = requests.get(TRENDING_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_field_html(field: str) -> str:
    url = FIELD_URL_TEMPLATE.format(field=field)
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return response.text


def parse_articles(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    for link in soup.select('a.block[href^="/article/"]'):
        field_link = link.select_one('a[href^="/field/"]')
        title_tag = link.select_one("h3")
        summary_tag = link.select_one("p")
        meta_spans = link.select("div.mt-3.flex.flex-wrap.items-center span")
        arxiv_tag = link.select_one("span.opacity-50")

        articles.append(
            {
                "title": title_tag.get_text(strip=True) if title_tag else "",
                "url": f"https://www.sotapapers.com{link['href']}",
                "summary": summary_tag.get_text(strip=True) if summary_tag else "",
                "field_href": field_link["href"] if field_link else "",
                "tags": [t.get_text(strip=True) for t in link.select('a[href^="/tag/"]')],
                "date": meta_spans[0].get_text(strip=True) if meta_spans else "",
                "arxiv_id": arxiv_tag.get_text(strip=True) if arxiv_tag else "",
                "trending": False,
            }
        )
    return articles


def fetch_arxiv_abstracts(arxiv_ids: list[str]) -> dict[str, str]:
    ids = [i for i in arxiv_ids if i]
    if not ids:
        return {}

    params = {"id_list": ",".join(ids), "max_results": len(ids)}
    response = requests.get(ARXIV_API_URL, params=params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    abstracts = {}
    for entry in root.findall(f"{ARXIV_ATOM_NS}entry"):
        entry_id = entry.findtext(f"{ARXIV_ATOM_NS}id") or ""
        match = re.search(r"abs/([^v]+)v?\d*$", entry_id)
        summary = entry.findtext(f"{ARXIV_ATOM_NS}summary")
        if match and summary:
            abstracts[match.group(1)] = " ".join(summary.split())
    return abstracts


def collect_articles(field: str, top_n: int) -> list[dict]:
    trending = [a for a in parse_articles(fetch_trending_html()) if a["field_href"] == f"/field/{field}"]
    for article in trending:
        article["trending"] = True

    merged = list(trending)
    seen_urls = {a["url"] for a in trending}

    if len(merged) < top_n:
        field_page = [
            a for a in parse_articles(fetch_field_html(field)) if a["field_href"] == f"/field/{field}"
        ]
        for article in field_page:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                merged.append(article)

    return merged


def build_markdown(articles: list[dict], date_label: str, translate: bool, field: str) -> str:
    lines = [f"# SOTA Papers - {field} - {date_label}", ""]
    for rank, article in enumerate(articles, start=1):
        lines.append(f"## {rank}. [{article['title']}]({article['url']})")
        tags = list(article["tags"])
        if article["trending"]:
            tags.append("Trending")
        if tags:
            lines.append(f"- Tags: {', '.join(tags)}")
        if article["date"]:
            lines.append(f"- Date: {article['date']}")
        if article["arxiv_id"]:
            lines.append(f"- arXiv: {article['arxiv_id']}")
        lines.append("")
        lines.append("**Summary (sotapapers 요약)**")
        lines.append("")
        lines.append(article["summary"])
        lines.append("")

        abstract = article.get("abstract", "")
        if abstract:
            lines.append("**Abstract (arXiv 원문)**")
            lines.append("")
            lines.append(abstract)
            lines.append("")
            if translate:
                lines.append("**Abstract 번역 (자동 번역)**")
                lines.append("")
                lines.append(translate_to_korean(abstract))
                lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SOTA Papers 다이제스트 생성 (Trending 우선, 부족분은 field 최신순으로 채움)"
    )
    parser.add_argument("--field", default="computer-science", help="필터링할 분야 슬러그 (기본: computer-science)")
    parser.add_argument("--top", type=int, default=10, help="상위 몇 개를 뽑을지 (기본 10)")
    parser.add_argument("--no-translate", action="store_true", help="한글 번역 없이 원문 summary만 출력")
    args = parser.parse_args()

    date_label = datetime.date.today().isoformat()

    try:
        articles = collect_articles(args.field, args.top)
    except requests.RequestException as exc:
        print(f"sotapapers.com에서 논문 목록을 가져오는 데 실패했습니다: {exc}", file=sys.stderr)
        sys.exit(1)

    if not articles:
        print(f"'{args.field}' 분야에 해당하는 논문이 없습니다.")
        return

    top_articles = articles[: args.top]

    try:
        abstracts = fetch_arxiv_abstracts([a["arxiv_id"] for a in top_articles])
    except requests.RequestException as exc:
        print(f"arXiv abstract 조회에 실패했습니다 (요약만 사용): {exc}", file=sys.stderr)
        abstracts = {}

    for article in top_articles:
        article["abstract"] = abstracts.get(article["arxiv_id"], "")

    markdown = build_markdown(
        top_articles, date_label, translate=not args.no_translate, field=args.field
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"sota_paper_{args.field}_{date_label}.md"
    out_path.write_text(markdown, encoding="utf-8")

    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
