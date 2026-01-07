# 속기록 자동 오타 검수 시스템 (Automated Meeting Minutes Proofreader) Implementation Plan

## 1. 개요 (Overview)
속기사가 작성한 회의록 초안(Raw Text)을 **Semantic Layer(의미 기반 기억소)**를 통해 강화된 LLM 에이전트가 교정하고, **Streamlit** 기반의 전문적인 웹 UI에서 효율적으로 검수하는 시스템입니다.

## 2. 아키텍처 (System Architecture)

### 2.1 Core Workflow
**"기록된 텍스트"**와 **"의도된 의미"** 사이의 간극을 **Vector DB**로 메우는 것이 핵심입니다.

```mermaid
graph TD
    User[속기사] -- "1. 파일 업로드 & 메타데이터 입력" --> StreamlitUI["Streamlit Web App"]
    
    subgraph "Semantic Layer (Brain)"
        MetaHandler[Metadata Processor]
   - 오타 검수 전, 메타데이터를 먼저 벡터화하여 메모리에 적재.
   - 에이전트가 문장을 읽다가 불확실한 단어(예: "웹캐시"?)를 만나면 의미 거리(Cosine Similarity)를 계산하여 가장 유사한 기준 단어("웹케시")를 찾아냄.
    end

    subgraph "Processing Core (Agent)"
        Chunker[Sliding Window Chunker]
        Retriever[Context Retriever]
        Corrector["Agent A: The Editor"]
        Verifier["Agent B: The Critic"]
    end

    StreamlitUI -- "2. 메타데이터(통합)" --> MetaHandler
    MetaHandler -- "3. 임베딩" --> VectorDB
    
    StreamlitUI -- "4. 텍스트 전달" --> Chunker
    Chunker -- "5. 청크 스트림" --> Retriever
    
    VectorDB -.-> "6. RAG Retrieval" -.-> Retriever
    Retriever -- "7. 텍스트 + 참고자료" --> Corrector
    
    Corrector --> Verifier
    Verifier -- "8. 검증된 수정안" --> StreamlitUI
    
    StreamlitUI -- "9. Visual Diff Rendering" --> User
```

### 2.2 Tech Stack
| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | **Streamlit** | 직관적인 2분할(Diff) UI. 전문적인 CSS 적용. |
| **Backend** | **Python** | LangGraph 에이전트 및 로직 제어. |
| **Semantic DB** | **Numpy + JSON** | 경량화된 의미 기반 검색. (Windows 호환성 및 안정성 확보) |
| **LLM Logic** | **LangGraph** | 에이전트 순환 구조. |
| **LLM Model** | **OpenAI GPT-4o** | 한국어 문맥 이해. |

## 3. UI/UX 개선 명세 (UI/UX Improvements)

### 3.1 Metadata Input Overhaul
- **통합 입력창**: 기존 주제, 참석자, 용어 입력을 하나의 `st.text_area`("회의 메타데이터 입력")로 통합.
- **Backend 연동**: 입력된 전체 텍스트를 Semantic Layer의 컨텍스트로 활용.

### 3.2 Layout Restructuring
- **File Uploader 우선 배치**: 사이드바 최상단에 파일 업로더 배치 (드래그 불필요).
- **Professional Design**:
    - **CSS**: 공무원/속기사 업무 환경에 맞춘 절제된 전문 디자인 (이모지 최소화, 명조/고딕 계열 정돈).
    - **Spinner 교체**: `st.progress`와 `st.empty`를 활용한 실시간 로그.

### 3.3 Visual Diff Logic (Crucial)
- **Problem**: 단순 텍스트 박스로는 어디가 수정되었는지 식별 불가능.
- **Solution**: `difflib` 라이브러리를 사용하여 원본(Original)과 수정본(Corrected)의 차이를 계산하고, HTML로 렌더링.
- **Visual Style**:
    - **삭제(Changed/Deleted)**: <span style="background-color:#ffeef0; color:#b31d28; text-decoration:line-through;">빨간색 배경 + 취소선</span>
    - **추가(Added/Corrected)**: <span style="background-color:#e6ffec; color:#22863a; font-weight:bold;">초록색 배경 + 굵게</span>
    - **Display**: 오른쪽 패널은 `st.text_area` 대신 `st.markdown(..., unsafe_allow_html=True)` 사용.

### 3.4 Progress Feedback
- **Loop Integration**: `workflow.process_chunk` 루프 내에서 진행률 업데이트.
- **Status Logs**: 현재 수행 중인 작업(청크 분석, 검증 등)을 한글 로그로 표시.

### 3.5 Global Rules & Config (New)
- **Feature**: 사이드바에 '검수 원칙(Rules)' 입력창 추가. 모든 에이전트(Corrector/Verifier)가 공유하는 시스템 프롬프트로 주입.
- **Default Value**:
    > 1. 너는 대한민국 최고의 속기사이며, 모든 텍스트에 대한 오타를 빠짐없이 검수하고 수정한다.
    > 2. 문맥이나 내용에 대한 수정은 절대 하지 않는다. 말한 그대로 적되, 잘못 적은 오타만을 수정해야하는 속기록 이기 떄문이다.
- **UI Cleanup**: 메인 화면의 `st.title` 제거. 깔끔하게 2분할 화면만 표시.
- **Placeholder Update**: '용어' 예시를 의회/속기 관련 용어로 변경.

## 4. Critical Bug Fixes (Prioritized)
> [!IMPORTANT]
> The user reported output discrepancies and crashes. These must be fixed before refining the UI.

### 4.1 Fix Chunker Duplication (Overlap Issue)
- **Problem**: `SlidingWindowChunker` with overlap + simple concatenation causes text duplication at every chunk boundary.
- **Solution**:
    - Modify `meeting_proofreader/chunker.py` to use **Zero Overlap** for processing.
    - Implement smart splitting (by newline/space) to avoid cutting words in half, ensuring context preservation without physical overlap in output.

### 4.2 Fix File Encoding Support
- **Problem**: `app.py` blindly decodes as `utf-8`. Windows users often use `cp949` or `utf-16`.
- **Solution**:
    - Implement valid encoding detection (Try UTF-8 -> CP949 -> UTF-16).
    - Handle BOM (Byte Order Mark) correctly.

## 5. 구현 로드맵 (Steps)

### Step 1: UI Layout Refactor (Frontend)
- [ ] `app.py`: `st.sidebar` 순서 변경 (업로더 -> 메타데이터).
- [ ] `app.py`: 3개 입력 필드를 1개로 병합.

### Step 2: Styling & Professionalism
- [ ] `app.py`: Custom CSS 주입 (폰트, 여백, 컬러).
- [ ] `app.py`: 이모지 제거 및 전문 용어로 레이블 변경.

### Step 3: Visual Diff Algorithm
- [ ] `utils/diff_view.py` (New): `difflib.SequenceMatcher` 등을 활용해 HTML Diff 생성 함수 구현.
- [ ] `app.py`: 수정된 텍스트 영역을 Markdown 렌더링으로 교체.

### Step 4: Progress Logic
- [ ] `app.py`: `process_chunk` 루프에 `progress_bar.progress()` 추가.

## 5. Verification Plan

### Manual Verification
- **Run**: `streamlit run app.py`
- **Checklist**:
    1.  **Diff Visibility**: 수정된 글자가 **초록색/붉은색**으로 명확히 구분되는가?
    2.  **Layout**: 파일 업로더가 사이드바 맨 위에 있는가?
    3.  **Input**: 메타데이터 통합 입력이 정상 작동하는가?
    3.  **Input**: 메타데이터 통합 입력이 정상 작동하는가?
    4.  **Progress**: 실행 시 퍼센트 바와 로그가 갱신되는가?

## 7. Security Enhancements (Access Control & Secrets)
**Goal**: Secure the app using GCP Secret Manager and implement basic access control.

### 7.1 GCP Secret Manager Integration
- **Problem**: API Key is currently visible in deployment scripts/Env vars.
- **Solution**: Use GCP Secret Manager (`gpt_key`).
- **Implementation**:
    - Update `deploy_cloudbuild.ps1` to replace `--set-env-vars` with `--set-secrets`.
    - Command: `--set-secrets="OPENAI_API_KEY=gpt_key:latest"`.

### 7.2 Application Access Control (Optional but Recommended)
- **Problem**: Current deployment allows unauthenticated access (`--allow-unauthenticated`). Anyone with the URL can use it.
- **Solution**: Implement Application-Level Password Protection (Simple Auth).
- **Implementation**:
    - Add `APP_PASSWORD` to Secrets or Env Vars.
    - In `app.py`: Show password input field first. Only load main UI if password matches.
    - Default Password Rule: User can set via env/secret.


## 6. GCP Cloud Run Deployment Strategy (New)
**Goal**: Deploy the Streamlit application to Google Cloud Run as a serverless container.

### 6.1 Docker Configuration
- **Base Image**: `python:3.10-slim` (Lightweight, sufficient for Streamlit & Numpy).
- **Dependencies**: `pip install -r requirements.txt`. (Must ensure `numpy`, `streamlit`, `langgraph`, `openai`, `langchain-openai` are listed).
- **Port**: Expose `8080` (Cloud Run default).

### 6.2 Deployment Script (`deploy.sh`)
- **Build**: `docker build -t gcr.io/[PROJECT_ID]/proofreader .` (or using `gcloud builds submit`)
- **Deploy**: 
    ```bash
    gcloud run deploy meeting-proofreader \
      --image gcr.io/[PROJECT_ID]/proofreader \
      --platform managed \
      --region asia-northeast3 \
      --allow-unauthenticated \
      --set-env-vars OPENAI_API_KEY=[KEY]
    ```

### 6.3 Pre-requisites
- [ ] `gcloud` CLI installed and authenticated.
- [ ] GCP Project created and billing enabled.
- [ ] Artifact Registry or Container Registry enabled.


