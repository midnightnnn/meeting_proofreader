import os
import json
import numpy as np
from openai import OpenAI
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class SemanticLayer:
    """
    Lightweight Semantic Layer using Numpy & JSON.
    Replaces ChromaDB to avoid SQLite/DLL crashes on Windows.
    """
    def __init__(self, persist_directory: str = "./chroma_db", embedding_function=None):
        # We use the same directory structure but different file
        self.persist_directory = persist_directory if persist_directory else "./chroma_db"
        self.memory_file = os.path.join(self.persist_directory, "simple_memory.json")
        
        # Data Structure:
        # {
        #   "metadata": [{"text": str, "embedding": List[float]}],
        #   "terms":    [...],
        #   "history":  [...]
        # }
        self.data = {"metadata": [], "terms": [], "history": []}

        # Initialize OpenAI Client directly
        try:
             api_key = os.environ.get("OPENAI_API_KEY")
             if not api_key:
                 print("[SemanticLayer] Warning: OPENAI_API_KEY not found.")
             self.client = OpenAI(api_key=api_key)
        except Exception as e:
             print(f"[SemanticLayer] OpenAI Client Init Failed: {e}")
             self.client = None
             
        self.load_memory()

    def _get_embedding(self, text: str) -> List[float]:
        if not self.client or not text:
            return [0.0] * 1536
            
        try:
            text = text.replace("\n", " ")
            res = self.client.embeddings.create(input=[text], model="text-embedding-3-small")
            return res.data[0].embedding
        except Exception as e:
            print(f"[SemanticLayer] Embedding Error: {e}")
            return [0.0] * 1536

    def add_metadata(self, text: str, source: str = "user_input"):
        if not text: return
        emb = self._get_embedding(text)
        self.data["metadata"].append({
            "text": text,
            "embedding": emb,
            "meta": {"source": source}
        })
        print(f"[SemanticLayer] Added metadata: {text[:20]}...")
        self.save_memory()

    def add_terms(self, terms: List[str]):
        if not terms: return
        print(f"[SemanticLayer] Adding {len(terms)} terms...")
        
        # Batch addition ? For simplicity, loop. 
        # OpenAI supports batch input, but let's keep it simple to handle errors per item if needed.
        # Actually batch is better for speed.
        valid_terms = [t for t in terms if t.strip()]
        if not valid_terms: return

        try:
            res = self.client.embeddings.create(input=valid_terms, model="text-embedding-3-small")
            for i, data_item in enumerate(res.data):
                self.data["terms"].append({
                    "text": valid_terms[i],
                    "embedding": data_item.embedding,
                    "meta": {"type": "glossary"}
                })
            print(f"[SemanticLayer] Added {len(valid_terms)} terms.")
            self.save_memory()
        except Exception as e:
            print(f"[SemanticLayer] Batch Embedding Error: {e}")

    def add_history(self, text: str, meeting_id: str):
        if not text: return
        emb = self._get_embedding(text)
        self.data["history"].append({
            "text": text,
            "embedding": emb,
            "meta": {"meeting_id": meeting_id}
        })
        self.save_memory()

    def search(self, query: str, n_results=3) -> Dict[str, Any]:
        """
        Returns {'relevant_terms': [], 'relevant_context': [], 'relevant_history': []}
        """
        q_emb = np.array(self._get_embedding(query))
        results = {}
        
        # Map our keys to the expected return keys
        # self.data keys: 'metadata', 'terms', 'history'
        # return keys: 'relevant_context', 'relevant_terms', 'relevant_history'
        key_map = {
            "metadata": "relevant_context",
            "terms": "relevant_terms",
            "history": "relevant_history"
        }
        
        for pool_key, result_key in key_map.items():
            collection = self.data.get(pool_key, [])
            if not collection:
                results[result_key] = []
                continue
            
            # Compute Cosine Similarity
            # Score = A . B (if normalized)
            # OpenAI embeddings are normalized to length 1.
            scores = []
            for item in collection:
                v = np.array(item["embedding"])
                score = np.dot(q_emb, v)
                scores.append((score, item["text"]))
            
            # Sort descending
            scores.sort(key=lambda x: x[0], reverse=True)
            
            # Take top K
            top_k = [x[1] for x in scores[:n_results]]
            results[result_key] = top_k
            
        return results

    def save_memory(self):
        if not os.path.exists(self.persist_directory):
             os.makedirs(self.persist_directory, exist_ok=True)
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[SemanticLayer] Save Error: {e}")

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                print(f"[SemanticLayer] Loaded memory from {self.memory_file}")
            except Exception as e:
                print(f"[SemanticLayer] Load Error: {e}")
        else:
            print("[SemanticLayer] Initialized new memory.")

    def reset_memory(self):
        self.data = {"metadata": [], "terms": [], "history": []}
        self.save_memory()
        print("[SemanticLayer] Memory reset.")
