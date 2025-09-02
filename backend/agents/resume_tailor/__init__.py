"""Resume tailoring agent built on top of LLMs.

This package encapsulates the prompt and orchestration logic for creating a
tailored resume JSON given a job analysis, current resume text, and user
constraints. It attempts to use `openai-agents` if available and falls back to
an OpenAI‑compatible Chat Completions call.
"""

