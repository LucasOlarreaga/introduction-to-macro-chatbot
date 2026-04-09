"""
Claude API integration — builds the prompt and calls the API.
"""
import anthropic
from . import config
from .prompts import build_system_prompt

_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client

CONTEXT_TEMPLATE = """--- DOCUMENT CONTEXT ---
{context}
--- END OF CONTEXT ---

User question: {question}"""


def format_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[Source {i}: {chunk['filename']}, p.{chunk['page']} ({chunk['type']})]:\n{chunk['text']}"
        )
    return "\n\n".join(parts)


def format_sources(chunks: list[dict]) -> list[dict]:
    """Deduplicated source list for the frontend to display."""
    seen = set()
    sources = []
    for chunk in chunks:
        key = (chunk["filename"], chunk["page"])
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename": chunk["filename"],
                "page": chunk["page"],
                "type": chunk["type"],
            })
    return sources


def generate_response(
    message: str,
    chunks: list[dict],
    history: list[dict],
    lang: str,
    mode: str = "direct",
) -> str:
    """
    Call Claude with the retrieved context and conversation history.
    mode is "direct" (full answers) or "guide" (Socratic questioning).
    history is a list of {"role": "user"|"assistant", "content": "..."}.
    Returns the assistant's reply as a string.
    """
    lang_label = "French" if lang == "fr" else "English"
    system = build_system_prompt(mode, lang_label)

    # Build messages list: history + current turn
    messages = list(history)  # copy

    if chunks:
        context_str = format_context(chunks)
        user_content = CONTEXT_TEMPLATE.format(context=context_str, question=message)
    else:
        user_content = (
            f"[No relevant documents found in the {lang_label} materials.]\n\nUser question: {message}"
        )

    messages.append({"role": "user", "content": user_content})

    client = get_client()
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    )

    return response.content[0].text
