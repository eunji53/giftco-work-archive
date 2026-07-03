"""
기프트코 음성데이터 배치 분석 스크립트
- 대상: 401 수신 통화 (외부 고객 → 상담원) — DIRECTION 설정으로 발신/전체도 가능
- STT: faster-whisper small (로컬)
- 분류: Ollama qwen2.5:3b (로컬)
- 실행: scripts/ 폴더 안에서 python analyze_inbound_calls.py
- 중단 후 재시작: 동일 명령어 재실행 (체크포인트 자동 복원)
- notebooks/01_analyze_inbound_calls.ipynb와 같은 데이터 폴더(../data/inbound/)를 공유합니다.
  노트북에서 소량 테스트 후, 전체 배치는 이 스크립트로 실행하는 용도입니다.
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv()

# ═══════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════
VOICE_NAS_PATH = os.environ.get("VOICE_NAS_PATH", "").strip()
if not VOICE_NAS_PATH:
    raise RuntimeError(
        ".env에 VOICE_NAS_PATH가 설정되지 않았습니다. "
        r"NAS 상의 통화 녹음 폴더 경로(예: \\NAS서버\mslab\DCS)를 .env에 넣어주세요."
    )

DATA_DIR = Path(__file__).parent / "../data/inbound"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 수신+발신 전체 메타데이터라 inbound/outbound 공용 위치(data/ 바로 아래)에 저장 (01 노트북과 동일 파일 공유)
METADATA_CSV = Path(__file__).parent / "../data/call_metadata.csv"
CHECKPOINT_FILE = DATA_DIR / "inbound_call_checkpoint.json"
OUTPUT_CSV = DATA_DIR / "inbound_call_classification.csv"
OUTPUT_JSON = DATA_DIR / "inbound_call_classification.json"

TARGET_NUMBER = "401"
DIRECTION = "수신"          # "수신"=외부→401, "발신"=401→외부, "전체"=둘 다
MIN_DURATION = 10           # 초 미만 스킵

MODEL_SIZE = "small"        # tiny / base / small
CPU_THREADS = 4
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
MAX_CHARS = 1800
SAVE_EVERY = 20              # N개마다 중간 저장
# ═══════════════════════════════════════════


def parse_filename(fname: str) -> dict:
    name, ext = os.path.splitext(fname)
    if ext.lower() not in {".wav", ".mp3"}:
        return {}
    parts = name.split("_")
    if len(parts) < 14:
        return {}
    caller = parts[0]
    receiver = parts[1]
    try:
        start_dt = datetime.strptime("_".join(parts[2:8]), "%Y_%m_%d_%H_%M_%S")
        end_dt = datetime.strptime("_".join(parts[8:14]), "%Y_%m_%d_%H_%M_%S")
        duration_sec = (end_dt - start_dt).total_seconds()
    except Exception:
        return {}
    return {
        "caller": caller,
        "receiver": receiver,
        "start_dt": start_dt,
        "duration_sec": duration_sec,
        "direction": "발신" if caller == TARGET_NUMBER else "수신",
    }


def scan_calls(base_path: str) -> list[dict]:
    """NAS 폴더를 순회하며 모든 통화 파일의 메타데이터를 수집합니다 (방향/대상번호 필터 없음).
    01_analyze_inbound_calls.ipynb의 parse_call_metadata()와 동일한 범위(수신+발신 전체)입니다.
    """
    records = []
    for root, _folders, files in os.walk(base_path):
        folder = os.path.basename(root)
        if not (len(folder) == 8 and folder.isdigit()):
            continue
        for fname in files:
            info = parse_filename(fname)
            if not info:
                continue
            records.append({
                "folder": folder,
                "filename": fname,
                "filepath": os.path.join(root, fname),
                **info,
            })
    return records


def save_metadata_csv(records: list[dict]):
    if not records:
        return
    with open(METADATA_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def collect_target_files(all_records: list[dict]) -> list[dict]:
    """DIRECTION/TARGET_NUMBER 조건에 맞는 통화만 골라냅니다."""
    result = []
    for info in all_records:
        if DIRECTION != "전체" and info["direction"] != DIRECTION:
            continue
        if info["caller"] != TARGET_NUMBER and info["receiver"] != TARGET_NUMBER:
            continue
        result.append(info)
    return result


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def transcribe(whisper_model, filepath: str) -> str:
    segments, _ = whisper_model.transcribe(
        filepath, language="ko", vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    return normalize_text(" ".join(s.text for s in segments))


def build_prompt(transcript: str) -> str:
    return f"""당신은 기프트코(판촉물 판매 사이트) 상담 전화를 분류하는 전문가입니다.
반드시 한국어로만 답변하세요. Do not use Chinese or any other language.
기프트코는 판촉물(볼펜, 가방, 머그컵, 의류, 인쇄물 등)을 판매하는 B2B/B2C 사이트입니다.

전사문을 읽고 아래 기준으로 분류하세요.

【상담】— 아래 중 하나라도 해당하면 무조건 상담
- 상품 문의 (가격, 수량, 재고, 종류, 샘플 요청)
- 주문/발주/견적/납품/배송/취소/환불 관련
- 결제, 세금계산서, 영수증 관련
- 로그인, 회원가입, 사이트 이용 문의
- 인쇄/제작 파일(디자인, 로고, 일러스트 등) 관련
- 거래처/공급업체 관련 업무 통화
- 문의가 해결되지 않았더라도 업무 관련이면 상담

【비상담】— 아래에만 해당
- 번호를 잘못 눌러 걸린 전화
- 기프트코가 아닌 다른 업체/기관으로 착각한 전화

【광고】— 광고, 영업, 스팸 전화

【불명확】— STT 품질이 너무 낮아 내용 파악 자체가 불가능한 경우만

중요: 업무 내용이 조금이라도 있으면 상담으로 분류하세요.
"문제가 해결되지 않았다", "짧은 통화다"는 비상담 이유가 될 수 없습니다.
작업:
1. label 결정 (상담/비상담/광고/불명확)
2. 화자를 "고객"/"상담원"으로 구분
3. 상담이면 QA 쌍 추출 (챗봇 학습용, 실질적 내용만)
4. 한 줄 요약

규칙: JSON만 반환. 마크다운/코드블록 없이. 모든 텍스트 값은 반드시 한국어로 작성.

JSON:
{{"label":"상담|비상담|광고|불명확","reason":"판단 근거","speaker_dialogue":[{{"speaker":"고객|상담원|불명","text":"내용"}}],"qa_pairs":[{{"question":"질문","answer":"답변"}}],"summary":"요약"}}

전사문:
\"\"\"{transcript}\"\"\"
""".strip()


def safe_parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            pass
    return {}


def normalize_label(raw: str) -> str:
    raw = (raw or "").strip()
    if raw in {"상담", "비상담", "광고", "불명확"}:
        return raw
    if "상담" in raw:
        return "상담"
    if "비상담" in raw:
        return "비상담"
    if "광고" in raw:
        return "광고"
    return "불명확"


def analyze_with_ollama(transcript: str) -> dict:
    prompt = build_prompt(transcript[:MAX_CHARS])
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=(30, 600))
    resp.raise_for_status()
    parsed = safe_parse_json(resp.json().get("response", ""))

    dialogue = [d for d in parsed.get("speaker_dialogue", [])
                if isinstance(d, dict) and d.get("text")]
    qa_pairs = [q for q in parsed.get("qa_pairs", [])
                if isinstance(q, dict) and q.get("question") and q.get("answer")]

    return {
        "label": normalize_label(parsed.get("label", "")),
        "reason": parsed.get("reason", ""),
        "summary": parsed.get("summary", ""),
        "speaker_dialogue": dialogue,
        "qa_pairs": qa_pairs,
    }


def save_results(all_results: list[dict], done_set: set):
    # 체크포인트 — atomic write (tmp → rename) 로 중간 손상 방지
    tmp_ckpt = str(CHECKPOINT_FILE) + ".tmp"
    with open(tmp_ckpt, "w", encoding="utf-8") as f:
        json.dump({"done_files": list(done_set), "results": all_results},
                  f, ensure_ascii=False)
    os.replace(tmp_ckpt, CHECKPOINT_FILE)

    csv_rows = []
    for r in all_results:
        dialogue_text = "\n".join(
            f"{d['speaker']}: {d['text']}" for d in r.get("speaker_dialogue", [])
        )
        qa_text = "\n\n".join(
            f"[QA {i}]\nQ: {q['question']}\nA: {q['answer']}"
            for i, q in enumerate(r.get("qa_pairs", []), 1)
        )
        csv_rows.append({
            "file_name": r["file_name"],
            "folder": r["folder"],
            "direction": r["direction"],
            "duration_sec": r["duration_sec"],
            "label": r["label"],
            "reason": r["reason"],
            "summary": r["summary"],
            "transcript": r["transcript"],
            "speaker_dialogue_text": dialogue_text,
            "qa_pairs_text": qa_text,
            "qa_count": len(r.get("qa_pairs", [])),
        })
    if csv_rows:
        tmp_csv = str(OUTPUT_CSV) + ".tmp"
        with open(tmp_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        os.replace(tmp_csv, OUTPUT_CSV)

    tmp_json = str(OUTPUT_JSON) + ".tmp"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp_json, OUTPUT_JSON)


def print_summary(all_results: list[dict]):
    from collections import Counter
    labels = Counter(r["label"] for r in all_results)
    total = sum(labels.values())
    print("\n" + "=" * 50)
    print("[ 최종 분류 결과 ]")
    print("=" * 50)
    for label, cnt in sorted(labels.items()):
        print(f"  {label:<10}: {cnt:>5}개  ({cnt/total*100:.1f}%)")
    print(f"  {'합계':<10}: {total:>5}개")
    consult = [r for r in all_results if r["label"] == "상담"]
    qa_total = sum(len(r.get("qa_pairs", [])) for r in consult)
    print(f"\n상담 통화: {len(consult)}개 | 생성된 QA: {qa_total}개")
    print(f"결과 파일: {OUTPUT_CSV}")
    print(f"           {OUTPUT_JSON}")


def main():
    print("=" * 50)
    print("기프트코 음성데이터 배치 분석")
    print(f"대상: {DIRECTION} 통화 ({TARGET_NUMBER}번)")
    print("=" * 50)

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"Ollama OK | 모델: {models}")
        if OLLAMA_MODEL not in models:
            print(f"경고: {OLLAMA_MODEL} 없음 → ollama pull {OLLAMA_MODEL}")
            return
    except Exception as e:
        print(f"Ollama 연결 실패: {e}\nOllama가 실행 중인지 확인하세요.")
        return

    print("\n파일 목록 수집 중...")
    all_calls = scan_calls(VOICE_NAS_PATH)
    save_metadata_csv(all_calls)
    print(f"전체 통화 메타데이터 저장 → {METADATA_CSV} ({len(all_calls)}건, 수신+발신 전체)")

    all_files = collect_target_files(all_calls)
    target = [f for f in all_files if f["duration_sec"] >= MIN_DURATION]
    skipped = len(all_files) - len(target)
    print(f"대상({DIRECTION}, {TARGET_NUMBER}번): {len(all_files)}개 | 처리 대상: {len(target)}개 | {MIN_DURATION}초 미만 스킵: {skipped}개")

    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            ckpt = json.load(f)
        done_set = set(ckpt.get("done_files", []))
        all_results = ckpt.get("results", [])
        print(f"체크포인트 복원: {len(done_set)}개 완료")
    else:
        done_set = set()
        all_results = []

    todo = [f for f in target if f["filepath"] not in done_set]
    print(f"남은 처리: {len(todo)}개\n")

    if not todo:
        print("모든 파일 처리 완료.")
        print_summary(all_results)
        return

    print(f"Whisper 모델 로딩 ({MODEL_SIZE})...")
    whisper_model = WhisperModel(MODEL_SIZE, device="cpu",
                                  compute_type="int8", cpu_threads=CPU_THREADS)
    print("Whisper 로딩 완료\n")

    total = len(todo)
    start_time = datetime.now()

    for i, row in enumerate(todo, 1):
        result = {
            "file_name": row["filename"],
            "folder": row["folder"],
            "direction": row["direction"],
            "duration_sec": row["duration_sec"],
            "label": "",
            "reason": "",
            "summary": "",
            "transcript": "",
            "speaker_dialogue": [],
            "qa_pairs": [],
        }

        try:
            transcript = transcribe(whisper_model, row["filepath"])
        except Exception as e:
            transcript = ""
            print(f"[STT 에러] {row['filename']}: {e}")
        result["transcript"] = transcript

        if transcript:
            try:
                analysis = analyze_with_ollama(transcript)
                result.update(analysis)
            except Exception as e:
                result["label"] = "불명확"
                print(f"[Ollama 에러] {row['filename']}: {e}")
        else:
            result["label"] = "불명확 (전사없음)"

        all_results.append(result)
        done_set.add(row["filepath"])

        elapsed = (datetime.now() - start_time).total_seconds()
        per_file = elapsed / i if i > 0 else 0
        remaining = per_file * (total - i)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{i:4d}/{total}] {result['label']:<6} "
              f"| {elapsed/60:5.1f}분 경과 | 남은예상 {remaining/60:.0f}분 "
              f"| {row['filename'][:50]}")

        if i % SAVE_EVERY == 0 or i == total:
            save_results(all_results, done_set)
            print(f"         → 저장 완료 ({len(all_results)}건 / done {len(done_set)}건)")

    print_summary(all_results)


if __name__ == "__main__":
    main()
