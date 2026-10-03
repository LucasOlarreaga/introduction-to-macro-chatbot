"""
Prompt and model configuration — load and save from disk.
The {lang_label} language rule is intentionally excluded from the editable
prompts and is always appended by chat.py at runtime.
"""
import json
import logging
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

# ── Defaults (no {lang_label} placeholder — that rule is appended in code) ────

DEFAULT_DIRECT = """You are MacroBot, the AI assistant of the Geneva School of Economics and Management (GSEM), operating in DIRECT mode.

Your behaviour rules:
1. Answer ONLY using the context documents provided below.
2. Always cite your sources at the end of your answer using this exact format:
   📄 [Filename, p.X] List every source you drew from as long as its from a slide or problem set
3. Be precise, professional, and pedagogically helpful. Explain your reasoning clearly.
4. Never invent, hallucinate, or extrapolate beyond what the documents say.
5. The user may write in French or English — respond in the same language they use.
6. When the user asks for a specific exercise (e.g. "exercise 2 of PS 2"), look for that exact exercise number in the retrieved documents and answer it directly. If the exercise number is not found, tell the user which exercises ARE available in the retrieved context so they can clarify.
7. If you receive a LaTeX formula, return your response without the LaTeX formatting."""

DEFAULT_GUIDE = """You are MacroBot, the AI assistant of the Geneva School of Economics and Management (GSEM), operating in GUIDE mode.

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
9. If you receive a LaTeX formula, return your response without the LaTeX formatting."""

# Appended at runtime — not exposed to the admin editor
_LANGUAGE_RULE = "\nYou only have access to the {lang_label} version of the course materials."


def _config_path() -> Path:
    return Path(config.PROMPTS_PATH)


def _read_config() -> dict:
    path = _config_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read config from {path}: {e}")
    return {}


def _write_config(data: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_prompts() -> dict:
    """Return {'direct': str, 'guide': str}, falling back to defaults if not saved yet."""
    data = _read_config()
    return {
        "direct": data.get("direct", DEFAULT_DIRECT),
        "guide": data.get("guide", DEFAULT_GUIDE),
    }


def save_prompts(direct: str, guide: str) -> None:
    """Persist both prompts to disk, preserving other config keys."""
    data = _read_config()
    data["direct"] = direct
    data["guide"] = guide
    _write_config(data)


def load_model() -> str:
    """Return the currently configured model id, falling back to config default."""
    return _read_config().get("model", config.CLAUDE_MODEL)


def save_model(model_id: str) -> None:
    """Persist the chosen model id to disk, preserving other config keys."""
    data = _read_config()
    data["model"] = model_id
    _write_config(data)


def build_system_prompt(mode: str, lang_label: str) -> str:
    """Return the full system prompt for the given mode, with language rule appended."""
    prompts = load_prompts()
    base = prompts["guide"] if mode == "guide" else prompts["direct"]
    return base + _LANGUAGE_RULE.format(lang_label=lang_label)
