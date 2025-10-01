# upsert_patent_db.py
# 목적: 특허 JSON들을 임베딩 → Qdrant의 patent_db 컬렉션으로 업서트
# 입력 폴더 예: unzip_data/patent/dataset/train/<각기다른_카테고리명>/.../*.json
# - split: train, val (둘 다 있으면 처리, 없으면 있는 것만 처리)
# - source: split 바로 하위의 1-레벨 디렉토리명을 소스로 간주하여, 소스별 최대 N개 샘플링
# 임베딩 포맷:
#   [발명의명칭] {invention_title}
#   [요약] {abstract}
#   [주요키워드] {keyword_csv}
# 메타데이터(payload): register_date, open_date, application_date, documentId, title, claims (+ split, source, path)

import os, glob, json, random, uuid, time
from typing import List, Dict, Any, Iterable, Tuple
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
import requests

# ── env
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8000")
COLLECTION = os.getenv("COLLECTION", "patent_db")
BASE_DIR = os.getenv("PATENT_BASE", "unzip_data/patent/dataset")
PER_SOURCE = int(os.getenv("PER_SOURCE", "500"))  # 소스(폴더)당 최대 개수
BATCH_EMBED = int(os.getenv("BATCH_EMBED", "64"))
BATCH_UPSERT = int(os.getenv("BATCH_UPSERT", "256"))
SEED = int(os.getenv("SEED", "42"))

random.seed(SEED)

# ── clients
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# ── helpers

def ping_embed() -> bool:
    try:
        r = requests.get(f"{EMBED_URL}/ping", timeout=8)
        return r.ok and r.json().get("status") == "ok"
    except Exception:
        return False


def embed_batch(texts: List[str], timeout=120, max_retries=3, backoff=2.0) -> List[List[float]]:
    """임베딩 서버 배치 호출 (간단한 재시도 포함)."""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(f"{EMBED_URL}/embed", json={"texts": texts}, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if "embeddings" not in data:
                raise RuntimeError("/embed 응답에 'embeddings' 없음")
            return data["embeddings"]
        except Exception as e:
            if attempt >= max_retries:
                raise
            sleep_s = backoff ** attempt
            print(f"[warn] embed retry {attempt}/{max_retries} after error: {e} → sleep {sleep_s:.1f}s")
            time.sleep(sleep_s)


def list_sources(split_dir: str) -> List[str]:
    """split 바로 하위의 1-레벨 디렉토리들을 소스로 간주."""
    if not os.path.isdir(split_dir):
        return []
    subs = [d for d in glob.glob(os.path.join(split_dir, "*")) if os.path.isdir(d)]
    subs.sort()
    return subs


def list_jsons_in_dir(dirpath: str) -> List[str]:
    return sorted(glob.glob(os.path.join(dirpath, "**", "*.json"), recursive=True))


def pick_files_per_source(split_dir: str, per_source: int) -> List[Tuple[str, str]]:
    """각 소스(폴더)에서 최대 per_source개 샘플링.
    반환: (filepath, source_name)
    """
    picked: List[Tuple[str, str]] = []
    for source_dir in list_sources(split_dir):
        source_name = os.path.basename(source_dir)
        files = list_jsons_in_dir(source_dir)
        if not files:
            print(f"[warn] empty source: {source_name}")
            continue
        n = min(per_source, len(files))
        chosen = random.sample(files, n) if len(files) > n else files
        picked.extend((p, source_name) for p in chosen)
        if len(files) < per_source:
            print(f"[warn] {source_name}: {len(files)}개만 존재 (요청 {per_source})")
    return picked


def load_doc(fp: str) -> Dict[str, Any]:
    with open(fp, encoding="utf-8") as f:
        obj = json.load(f)
    # 특허 JSON은 보통 {"dataset": {...}} 래핑이 있으므로 풀어서 반환
    if isinstance(obj, dict) and "dataset" in obj and isinstance(obj["dataset"], dict):
        return obj["dataset"]
    return obj


def norm_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        return ", ".join(map(str, x))
    return str(x)


def build_embed_text(pat: Dict[str, Any]) -> str:
    title = norm_str(pat.get("invention_title") or pat.get("title"))
    abstract = norm_str(pat.get("abstract"))
    keyword = pat.get("keyword")
    if isinstance(keyword, (list, tuple)):
        keyword_csv = ", ".join(map(str, keyword))
    elif keyword is None:
        keyword_csv = ""
    else:
        keyword_csv = str(keyword)
    return f"[발명의명칭] {title}\n[요약] {abstract}\n[주요키워드] {keyword_csv}"


def build_payload(pat: Dict[str, Any], *, split: str, source: str, path: str) -> Dict[str, Any]:
    payload = {
        "documentId": pat.get("documentId"),
        "title": pat.get("invention_title") or pat.get("title"),
        "claims": pat.get("claims"),
        "register_date": pat.get("register_date"),
        "open_date": pat.get("open_date"),
        "application_date": pat.get("application_date"),
        # 추적/디버깅용
        "split": split,
        "source": source,
        "path": path.replace("\\", "/"),
    }
    # 필요 시 확장: ipc_* 등 추가 가능
    return payload


def batched(it: Iterable[Any], size: int) -> Iterable[List[Any]]:
    buf: List[Any] = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def main():
    if not ping_embed():
        raise SystemExit(f"[err] 임베딩 서버 ping 실패: {EMBED_URL}")

    total_files = 0
    tasks: List[Tuple[str, str, str]] = []  # (filepath, split, source)
    for split in ("train", "val"):
        split_dir = os.path.join(BASE_DIR, split)
        picks = pick_files_per_source(split_dir, PER_SOURCE)
        tasks.extend((fp, split, src) for fp, src in picks)
        total_files += len(picks)
        print(f"[info] {split}: picked {len(picks)} files from {len(list_sources(split_dir))} sources")

    if total_files == 0:
        raise SystemExit(f"[err] 선택된 파일이 없습니다. BASE_DIR 확인: {BASE_DIR}")

    print(f"[info] total selected files = {total_files}")

    pending: List[PointStruct] = []
    processed = 0

    for task_batch in batched(tasks, BATCH_EMBED):
        docs: List[Dict[str, Any]] = []
        texts: List[str] = []
        metas: List[Tuple[str, str, str]] = []  # (split, source, path)

        # 1) 로드 & 텍스트 구성
        for fp, split, src in task_batch:
            try:
                pat = load_doc(fp)
                txt = build_embed_text(pat)
                docs.append(pat)
                texts.append(txt)
                metas.append((split, src, fp))
            except Exception as e:
                print(f"[err] load {fp}: {e}")

        if not texts:
            continue

        # 2) 임베딩
        try:
            vecs = embed_batch(texts)
        except Exception as e:
            print(f"[err] embed failed for batch({len(texts)}): {e}")
            continue

        # 3) PointStruct 생성
        for pat, vec, (split, src, fp) in zip(docs, vecs, metas):
            payload = build_payload(pat, split=split, source=src, path=fp)
            point = PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload)
            pending.append(point)

        # 4) 업서트(배치)
        for up_batch in batched(pending, BATCH_UPSERT):
            try:
                qdrant.upsert(collection_name=COLLECTION, points=up_batch)
                processed += len(up_batch)
                print(f"[ok] upserted {len(up_batch)} (total={processed})")
            except Exception as e:
                print(f"[err] upsert batch ({len(up_batch)}): {e}")
            finally:
                # 사용한 만큼 비우기
                pending = pending[len(up_batch):]

    print(f"[done] 업서트 완료: total={processed}")


if __name__ == "__main__":
    main()
