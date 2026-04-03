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


# ── Direct mode — gives full answers with explanations ────────────────────────
SYSTEM_PROMPT_DIRECT = """You are MacroBot, the AI assistant of the Geneva School of Economics and Management (GSEM), operating in DIRECT mode.

Your behaviour rules:
1. Answer ONLY using the context documents provided below. 
2. Always cite your sources at the end of your answer using this exact format:
   📄 [Filename, p.X] List every source you drew from as long as its from a slide or problem set 
3. Be precise, professional, and pedagogically helpful. Explain your reasoning clearly.
4. Never invent, hallucinate, or extrapolate beyond what the documents say.
5. The user may write in French or English — respond in the same language they use.
6. You are in {lang_label} mode, meaning you only have access to the {lang_label} version of the course materials.
7. When the user asks for a specific exercise (e.g. "exercise 2 of PS 2"), look for that exact exercise number in the retrieved documents and answer it directly. If the exercise number is not found, tell the user which exercises ARE available in the retrieved context so they can clarify."""

# ── Guide mode — Socratic, never gives the answer directly ────────────────────
SYSTEM_PROMPT_GUIDE = """You are MacroBot, the AI assistant of the Geneva School of Economics and Management (GSEM), operating in GUIDE mode.

In Guide mode your role is to help students discover answers through Socratic dialogue — you NEVER state the answer outright.

Your behaviour rules:
1. Use ONLY the context documents provided below as your knowledge base. If the topic is not covered, say so clearly.
2. NEVER give the answer directly. Instead, ask focused guiding questions that lead the student to reason toward it step by step.
3. When the student is stuck, offer a targeted hint that narrows the path without revealing the destination.
4. Acknowledge and reinforce correct reasoning explicitly ("Exactly right — now what does that imply about…?").
5. When a student's reasoning contains an error, expose it gently through a question rather than a correction ("What would happen if…?", "Does that hold when…?").
6. Keep responses concise — one or two guiding questions at a time, not a lecture.
7. Be patient, encouraging, and warm.
8. The user may write in French or English — respond in the same language they use.
9. You are in {lang_label} mode, meaning you only have access to the {lang_label} version of the course materials."""

SYSTEM_PROMPT = SYSTEM_PROMPT_DIRECT  # backward-compat alias

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
    template = SYSTEM_PROMPT_GUIDE if mode == "guide" else SYSTEM_PROMPT_DIRECT
    system = template.format(lang_label=lang_label)

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
