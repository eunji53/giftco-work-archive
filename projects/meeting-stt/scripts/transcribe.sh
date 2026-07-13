#!/usr/bin/env bash
# 오디오 파일(또는 폴더)을 STT 변환하는 래퍼 스크립트
#
# 사용법:
#   ./scripts/transcribe.sh <오디오파일 또는 폴더 경로...> [python 스크립트 추가 옵션...]
#
# 예시:
#   ./scripts/transcribe.sh "/c/Users/USER/Desktop/회의녹음.m4a"
#   ./scripts/transcribe.sh "/c/Users/USER/Desktop/회의폴더"
#   ./scripts/transcribe.sh file1.m4a file2.m4a --model medium
#
# 결과는 프로젝트 루트의 output/ 폴더에 "<원본파일명>_STT.txt"로 저장됩니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$#" -eq 0 ]; then
  echo "사용법: $0 <오디오파일 또는 폴더 경로...> [--model 모델명] [--language ko] ..."
  exit 1
fi

PYTHON_BIN="python"
if ! command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" "$PROJECT_ROOT/src/stt_transcribe.py" "$@" --output-dir "$PROJECT_ROOT/output"
