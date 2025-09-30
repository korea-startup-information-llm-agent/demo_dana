import os
import zipfile
import re

SOURCE_DIR = "patent_data"
TARGET_DIR = "unzip_data/patent/dataset"

SPLIT_MAP = {
    "TL": "train",
    "VL": "val",
}

ZIP_PATTERN = re.compile(r"^(TL|VL)_.*\.zip$")

def unzip_patent_data():
    for root, _, files in os.walk(SOURCE_DIR):
        for fname in files:
            if not fname.lower().endswith(".zip"):
                continue
            zip_path = os.path.join(root, fname)
            
            match = ZIP_PATTERN.match(fname)
            if not match:
                print("⚠️ 패턴 매칭 실패:", fname)
                continue
            
            split_prefix = match.group(1)
            split = SPLIT_MAP.get(split_prefix, "other")
            
            # zip 이름 그대로 폴더로 생성
            zip_stem = os.path.splitext(fname)[0]
            extract_dir = os.path.join(TARGET_DIR, split, zip_stem)
            os.makedirs(extract_dir, exist_ok=True)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(extract_dir)
                print("✅ 해제 완료:", fname, "->", extract_dir)
            except Exception as e:
                print("❌ 해제 실패:", fname, "에러:", e)

if __name__ == "__main__":
    unzip_patent_data()
