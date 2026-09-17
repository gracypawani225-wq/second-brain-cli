"""Optional Gemini-powered answers grounded in locally saved notes."""

from __future__ import annotations

import os

from .db import Note


class AIConfigurationError(RuntimeError):
    """Raised when the optional AI feature is not configured."""


def answer_question(question: str, notes: list[Note]) -> str:
    """Ask Gemini to answer strictly from the supplied notes."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AIConfigurationError("GEMINI_API_KEY is not set. Add it to your environment to use `brain ask`.")
    if not notes:
        return "I don't have enough information in your saved notes to answer that."

    try:
        from google import genai
    except ImportError as error:
        raise AIConfigurationError(
            "AI support is optional. Install it with `pip install -e '.[ai]'`."
        ) from error

    context = "\n\n".join(f"[Note #{note.id}] {note.text}" for note in notes)
    prompt = f"""You are a careful second-brain assistant. Answer the user's question using ONLY the notes below.
If the notes do not contain enough information, say exactly that you do not have enough information. Do not add outside facts.

Question: {question}

Saved notes:
{context}
"""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    return response.text or "I don't have enough information in your saved notes to answer that."
