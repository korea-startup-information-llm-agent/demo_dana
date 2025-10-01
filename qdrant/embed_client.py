import requests, time, os
from typing import List

EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8000")

class EmbedClient:
    def __init__(self, base: str | None = None, timeout: int = 30):
        self.base = base or EMBED_URL
        self.timeout = timeout

    def ping(self) -> bool:
        try:
            r = requests.get(f"{self.base}/ping", timeout=5)
            return r.ok and r.json().get("status") == "ok"
        except Exception:
            return False

    def embed(self, texts: List[str]) -> List[List[float]]:
        for attempt in range(3):
            try:
                r = requests.post(f"{self.base}/embed", json={"texts": texts}, timeout=self.timeout)
                r.raise_for_status()
                return r.json()["embeddings"]
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
