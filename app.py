import streamlit as st
import time
import concurrent.futures
import json
import base64
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Page Configuration must be first
st.set_page_config(
    page_title="의사록 자동 오타 검수 시스템",
    page_icon="📃",
    layout="wide",
    initial_sidebar_state="expanded"
)

from meeting_proofreader.utils.diff_view import generate_diff_html
import re
import streamlit.components.v1 as components

# --- Server-Side Session Cache (Hybrid: Memory + Firestore) ---
@st.cache_resource
def get_server_session_cache():
    return {}

SERVER_SESSION_CACHE = get_server_session_cache()

# Firestore Init (Safe Failover)
# Firestore Init (Safe Failover) -> Cached Resource
@st.cache_resource
def get_firestore_client():
    try:
        from google.cloud import firestore
        # On Cloud Run, this uses default service account. 
        # Locally, it will look for ADC. If it hangs, user might need to set creds.
        db = firestore.Client()
        print("[System] Firestore Client Initialized.")
        return db
    except Exception as e:
        print(f"[System] Firestore Init Failed (Using Memory Only): {e}")
        return None

DB_CLIENT = get_firestore_client()


def get_session_id():
    """Get or create session ID from query params"""
    query_params = st.query_params
    if "session" in query_params:
        return query_params["session"]
    return None

def create_session_id():
    """Create new session ID and set in query params"""
    import uuid
    new_id = str(uuid.uuid4())
    st.query_params["session"] = new_id
    return new_id

def save_session(session_id):
    """Save critical state to server cache (Memory + Firestore)"""
    if not session_id:
        return
        
    data = {
        "authenticated": st.session_state.get("authenticated", False),
        "original_text": st.session_state.get("original_text", ""),
        "corrected_text": st.session_state.get("corrected_text", ""),
        "processing_complete": st.session_state.get("processing_complete", False),
        "timestamp": datetime.now().isoformat()
    }
    
    # 1. Memory Cache
    SERVER_SESSION_CACHE[session_id] = data
    
    # 2. Firestore Persistence
    if DB_CLIENT:
        try:
            doc_ref = DB_CLIENT.collection('meeting_sessions').document(session_id)
            doc_ref.set(data)
            # print(f"[Firestore] Saved session {session_id}")
        except Exception as e:
            print(f"[Firestore] Save Error: {e}")

def load_session(session_id):
    """Load critical state from server cache (Memory -> Firestore)"""
    # 1. Try Memory first (Fastest)
    if session_id in SERVER_SESSION_CACHE:
        data = SERVER_SESSION_CACHE[session_id]
        st.session_state.authenticated = data.get("authenticated", False)
        st.session_state.original_text = data.get("original_text", "")
        st.session_state.corrected_text = data.get("corrected_text", "")
        st.session_state.processing_complete = data.get("processing_complete", False)
        return True
    
    # 2. Try Firestore (Persistence)
    if DB_CLIENT:
        try:
            doc_ref = DB_CLIENT.collection('meeting_sessions').document(session_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                
                # Restore to Memory for next time
                SERVER_SESSION_CACHE[session_id] = data
                
                # Restore to State
                st.session_state.authenticated = data.get("authenticated", False)
                st.session_state.original_text = data.get("original_text", "")
                st.session_state.corrected_text = data.get("corrected_text", "")
                st.session_state.processing_complete = data.get("processing_complete", False)
                print(f"[Firestore] Restored session {session_id}")
                return True
        except Exception as e:
            print(f"[Firestore] Load Error: {e}")
            
    return False



def highlight_search(text: str, search_term: str, container_id: str) -> tuple[str, bool]:
    """검색어를 노란색 하이라이트로 표시, 첫 번째 매치에 id 부여"""
    if not search_term or not text:
        return text, 0
    
    escaped = re.escape(search_term)
    
    count = 0
    def replace_func(match):
        nonlocal count
        html = f'<mark id="{container_id}-match-{count}" style="background-color: yellow; padding: 0 2px;">{match.group(1)}</mark>'
        count += 1
        return html
    
    highlighted = re.sub(f'({escaped})', replace_func, text, flags=re.IGNORECASE)
    return highlighted, count


def render_scrollable_content(content_html: str, container_id: str, match_index: int = 0, match_count: int = 0, height: int = 600):
    """스크롤 가능한 HTML 컨테이너 렌더링"""
    scroll_script = ""
    if match_count > 0:
        target_id = f"{container_id}-match-{match_index}"
        scroll_script = f'''
            <script>
                setTimeout(function() {{
                    const el = document.getElementById("{target_id}");
                    if (el) {{
                        el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    }}
                }}, 100);
            </script>
        '''
    
    html_content = f'''
        <style>
            body {{ margin: 0; padding: 0; font-family: 'Noto Sans KR', sans-serif; }}
            .scroll-container {{
                height: {height}px;
                overflow-y: auto;
                padding: 15px;
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                line-height: 1.6;
                font-size: 14px;
                white-space: pre-wrap;
            }}
            mark {{ transition: border 0.3s; }}
        </style>
        <div class="scroll-container">{content_html}</div>
        {scroll_script}
    '''
    components.html(html_content, height=height+30, scrolling=False)






# --- Professional Custom CSS ---
st.markdown("""
<style>
    /* Font and General Style */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
        color: #333333;
    }
    
    /* Header Styling */
    h1 {
        font-weight: 700;
        color: #1a1a1a;
        font-size: 2.2rem;
        border-bottom: 2px solid #0056b3;
        padding-bottom: 15px;
        margin-bottom: 30px;
    }
    
    h2, h3 {
        font-weight: 600;
        color: #2c3e50;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
    }
    
    /* Input Fields */
    .stTextArea textarea {
        background-color: #ffffff;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 0.95rem;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #0056b3;
        color: white;
        font-weight: 500;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        transition: background-color 0.2s;
    }
    .stButton > button:hover {
        background-color: #004494;
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background-color: #0056b3;
    }
    
    /* Diff View Container */
    .diff-container {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 20px;
        background-color: #ffffff;
        height: 600px;
        overflow-y: auto;
        line-height: 1.6;
        font-size: 1rem;
        white-space: pre-wrap; /* Preserve newlines */
    }
    
    .original-text {
        color: #555;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # --- Simple Session-based Password Protection ---
    import os
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "1234")
    
    # --- Session Restoration ---
    session_id = get_session_id()
    if session_id:
        # Try to restore session only if not already auth (or always to sync?)
        if "authenticated" not in st.session_state:
             load_session(session_id)

    # Initialize Session State
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown("### 🔒 접근 인증")
        password_input = st.text_input("비밀번호를 입력하세요", type="password")
        if st.button("로그인"):
            if password_input == APP_PASSWORD:
                st.session_state.authenticated = True
                
                # Create and Save Session logic
                if not session_id:
                    session_id = create_session_id()
                save_session(session_id)
                
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        st.stop()
    
    # --- Sidebar: File Upload & Metadata (Reordered) ---
    # 설정 파일 경로
    import json
    from pathlib import Path
    CONFIG_FILE = Path("user_config.json")
    
    @st.cache_data(ttl=300) # Cache for 5 mins
    def load_config():
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except:
                return {}
        return {}
    
    def save_config(rules: str, metadata: str):
        CONFIG_FILE.write_text(
            json.dumps({"rules": rules, "metadata": metadata}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    saved_config = load_config()
    
    with st.sidebar:
        st.subheader("1. 의사록 파일 업로드")
        uploaded_file = st.file_uploader(
            "검수할 파일을 선택하세요.", 
            type=["txt", "hwp"],
            help="지원 형식: TXT, HWP"
        )
        
        st.divider()

        st.subheader("2. 검수 원칙 (Global Rules)")
        default_rules = """1. 너는 대한민국 최고의 속기사이며, 모든 텍스트에 대한 오타를 빠짐없이 검수하고 수정한다.
2. 문맥이나 내용에 대한 수정은 절대 하지 않는다. 말한 그대로 적되, 잘못 적은 오타만을 수정해야하는 속기록 이기 떄문이다."""
        rules_text = st.text_area(
            "모든 에이전트가 준수할 규칙", 
            value=saved_config.get("rules", default_rules), 
            height=150
        )
        
        st.divider()
        
        st.subheader("3. 회의 메타데이터 입력")
        st.info("회의명, 참석자, 주요 용어 등을 자유롭게 입력하세요. 이 정보는 오타 검수 정확도를 높이는 데 사용됩니다.")
        
        metadata_text = st.text_area(
            "메타데이터 (줄바꿈이나 콤마로 구분)", 
            value=saved_config.get("metadata", ""),
            placeholder="예시:\n회의명: 제315회 임시회 본회의\n참석자: 김의원, 박시장, 이국장\n용어: 조례안, 추경예산, 의결, 정회, 산회",
            height=250
        )
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("설정 저장", use_container_width=True):
                save_config(rules_text, metadata_text)
                st.success("저장됨!")
        with col2:
            start_btn = st.button("검수 시작", type="primary", use_container_width=True)

    # --- Initialize Session State ---
    if "original_text" not in st.session_state:
        st.session_state.original_text = ""
    if "corrected_text" not in st.session_state:
        st.session_state.corrected_text = ""
    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False
    if "restored_from_storage" not in st.session_state:
        st.session_state.restored_from_storage = False
    
    # --- Restore from localStorage (한 번만 시도) ---
    if not st.session_state.restored_from_storage:
        st.session_state.restored_from_storage = True
        try:
            stored_data = streamlit_js_eval(js_expressions="localStorage.getItem('proofreader_session')")
            if stored_data:
                data = json.loads(stored_data)
                st.session_state.original_text = data.get('original_text', '')
                st.session_state.corrected_text = data.get('corrected_text', '')
                st.session_state.processing_complete = data.get('processing_complete', False)
                if st.session_state.processing_complete:
                    st.toast('이전 검수 결과를 복원했습니다.', icon='✅')
        except:
            pass

    # --- Initialize Backend ---
    if "workflow" not in st.session_state:
        try:
            from meeting_proofreader.graph import ProofreadingWorkflow
            from meeting_proofreader.chunker import SlidingWindowChunker
            st.session_state.workflow = ProofreadingWorkflow()
            st.session_state.chunker = SlidingWindowChunker()
        except Exception as e:
            st.error(f"시스템 초기화 오류: {e}")

    # --- Main Logic ---
    if start_btn:
        if uploaded_file and st.session_state.get("workflow"):
            # 1. Update Semantic Layer with Metadata
            if metadata_text:
                # Simple parsing: split by newlines or commas
                # Ideally, we pass the raw text to a smart extractor, but for now simple terms extraction
                # We assume the user inputs comma or newline separated info.
                raw_terms = metadata_text.replace("\n", ",").split(",")
                term_list = [t.strip() for t in raw_terms if t.strip()]
                
                # Add to semantic memory
                st.session_state.workflow.semantic_layer.add_terms(term_list)
            
            # 2. 파일에서 텍스트 추출 (TXT/PDF/HWP 지원)
            from meeting_proofreader.file_parser import extract_text_from_file
            
            raw_data = uploaded_file.read()
            try:
                raw_text = extract_text_from_file(raw_data, uploaded_file.name)
            except ValueError as e:
                st.error(str(e))
                st.stop()
            except ImportError as e:
                st.error(str(e))
                st.stop()
                
            # Normalize line endings
            raw_text = raw_text.replace("\r\n", "\n")
            st.session_state.original_text = raw_text
            
            # UI Components for Progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # 3. Chunking
                status_text.text("텍스트 분석 및 청크 분할 중...")
                chunks = st.session_state.chunker.chunk_text(raw_text)
                total_chunks = len(chunks)
                
                # Parallel Processing (ThreadPoolExecutor)
                results_dict = {}
                completed_count = 0
                full_corrected_text = [] # Will be filled after sorting
                
                # 스레드에서 session_state 접근 불가하므로 미리 추출
                workflow = st.session_state.workflow
                
                # Worker function for threading
                def process_chunk_task(chunk_data, rules):
                    # Pure python logic (no st calls here)
                    return workflow.process_chunk(chunk_data, global_rules=rules)

                max_workers = 5
                print(f"[App] Starting parallel processing of {total_chunks} chunks with {max_workers} workers.")
                status_text.text(f"병렬 처리 시작 ({max_workers} 스레드)...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks
                    # Map future to chunk index for tracking
                    future_to_index = {
                        executor.submit(process_chunk_task, chunk, rules_text): chunk['index'] 
                        for chunk in chunks
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_index):
                        idx = future_to_index[future]
                        try:
                            result = future.result()
                            final_text = result['final_text']
                            results_dict[idx] = final_text
                            print(f"[App] Finished chunk {idx}")
                        except Exception as exc:
                            print(f"[App] Chunk {idx} generated an exception: {exc}")
                            # Fallback: maintain original text or error message
                            # Retrieve original text from chunk list if possible, or just fail safely
                            # Finding the original chunk text is expensive unless we have it handy.
                            # We can just put a placeholder or re-raise
                            st.error(f"Error in chunk {idx}: {exc}")
                            results_dict[idx] = f"[Error Processing Chunk {idx}]"

                        completed_count += 1
                        progress = completed_count / total_chunks
                        progress_bar.progress(progress)
                        status_text.text(f"진행 중: {completed_count} / {total_chunks} 구역 완료")
                
                # 순서대로 정렬하여 합치기
                full_corrected_text = []
                for i in range(total_chunks):
                    if i in results_dict:
                        full_corrected_text.append(results_dict[i])
                    else:
                        full_corrected_text.append("") # Should not happen if all futures complete
                
                # Finish
                progress_bar.progress(100)
                status_text.text("완료: 모든 검수 작업이 끝났습니다.")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
                
                st.session_state.corrected_text = "".join(full_corrected_text)
                st.session_state.processing_complete = True
                print(f"[App] Processing complete. Final text length: {len(st.session_state.corrected_text)}")
                
                # Save session after processing
                save_session(session_id)
                
                # Force rerun to update UI
                st.rerun()
                
                # --- Save to localStorage ---

                
            except Exception as e:
                import traceback
                st.error(f"검수 중 오류 발생: {e}")
                st.code(traceback.format_exc())
                
                # Still show partial results if any
                if full_corrected_text:
                    st.session_state.corrected_text = "".join(full_corrected_text)
                    st.session_state.processing_complete = True
                
        elif not uploaded_file:
            st.warning("파일을 먼저 업로드해주세요.")
        else:
            st.error("백엔드 연결 실패.")

    # --- Result View (Left: Original / Right: Diff) ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("원문 (Original)")
        
        # 검색 UI: st.form을 사용하여 엔터키 입력 시 '다음 찾기' 기능 구현
        with st.form(key="orig_search_form", clear_on_submit=False):
            c1, c2 = st.columns([5, 1])
            with c1:
                search_original = st.text_input("원문 검색", key="search_orig_input", placeholder="검색어 입력 후 Enter...", label_visibility="collapsed")
            with c2:
                # 엔터키 누르면 이 버튼이 트리거됨 (보이기는 '찾기'지만 실제론 Next 역할)
                submit_orig = st.form_submit_button("FormSubmit", use_container_width=True) # Label hidden via CSS if needed, or simple 'Find'

        # CSS로 폼 제출 버튼 숨기기 (엔터키 기능만 살리기 위해)
        st.markdown("""
        <style>
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] {
            display: none;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Session State Init
        if 'orig_search_idx' not in st.session_state: st.session_state.orig_search_idx = 0
        if 'orig_last_query' not in st.session_state: st.session_state.orig_last_query = ""
        
        # 쿼리 변경 감지
        if search_original != st.session_state.orig_last_query:
            st.session_state.orig_search_idx = 0
            st.session_state.orig_last_query = search_original
        # 쿼리가 같고 Submit(엔터)되었다면 -> 인덱스 증가 (Next)
        elif submit_orig and search_original:
             st.session_state.orig_search_idx += 1

        original_display = st.session_state.original_text if st.session_state.original_text else "(파일을 업로드하면 내용이 표시됩니다.)"
        match_count = 0
        
        if search_original and st.session_state.original_text:
            original_display, match_count = highlight_search(st.session_state.original_text, search_original, "orig")
            
            # 인덱스 범위 조정
            if match_count > 0:
                st.session_state.orig_search_idx = st.session_state.orig_search_idx % match_count
            
            # 매치 카운트 표시 (브라우저 스타일: 1/5)
            if match_count > 0:
                st.caption(f"{st.session_state.orig_search_idx + 1} / {match_count}")
        
        render_scrollable_content(original_display, "orig", st.session_state.orig_search_idx, match_count)

    with col2:
        st.subheader("검수 결과 (Corrected & Diff)")
        
        with st.form(key="corr_search_form", clear_on_submit=False):
            c1, c2 = st.columns([5, 1])
            with c1:
                search_corrected = st.text_input("검수결과 검색", key="search_corr_input", placeholder="검색어 입력 후 Enter...", label_visibility="collapsed")
            with c2:
                submit_corr = st.form_submit_button("FormSubmit", use_container_width=True)

        # Session State Init
        if 'corr_search_idx' not in st.session_state: st.session_state.corr_search_idx = 0
        if 'corr_last_query' not in st.session_state: st.session_state.corr_last_query = ""
        
        if search_corrected != st.session_state.corr_last_query:
            st.session_state.corr_search_idx = 0
            st.session_state.corr_last_query = search_corrected
        elif submit_corr and search_corrected:
            st.session_state.corr_search_idx += 1
        
        match_count = 0
        diff_html = ""
        container_id_for_scroll = "diff"
        current_scroll_idx = 0
        
        if st.session_state.processing_complete and st.session_state.corrected_text:
            # --- Optimization: Cache Diff HTML ---
            # Recomputing difflib on every button click is too slow.
            should_compute = False
            if 'cached_diff_html' not in st.session_state:
                should_compute = True
            elif 'cached_diff_text_hash' not in st.session_state: # Backward compat
                should_compute = True
            else:
                # Simple check: has the text changed?
                current_hash = hash(st.session_state.original_text + st.session_state.corrected_text)
                if st.session_state.cached_diff_text_hash != current_hash:
                    should_compute = True

            if should_compute:
                with st.spinner("비교 화면 생성 중... (잠시만 기다려주세요)"):
                    diff_html, diff_change_count = generate_diff_html(st.session_state.original_text, st.session_state.corrected_text)
                    
                    st.session_state.cached_diff_html = diff_html
                    st.session_state.cached_diff_count = diff_change_count
                    st.session_state.cached_diff_text_hash = hash(st.session_state.original_text + st.session_state.corrected_text)
            else:
                diff_html = st.session_state.cached_diff_html
                diff_change_count = st.session_state.cached_diff_count
            
            if search_corrected:
                # --- Search Mode (Dynamic, cannot be easily cached completely, but regex is fast) ---
                diff_html, match_count = highlight_search(diff_html, search_corrected, "corr")
                container_id_for_scroll = "corr"
                
                if match_count > 0:
                    st.session_state.corr_search_idx = st.session_state.corr_search_idx % match_count
                    if submit_corr:
                         pass
                
                if match_count > 0:
                    st.caption(f"검색 결과: {st.session_state.corr_search_idx + 1} / {match_count}")
                
                current_scroll_idx = st.session_state.corr_search_idx
                
            else:
                # --- Diff Navigation Mode (Default) ---
                total_changes = diff_change_count
                
                if 'diff_nav_idx' not in st.session_state: st.session_state.diff_nav_idx = 0
                
                if total_changes > 0:
                    # Index Bounds Check
                    st.session_state.diff_nav_idx = min(st.session_state.diff_nav_idx, total_changes - 1)
                    
                    # Simple Navigation UI
                    c_prev, c_cnt, c_next = st.columns([1, 2, 1])
                    
                    with c_prev:
                        if st.button("◀", key="diff_b_prev", use_container_width=True, help="이전 수정사항"):
                            st.session_state.diff_nav_idx = max(0, st.session_state.diff_nav_idx - 1)
                            st.rerun()
                            
                    with c_next:
                        if st.button("▶", key="diff_b_next", use_container_width=True, help="다음 수정사항"):
                            st.session_state.diff_nav_idx = min(total_changes - 1, st.session_state.diff_nav_idx + 1)
                            st.rerun()
                            
                    with c_cnt:
                        st.markdown(f"<div style='text-align:center; padding-top:7px; font-weight:bold; font-size:0.9rem; color:#555;'>변경 사항: {st.session_state.diff_nav_idx + 1} / {total_changes}</div>", unsafe_allow_html=True)
                
                else:
                     st.info("수정된 내용이 없거나 공백 변경만 있습니다.")

                current_scroll_idx = st.session_state.diff_nav_idx
                match_count = total_changes # To trigger scroll script logic if > 0
                container_id_for_scroll = "diff" # Matches id="diff-match-{idx}" in diff_view.py

        else:
             diff_html = '<div class="diff-container" style="color:#999; text-align:center; padding-top:200px;">(검수가 완료되면 수정된 내역이 표시됩니다.)</div>'

        render_scrollable_content(diff_html, container_id_for_scroll, current_scroll_idx, match_count)

        # --- Footer Export ---
        if st.session_state.processing_complete:
            st.divider()
            col_dl, col_reset = st.columns([3, 1])
            with col_dl:
                st.download_button(
                    label="수정된 파일 다운로드 (.txt)",
                    data=st.session_state.corrected_text,
                    file_name=f"corrected_minutes_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col_reset:
                if st.button("🗑️ 초기화", use_container_width=True, help="검수 결과를 삭제하고 새로 시작합니다."):
                    st.session_state.original_text = ""
                    st.session_state.corrected_text = ""
                    st.session_state.processing_complete = False

                    st.rerun()

if __name__ == "__main__":
    main()
