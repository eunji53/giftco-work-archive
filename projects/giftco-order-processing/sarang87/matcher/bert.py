# -*- coding: utf-8 -*-
"""
판촉사랑(87sarang) 구매처명 매칭 - BERT(KR-SBERT) 상품명 유사도 관련 함수.

02_match_buyer_names.py(운영 스크립트)에서 분리되었습니다.
임베딩 캐시(_embedding_cache)와 로딩된 모델(bert_model)은 이 모듈 안에 캡슐화합니다.
"""

import pickle

from .config import *  # noqa: F401,F403 (설정값은 matcher/config.py에서 관리)
from .logging_setup import log
from .normalize import clean_text


def check_cuda_or_raise():
    """torch CUDA 사용 가능 여부를 확인합니다. GPU가 없으면 중단합니다."""
    try:
        import torch
    except ImportError as exc:
        raise ImportError(
            "GPU BERT를 사용하려면 torch 설치가 필요합니다. "
            "예: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126"
        ) from exc

    log("torch version:", torch.__version__)
    log("torch CUDA build:", torch.version.cuda)
    log("cuda available:", torch.cuda.is_available())

    if not torch.cuda.is_available():
        message = (
            "CUDA GPU를 사용할 수 없습니다.\n"
            "현재 선택한 VS Code 커널이 GPU 지원 torch를 사용하지 않거나, NVIDIA 드라이버/CUDA 환경이 맞지 않습니다.\n"
            "커널이 'Python 3.11 (work GPU)' 또는 work 환경으로 잡혀 있는지 확인하세요."
        )
        if REQUIRE_CUDA_GPU:
            raise RuntimeError(message)
        log(message)
        return "cpu"

    log("GPU:", torch.cuda.get_device_name(0))
    return "cuda"

bert_model = None

def load_embedding_cache():
    """디스크에 저장된 임베딩 캐시를 불러옵니다. {모델명: {상품명: 임베딩}} 구조라 모델을 바꿔도 안 섞입니다."""
    if EMBEDDING_CACHE_FILE.exists():
        try:
            with open(EMBEDDING_CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            log(
                "임베딩 캐시 불러옴:", EMBEDDING_CACHE_FILE,
                f"(모델 {BERT_MODEL_NAME} 캐시 {len(cache.get(BERT_MODEL_NAME, {}))}건)",
            )
            return cache
        except Exception as exc:
            log("임베딩 캐시를 불러오지 못해 새로 시작합니다:", exc)
    return {}


def save_embedding_cache():
    """임베딩 캐시를 디스크에 저장합니다. 중간에 멈춰도 이미 계산한 임베딩은 다시 계산하지 않도록 합니다."""
    EMBEDDING_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMBEDDING_CACHE_FILE, "wb") as f:
        pickle.dump(_embedding_cache, f)


_embedding_cache = load_embedding_cache()

def get_bert_model():
    """SentenceTransformer 모델을 최초 1회만 로드합니다."""
    global bert_model
    if bert_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "BERT 상품명 유사도를 사용하려면 sentence-transformers 설치가 필요합니다. "
                "노트북에서 `pip install sentence-transformers` 실행 후 다시 실행하세요."
            ) from exc

        device = check_cuda_or_raise() if BERT_DEVICE == "cuda" else BERT_DEVICE
        log("BERT 모델 로딩 중:", BERT_MODEL_NAME)
        log("BERT device:", device)
        bert_model = SentenceTransformer(BERT_MODEL_NAME, device=device)
        log("BERT 모델 로딩 완료")
    return bert_model

def get_product_embedding(text):
    """상품명 1개를 embedding으로 변환하고 cache로 재사용합니다(모델별로 디스크에도 저장)."""
    text = clean_text(text)
    if not text:
        return None

    model_cache = _embedding_cache.setdefault(BERT_MODEL_NAME, {})
    if text in model_cache:
        return model_cache[text]

    model = get_bert_model()
    emb = model.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    model_cache[text] = emb
    return emb

def cosine_sim(a, b):
    if a is None or b is None:
        return -1.0
    return float(a @ b)

def find_bert_product_candidates(query_product, candidate_indexes, dftr_work, sort_trade_indexes, threshold=None):
    """같은 중분류+소분류+날짜 후보 안에서만 BERT 유사도 비교.

    dftr_work, sort_trade_indexes는 호출하는 스크립트(02_match_buyer_names.py)의
    거래데이터 작업용 DataFrame과 정렬 함수를 그대로 받아서 씁니다.

    반환값:
    - bert_indexes: threshold 이상 후보 index 목록
    - bert_scores: {거래데이터 index: 유사도 점수}
    """
    threshold = BERT_SIM_THRESHOLD if threshold is None else threshold
    query_product = clean_text(query_product)
    candidate_indexes = sort_trade_indexes(list(dict.fromkeys(candidate_indexes)))

    if not USE_BERT_PRODUCT_SIMILARITY:
        return [], {}

    if not query_product or not candidate_indexes:
        return [], {}

    # BERT 후보 수 제한 없음:
    # 이미 중분류+소분류+날짜 조건으로 후보를 줄였으므로,
    # 해당 날짜 후보 전체를 대상으로 상품명 유사도를 계산합니다.

    q_emb = get_product_embedding(query_product)
    scored = []
    score_map = {}

    for idxtr in candidate_indexes:
        cand_product = clean_text(dftr_work.at[idxtr, "_key_product_relaxed"]) or clean_text(dftr_work.at[idxtr, "_key_product_exact"]) or clean_text(dftr_work.at[idxtr, "_key_product_raw"])
        if not cand_product:
            continue

        c_emb = get_product_embedding(cand_product)
        score = cosine_sim(q_emb, c_emb)
        score_map[idxtr] = score

        if score >= threshold:
            scored.append((idxtr, score))

    # 유사도 높은 순서, 같으면 거래데이터 원본 순서
    scored.sort(key=lambda x: (-x[1], dftr_work.at[x[0], "_trade_order"]))

    return [idx for idx, score in scored], score_map
