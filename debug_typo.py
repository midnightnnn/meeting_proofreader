"""
Debug script to test the correction pipeline with a simple typo.
"""
from dotenv import load_dotenv
load_dotenv()

from meeting_proofreader.graph import ProofreadingWorkflow

# Initialize the workflow
workflow = ProofreadingWorkflow()

# Test case: Simple typo that should be corrected
test_text = """아산시 돌봄노동자 권리 보장 및 처우 개선에 관한 조례앙 일부개정조례안을 심사하도록 하겠습니다."""

chunk_data = {"id": "test_chunk_1", "text": test_text}

print("=" * 60)
print("원본 텍스트:")
print(test_text)
print("=" * 60)

result = workflow.process_chunk(chunk_data, global_rules="오타를 수정하세요. 예: 조례앙 -> 조례안")

print("\n" + "=" * 60)
print(f"최종 결과 (Status: {result['status']}):")
print(result['final_text'])
print("=" * 60)
print(f"변경 사유: {result['changes_reason']}")
