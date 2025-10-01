# init_ipraw_db.py
# 목적: 임베딩 차원 자동 추론 → Qdrant Cloud/로컬에 ipraw_db 컬렉션 및 인덱스 생성

import os, sys, time
from dotenv import load_dotenv
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PayloadSchemaType

# ── env 로드
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # Cloud면 필수
EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8000")
COLLECTION = os.getenv("COLLECTION", "ipraw_db")

def ping_embed() -> bool:
    try:
        r = requests.get(f"{EMBED_URL}/ping", timeout=5)
        return r.ok and r.json().get("status") == "ok"
    except Exception:
        return False

def infer_dim() -> int:
    r = requests.post(f"{EMBED_URL}/embed", json={"texts": ["dim probe"]}, timeout=15)
    r.raise_for_status()
    emb = r.json()["embeddings"][0]
    if not isinstance(emb, list) or not emb:
        raise RuntimeError("임베딩 응답 형식이 올바르지 않습니다.")
    return len(emb)

def ensure_collection(client: QdrantClient, name: str, dim: int):
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        print(f"[ok] collection '{name}' already exists")
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"[ok] created collection '{name}' (dim={dim}, metric=cosine)")

def ensure_payload_indexes(client: QdrantClient, name: str):
    # 자주 필터링할 필드 인덱싱
    fields = [
        ("kind", PayloadSchemaType.KEYWORD),
        ("split", PayloadSchemaType.KEYWORD),
        ("response_institute", PayloadSchemaType.KEYWORD),
        ("response_date", PayloadSchemaType.KEYWORD),
    ]
    for field, schema in fields:
        try:
            client.create_payload_index(collection_name=name, field_name=field, field_schema=schema)
            print(f"[ok] payload index created: {field}")
        except Exception as e:
            # 이미 있으면 건너뜀
            print(f"[skip] index {field}: {e}")

def main():
    print(f"[info] QDRANT_URL={QDRANT_URL}")
    print(f"[info] COLLECTION={COLLECTION}")
    if not ping_embed():
        print(f"[err] 임베딩 서버 ping 실패: {EMBED_URL}")
        sys.exit(1)

    try:
        dim = infer_dim()
        print(f"[info] inferred embedding dim = {dim}")
    except Exception as e:
        print("[err] 임베딩 차원 추론 실패:", e)
        sys.exit(1)

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    ensure_collection(client, COLLECTION, dim)
    ensure_payload_indexes(client, COLLECTION)
    print("[done] ipraw_db 초기화 완료")

if __name__ == "__main__":
    main()
