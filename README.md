# Data Processing for Patent & Legal Dataset

이 문서는 현재 진행된 법률/특허 데이터셋 처리 과정과 폴더 구조, 사용 방법을 정리한 문서입니다. 

<br><br>

## 진행 사항 및 최종 목적

현재까지 작업한 내용:

1. **법률 데이터셋 (ip_legal_data)**

   - labeled zip 파일 압축 해제
   - 폴더 구조를 분석용으로 정리 (예: `judgment/qa/train/`, `judgment/summary/`)
   - 원본 raw 데이터는 제외

2. **특허 데이터셋 (patent_data)**
   - labeled zip 파일 압축 해제
   - 각 폴더 내 JSON 파일을 JSONL로 합치고 기존 JSON 삭제
   - raw 및 `Other` 폴더는 제외

<br>

> 이 단계까지는 단순히 데이터 분석 및 테스트 용이성을 위해 **폴더 구조와 파일 형식만 정리한 상태**입니다.

<br>

### 최종 목표

1. **법률 데이터 (지식재산권법)**

   - LLM 파인튜닝용 소스 데이터로 가공
   - 데이터 전처리 및 정형화 후, 학습에 활용할 수 있는 형태로 준비
   - 실제 모델 학습은 이 폴더 외 다른 환경에서 수행

2. **특허 데이터**
   - JSONL 데이터 기반으로 벡터 DB 저장용 스키마 설계
   - 내부 검색용 데이터로 구축 및 관리
   - 분석, 검색, 추천 시스템 등에서 활용 가능
   - 실제 DB 구축과 운영은 이 폴더 외 다른 단계에서 진행

<br>

> 현재 폴더와 파일 정리는 **데이터 전처리와 구조 정리 단계**이며, 실제 ML 학습이나 DB 운영은 별도의 환경에서 이어서 수행됩니다.

<br><br>

## 폴더 구조

```bash
data-prop/
│
├─ ip_legal_data/  # 법률 데이터 원본 (raw/labeled)
├─ patent_data/    # 특허 데이터 원본 (labeled only, raw는 사용하지 않음)
│
└─ unzip_data/
    ├─ ip/
    │   ├─ dataset/       # 압축 해제된 법률 데이터셋 저장
    │   │   ├─ judgment/
    │   │   │   ├─ qa/
    │   │   │   │   ├─ train/
    │   │   │   │   └─ val/
    │   │   │   └─ summary/
    │   │   └─ ...        # 다른 법률 종류별로 동일 구조
    │   └─ unzip.py       # 법률 데이터셋 압축 해제 코드
    │
    └─ patent/
        ├─ dataset/
        │   ├─ train/
        │   │   ├─ <zip_name_folder>/ # 예: TL_C_ICT_SW_CC_빅데이터_인공지능_CCA_...
        │   │   │   └─ TL_CCA.jsonl   # jsonl로 합친 데이터
        │   │   └─ ...
        │   └─ val/
        │       ├─ <zip_name_folder>/
        │       │   └─ VL_CCB.jsonl
        │       └─ ...
        │
        ├─ unzip.py        # 특허 데이터셋 압축 해제 코드
        └─ merge_jsonl.py  # 폴더 내 모든 json 파일을 jsonl로 합치고 기존 json 삭제
```

<br><br>

## 데이터 준비

- 구글 드라이브에서 제공되는 `dataset` 폴더에는 두 개의 데이터셋이 있습니다:

  1. `ip_legal_data`
  2. `patent_data`

- 이 두 폴더를 그대로 작업 폴더 최상단(`data-prop/`) 루트에 위치시키면 됩니다.

- 각 데이터셋 안에는 **라벨링 데이터(labeled)**와 **원천 데이터(raw)**가 포함되어 있습니다.
  - 실행 코드는 **raw 폴더와 patent_data/Other 폴더는 제외**하고 labeled 데이터만 처리합니다.
  - 즉, zip 압축 해제 및 JSON → JSONL 변환 과정에서 **raw와 Other 폴더는 자동으로 무시**됩니다.

<br><br>

## 작업 과정

### 1. 법률 데이터셋 압축 해제

- `unzip_data/ip/unzip.py` 실행
- 각 zip 파일을 **종류(kind) + 형식(form) + split(train/val)** 기준으로 하위 폴더에 압축 해제
- 한글명을 영어로 변환하여 폴더 관리
  - 예: `판결문/질의응답` → `judgment/qa`

<br>

### 2. 특허 데이터셋 압축 해제

- `unzip_data/patent/unzip.py` 실행
- labeled zip만 사용, raw zip은 무시
- 각 zip 파일은 train/val 기준 폴더 아래 **zip 이름 그대로 폴더 생성 후 압축 해제**
- 예:
  ```bash
  patent_data/train/labeled/TL_C_ICT_SW_CC_빅데이터_인공지능_CCA_...zip
  → unzip_data/patent/dataset/train/TL_C_ICT_SW_CC_빅데이터_인공지능_CCA_.../
  ```

<br>

### 3. 특허 JSON 파일 합치기

- `unzip_data/patent/merge_jsonl.py` 실행
- 각 zip 폴더 내 모든 `.json` 파일을 **한 줄 JSONL**로 합치고 기존 JSON 파일 삭제
- JSONL 파일명: zip 폴더명에서 TL/VL + 마지막 코드 추출
  - 예: `TL_C_ICT_SW_CC_...` → `TL_CCA.jsonl`
  - 예: `VL_C_ICT_SW_CC_...` → `VL_CCB.jsonl`
- 최종 폴더 구조:
  ```bash
  unzip_data/patent/dataset/train/TL_C_ICT_SW_CC_.../TL_CCA.jsonl
  unzip_data/patent/dataset/val/VL_CCB/...
  ```

<br><br>

## 실행 순서 예시

1. raw 데이터를 `data-prop/` 루트에 위치

2. 법률 데이터 압축 해제

   ```bash
   python unzip_data/ip/unzip.py
   ```

3. 특허 데이터 압축 해제

   ```bash
   python unzip_data/patent/unzip.py
   ```

4. 특허 데이터 JSON → JSONL 변환 및 기존 JSON 삭제
   ```bash
   python unzip_data/patent/merge_jsonl.py
   ```

<br>
