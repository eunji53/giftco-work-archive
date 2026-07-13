# meeting-stt

회의 녹음 파일(m4a, mp3, wav 등)을 텍스트로 변환하기 위한 STT(Speech-to-Text) 도구입니다.
[faster-whisper](https://github.com/SYSTRAN/faster-whisper)를 사용하며, 로컬 GPU(CUDA)가 있으면 자동으로 활용하고, 없으면 CPU로 동작합니다.

## 왜 이 모델을 쓰는가

- 기본 모델은 **`large-v3`**로 설정되어 있습니다. Whisper 계열 모델 중 정확도가 가장 높은 등급이며, 로컬 GPU(RTX 5060 Ti, VRAM 8GB)에서 CUDA + float16으로 정상 동작하는 것을 확인했습니다.
- 속도가 더 중요한 경우 `--model medium` 또는 `--model large-v3-turbo` 등으로 바꿔서 실행할 수 있습니다(정확도는 다소 낮아질 수 있음).
- 한국어 회의 녹음을 기준으로 만들어졌으며 기본 언어는 `ko`이지만, `--language` 옵션으로 다른 언어도 지정할 수 있습니다.

## 설치

```bash
pip install -r requirements.txt
```

- Python 3.10 이상 권장
- NVIDIA GPU + 드라이버가 있으면 자동으로 사용합니다(별도 CUDA 툴킷 설치 없이 ctranslate2가 자체적으로 처리). GPU가 없거나 실패하면 자동으로 CPU(int8)로 전환됩니다.
- 최초 실행 시 모델 파일이 Hugging Face에서 자동 다운로드됩니다(수백 MB~수 GB, 인터넷 연결 필요). 이후에는 캐시된 모델을 재사용합니다.

## 사용법

### 쉘 스크립트로 실행 (권장)

사용하는 셸에 맞는 스크립트를 실행하세요. 셋 다 같은 동작을 하는 래퍼입니다.

**Git Bash / WSL** (`transcribe.sh`)

```bash
# 파일 하나
./scripts/transcribe.sh "/c/Users/USER/Desktop/회의녹음.m4a"

# 여러 파일
./scripts/transcribe.sh "회의_1.m4a" "회의_2.m4a"

# 폴더 전체 (폴더 안의 지원 확장자 파일을 모두 찾아서 변환)
./scripts/transcribe.sh "/c/Users/USER/Desktop/회의자료폴더"

# 모델/언어 등 옵션 추가
./scripts/transcribe.sh "회의녹음.m4a" --model medium --language ko
```

**PowerShell** (`transcribe.ps1`)

```powershell
.\scripts\transcribe.ps1 ".\data\회의녹음.m4a"
.\scripts\transcribe.ps1 ".\data\회의녹음.m4a" --model medium --language ko
```

**cmd.exe** (`transcribe.bat`)

```bat
scripts\transcribe.bat ".\data\회의녹음.m4a"
scripts\transcribe.bat ".\data\회의녹음.m4a" --model medium --language ko
```

cmd.exe에서는 `./` 접두사를 쓰지 마세요(`.`을 명령어로 인식해 오류가 납니다). `scripts\...` 또는 `scripts/...`처럼 접두사 없이 실행하면 됩니다.

### 파이썬 스크립트 직접 실행

```bash
python src/stt_transcribe.py "회의녹음.m4a" --output-dir output
```

## 옵션

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `inputs` | (필수) | 오디오 파일 경로 또는 폴더 경로 (여러 개 지정 가능) |
| `--output-dir` | `output` | 변환 결과 저장 폴더 |
| `--model` | `large-v3` | Whisper 모델 크기 (tiny/base/small/medium/large-v3/large-v3-turbo 등) |
| `--language` | `ko` | 언어 코드 |
| `--device` | `auto` | `auto`(GPU 우선, 실패 시 CPU) / `cuda` / `cpu` |
| `--compute-type` | `float16` | 연산 정밀도 (CPU 사용 시 자동으로 `int8`로 조정됨) |

## 결과물

- `output/<원본파일명>_STT.txt` 형태로 저장됩니다.
- 각 줄은 `[시작시각 - 종료시각] 텍스트` 형식의 타임스탬프 포함 텍스트입니다.
- 같은 파일을 다시 변환하면 기존 결과를 덮어씁니다.
- `output/` 폴더는 `.gitignore`에 포함되어 있어 git에 커밋되지 않습니다(회의 내용은 민감정보일 수 있으므로).

## 지원 확장자

`.m4a` `.mp3` `.wav` `.mp4` `.aac` `.flac` `.ogg` `.wma`

## 알려진 한계

- 화자 분리(diarization) 기능은 없습니다. 여러 명이 대화하는 녹음에서는 발언자 구분 없이 순서대로만 텍스트가 생성됩니다.
- 무음/잡음 구간에서 동일한 짧은 단어(예: "네")가 반복 생성되는 오류가 간혹 발생할 수 있습니다. 회의록 등 문서로 정리할 때는 원문을 그대로 신뢰하지 말고 이상하게 반복되는 구간은 확인이 필요합니다.
