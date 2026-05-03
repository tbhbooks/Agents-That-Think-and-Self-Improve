"""Chapter 0 smoke test.

Uses the shared llm wrapper so .env backend selection works:
- TBH_LLM_BACKEND=api
- TBH_LLM_BACKEND=cli
"""

from tbh_code.llm import chat

reply = chat([{"role": "user", "content": "Say 'tbh-code ready' and nothing else."}])
print(reply)
