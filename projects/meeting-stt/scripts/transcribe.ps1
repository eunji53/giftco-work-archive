# 오디오 파일(또는 폴더)을 STT 변환하는 PowerShell 래퍼 스크립트
#
# 사용법:
#   .\scripts\transcribe.ps1 <오디오파일 또는 폴더 경로...> [python 스크립트 추가 옵션...]
#
# 예시:
#   .\scripts\transcribe.ps1 ".\data\0713회의.m4a"
#   .\scripts\transcribe.ps1 ".\data" --model medium
#
# 결과는 프로젝트 루트의 output\ 폴더에 "<원본파일명>_STT.txt"로 저장됩니다.

$ErrorActionPreference = "Stop"

if ($args.Count -eq 0) {
    Write-Output "사용법: .\scripts\transcribe.ps1 <오디오파일 또는 폴더 경로...> [--model 모델명] [--language ko] ..."
    exit 1
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot

python "$ProjectRoot\src\stt_transcribe.py" @args --output-dir "$ProjectRoot\output"
