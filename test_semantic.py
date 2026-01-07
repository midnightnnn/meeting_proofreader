import os
import traceback
from meeting_proofreader.semantic_layer import SemanticLayer

# Define a simple dummy embedding function for testing without API keys
class DummyEmbeddingFunction:
    def __call__(self, input):
        # Return a fixed size vector (e.g., 3 dimensions) for each input text
        return [[0.1, 0.2, 0.3] for _ in input]
        
    def name(self):
        return "dummy_embedding_function"

def test_semantic_layer():
    try:
        print("--- Initializing Semantic Layer with Dummy Embeddings ---")
        dummy_ef = DummyEmbeddingFunction()
        # Use a separate test DB to avoid conflict with "openai" embeddings in main DB
        sl = SemanticLayer(persist_directory="./chroma_test_db", embedding_function=dummy_ef)
        
        print("\n--- Resetting Memory ---")
        sl.reset_memory()
        
        print("\n--- Adding Data ---")
        try:
            sl.add_metadata("Meeting Topic: Financial Q3 Review. Attendees: Alice, Bob, Charlie.")
        except Exception as e:
            print("Error adding metadata:", e)
            traceback.print_exc()

        try:    
            sl.add_terms(["EBITDA", "ROI", "Churn Rate"])
        except Exception as e:
            print("Error adding terms:", e)
            traceback.print_exc()

        try:
            sl.add_history("Previous meeting decided to increase marketing budget.", "meeting_001")
        except Exception as e:
            print("Error adding history:", e)
            traceback.print_exc()
        
        print("\n--- Searching 'budget' ---")
        res1 = sl.search("budget")
        print("Result 1:", res1)
        
        print("\n--- Searching 'EBITDA' ---")
        res2 = sl.search("EBITDA")
        print("Result 2:", res2)

        print("\n--- Done ---")
    except Exception as e:
        print("Fatal Error:", e)
        traceback.print_exc()

if __name__ == "__main__":
    test_semantic_layer()
