"""Hugging Face 'papers/trending' 일일 다이제스트 생성 스크립트.

huggingface.co/api/daily_papers 에서 논문 목록을 받아 업보트 순으로
정렬한 뒤, 상위 N개를 마크다운 파일로 저장한다.
"""

import argparse
import datetime
import sys
from pathlib import Path

import requests
from deep_translator import GoogleTranslator

API_URL = "https://huggingface.co/api/daily_papers"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def translate_to_korean(text: str) -> str:
    try:
        return GoogleTranslator(source="en", target="ko").translate(text)
    except Exception as exc:
        return f"(번역 실패: {exc})"


def fetch_papers(date: str | None) -> list[dict]:
    params = {"date": date} if date else {}
    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def build_markdown(papers: list[dict], top_n: int, date_label: str, translate: bool) -> str:
    sorted_papers = sorted(papers, key=lambda p: p.get("upvotes", 0), reverse=True)
    top_papers = sorted_papers[:top_n]

    lines = [f"# Hugging Face Trending Papers - {date_label}", ""]
    for rank, entry in enumerate(top_papers, start=1):
        paper = entry.get("paper", entry)
        title = paper.get("title", "제목 없음")
        paper_id = paper.get("id", "")
        upvotes = entry.get("upvotes", paper.get("upvotes", 0))
        authors = ", ".join(a.get("name", "") for a in paper.get("authors", []))
        summary = paper.get("summary", "").strip()
        url = f"https://huggingface.co/papers/{paper_id}" if paper_id else ""

        lines.append(f"## {rank}. [{title}]({url})")
        lines.append(f"- Upvotes: {upvotes}")
        if authors:
            lines.append(f"- Authors: {authors}")
        lines.append("")
        lines.append("**Abstract (원문)**")
        lines.append("")
        lines.append(summary)
        lines.append("")
        if translate and summary:
            lines.append("**번역 (자동 번역)**")
            lines.append("")
            lines.append(translate_to_korean(summary))
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="HF 트렌딩 논문 다이제스트 생성")
    parser.add_argument("--date", help="조회할 날짜 (YYYY-MM-DD), 미지정 시 오늘")
    parser.add_argument("--top", type=int, default=10, help="상위 몇 개를 뽑을지 (기본 10)")
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="한글 번역 없이 원문 abstract만 출력",
    )
    args = parser.parse_args()

    date_label = args.date or datetime.date.today().isoformat()

    try:
        papers = fetch_papers(args.date)
    except requests.RequestException as exc:
        print(f"논문 목록을 가져오는 데 실패했습니다: {exc}", file=sys.stderr)
        sys.exit(1)

    if not papers:
        print(f"{date_label} 날짜에 등록된 논문이 없습니다.")
        return

    markdown = build_markdown(papers, args.top, date_label, translate=not args.no_translate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"papers_digest_{date_label}.md"
    out_path.write_text(markdown, encoding="utf-8")

    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
