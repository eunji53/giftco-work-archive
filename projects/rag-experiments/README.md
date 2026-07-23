# rag-experiments

RAG(검색증강생성) 시스템을 이해하기 위한 학습/실습 프로젝트. FAQ 검색과 상품 추천에 임베딩 기반 검색을 적용해보는 실험 노트북들입니다.

## 폴더 구조

- `faq/` — FAQ 검색 RAG 실험 (TF-IDF → 임베딩 → BM25+임베딩 하이브리드 순으로 발전)
  - `notebooks/`
    - `giftco_faq_rag_v0_starter.ipynb` — TF-IDF 문자 n-gram 검색 (원본 FAQ 25개, LLM 답변 생성은 OpenRouter)
    - `giftco_faq_rag_v1_embedding.ipynb` — 임베딩(SBERT) 의미 검색으로 업그레이드 (보완된 FAQ 38개, jhgan/KR-SBERT 모델 비교, LLM 답변 생성은 Ollama/Claude/OpenRouter)
    - `giftco_faq_rag_v2_hybrid.ipynb` — BM25 + 임베딩을 RRF로 결합한 하이브리드 검색 (v1의 임베딩 캐시를 그대로 재사용)
  - git에는 `notebooks/`만 올라갑니다. 아래는 로컬에서 직접 준비하거나 실행 시 자동 생성됩니다.
    - `data/` — 실행 전 직접 채워야 함: `기프트코_FAQ.xlsx`(원본 25개, v0용), `기프트코_FAQ_보완_v1.xlsx`(보완 38개, v1부터 사용)
    - `cache/` — 임베딩 캐시, 실행하면 자동 생성
    - `output/` — 버전별 결과 저장, 실행하면 자동 생성 (파일명에 `_v0` 등 접미사)
  - 실행 순서: v0 → v1 → v2 (v2는 v1의 임베딩 캐시를 재사용하므로 v1을 먼저 실행해야 함)

- `product-recommendation/` — 상품 추천 RAG 실험 (TF-IDF → row 임베딩 검색 → profile 집계 검색 순으로 발전, v3 계획 중)
  - `giftco_product_recommendation_v0.ipynb` ~ `v2.ipynb`, `README.md`(버전별 학습목표·문제점 상세 정리), `docs/`(문제점 및 보완방향 문서)
  - `data/`, `cache/`, `output/` — 전부 로컬에만 존재, git에는 안 올라감

