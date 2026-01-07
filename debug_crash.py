import os
import sys
import traceback

# Simulate Environment
# os.environ["OPENAI_API_KEY"] = "sk-..." # Removed to use real .env
from dotenv import load_dotenv
load_dotenv(override=True)


import sqlite3
print(f"Sqlite3 version: {sqlite3.sqlite_version}")
sys.stdout.flush()

try:
    print("1. Importing modules...", flush=True)
    from meeting_proofreader.graph import ProofreadingWorkflow
    from meeting_proofreader.chunker import SlidingWindowChunker
    print("   Imports successful.", flush=True)

    print("2. Initializing Workflow...", flush=True)
    workflow = ProofreadingWorkflow(persist_directory=None)
    chunker = SlidingWindowChunker()
    print("   Workflow initialized.", flush=True)

    print("3. Adding Metadata...", flush=True)
    term_list = ["테스트", "용어", "디버깅"]
    workflow.semantic_layer.add_terms(term_list)
    print("   Metadata added.", flush=True)

    print("4. Chunking Text...", flush=True)
    raw_text = "이것은 테스트 텍스트입니다. 오타가 잇습니다. 웹케시를 웹캐시라고 썻네요."
    chunks = chunker.chunk_text(raw_text)
    print(f"   Chunked into {len(chunks)} chunks.", flush=True)

    print("5. Processing Chunks...", flush=True)
    for i, chunk in enumerate(chunks):
        print(f"   Processing chunk {i+1}...", flush=True)
        result = workflow.process_chunk(chunk)
        print(f"   Result: {result['final_text'][:20]}...", flush=True)

    print("6. Done.", flush=True)

except BaseException as e:
    print(f"CRASH DETECTED! Type: {type(e)}")
    traceback.print_exc()

