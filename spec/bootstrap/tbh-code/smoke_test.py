"""Chapter 0 smoke test."""

import aisuite as ai
from dotenv import load_dotenv

load_dotenv()
client = ai.Client()

MODEL = "anthropic:claude-sonnet-4-20250514"

response = client.chat.completions.create(
    model=MODEL,
    max_tokens=100,
    messages=[{"role": "user", "content": "Say 'tbh-code ready' and nothing else."}],
)
print(response.choices[0].message.content)
