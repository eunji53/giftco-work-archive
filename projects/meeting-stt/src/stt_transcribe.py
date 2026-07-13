"""
범용 음성 파일 STT(Speech-to-Text) 변환 스크립트

- faster-whisper 기반으로 오디오 파일을 텍스트로 변환한다.
- 파일 하나, 여러 개, 폴더 경로를 입력으로 받을 수 있다.
- 기본 모델은 large-v3 (로컬 GPU에서 검증된 최고 정확도 등급).
"""

import argparse
import sys
from pathlib import Path

from faster_whisper import WhisperModel

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".mp4", ".aac", ".flac", ".ogg", ".wma"}
DEFAULT_MODEL = "large-v3"


def format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def collect_audio_files(paths: list[str]) -> list[Path]:
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(f)
        elif path.is_file():
            files.append(path)
        else:
            print(f"[경고] 경로를 찾을 수 없습니다: {p}", file=sys.stderr)
    return files


def load_model(model_size: str, device: str, compute_type: str) -> WhisperModel:
    if device == "auto":
        try:
            print(f"[모델 로딩] {model_size} (device=cuda 시도, compute_type={compute_type})")
            return WhisperModel(model_size, device="cuda", compute_type=compute_type)
        except Exception as e:
            print(f"[안내] GPU 사용 불가({e}), CPU로 전환합니다.", file=sys.stderr)
            return WhisperModel(model_size, device="cpu", compute_type="int8")

    if device == "cpu" and compute_type == "float16":
        compute_type = "int8"
    print(f"[모델 로딩] {model_size} (device={device}, compute_type={compute_type})")
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_file(model: WhisperModel, path: Path, language: str) -> str:
    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )
    print(f"  감지 언어: {info.language} (확률 {info.language_probability:.2f})")

    lines = []
    for seg in segments:
        start = format_timestamp(seg.start)
        end = format_timestamp(seg.end)
        lines.append(f"[{start} - {end}] {seg.text.strip()}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="오디오 파일(들)을 faster-whisper로 텍스트 변환합니다."
    )
    parser.add_argument(
        "inputs", nargs="+", help="오디오 파일 경로 또는 폴더 경로 (여러 개 지정 가능)"
    )
    parser.add_argument(
        "--output-dir", default="output", help="결과 저장 폴더 (기본값: output)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="Whisper 모델 크기 (기본값: large-v3)"
    )
    parser.add_argument("--language", default="ko", help="언어 코드 (기본값: ko)")
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="실행 장치 (기본값: auto - GPU 우선, 실패 시 CPU)",
    )
    parser.add_argument(
        "--compute-type",
        default="float16",
        help="연산 정밀도 (기본값: float16, CPU 사용 시 자동으로 int8)",
    )
    args = parser.parse_args()

    files = collect_audio_files(args.inputs)
    if not files:
        print("변환할 오디오 파일을 찾지 못했습니다.", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model = load_model(args.model, args.device, args.compute_type)

    succeeded, failed = [], []
    for f in files:
        print(f"\n[STT] {f.name}")
        try:
            text = transcribe_file(model, f, args.language)
        except Exception as e:
            print(f"  [오류] {f.name} 변환 실패: {e}", file=sys.stderr)
            failed.append(f)
            continue

        out_path = output_dir / f"{f.stem}_STT.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"  -> 저장 완료: {out_path} ({len(text)}자)")
        succeeded.append(f)

    print(f"\n완료: 성공 {len(succeeded)}건, 실패 {len(failed)}건")
    if failed:
        print("실패 파일:", ", ".join(str(f) for f in failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
