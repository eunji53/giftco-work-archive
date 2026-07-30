# papers-digest

관심있는 논문 사이트들을 매일 훑어보기 쉽도록, 상위 논문만 뽑아
마크다운 다이제스트로 저장하는 스크립트 모음.

## 1. Hugging Face Trending (`fetch_hf_paper.py`)

- `https://huggingface.co/api/daily_papers` 에서 해당 날짜의 논문 목록을 가져온다. (별도 API 키 불필요)
- 업보트 수 기준 내림차순 정렬 후 상위 N개만 추린다.
- 제목(원문 링크 포함), 저자, 업보트 수, 원문 abstract를 마크다운으로 저장한다.
- 기본적으로 abstract를 한글로 자동 번역해서 원문과 함께 병기한다 (`deep-translator`의 무료 Google 번역 엔드포인트 사용, API 키 불필요).

### 실행 방법

```bash
cd src
python fetch_hf_paper.py                # 오늘 날짜, 상위 10개, 한글 번역 포함
python fetch_hf_paper.py --top 5        # 상위 5개만
python fetch_hf_paper.py --date 2026-07-20   # 특정 날짜 조회
python fetch_hf_paper.py --no-translate # 번역 없이 원문만
```

결과는 `../output/papers_digest_YYYY-MM-DD.md` 에 저장된다.

### 참고

- 관심 키워드로 필터링하는 기능은 없음 (사용자 요청에 따라 업보트 상위 N개만 표시).
- 번역은 무료 비공식 Google 번역 엔드포인트를 사용하므로, 간혹 요청이 막히거나 품질이 들쭉날쭉할 수 있음. 실패 시 "(번역 실패: ...)" 문구가 대신 표시됨.
- 자동 스케줄링 없음 — 필요할 때 수동으로 실행하는 방식.

## 2. SOTA Papers (`fetch_sota_paper.py`)

- `https://www.sotapapers.com/trending` 페이지(참여도/engagement 기준 정렬)에서 지정한 분야(기본 Computer Science) 논문을 우선 가져온다. (조회수 정렬 자체는 사이트에 없어 참여도 순 Trending으로 대체)
- Trending은 전체 분야 통틀어 소수만 노출되는 큐레이션 리스트라 개수가 `--top`에 못 미치면, `https://www.sotapapers.com/field/<분야>` 1페이지(최신순)에서 중복 없이 나머지를 채운다.
- 별도 API가 없는 사이트라 서버 렌더링된 HTML을 `requests` + `BeautifulSoup`으로 직접 파싱한다.
- 제목(원문 링크 포함), 분야 태그(cs.AI 등, Trending 출신이면 `Trending` 태그 추가), 날짜, arXiv ID, sotapapers 요약(한 줄)을 마크다운으로 저장한다.
- 추려진 상위 N개에 한해 arXiv 공식 API(`export.arxiv.org/api/query`, 별도 키 불필요)로 arxiv_id를 조회해 **원문 abstract 전문**을 함께 가져온다.
- 기본적으로 abstract 전문을 한글로 자동 번역해서 원문과 함께 병기한다.

### 실행 방법

```bash
cd src
python fetch_sota_paper.py                       # Computer Science, 상위 10개, 한글 번역 포함
python fetch_sota_paper.py --field physics        # 다른 분야로 필터링
python fetch_sota_paper.py --top 5                # 상위 5개만
python fetch_sota_paper.py --no-translate         # 번역 없이 원문만
```

결과는 `../output/sota_paper_<field>_YYYY-MM-DD.md` 에 저장된다.

### 참고

- "조회수" 지표가 아니라 "참여도(engagement, Trending)" + "최신순(field 페이지)" 조합이며, 날짜별 과거 조회(`--date`) 기능은 없다.
- `field` 페이지도 클라이언트 자바스크립트로만 페이지네이션되는 구조라, `requests`로는 1페이지(최신 약 10개)까지만 안정적으로 가져올 수 있다. 그 이상(2~5페이지, ~50개)을 모두 수집하려면 Playwright 등 브라우저 자동화가 필요하다.
- Trending + field 1페이지를 합쳐도 `--top` 개수를 못 채우면 2페이지를 추가로 시도하지 않고, 에러 없이 **모은 만큼만** 반환한다 (예: `--top 15`처럼 크게 주면 그보다 적은 개수만 나올 수 있음).
- 사이트가 Next.js 기반이라 마크업 구조가 바뀌면 파싱이 깨질 수 있다.

## 필요 패키지

- Python 3.10+
- `requests` (`pip install requests`)
- `deep-translator` (`pip install deep-translator`)
- `beautifulsoup4` (`pip install beautifulsoup4`) — sotapapers.com 스크립트용
