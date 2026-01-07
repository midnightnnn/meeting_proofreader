from typing import TypedDict, List, Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import os

try:
    from .prompts import CORRECTOR_SYSTEM, CORRECTOR_HUMAN, VERIFIER_SYSTEM, VERIFIER_HUMAN
except ImportError:
    from prompts import CORRECTOR_SYSTEM, CORRECTOR_HUMAN, VERIFIER_SYSTEM, VERIFIER_HUMAN



def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def calculate_cer(s1: str, s2: str) -> float:
    """Calculates Character Error Rate (CER)."""
    dist = levenshtein_distance(s1, s2)
    return dist / max(len(s1), len(s2), 1)


class AgentState(TypedDict):
    chunk_id: str
    original_text: str
    global_rules: str
    context_data: Dict[str, Any]
    corrected_text: Optional[str]
    verification_result: Optional[Dict[str, Any]]
    final_text: Optional[str]
    pre_context: Optional[str]
    post_context: Optional[str]


class CorrectorOutput(BaseModel):
    corrected_text: str = Field(description="The text after correcting typos and context errors.")
    changes_made: List[str] = Field(description="List of brief descriptions of changes made.")


class VerifierOutput(BaseModel):
    status: str = Field(description="One of 'ACCEPT', 'REJECT', 'MODIFY'.")
    reason: str = Field(description="Reason for the decision.")
    final_text: str = Field(description="The final version of the text to be used.")


class ProofreaderAgents:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[Warning] OPENAI_API_KEY missing in Agents.")
        # gpt-4o-mini의 경우 JSON 모드를 명시하면 더 안정적임
        self.llm = ChatOpenAI(
            model=model_name, 
            temperature=0, 
            openai_api_key=api_key,
            model_kwargs={"response_format": {"type": "json_object"}},
            request_timeout=60
        )

    def _repair_line_breaks(self, original: str, corrected: str) -> str:
        """
        Attempts to fix line breaks in corrected text to match original text exactly.
        """
        print("[Agent A] Attempting to repair line breaks...")
        repair_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a formatting assistant. Your ONLY job is to fix line breaks. Output JSON."),
            ("human", """
Originl Text (Correct Line Breaks):
{original}

Corrected Text (Wrong Line Breaks):
{corrected}

**Instruction**:
Output a JSON object with a single key "corrected_text".
The value should be the **Corrected Text** but reformatted so it has the **EXACT** same line break positions as the **Original Text**.
- Do NOT change any words or spelling.
- Do NOT add or remove content.
- ONLY adjust `\\n` (newlines) to match the Original Text.
""")
        ])
        
        chain = repair_prompt | self.llm | JsonOutputParser()
        try:
            result = chain.invoke({"original": original, "corrected": corrected})
            return result.get('corrected_text', corrected).strip()
        except:
             return corrected

    def corrector_agent(self, state: AgentState) -> Dict[str, Any]:
        """Agent A: 오타 교정"""
        print(f"--- [Agent A] Correcting Chunk {state.get('chunk_id')} ---")
        original_text = state['original_text']
        context = state.get('context_data', {})
        
        terms = context.get('relevant_terms', [])
        meta_context = context.get('relevant_context', [])
        
        # New: Get Neighbor Context from Chunker
        pre_ctx = state.get('pre_context', "")
        post_ctx = state.get('post_context', "")
        
        neighbor_context = ""
        if pre_ctx or post_ctx:
             neighbor_context = f"\n[Surrounding Text for Reference - DO NOT EDIT THIS]\n(Previous): ...{pre_ctx}\n(Next): {post_ctx}..."

        rules = state.get('global_rules', "오타를 수정하세요.")
        context_str = f"Specific Terms/Jargon identified: {terms}\nMeeting Context: {meta_context}{neighbor_context}"
        
        parser = JsonOutputParser(pydantic_object=CorrectorOutput)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", CORRECTOR_SYSTEM),
            ("human", CORRECTOR_HUMAN)
        ])
        
        chain = prompt | self.llm | parser
        
        try:
            result = chain.invoke({
                "rules": rules,
                "context": context_str,
                "text": original_text,
                "format_instructions": parser.get_format_instructions()
            })
            
            if 'corrected_text' not in result:
                print(f"[Agent A] Error: Key 'corrected_text' missing. Raw result: {result}")
                return {"corrected_text": original_text}
                
            corrected = result['corrected_text']
            
            # --- Validations ---
            
            # 1. Strict Line Break Check & Retry (Ignoring trailing whitespace)
            orig_strip = original_text.strip()
            corr_strip = corrected.strip()
            
            if orig_strip.count('\n') != corr_strip.count('\n'):
                 orig_cnt = orig_strip.count('\n')
                 corr_cnt = corr_strip.count('\n')
                 print(f"[Agent A] Warning: Line break count mismatch ({orig_cnt} vs {corr_cnt}). Attempting repair...")
                 corrected = self._repair_line_breaks(original_text, corrected)
                 corr_strip = corrected.strip()
                 
                 # Re-check after repair - 실패해도 경고만 출력하고 계속 진행
                 if orig_strip.count('\n') != corr_strip.count('\n'):
                     print(f"[Agent A] Warning: Repair failed. Proceeding with changed line breaks.")
                     # 원본으로 되돌리지 않음 - 오타 교정 우선
            
            # If internal structure matches, restore original leading/trailing whitespace
            # This handles cases where LLM stripped the output but internal lines are correct
            if original_text.count('\n') != corrected.count('\n'): # If raw counts differ but stripped match
                 # Heuristic: Apply original's leading/trailing whitespace to corrected
                 left_ws = original_text[:len(original_text) - len(original_text.lstrip())]
                 right_ws = original_text[len(original_text.rstrip()):]
                 corrected = left_ws + corr_strip + right_ws
            
            # 2. CER (Character Error Rate) Check
            # Very short (Word only): < 10 chars -> 60% (Allow 1 char fix in 2-char word: 50%)
            # Short phrase: < 50 chars -> 40%
            # Long sentence: >= 50 chars -> 20%
            orig_len = len(original_text)
            if orig_len < 10:
                cer_threshold = 0.60
            elif orig_len < 50:
                cer_threshold = 0.40
            else:
                cer_threshold = 0.20
            
            cer = calculate_cer(original_text, corrected)
            if cer > cer_threshold:
                 print(f"[Agent A] Warning: CER {cer*100:.1f}% > {cer_threshold*100:.0f}%, reverting.")
                 return {"corrected_text": original_text}
            
            return {"corrected_text": corrected}
        except Exception as e:
            print(f"[Agent A] Error: {e}")
            return {"corrected_text": original_text}

    def verifier_agent(self, state: AgentState) -> Dict[str, Any]:
        """Agent B: 과도 수정 검증"""
        print(f"--- [Agent B] Verifying Chunk {state.get('chunk_id')} ---")
        original = state['original_text']
        corrected = state['corrected_text']
        
        if original == corrected:
             return {
                "verification_result": {"status": "ACCEPT", "reason": "No changes made."},
                "final_text": original
            }

        rules = state.get('global_rules', "오타 수정 여부를 검증하세요.")
        parser = JsonOutputParser(pydantic_object=VerifierOutput)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", VERIFIER_SYSTEM),
            ("human", VERIFIER_HUMAN)
        ])
        
        chain = prompt | self.llm | parser
        
        try:
            result = chain.invoke({
                "rules": rules,
                "original": original,
                "corrected": corrected,
                "format_instructions": parser.get_format_instructions()
            })
            
            status = result['status']
            final = result['final_text']
            
            # ACCEPT 시에는 corrected를 사용, REJECT 시에는 original 사용 (LLM 재생성 방지)
            if status == 'ACCEPT':
                final = corrected
            elif status == 'REJECT':
                final = original
            # MODIFY의 경우에만 LLM이 생성한 final_text 사용, 단 검증 필요
            else:
                should_revert = False
                
                # 1. Strict Line Break Check (Ignoring trailing whitespace)
                orig_strip = original.strip()
                final_strip = final.strip()
                
                if orig_strip.count('\n') != final_strip.count('\n'):
                    orig_cnt = orig_strip.count('\n')
                    final_cnt = final_strip.count('\n')
                    print(f"[Agent B] MODIFY Result Line break mismatch ({orig_cnt} vs {final_cnt}). Proceeding anyway.")
                    # should_revert = True  # 줄바꿈 불일치로 되돌리지 않음
                else:
                    # Restore whitespace if internal structure matches
                    if original.count('\n') != final.count('\n'):
                        left_ws = original[:len(original) - len(original.lstrip())]
                        right_ws = original[len(original.rstrip()):]
                        final = left_ws + final_strip + right_ws
                
                # 2. CER Check
                # Same threshold logic as Corrector
                orig_len = len(original)
                if orig_len < 10:
                    cer_threshold = 0.60
                elif orig_len < 50:
                    cer_threshold = 0.40
                else:
                    cer_threshold = 0.20
                
                if not should_revert and calculate_cer(original, final) > cer_threshold:
                     print(f"[Agent B] MODIFY Result CER too high ({calculate_cer(original, final)*100:.1f}% > {cer_threshold*100:.0f}%).")
                     should_revert = True
                
                if should_revert:
                    print(f"[Agent B] Reverting MODIFY result to original.")
                    final = original
            
            return {
                "verification_result": {
                    "status": status, 
                    "reason": result['reason']
                },
                "final_text": final
            }
        except Exception as e:
             print(f"[Agent B] Error: {e}")
             return {
                "verification_result": {"status": "ERROR", "reason": str(e)},
                "final_text": original
            }
