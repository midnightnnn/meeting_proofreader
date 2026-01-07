from typing import List, Dict, Any
import uuid

class SlidingWindowChunker:
    """
    Splits long text into overlapping chunks for processing.
    """
    def __init__(self, window_size: int = 1000, overlap: int = 100):
        self.window_size = window_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Splits text into chunks using a zero-overlap strategy for the 'target text' 
        to prevent duplication in the final output.
        However, it includes 'pre_context' and 'post_context' (surrounding text) 
        in the chunk data so the LLM can understand the flow.
        """
        if not text:
            return []

        chunks = []
        text_len = len(text)
        start = 0
        chunk_index = 0
        
        # Context window size (how much to look back/ahead)
        context_window = 200

        while start < text_len:
            # Determine potential end of chunk
            end = min(start + self.window_size, text_len)
            
            # If we are not at the end of the text, try to find a natural break point (newline/space)
            if end < text_len:
                # Look for last newline in the last 10% of the window
                search_limit = max(start, end - int(self.window_size * 0.1))
                
                # Priority 1: Newline
                last_newline = text.rfind('\n', search_limit, end)
                if last_newline != -1:
                    end = last_newline + 1 # Include the newline
                else:
                    # Priority 2: Space
                    last_space = text.rfind(' ', search_limit, end)
                    if last_space != -1:
                        end = last_space + 1 # Include the space
            
            chunk_text = text[start:end]
            
            # --- Get Context ---
            # Pre-context: ensure we don't go below 0
            pre_start = max(0, start - context_window)
            pre_context = text[pre_start:start]
            
            # Post-context: ensure we don't go beyond text_len
            post_end = min(text_len, end + context_window)
            post_context = text[end:post_end]
            # -------------------
            
            chunk_data = {
                "id": str(uuid.uuid4()),
                "index": chunk_index,
                "text": chunk_text,
                "pre_context": pre_context,   # Previous text (for reference only)
                "post_context": post_context, # Next text (for reference only)
                "start_char": start,
                "end_char": end,
            }
            chunks.append(chunk_data)
            
            chunk_index += 1
            
            # Move start to exactly where the last chunk ended (Zero Overlap for target text)
            start = end
            
        return chunks
