# hf-papers-digest

Hugging Face `papers/trending` 페이지의 논문을 매일 훑어보기 쉽도록,
업보트 상위 논문만 뽑아 마크다운 다이제스트로 저장하는 스크립트.

## 동작 방식

- `https://huggingface.co/api/daily_papers` 에서 해당 날짜의 논문 목록을 가져온다. (별도 API 키 불필요)
- 업보트 수 기준 내림차순 정렬 후 상위 N개만 추린다.
- 제목(원문 링크 포함), 저자, 업보트 수, 원문 abstract를 마크다운으로 저장한다.
- 기본적으로 abstract를 한글로 자동 번역해서 원문과 함께 병기한다 (`deep-translator`의 무료 Google 번역 엔드포인트 사용, API 키 불필요).

## 실행 방법

```bash
cd src
python fetch_papers.py                # 오늘 날짜, 상위 10개, 한글 번역 포함
python fetch_papers.py --top 5        # 상위 5개만
python fetch_papers.py --date 2026-07-20   # 특정 날짜 조회
python fetch_papers.py --no-translate # 번역 없이 원문만
```

결과는 `../output/papers_digest_YYYY-MM-DD.md` 에 저장된다.

## 필요 패키지

- Python 3.10+
- `requests` (`pip install requests`)
- `deep-translator` (`pip install deep-translator`)

## 참고

- 관심 키워드로 필터링하는 기능은 없음 (사용자 요청에 따라 업보트 상위 N개만 표시).
- 번역은 무료 비공식 Google 번역 엔드포인트를 사용하므로, 간혹 요청이 막히거나 품질이 들쭉날쭉할 수 있음. 실패 시 "(번역 실패: ...)" 문구가 대신 표시됨.
- 자동 스케줄링 없음 — 필요할 때 수동으로 실행하는 방식.
