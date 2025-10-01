import os, glob, json, random, uuid
from typing import List, Tuple
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
import requests

# ── env
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
EMBED_URL = os.getenv("EMBED_URL")
COLLECTION = os.getenv("COLLECTION", "ipraw_db")

# ── clients
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def embed_batch(texts: List[str], timeout=120) -> List[List[float]]:
    r = requests.post(f"{EMBED_URL}/embed", json={"texts": texts}, timeout=timeout)
    r.raise_for_status()
    return r.json()["embeddings"]

def list_files(base: str, kind: str, sub: str, split: str) -> List[str]:
    """kind/sub(split)/files → 존재하는 경로만"""
    pat = os.path.join(base, kind, sub, split, "*.json")
    return sorted(glob.glob(pat))

def sample_by_sources(base: str, kind: str, split: str, sources: List[str], per_source: int) -> List[Tuple[str, str, str, str]]:
    """
    반환: (path, kind, subkind, split) 리스트
    """
    picked = []
    for sub in sources:
        files = list_files(base, kind, sub, split)
        if len(files) == 0:
            print(f"[warn] no files: {kind}/{sub}/{split}")
            continue
        n = min(per_source, len(files))
        chosen = random.sample(files, n) if len(files) > n else files
        picked.extend((p, kind, sub, split) for p in chosen)
        if len(files) < per_source:
            print(f"[warn] {kind}/{sub}/{split} {len(files)}개만 존재 (요청 {per_source})")
    return picked

def load_doc(fp: str) -> dict:
    with open(fp, encoding="utf-8") as f:
        return json.load(f)

def to_text_for_embed(doc: dict) -> str:
    info = doc.get("info", {})
    task = doc.get("taskinfo", {})
    title = info.get("title", "") or ""
    output = task.get("output", "") or ""
    return f"[제목] {title}\n[요약] {output}"

def to_payload(doc: dict, kind: str, subkind: str, split: str) -> dict:
    info = doc.get("info", {})
    task = doc.get("taskinfo", {})
    return {
        "doc_id": info.get("doc_id"),
        "response_institute": info.get("document_type"),
        "response_date": info.get("decision_date"),
        "title": info.get("title"),
        "sentences": task.get("sentences"),
        "kind": kind,           # decision / judgment / statute / ...
        "subkind": subkind,     # qa / summary
        "split": split,         # train / val
    }

def batch(iterable, size):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf

def main():
    base = "unzip_data/ip/dataset"
    kinds = ["judgment", "statute", "trial_decision", "decision", "interpretation"]

    # 요구사항:
    # - statute: qa만 존재 → qa에서 train 500 + val 500
    # - 그 외: qa, summary 각각에서 train 500 + val 500 → 총 2,000/종류
    plan = {}
    for k in kinds:
        if k == "statute":
            plan[k] = {"sources": ["qa"], "per_source": 500}
        else:
            plan[k] = {"sources": ["qa", "summary"], "per_source": 500}

    # 수집 대상 파일 나열
    tasks: List[Tuple[str, str, str, str]] = []  # (path, kind, subkind, split)
    for k in kinds:
        sources = plan[k]["sources"]
        per_source = plan[k]["per_source"]
        for split in ["train", "val"]:
            picks = sample_by_sources(base, k, split, sources, per_source)
            tasks.extend(picks)

    print(f"[info] total selected files = {len(tasks)}")

    # ---- 업서트: 임베딩을 배치로, 업서트도 배치로
    BATCH_EMBED = 64
    BATCH_UPSERT = 256

    to_upsert: List[PointStruct] = []
    for task_batch in batch(tasks, BATCH_EMBED):
        # 1) 로드 & 임베딩 입력 준비
        docs = []
        texts = []
        metas = []
        for (path, kind, sub, split) in task_batch:
            try:
                d = load_doc(path)
                docs.append(d)
                texts.append(to_text_for_embed(d))
                metas.append((kind, sub, split))
            except Exception as e:
                print(f"[err] load {path}: {e}")

        # 2) 임베딩
        try:
            vectors = embed_batch(texts)
        except Exception as e:
            print(f"[err] embed batch failed ({len(texts)} docs): {e}")
            continue

        # 3) PointStruct 생성
        for d, vec, meta in zip(docs, vectors, metas):
            kind, sub, split = meta
            payload = to_payload(d, kind, sub, split)
            to_upsert.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload=payload
            ))

        # 4) 업서트 (적당한 크기로 쪼개서)
        for up_batch in batch(to_upsert, BATCH_UPSERT):
            try:
                qdrant.upsert(collection_name=COLLECTION, points=up_batch)
                print(f"[ok] upserted {len(up_batch)} points (total so far)")
            except Exception as e:
                print(f"[err] upsert batch ({len(up_batch)}): {e}")
            finally:
                # 비운 것만 제거
                to_upsert = to_upsert[len(up_batch):]

    print("[done] 업서트 완료")

if __name__ == "__main__":
    main()
