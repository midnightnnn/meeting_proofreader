from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from typing import Dict, Any

try:
    from .agents import AgentState, ProofreaderAgents
    from .semantic_layer import SemanticLayer
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from agents import AgentState, ProofreaderAgents
    from semantic_layer import SemanticLayer

class ProofreadingWorkflow:
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.agents = ProofreaderAgents()
        # Ensure we point to the right persistence directory
        self.semantic_layer = SemanticLayer(persist_directory=persist_directory) 
        
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # Define Nodes
        workflow.add_node("retrieve", self.retrieve_context)
        workflow.add_node("correct", self.agents.corrector_agent)
        workflow.add_node("verify", self.agents.verifier_agent)

        # Define Edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "correct")
        workflow.add_edge("correct", "verify")
        workflow.add_edge("verify", END)

        return workflow

    def retrieve_context(self, state: AgentState) -> Dict[str, Any]:
        """
        Node: Retrieval from ChromaDB
        """
        print(f"--- [Graph] Retrieve Context for Chunk {state.get('chunk_id')} ---")
        text = state['original_text']
        
        # Search semantic layer
        results = self.semantic_layer.search(text)
        
        return {"context_data": results}

    def process_chunk(self, chunk_data: Dict[str, Any], global_rules: str = "") -> Dict[str, Any]:
        """
        Entry point to process a single chunk.
        """
        initial_state: AgentState = {
            "chunk_id": chunk_data.get("id"),
            "original_text": chunk_data.get("text"),
            "global_rules": global_rules,
            "context_data": {},
            "corrected_text": None,
            "verification_result": None,
            "final_text": None,
            "pre_context": chunk_data.get("pre_context"),
            "post_context": chunk_data.get("post_context")
        }

        # Run the graph
        final_state = self.app.invoke(initial_state)
        
        return {
            "chunk_id": final_state["chunk_id"],
            "original_text": final_state["original_text"],
            "final_text": final_state["final_text"],
            "status": final_state["verification_result"]["status"],
            "changes_reason": final_state["verification_result"]["reason"]
        }
