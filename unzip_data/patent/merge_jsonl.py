import os
import json
import re

BASE_DIR = "unzip_data/patent/dataset"

def make_jsonl_for_folder(folder_path):
    # 폴더명에서 TL/VL 접두사와 마지막 코드 추출
    folder_name = os.path.basename(folder_path)
    
    match = re.match(r"(TL|VL)_.*_([A-Z]{3})", folder_name)
    if match:
        prefix, code = match.groups()
        output_name = f"{prefix}_{code}.jsonl"
    else:
        output_name = folder_name + ".jsonl"
    
    output_path = os.path.join(folder_path, output_name)
    
    with open(output_path, "w", encoding="utf-8") as fout:
        for fname in os.listdir(folder_path):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(folder_path, fname)
            with open(fpath, "r", encoding="utf-8") as fin:
                line = fin.read().strip()
                if line:
                    fout.write(line + "\n")
            # JSON 파일 삭제
            os.remove(fpath)
    
    print(f"✅ JSONL 생성 완료 및 기존 JSON 삭제: {output_path}")

def process_all():
    for split in ["train", "val"]:
        split_dir = os.path.join(BASE_DIR, split)
        if not os.path.exists(split_dir):
            continue
        for folder_name in os.listdir(split_dir):
            folder_path = os.path.join(split_dir, folder_name)
            if os.path.isdir(folder_path):
                make_jsonl_for_folder(folder_path)

if __name__ == "__main__":
    process_all()
