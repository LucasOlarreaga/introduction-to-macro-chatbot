"""
Claude API integration — builds the prompt and calls the API.
"""
import anthropic
from . import config

_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are IntegrAI, the AI pedagogical assistant of the Geneva School of Economics and Management (GSEM). You help faculty members integrate Generative AI responsibly into their teaching and assessment practices, in alignment with the GSEM AI Taskforce guidelines.

Your behaviour rules:
1. Answer ONLY using the context documents provided below. If the answer is not in the documents, say clearly that you could not find the information in the available course materials.
2. Always cite your sources at the end of your answer using this exact format:
   📄 [Filename, p.X]
   List every source you drew from.
3. Be precise, professional, and pedagogically helpful.
4. Never invent, hallucinate, or extrapolate beyond what the documents say.
5. The user may write in French or English — respond in the same language they use.
6. You are in {lang_label} mode, meaning you only have access to the {lang_label} version of the course materials.
7. When the user asks for a specific exercise (e.g. "exercise 2 of PS 2"), look for that exact exercise number in the retrieved documents and answer it directly. If the exercise number is not found, tell the user which exercises ARE available in the retrieved context so they can clarify."""

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
) -> str:
    """
    Call Claude with the retrieved context and conversation history.
    history is a list of {"role": "user"|"assistant", "content": "..."}.
    Returns the assistant's reply as a string.
    """
    lang_label = "French" if lang == "fr" else "English"
    system = SYSTEM_PROMPT.format(lang_label=lang_label)

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
