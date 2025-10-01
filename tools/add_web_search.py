# C:\dana\demo_dana\tools\add_web_search.py
import json, os, random, re

SRC = r"C:\dana\demo_dana\data\sft\train.jsonl"
OUT_MIX = r"C:\dana\demo_dana\data\sft\train_mixed.jsonl"
OUT_SYN = r"C:\dana\demo_dana\data\sft\web_search_synth.jsonl"

SYS_PROMPT = ('You are a routing model for an IP/patent assistant. '
              'Output JSON only: {"intent","action","jurisdiction","confidence"}. '
              'If unsure or evidence is needed, choose action="retrieve". '
              'If query likely needs up-to-date market/news/policy/spec info or internal DB may not contain it, choose action="web_search".')

TEMPLATES = [
    "2025년 {topic} 관련 최신 {kind} 변경사항 요약해줘.",
    "이번 달 발표된 {org}의 {kind} 공지 핵심만 알려줘.",
    "어제 나온 {product} {kind} 내용을 정리해줘.",
    "{country}에서 최근 개정된 {law} 이슈 업데이트 있어?",
    "최근 {org} 보도자료로 확인된 {topic} 동향을 알려줘.",
]
TOPICS = ["PCT 수수료", "상표 출원 수수료", "디자인 심사 기준", "직무발명 보상", "AI 관련 특허 심사 가이드라인",
          "특허료 감면", "우선심사 요건", "공지예외 요건", "분할출원 절차", "전자출원 시스템"]
KINDS = ["정책", "가이드라인", "뉴스", "공지", "요율", "업데이트"]
ORGS = ["WIPO", "USPTO", "KIPO", "EPO"]
PRODUCTS = ["KIPOnet", "Patentscope", "PAIR", "Patent Center"]
COUNTRIES = ["미국(US)", "한국(KR)", "유럽(EU)", "WIPO"]
LAWS = ["특허법", "상표법", "디자인보호법"]

def synth(n=200, seed=42):
    random.seed(seed)
    out = []
    for _ in range(n):
        t = random.choice(TEMPLATES)
        msg = t.format(
            topic=random.choice(TOPICS),
            kind=random.choice(KINDS),
            org=random.choice(ORGS),
            product=random.choice(PRODUCTS),
            country=random.choice(COUNTRIES),
            law=random.choice(LAWS),
        )
        # jurisdiction 힌트 간단 추정
        jur = "WIPO" if "WIPO" in msg else ("US" if "USPTO" in msg or "미국" in msg else ("KR" if "한국" in msg or "KIPO" in msg else "unknown"))
        resp = json.dumps({"intent":"patent_info","action":"web_search","jurisdiction":jur,"confidence":0.65}, ensure_ascii=False)
        out.append({
            "messages":[
                {"role":"system","content":SYS_PROMPT},
                {"role":"user","content":msg}
            ],
            "response": resp
        })
    return out

def count_web_search(path):
    ws = 0; total = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s: continue
            total += 1
            try:
                obj = json.loads(s)
                r = json.loads(obj["response"])
                if r.get("action") == "web_search":
                    ws += 1
            except Exception:
                pass
    return ws, total

def mix_to_ratio(src, synth_items, target_ratio=0.15):
    # src 전부 + synth 일부를 합쳐서 최종 web_search 비율을 target_ratio로 맞춤
    src_items = []
    ws_src = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s: continue
            obj = json.loads(s)
            try:
                r = json.loads(obj["response"])
            except Exception:
                continue
            if r.get("action") == "web_search": ws_src += 1
            src_items.append(obj)
    total_src = len(src_items)
    ws_needed = int((target_ratio * total_src - ws_src) / (1 - target_ratio)) if target_ratio < 1 else 0
    ws_needed = max(0, ws_needed)
    synth_slice = synth_items[:ws_needed]
    mixed = src_items + synth_slice
    random.shuffle(mixed)
    return mixed, synth_slice

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT_MIX), exist_ok=True)
    # 1) 합성 생성
    syn = synth(n=200)
    with open(OUT_SYN, "w", encoding="utf-8") as fo:
        for s in syn: fo.write(json.dumps(s, ensure_ascii=False) + "\n")
    # 2) 비율 계산 + 믹싱(목표 15%)
    mixed, used = mix_to_ratio(SRC, syn, target_ratio=0.15)
    with open(OUT_MIX, "w", encoding="utf-8") as fo:
        for s in mixed: fo.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"[OK] web_search_synth={len(syn)}, used_for_mix={len(used)}, out={OUT_MIX}")
