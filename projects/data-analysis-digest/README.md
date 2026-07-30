# data-analysis-digest

데이터 분석/AI 관련 최신 글과 인기 글을 매일 훑어보기 쉽도록,
본문 전체를 가져와 핵심만 요약해 마크다운으로 정리하는 스크립트.
영문 요약과 한글 번역은 별도 파일로 나뉜다.

## 포함된 소스

**최신글 (RSS, 사이트당 최근 N개)**
- **Analytics Vidhya** (`analyticsvidhya.com/feed/`)
- **Machine Learning Mastery** (`machinelearningmastery.com/feed/`)
- **KDnuggets** (`kdnuggets.com/feed`)

**이주의 인기글 (조회수/추천수 기반)**
- **Hacker News** — `machine learning`, `LLM`, `data analysis`, `deep learning`, `AI agent` 키워드로 검색해 최근 7일 내 포인트(추천수) 높은 순
- **Reddit** — `r/MachineLearning`, `r/datascience` 주간 인기글(업보트 기준, `top.rss?t=week`)

## 제외된 사이트

- **Towards Data Science** — 기사 페이지 접속이 Cloudflare 봇 차단에 걸리고(RSS 목록은 되지만 본문 페이지는 안 열림), 일부 글은 Medium 멤버십 페이월이 있어 자동화에서 제외.
- **Data Elixir** — RSS 요청이 봇 차단(HTTP 403)되어 자동 수집 불가. 필요하면 https://dataelixir.com 에서 직접 구독/열람.
- **Kaggle Discussions/Notebooks** — RSS를 제공하지 않음. Kaggle API로 우회 가능하지만 별도 인증 키 설정이 필요해 이번 스코프에서는 제외.

## 동작 방식

1. 각 RSS 사이트에서 발행 시각과 무관하게 사이트당 최근 N개(기본 7개, `--count`)를 가져오고, Hacker News/Reddit에서는 이번 주 인기글을 소스당 N개(기본 5개, `--popular-count`) 가져온다.
2. 각 글의 실제 페이지에 접속해 `trafilatura`로 본문 전체를 추출한다 (RSS의 한 줄짜리 요약이 아니라 실제 기사 내용 기준).
3. 본문 전체를 그대로 넣으면 너무 길어서, 표/코드/목록 기호 같은 비-본문 조각을 걸러낸 뒤(`clean_extracted_text`) 무료 추출 요약 알고리즘(`sumy`의 LexRank)으로 핵심 문장 몇 개만 골라낸다 (기본 6문장, `--sentences`로 조절, 4단어 미만 짧은 조각은 자동 제외).
4. 영문 요약은 `articles_digest_YYYY-MM-DD.md`에, 한글 번역본은 `articles_digest_YYYY-MM-DD_korean.md`에 각각 저장한다. 두 파일 모두 "최신글" 섹션 아래에 "이주의 인기글" 섹션이 이어진다.

## 실행 방법

```bash
cd src
python fetch_articles.py                  # 최신글 사이트당 7개 + 인기글 소스당 5개, 영문+한글 파일 둘 다 생성
python fetch_articles.py --count 10       # 최신글 개수 늘리기
python fetch_articles.py --popular-count 3 # 인기글 개수 줄이기
python fetch_articles.py --no-popular     # 인기글 섹션(HN/Reddit) 생성 안 함
python fetch_articles.py --sentences 10   # 요약 문장 수 늘리기
python fetch_articles.py --no-translate   # 한글 파일 생성 안 함
```

결과는 `../output/` 에 저장된다:
- `articles_digest_YYYY-MM-DD.md` — 영문 요약
- `articles_digest_YYYY-MM-DD_korean.md` — 한글 번역

## 필요 패키지

- Python 3.10+
- `feedparser`, `requests`, `trafilatura`, `sumy`, `deep-translator`
- `nltk` punkt_tab 데이터 (최초 1회 `python -c "import nltk; nltk.download('punkt_tab')"` 필요)

## 참고

- 추출 요약(LexRank)은 원문에서 중요해 보이는 문장을 그대로 뽑아오는 방식이라, 가끔 표(table)나 문맥이 어색하게 이어질 수 있음. AI 재작성 요약이 아니라 무료 추출 요약임. 표/코드/목록 기호(`A.` `B.` 같은 조각)는 정제 단계에서 걸러내지만 완전히 사라진다는 보장은 없음.
- 번역은 무료 비공식 Google 번역 엔드포인트를 사용하므로, 간혹 요청이 막히거나 품질이 들쭉날쭉할 수 있음. 실패 시 "(번역 실패: ...)" 문구가 대신 표시됨.
- 일부 글은 본문 페이지 접속에 실패할 수 있는데, 이 경우 RSS 요약을 기반으로 대체 요약한다 (해당 글에 안내 문구 표시).
- Hacker News는 Algolia 검색 API(인증 불필요)를 키워드별로 호출해 합친 뒤 포인트 높은 순으로 정렬한다. 그 주에 관련 키워드 글이 적으면 결과가 적을 수 있다.
- Reddit은 `top.rss?t=week`(주간 인기글, 업보트 기준)를 사용한다. Reddit이 요청을 차단(403/429)하면 해당 서브레딧은 빈 목록으로 처리되고 에러 메시지만 출력된다.
- 자동 스케줄링 없음 — 필요할 때 수동으로 실행하는 방식.
