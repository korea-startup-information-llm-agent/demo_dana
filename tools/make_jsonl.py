import os, json, glob, sys, argparse, math

# ---------- 경로 ----------
PROJECT_ROOT = r"C:\dana\demo_dana"
DATA_ROOT    = os.path.join(PROJECT_ROOT, r"unzip_data\ip\dataset")
OUT_TRAIN    = os.path.join(PROJECT_ROOT, r"data\sft\train.jsonl")
OUT_VAL      = os.path.join(PROJECT_ROOT, r"data\sft\val.jsonl")
OUT_LEFTOVER = os.path.join(PROJECT_ROOT, r"data\sft\summary_leftover.jsonl")

# ---------- 상수 ----------
SYS_PROMPT = (
    'You are a routing model for an IP/patent assistant. '
    'Output JSON only: {"intent","action","jurisdiction","confidence"}. '
    'If unsure or evidence is needed, choose action="retrieve".'
)
PROCESS_KWS = ["절차","방법","불복","기한","수수료","심판","출원","PCT","진입"]

# ---------- 유틸 ----------
def try_read(fp):
    # 빠른 경로: UTF-8 -> UTF-8-SIG, 실패 시에만 CP949 시도
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            with open(fp, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            raise e
    raise UnicodeDecodeError("all", b"", 0, 1, "unsupported encoding")

def safe_load_json(fp):
    try:
        txt = (try_read(fp) or "").strip()
        if not txt:
            return None
        if txt.startswith("["):
            arr = json.loads(txt)
            return arr[0] if isinstance(arr, list) and arr else None
        return json.loads(txt)
    except Exception:
        return None

def to_sample(user_text, doc_type, task_type):
    jur = "KR" if doc_type and any(k in doc_type for k in ["특허","심판","특허심판원","특허법원"]) else "unknown"
    u = (user_text or "").strip()
    tt = (task_type or "").lower()

    if tt.startswith("02"):                      # summary
        intent, action, conf = "patent_info", "summarize", 0.68
    elif any(k in u for k in PROCESS_KWS):       # process-ish
        intent, action, conf = "process", "retrieve", 0.76
    else:
        intent, action, conf = "patent_info", "retrieve", 0.72

    resp = json.dumps(
        {"intent": intent, "action": action, "jurisdiction": jur, "confidence": round(conf,2)},
        ensure_ascii=False
    )
    return {
        "messages": [
            {"role":"system","content":SYS_PROMPT},
            {"role":"user","content":u}
        ],
        "response": resp
    }

def collect_paths(root, split):
    cats = ["judgment","statute","trial_decision","decision","interpretation"]
    qa_paths, sum_paths = [], []
    for c in cats:
        qa_paths  += glob.glob(os.path.join(root, c, "qa",      split, "*.json"))
        sum_paths += glob.glob(os.path.join(root, c, "summary", split, "*.json"))
    qa_paths.sort(); sum_paths.sort()
    return qa_paths, sum_paths

def write_samples(paths, fo, limit=None, tag=""):
    n = 0
    for i, fp in enumerate(paths, 1):
        if limit and n >= limit: break
        rec = safe_load_json(fp)
        if not rec: continue
        info  = (rec.get("info") or {})
        tinfo = (rec.get("taskinfo") or {})
        ttype = str(info.get("taskType",""))
        dtype = str(info.get("document_type",""))
        user_q = (tinfo.get("input") or "")
        s = to_sample(user_q, dtype, ttype)
        fo.write(json.dumps(s, ensure_ascii=False) + "\n")
        n += 1
        if i % 1000 == 0:
            print(f"[{tag}] processed {i}/{len(paths)}")
    return n

def write_summary(paths, fo_top, fo_left, take_top_ratio=0.2, limit=None):
    total = len(paths)
    if total == 0:
        return 0, 0
    take = math.floor(total * take_top_ratio)
    # limit이 있으면, take도 limit에 맞춰 줄임
    if limit: take = min(take, limit)
    top_paths = paths[:take]
    left_paths = paths[take:]

    # top -> train
    n_top = 0
    for i, fp in enumerate(top_paths, 1):
        rec = safe_load_json(fp)
        if not rec: continue
        info  = (rec.get("info") or {})
        ttype = str(info.get("taskType",""))
        dtype = str(info.get("document_type",""))
        title = info.get("title","해당 문서")
        user_q = f"{title} 관련 심결의 핵심을 한국어로 간단히 요약해줘."
        s = to_sample(user_q, dtype, ttype or "02(TS)")
        fo_top.write(json.dumps(s, ensure_ascii=False) + "\n")
        n_top += 1
        if i % 1000 == 0:
            print(f"[SUM:top] processed {i}/{len(top_paths)}")

    # leftover -> 별도 파일
    n_left = 0
    for i, fp in enumerate(left_paths, 1):
        rec = safe_load_json(fp)
        if not rec: continue
        info  = (rec.get("info") or {})
        ttype = str(info.get("taskType",""))
        dtype = str(info.get("document_type",""))
        title = info.get("title","해당 문서")
        user_q = f"{title} 관련 심결의 핵심을 한국어로 간단히 요약해줘."
        s = to_sample(user_q, dtype, ttype or "02(TS)")
        fo_left.write(json.dumps(s, ensure_ascii=False) + "\n")
        n_left += 1
        if i % 1000 == 0:
            print(f"[SUM:leftover] processed {i}/{len(left_paths)}")

    return n_top, n_left

def main(limit=None):
    print(f"[INFO] DATA_ROOT = {DATA_ROOT}")
    if not os.path.isdir(DATA_ROOT):
        print("[FATAL] dataset root not found"); sys.exit(1)

    os.makedirs(os.path.dirname(OUT_TRAIN), exist_ok=True)

    # --- TRAIN (스트리밍 2-pass: 경로만 모으고 바로 기록) ---
    qa_train, sum_train = collect_paths(DATA_ROOT, "train")
    print(f"[SCAN train] qa={len(qa_train)}, summary={len(sum_train)}")

    with open(OUT_TRAIN, "w", encoding="utf-8") as f_train, \
         open(OUT_LEFTOVER, "w", encoding="utf-8") as f_left:

        # QA 전부(또는 limit) 스트리밍 기록
        qa_limit = None if not limit else max(0, limit - 0)  # limit는 전체 샘플 가이드용
        n_qa = write_samples(qa_train, f_train, limit=qa_limit, tag="QA-train")

        # SUMMARY 상단 20%만 train, 나머지 leftover
        # limit이 있으면, 남은 여력을 summary에 할당(대략적)
        sum_limit = None
        if limit:
            sum_limit = max(0, limit - n_qa)
        n_top, n_left = write_summary(sum_train, f_train, f_left, take_top_ratio=0.2, limit=sum_limit)

    # --- VAL (검증은 제한 없이 전부 포함) ---
    qa_val, sum_val = collect_paths(DATA_ROOT, "val")
    print(f"[SCAN val] qa={len(qa_val)}, summary={len(sum_val)}")
    with open(OUT_VAL, "w", encoding="utf-8") as f_val:
        n_qv = write_samples(qa_val, f_val, limit=None, tag="QA-val")
        # val은 요약도 모두 포함
        n_sv_top, _ = write_summary(sum_val, f_val, open(os.devnull, "w", encoding="utf-8"), take_top_ratio=1.0, limit=None)

    print("=== SUMMARY ===")
    print(f"TRAIN  QA_written: {n_qa}, SUM_top20_written: {n_top}, SUM_leftover_written: {n_left}")
    print(f"VAL    QA_written: {n_qv}, SUM_all_written: {n_sv_top}")
    print("[OK] wrote:")
    print(" -", OUT_TRAIN)
    print(" -", OUT_VAL)
    print(" -", OUT_LEFTOVER)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="(선택) train에서 최대 샘플 수 대략 제한용")
    args = parser.parse_args()
    main(limit=args.limit)
