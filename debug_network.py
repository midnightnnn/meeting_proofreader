import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
print("Checking OpenAI connectivity...")

try:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.embeddings.create(
        input="test",
        model="text-embedding-3-small"
    )
    print("SUCCESS: Embedding retrieved.")
    print(response.data[0].embedding[:5])
except Exception as e:
    print(f"FAILURE: {e}")
