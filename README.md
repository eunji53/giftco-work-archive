# giftco-work-archive

`C:\Users\USER\Desktop\workspace`에 흩어져 있던 작업물을 Git으로 관리하기 좋은 구조로 정리한 사본입니다.

## 폴더 구조

**정리해서 커밋하는 프로젝트만 아래에 표시합니다. 나머지는 정리되는 대로 추가할 예정입니다.**

```
giftco-work-archive/
├─ README.md              # 이 파일
├─ .env.example            # 필요한 환경변수 목록 (값은 비어 있음)
└─ projects/
   ├─ giftco-supplier/          # 대한판촉 입점업체 크롤링 + 공급사 데이터 분석 + 상품조회 뷰어
   ├─ voice-data-pipeline/      # 수신/발신 통화 녹음 분석 및 시각화
   ├─ giftco-tool/              # 상품명 카테고리 라벨링/검수용 tkinter GUI 툴 모음
   ├─ giftco-order-processing/  # 조아기프트/고려기프트 발주서 수집·파싱·정리 파이프라인
   ├─ meeting-stt/              # 회의 녹음파일 STT 변환 도구 (faster-whisper, GPU)
   └─ rag-experiments/          # RAG 학습/실습 — FAQ 검색 임베딩 실험 노트북
```

각 프로젝트 폴더 안의 `README.md`(정리 경위)와 `README_git.md`(실행 방법)를 참고하세요.

## 중요 — 이 저장소에 없는 것들

- 실제 발주서/거래처 첨부파일, 음성데이터, 이메일 원문 덤프 등 원본 업무 데이터는 포함하지 않습니다.
- 로그인 쿠키 등 자격증명이 하드코딩되어 있던 코드는 `.env` 기반으로 값을 분리한 버전만 포함합니다.
- 모든 노트북(`.ipynb`)은 실행 결과(output)를 제거한 상태로 커밋합니다. 실제 거래처/공급업체 담당자명·연락처 등이 실행 결과에 남는 경우가 있어 원칙으로 정했습니다.

## Git 상태

프로젝트가 정리되는 대로 하나씩 커밋합니다. 현재 giftco-supplier, voice-data-pipeline, giftco-tool, giftco-order-processing, meeting-stt, rag-experiments 여섯 프로젝트가 커밋되어 있습니다.
