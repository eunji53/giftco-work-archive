# rag-experiments

RAG(검색증강생성) 시스템을 이해하기 위한 학습/실습 프로젝트. FAQ 검색과 상품 추천에 임베딩 기반 검색을 적용해보는 실험 노트북들입니다.

## 폴더 구조


- `notebooks/faq/` — FAQ 검색 RAG 실험 (TF-IDF → 임베딩 → BM25+임베딩 하이브리드 순으로 발전)
  - `giftco_faq_rag_v0_starter.ipynb` — TF-IDF 문자 n-gram 검색 (원본 FAQ 25개, LLM 답변 생성은 OpenRouter)
  - `giftco_faq_rag_v1_embedding.ipynb` — 임베딩(SBERT) 의미 검색으로 업그레이드 (보완된 FAQ 38개, jhgan/KR-SBERT 모델 비교, LLM 답변 생성은 Ollama/Claude/OpenRouter)
  - `giftco_faq_rag_v2_hybrid.ipynb` — BM25 + 임베딩을 RRF로 결합한 하이브리드 검색 (v1의 임베딩 캐시를 그대로 재사용)
  - `data/`, `cache/`(임베딩 캐시, 기법 단위), `output/`(버전별 결과, 파일명에 `_v0` 등 접미사) — 전부 로컬에만 존재, git에는 안 올라감

