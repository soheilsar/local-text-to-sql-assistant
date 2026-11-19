"""Quick check that Ollama is running and the configured model answers."""
import requests
from sql_assistant import OLLAMA_URL, MODEL

r = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with only the word: ready"}],
        "think": False,
        "stream": False,
        "options": {"temperature": 0},
    },
    timeout=60,
)
print(f"{MODEL} replied:", r.json()["message"]["content"])
