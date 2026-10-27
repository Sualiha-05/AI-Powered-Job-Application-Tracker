"""Compare the keyword and LLM extractors on a sample (or your own) job description.

    export GEMINI_API_KEY=...           # or ANTHROPIC_API_KEY; never commit a key
    python scripts/try_extract.py                # built-in sample
    python scripts/try_extract.py my_jd.txt      # your own file
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.extract import extract_skills  # noqa: E402
from app.llm_extract import LLMUnavailable, get_llm_client, llm_extract  # noqa: E402

SAMPLE = """Full Stack Engineer
We are looking for someone with 2+ years of experience in React and Node.js.
You will build REST APIs on PostgreSQL and deploy with Docker on AWS.
Nice to have: experience with Kubernetes or GraphQL. Familiarity with LLM apps is a plus."""

text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else SAMPLE
print("Keyword baseline:", extract_skills(text))

client = get_llm_client()
if client is None:
    sys.exit("\nNo GEMINI_API_KEY or ANTHROPIC_API_KEY set, skipping the LLM extractor.")
try:
    out = llm_extract(text, "job_description", client)
except LLMUnavailable as err:
    sys.exit(f"\nLLM call failed: {err}")

print(f"\nLLM ({out.extractor}):")
for d in out.details:
    print(f"  {d.name:<14} {d.importance:<10} \"{d.quote}\"")
print(f"\ndropped (ungrounded): {out.dropped}   usage: {out.usage}")
