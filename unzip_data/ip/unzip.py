import os
import zipfile
import re

SOURCE_DIR = "ip_legal_data"
TARGET_DIR = "unzip_data/ip/dataset"

KIND_MAP = {
    "판결문": "judgment",
    "법령": "statute",
    "심결례": "trial_decision",
    "심결문": "decision",
    "유권해석": "interpretation",
}

FORM_MAP = {
    "질의응답": "qa",
    "요약": "summary",
}

# TL_ = train, VL_ = val
SPLIT_MAP = {
    "TL": "train",
    "VL": "val",
}

ZIP_PATTERN = re.compile(r"^(TL|VL)_.*_(판결문|법령|심결례|심결문|유권해석).*_(질의응답|요약)\.zip$")

def unzip_all():
    for root, _, files in os.walk(SOURCE_DIR):
        for fname in files:
            if not fname.lower().endswith(".zip"):
                continue
            zip_path = os.path.join(root, fname)
            
            match = ZIP_PATTERN.match(fname)
            if not match:
                print("⚠️ 패턴 매칭 실패:", fname)
                continue
            
            split_prefix, kind_kor, form_kor = match.groups()
            kind = KIND_MAP[kind_kor]
            form = FORM_MAP[form_kor]
            split = SPLIT_MAP.get(split_prefix, "other")
            
            extract_dir = os.path.join(TARGET_DIR, kind, form, split)
            os.makedirs(extract_dir, exist_ok=True)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(extract_dir)
                print("✅ 해제 완료:", fname, "->", extract_dir)
            except Exception as e:
                print("❌ 해제 실패:", fname, "에러:", e)

if __name__ == "__main__":
    unzip_all()
