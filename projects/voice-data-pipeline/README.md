# voice-data-pipeline

음성 통화 데이터 수집/이동, STT(음성→텍스트) 변환, Ollama를 이용한 요약/정리, 정리된 데이터 기반 분석까지 이어지는 파이프라인 코드입니다.

## 폴더 구조

```
voice-data-pipeline/
├─ notebooks/
│  ├─ 01_analyze_inbound_calls.ipynb            # 완성본: 수신 통화 STT + 상담/비상담 분류 (소량 테스트용)
│  └─ 02_visualize_inbound_call_analysis.ipynb  # 완성본: 위 결과 시각화 (이미지 11개)
├─ scripts/
│  └─ analyze_inbound_calls.py                  # 완성본: 01과 같은 로직의 전체 배치용 스크립트 (야간 실행)
├─ notebooks_scripts/   # 원본/미정리 노트북·스크립트 (발신통화 등, 다음 정리 대상)
├─ data/
│  ├─ call_metadata.csv   # NAS 전체(수신+발신) 파일명 기반 메타데이터 — inbound/outbound 공용, gitignore 대상
│  ├─ inbound/    # 수신 분류결과 (csv/json/checkpoint) — gitignore 대상
│  └─ outbound/   # 발신통화 정리 시 사용 예정 (현재 비어 있음)
└─ output/
   ├─ inbound/    # 시각화 결과 이미지 11개 — gitignore 대상
   └─ outbound/   # 발신통화 시각화 시 사용 예정 (현재 비어 있음)
```

## 실행 방법

1. 저장소 루트 `.env.example`을 복사해 `.env` 생성 후 `VOICE_NAS_PATH`(NAS 통화 녹음 폴더 경로)를 채웁니다.
2. 로컬에 Ollama가 설치되어 있고 `qwen2.5:3b` 모델이 pull되어 있어야 합니다 (`ollama pull qwen2.5:3b`).
3. `pip install faster-whisper python-dotenv pandas requests matplotlib seaborn` (한글 폰트로 `Malgun Gothic` 필요, Windows 기본 제공)
4. **소량 테스트**: `notebooks/01_analyze_inbound_calls.ipynb` 실행 → `data/inbound/`에 결과 생성. `TEST_N`(개수) 또는 `TEST_DATE`(예: `"20260601"`)로 범위를 좁혀서 확인
5. **전체 배치**: 테스트가 끝나면 `scripts/` 폴더 안에서 `python analyze_inbound_calls.py`로 전체 실행 (야간 실행 권장, 체크포인트로 중단 후 재개 가능). 01 노트북과 같은 `data/inbound/` 결과 파일을 이어서 씁니다
6. `notebooks/02_visualize_inbound_call_analysis.ipynb` 실행 → `output/inbound/`에 이미지 11개 생성

`회의록 작성.py`는 `ANTHROPIC_API_KEY` 환경변수가 필요합니다.

## 참고 — 실제 통화 데이터는 git에 올라가지 않습니다

`data/`, `output/` 폴더 전체가 `.gitignore`에 등록되어 있습니다. 실제 고객 통화 전사문/요약/QA가 담기기 때문입니다. 로컬에서 실행하면 폴더가 자동 생성되지만, 커밋 대상이 아닙니다.
