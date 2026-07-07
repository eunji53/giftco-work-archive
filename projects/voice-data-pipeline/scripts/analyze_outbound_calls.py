"""
기프트코 음성데이터 배치 분석 스크립트 — 발신 통화
- 대상: 401 발신 통화 (상담원 → 외부)
- 1단계: 통화 유형 분류 (고객콜백 / 공급업체 / 기타)
- 2단계: 유형별 상세 분석
    · 고객콜백 → callback_reason/resolution_status/customer_sentiment/QA 추출
    · 공급업체 → 재고·가격·발주 중심 상세 분석
- STT: faster-whisper small (로컬)
- LLM: Ollama qwen2.5:3b (로컬)
- 실행: scripts/ 폴더 안에서 python analyze_outbound_calls.py
- 중단 후 재시작: 동일 명령어 재실행 (체크포인트 자동 복원)
- notebooks/03_analyze_outbound_calls.ipynb와 같은 데이터 폴더(../data/outbound/)를 공유합니다.
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

DATA_DIR = Path(__file__).parent / "../data/outbound"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 수신+발신 전체 메타데이터라 inbound/outbound 공용 위치(data/ 바로 아래)에 저장 (01/03 노트북과 동일 파일 공유)
METADATA_CSV = Path(__file__).parent / "../data/call_metadata.csv"
CHECKPOINT_FILE = DATA_DIR / "outbound_call_checkpoint.json"
OUTPUT_CSV = DATA_DIR / "outbound_call_classification.csv"
OUTPUT_JSON = DATA_DIR / "outbound_call_classification.json"

TARGET_NUMBER = "401"
DIRECTION = "발신"
MIN_DURATION = 10           # 초 미만 스킵

MODEL_SIZE = "small"        # tiny / base / small
CPU_THREADS = 4
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
MAX_CHARS = 1800
SAVE_EVERY = 20
# ═══════════════════════════════════════════

VALID_TYPES = {"고객콜백", "공급업체", "기타"}


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
    scripts/analyze_inbound_calls.py의 scan_calls()와 동일한 범위(수신+발신 전체)입니다.
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
        if info["direction"] != DIRECTION:
            continue
        if info["caller"] != TARGET_NUMBER:
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


# qwen2.5는 중국어 모델 특성상 한국어 프롬프트에도 중국어가 섞여 나올 수 있어, 언어 강제 문구 + 감지 후 재시도로 방어합니다.
LANG_GUARD = (
    "!!! IMPORTANT: You MUST respond ONLY in Korean (한국어). "
    "중국어(Chinese) 사용 절대 금지. 영어도 사용하지 마세요. "
    "모든 텍스트 필드 값은 반드시 한국어로만 작성하세요. !!!"
)
HAS_CHINESE_RE = re.compile(r"[一-鿿㐀-䶿]")


def has_chinese(text: str) -> bool:
    return bool(HAS_CHINESE_RE.search(text))


# ───────────────────────────────────────────
# 1단계: 유형 분류 (고객콜백 / 공급업체 / 기타)
# ───────────────────────────────────────────
def build_type_prompt(transcript: str) -> str:
    return f"""{LANG_GUARD}

기프트코(판촉물 판매 사이트) 상담원이 외부로 건 발신 통화입니다.
반드시 한국어로만 답변하세요. Do not use Chinese or any other language.

【핵심 판단 기준: 상대방이 누구인가?】

상대방이 공급사·제조사·도매업체 직원이면 → "공급업체"
  · 기프트코에 상품을 납품하는 업체
  · 상담원이 재고·단가·납기·발주·인쇄조건 등을 확인하려 전화
  · 상대방이 "저희 상품", "저희 단가", "납기" 같은 공급자 표현 사용
  · 사이트 등록 단가·상품 정보 확인 (예: "단가 맞나요?", "등록 정보 확인")

상대방이 구매 고객·의뢰인이면 → "고객콜백"
  · 기프트코에서 상품을 사려는 일반 소비자 또는 구매 담당자
  · 상담원이 이전 문의에 답변하거나 주문·배송·결제를 처리하려 전화
  · 상대방이 "주문했는데", "언제 오나요" 같은 구매자 표현 사용

위 두 가지에 해당하지 않으면 → "기타"
  · 잘못 건 전화, 업무 무관, STT 불량, 판단 불가

규칙: JSON만 반환. 마크다운/코드블록 없이. 모든 텍스트 값은 반드시 한국어로 작성.

JSON:
{{"call_type":"고객콜백|공급업체|기타","reason":"상대방 역할 근거 한 줄"}}

전사문:
\"\"\"{transcript}\"\"\"
""".strip()


# ───────────────────────────────────────────
# 2단계 A: 고객콜백 상세 분석
# ───────────────────────────────────────────
def build_customer_prompt(transcript: str) -> str:
    return f"""{LANG_GUARD}

당신은 기프트코(판촉물 판매 사이트) 상담원의 고객 콜백 통화를 분석하는 전문가입니다.
반드시 한국어로만 답변하세요. Do not use Chinese or any other language.
기프트코는 판촉물(볼펜, 가방, 머그컵, 의류, 인쇄물 등)을 판매하는 B2B/B2C 사이트입니다.

이 통화는 상담원(기프트코)이 고객에게 직접 먼저 전화를 건 콜백입니다.

작업 목록 (모두 추출):
1. callback_reason — 상담원이 전화한 이유 (예: "배송 지연 안내", "견적 답변", "주문 확인", "결제 확인" 등)
2. resolution_status — 이번 통화에서 문제/문의가 해결됐는지 (해결/미해결/부분해결/불명확)
3. customer_sentiment — 고객의 반응/태도 (만족/중립/불만/불명확)
4. follow_up_needed — 추가 후속 조치 필요 여부 (true/false/null)
5. follow_up_detail — 후속 조치 내용 (없으면 null)
6. speaker_dialogue — 화자 구분 대화 [{{"speaker":"고객|상담원|불명","text":"내용"}}]
7. qa_pairs — 챗봇 학습용 QA 쌍. "이전 문의 → 이번 답변" 형태로 재구성. 실질적 내용만.
8. summary — 통화 전체 한 줄 요약

규칙: JSON만 반환. 마크다운/코드블록 없이. 모든 텍스트 값은 반드시 한국어로 작성.

JSON:
{{"callback_reason":"","resolution_status":"해결|미해결|부분해결|불명확","customer_sentiment":"만족|중립|불만|불명확","follow_up_needed":null,"follow_up_detail":null,"speaker_dialogue":[{{"speaker":"고객|상담원|불명","text":"내용"}}],"qa_pairs":[{{"question":"질문","answer":"답변"}}],"summary":"요약"}}

전사문:
\"\"\"{transcript}\"\"\"
""".strip()


# ───────────────────────────────────────────
# 2단계 B: 공급업체 통화 상세 분석
# ───────────────────────────────────────────
def build_supplier_prompt(transcript: str) -> str:
    return f"""{LANG_GUARD}

당신은 기프트코(판촉물 판매 사이트) 상담원과 공급업체 간의 통화를 분석하는 전문가입니다.
반드시 한국어로만 답변하세요. Do not use Chinese or any other language.
기프트코는 판촉물(볼펜, 가방, 머그컵, 의류, 인쇄물 등)을 판매하며, 상담원이 공급업체에 직접 전화해 재고·가격·납기 등을 확인합니다.

아래 항목을 모두 추출하세요.

1. supplier_name: 공급업체·업체명 (언급 없으면 null)
2. summary: 통화 전체 한 줄 요약
3. products: 언급된 상품 목록 (배열). 각 항목:
   - product_name: 상품명
   - quantity: 수량 (언급 없으면 null)
   - unit_price: 단가 (언급 없으면 null)
   - total_price: 총액 (언급 없으면 null)
   - stock_available: 재고 여부 (true/false/null)
   - delivery_date: 납기·배송 예정 (언급 없으면 null)
   - print_condition: 인쇄·제작 조건 (언급 없으면 null)
   - notes: 기타 특이사항
4. price_negotiation: 가격 협의 내용 요약 (없으면 null)
5. order_confirmed: 발주 확정 여부 (true/false/null)
6. issues: 문제점·이슈 (재고 없음, 납기 지연, 가격 이견 등. 없으면 null)
7. follow_up: 후속 조치 필요 사항 (없으면 null)
8. speaker_dialogue: 화자 구분 대화 [{{"speaker":"상담원|공급업체담당|불명","text":"내용"}}]

규칙: JSON만 반환. 마크다운/코드블록 없이. 모든 텍스트 값은 반드시 한국어로 작성.

JSON:
{{"supplier_name":null,"summary":"","products":[{{"product_name":"","quantity":null,"unit_price":null,"total_price":null,"stock_available":null,"delivery_date":null,"print_condition":null,"notes":""}}],"price_negotiation":null,"order_confirmed":null,"issues":null,"follow_up":null,"speaker_dialogue":[{{"speaker":"상담원|공급업체담당|불명","text":"내용"}}]}}

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


def normalize_call_type(raw: str) -> str:
    raw = (raw or "").strip()
    if raw in VALID_TYPES:
        return raw
    if "고객" in raw:
        return "고객콜백"
    if "공급" in raw:
        return "공급업체"
    return "기타"


def call_ollama(prompt: str, max_retries: int = 2) -> dict:
    """중국어 응답이 감지되면 최대 max_retries회 재시도합니다 (qwen2.5 계열의 알려진 이슈)."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    result, raw = {}, ""
    for attempt in range(max_retries + 1):
        resp = requests.post(OLLAMA_URL, json=payload, timeout=(30, 600))
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        result = safe_parse_json(raw)
        if not has_chinese(raw):
            return result
        if attempt < max_retries:
            print(f"         ⚠ 중국어 감지 → 재시도 ({attempt + 1}/{max_retries})")
    print("         ⚠ 재시도 후에도 중국어 포함 — 결과 그대로 사용")
    return result


def classify_call_type(transcript: str) -> tuple[str, str]:
    parsed = call_ollama(build_type_prompt(transcript[:MAX_CHARS]))
    return normalize_call_type(parsed.get("call_type", "")), parsed.get("reason", "")


def analyze_customer_callback(transcript: str) -> dict:
    parsed = call_ollama(build_customer_prompt(transcript[:MAX_CHARS]))
    dialogue = [d for d in parsed.get("speaker_dialogue", [])
                if isinstance(d, dict) and d.get("text")]
    qa_pairs = [q for q in parsed.get("qa_pairs", [])
                if isinstance(q, dict) and q.get("question") and q.get("answer")]
    return {
        "summary": parsed.get("summary", ""),
        "callback_reason": parsed.get("callback_reason", ""),
        "resolution_status": parsed.get("resolution_status", "불명확"),
        "customer_sentiment": parsed.get("customer_sentiment", "불명확"),
        "follow_up_needed": parsed.get("follow_up_needed"),
        "follow_up_detail": parsed.get("follow_up_detail"),
        "speaker_dialogue": dialogue,
        "qa_pairs": qa_pairs,
        # 공급업체 전용 필드는 빈값
        "supplier_name": None,
        "products": [],
        "price_negotiation": None,
        "order_confirmed": None,
        "issues": None,
        "follow_up": None,
    }


def analyze_supplier_call(transcript: str) -> dict:
    parsed = call_ollama(build_supplier_prompt(transcript[:MAX_CHARS]))
    dialogue = [d for d in parsed.get("speaker_dialogue", [])
                if isinstance(d, dict) and d.get("text")]
    products = [p for p in parsed.get("products", [])
                if isinstance(p, dict) and p.get("product_name")]
    return {
        "summary": parsed.get("summary", ""),
        "speaker_dialogue": dialogue,
        "supplier_name": parsed.get("supplier_name"),
        "products": products,
        "price_negotiation": parsed.get("price_negotiation"),
        "order_confirmed": parsed.get("order_confirmed"),
        "issues": parsed.get("issues"),
        "follow_up": parsed.get("follow_up"),
        # 고객콜백 전용 필드는 빈값
        "callback_reason": "",
        "resolution_status": "",
        "customer_sentiment": "",
        "follow_up_needed": None,
        "follow_up_detail": None,
        "qa_pairs": [],
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
        products = r.get("products", [])
        products_text = "\n\n".join(
            (
                f"[상품 {i}]\n"
                f"상품명: {p.get('product_name', '')}\n"
                f"수량: {p.get('quantity', '')}\n"
                f"단가: {p.get('unit_price', '')}\n"
                f"총액: {p.get('total_price', '')}\n"
                f"재고: {'있음' if p.get('stock_available') is True else '없음' if p.get('stock_available') is False else '미확인'}\n"
                f"납기: {p.get('delivery_date', '')}\n"
                f"인쇄조건: {p.get('print_condition', '')}\n"
                f"비고: {p.get('notes', '')}"
            )
            for i, p in enumerate(products, 1)
        )
        csv_rows.append({
            "file_name": r["file_name"],
            "folder": r["folder"],
            "duration_sec": r["duration_sec"],
            "call_type": r["call_type"],
            "call_type_reason": r.get("call_type_reason", ""),
            "summary": r.get("summary", ""),
            "callback_reason": r.get("callback_reason") or "",
            "resolution_status": r.get("resolution_status") or "",
            "customer_sentiment": r.get("customer_sentiment") or "",
            "follow_up_needed": "" if r.get("follow_up_needed") is None
                                  else ("필요" if r["follow_up_needed"] else "불필요"),
            "follow_up_detail": r.get("follow_up_detail") or "",
            "supplier_name": r.get("supplier_name") or "",
            "products_text": products_text,
            "product_count": len(products),
            "price_negotiation": r.get("price_negotiation") or "",
            "order_confirmed": "" if r.get("order_confirmed") is None
                                  else ("확정" if r["order_confirmed"] else "미확정"),
            "issues": r.get("issues") or "",
            "follow_up": r.get("follow_up") or "",
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
    types = Counter(r["call_type"] for r in all_results)
    total = len(all_results)

    print("\n" + "=" * 50)
    print("[ 발신 통화 분석 결과 ]")
    print("=" * 50)
    for t, cnt in sorted(types.items()):
        print(f"  {t:<10}: {cnt:>5}개  ({cnt/total*100:.1f}%)")
    print(f"  {'합계':<10}: {total:>5}개")

    callbacks = [r for r in all_results if r["call_type"] == "고객콜백"]
    suppliers = [r for r in all_results if r["call_type"] == "공급업체"]
    qa_total = sum(len(r.get("qa_pairs", [])) for r in callbacks)
    prod_total = sum(len(r.get("products", [])) for r in suppliers)
    confirmed = sum(1 for r in suppliers if r.get("order_confirmed") is True)
    issues_cnt = sum(1 for r in suppliers if r.get("issues"))

    print(f"\n고객콜백: {len(callbacks)}개 | 생성된 QA: {qa_total}개")
    print(f"공급업체: {len(suppliers)}개 | 상품 언급: {prod_total}건 | "
          f"발주확정: {confirmed}건 | 이슈: {issues_cnt}건")
    print(f"\n결과 파일: {OUTPUT_CSV}")
    print(f"           {OUTPUT_JSON}")


def main():
    print("=" * 50)
    print("기프트코 음성데이터 배치 분석 — 발신 통화")
    print(f"대상: {DIRECTION} 통화 ({TARGET_NUMBER}번 발신)")
    print("분류: 고객콜백 / 공급업체 / 기타")
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
        # NAS 연결이 끊겨 파일을 못 찾는 경우: 완료 처리하지 않고 건너뛰어 다음 실행 때 재시도되게 함
        if not os.path.exists(row["filepath"]):
            print(f"[파일없음 스킵] {row['filename']} — 네트워크 연결 확인 후 재실행하세요.")
            continue

        result = {
            "file_name": row["filename"],
            "folder": row["folder"],
            "duration_sec": row["duration_sec"],
            "call_type": "",
            "call_type_reason": "",
            "summary": "",
            "transcript": "",
            "speaker_dialogue": [],
            "qa_pairs": [],
            "callback_reason": "",
            "resolution_status": "",
            "customer_sentiment": "",
            "follow_up_needed": None,
            "follow_up_detail": None,
            "supplier_name": None,
            "products": [],
            "price_negotiation": None,
            "order_confirmed": None,
            "issues": None,
            "follow_up": None,
        }

        try:
            transcript = transcribe(whisper_model, row["filepath"])
        except Exception as e:
            transcript = ""
            print(f"[STT 에러] {row['filename']}: {e}")
        result["transcript"] = transcript

        if not transcript:
            result["call_type"] = "기타"
            result["call_type_reason"] = "STT 전사 없음"
            all_results.append(result)
            done_set.add(row["filepath"])
            _print_progress(i, total, start_time, result)
            _auto_save(i, total, all_results, done_set)
            continue

        # 1단계: 유형 분류
        try:
            call_type, ct_reason = classify_call_type(transcript)
        except Exception as e:
            call_type, ct_reason = "기타", f"분류 에러: {e}"
            print(f"[유형분류 에러] {row['filename']}: {e}")

        result["call_type"] = call_type
        result["call_type_reason"] = ct_reason

        # 2단계: 유형별 상세 분석
        try:
            if call_type == "고객콜백":
                result.update(analyze_customer_callback(transcript))
            elif call_type == "공급업체":
                result.update(analyze_supplier_call(transcript))
            # 기타 → 추가 분석 없음 (reason만)
        except Exception as e:
            print(f"[분석 에러] {row['filename']}: {e}")

        all_results.append(result)
        done_set.add(row["filepath"])

        _print_progress(i, total, start_time, result)
        _auto_save(i, total, all_results, done_set)

    print_summary(all_results)


def _print_progress(i: int, total: int, start_time: datetime, result: dict):
    elapsed = (datetime.now() - start_time).total_seconds()
    per_file = elapsed / i if i > 0 else 0
    remaining = per_file * (total - i)
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{i:4d}/{total}] {result['call_type']:<10} "
          f"| {elapsed/60:5.1f}분 경과 | 남은예상 {remaining/60:.0f}분 "
          f"| {result['file_name'][:45]}")


def _auto_save(i: int, total: int, all_results: list, done_set: set):
    if i % SAVE_EVERY == 0 or i == total:
        save_results(all_results, done_set)
        print(f"         → 저장 완료 ({len(all_results)}건 / done {len(done_set)}건)")


if __name__ == "__main__":
    main()
