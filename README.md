
# IP Legal → SFT Routing Dataset

법률(지식재산권) 데이터셋을 **LLM 라우팅(SFT)** 용 JSONL로 변환하는 프로젝트입니다.
목표는 **지식 주입 X**, **행동 정책(의도/툴선택/관할/JSON 형식)** 학습입니다.

* 모델(예정): Llama 3.2 **3B Instruct** (QLoRA SFT, 온디바이스: `llama.cpp + GGUF`)
* 액션 스키마:

  * `intent`: `patent_info | process | brainstorm | other`
  * `action`: `retrieve | summarize | finalize | (선택) web_search`
  * `jurisdiction`: `KR | US | WIPO | unknown`
  * `confidence`: `0.0–1.0`
* 출력 포맷(라인 단위 JSONL):

  ```json
  {
    "messages": [
      {"role":"system","content":"...JSON only & routing rules..."},
      {"role":"user","content":"<사용자 질문>"}
    ],
    "response":"{\"intent\":\"...\",\"action\":\"...\",\"jurisdiction\":\"...\",\"confidence\":0.73}"
  }
  ```

---

## 현재 상태

* 공유 드라이브에 제공된 **법률 데이터셋 zip** 파일을 루트에 두고, `unzip.py` 실행으로 압축 해제함
* 특허 데이터는 이번 리비전에서 **비사용/보류**
* 변환 결과:

  ```
  TRAIN  QA_written: 76160, SUM_top20_written: 880, SUM_leftover_written: 3520
  VAL    QA_written: 9520,  SUM_all_written : 550
  ```
* 산출물:

  ```
  C:\dana\demo_dana\data\sft\train.jsonl
  C:\dana\demo_dana\data\sft\val.jsonl
  C:\dana\demo_dana\data\sft\summary_leftover.jsonl
  ```
* (선택) `web_search` 합성 샘플 추가 가능 → `train_mixed.jsonl` 생성

---

## 폴더 구조

```
C:\dana\demo_dana
├─ ip_legal_data.zip          # 공유 드라이브에서 복사해온 원본 zip
├─ unzip_data\ip\dataset\     # unzip.py 실행 결과
│  ├─ judgment\{qa,summary}\{train,val}\*.json
│  ├─ statute\{qa,summary}\{train,val}\*.json
│  ├─ trial_decision\...
│  ├─ decision\...
│  └─ interpretation\...
├─ tools\
│  ├─ unzip.py                # 법률 데이터셋 압축 해제
│  ├─ make_jsonl.py           # 원본 → SFT JSONL 변환 (summary 상단 20%만 포함)
│  └─ add_web_search.py       # (선택) web_search 합성 & 비율 믹싱
└─ data\sft\
   ├─ train.jsonl
   ├─ val.jsonl
   ├─ summary_leftover.jsonl
   └─ (옵션) train_mixed.jsonl
```

---

## 실행 순서

### 1) 법률 데이터 압축 해제 (필수)

1. 공유 드라이브에서 `ip_legal_data.zip`을 받아서 프로젝트 루트(`C:\dana\demo_dana`)에 둡니다.
2. 압축 해제 실행:

   ```bat
   cd C:\dana\demo_dana
   python tools\unzip.py
   ```
3. 실행 후 `unzip_data/ip/dataset/` 폴더가 자동 생성되고, 판결문/심결문/법령 등 폴더 구조로 정리됩니다.

---

### 2) 법률 데이터 → SFT JSONL 변환 (필수)

```bat
cd C:\dana\demo_dana
python tools\make_jsonl.py
```

* QA는 전부 포함 (사용자 질문 → `action=retrieve` 중심)
* Summary는 **상단 20%만** 포함 → `action=summarize` 신호 학습
* 남은 Summary 80%는 `summary_leftover.jsonl`로 별도 저장

---

### 3) (선택) 외부 검색 액션 추가(web_search)

```bat
python tools\add_web_search.py
```

* 결과물:

  * `web_search_synth.jsonl` (합성 원본)
  * `train_mixed.jsonl` (기존 + 합성 섞기, 기본: web_search 약 **15%** 비율)

> 처음에는 `train.jsonl`만으로 학습하고, **외부검색 라우팅 필요** 시 `train_mixed.jsonl`을 사용하세요.

---

## 학습에 연결

* (예) `configs/train.yaml`에서 경로 지정:

  ```yaml
  data:
    train_path: C:\dana\demo_dana\data\sft\train.jsonl        # 또는 train_mixed.jsonl
    val_path:   C:\dana\demo_dana\data\sft\val.jsonl
  ```
* 학습은 별도 프로젝트(예: `C:\patent-llama`)에서 수행.

  ```bat
  copy C:\dana\demo_dana\data\sft\*.jsonl  C:\patent-llama\data\sft\
  ```

---

## .gitignore 권장

산출물은 커밋하지 않습니다.

```
# SFT outputs
/data/sft/*.jsonl
!/data/sft/README.md
```

---

## 다음 단계

1. `train_mixed.jsonl`로  QLoRA SFT
2. LangGraph 라우터 연결:

   * `retrieve` → 내부 RAG
   * `summarize` → 요약기
   * `web_search` → 외부 검색 툴
   * `finalize`는 드물게 허용