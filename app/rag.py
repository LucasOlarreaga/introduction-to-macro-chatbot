"""
ChromaDB setup and retrieval.
One collection per language: gsem_fr, gsem_en.
"""
import re
import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from . import config

logger = logging.getLogger(__name__)

# Singleton clients — initialised once per process
_chroma_client = None
_embedding_fn = None

# ---------------------------------------------------------------------------
# Query-intent detection
# ---------------------------------------------------------------------------

# Matches any reference to a problem set, in French or English, with or without a number.
#
# English: PS, PS1, PS 2, problem set, exercise set, exercice set, problem sheet, worksheet
# French:  TP, TP3, TP 4, travaux pratiques, série d'exercices, feuille d'exercices
# Generic: exercice(s), exercise(s), correction(s)
_PROBLEM_SET_RE = re.compile(
    r"\b("
    # ── English ──────────────────────────────────────────────
    r"ps\s*\d*"
    r"|problem\s+sets?"
    r"|exercise\s+sets?"
    r"|exercice\s+sets?"          # franglais variant
    r"|problem\s+sheets?"
    r"|work\s*sheets?"
    # ── French ───────────────────────────────────────────────
    r"|tp\s*\d*"
    r"|travaux\s+pratiques?"
    r"|s[eé]ries?\s+d['']exercices?"
    r"|feuilles?\s+d['']exercices?"
    # ── Generic (kept for broad coverage) ────────────────────
    r"|exercices?"
    r"|exercises?"
    r"|corrections?"
    r")\b",
    re.IGNORECASE,
)

# Captures the specific number when a numbered problem set is referenced.
# The keyword list mirrors _PROBLEM_SET_RE but only keeps forms that naturally
# precede a number (avoids false positives from bare "exercice 2").
#
# Examples matched:
#   EN → PS 2, PS2, problem set 3, exercise set 1, problem sheet 4, worksheet 2
#   FR → TP 1, TP4, travaux pratiques 2, série d'exercices 3, feuille d'exercices 1
_PROBLEM_SET_NUM_RE = re.compile(
    r"\b(?:"
    # ── English ──────────────────────────────────────────────
    r"ps"
    r"|problem\s+sets?"
    r"|exercise\s+sets?"
    r"|exercice\s+sets?"
    r"|problem\s+sheets?"
    r"|work\s*sheets?"
    # ── French ───────────────────────────────────────────────
    r"|tp"
    r"|travaux\s+pratiques?"
    r"|s[eé]ries?\s+d['']exercices?"
    r"|feuilles?\s+d['']exercices?"
    r")\s*(\d+)\b",
    re.IGNORECASE,
)

# Matches an explicit week number reference.
# e.g. "week 2", "week2", "Week 12", "semaine 3", "séance 4"
_WEEK_RE = re.compile(
    r"\b(?:week|semaine|s[eé]ance)\s*(\d{1,2})\b",
    re.IGNORECASE,
)

# Matches an explicit French slide-deck number (the numeric prefix in filenames
# like "02_PIB.pdf", "10_EquilibreEcoOuverte.pdf").
# e.g. "slide 2", "cours 3", "chapitre 10", "diapo 5"
_FR_SLIDE_NUM_RE = re.compile(
    r"\b(?:slide|cours|chapitre|diapo(?:sitive)?|s[eé]ance)\s*(\d{1,2})\b",
    re.IGNORECASE,
)


def _is_problem_set_query(query: str) -> bool:
    return bool(_PROBLEM_SET_RE.search(query))


def _detect_problem_set_number(query: str) -> str | None:
    """Return the specific PS/TP number if referenced, e.g. '2' for 'PS 2'."""
    m = _PROBLEM_SET_NUM_RE.search(query)
    return m.group(1) if m else None


def _get_filenames_for_problem_set(
    collection: chromadb.Collection, ps_num: str
) -> list[str]:
    """
    Return all problem_set filenames that reference the given PS/TP number.
    Matches patterns like 'PS 2', 'PS2', 'TP2', 'TP 2' in filenames.
    """
    pattern = re.compile(
        rf"\b(?:ps|tp)\s*{re.escape(ps_num)}\b",
        re.IGNORECASE,
    )
    results = collection.get(where={"type": "problem_sets"}, include=["metadatas"])
    filenames: set[str] = set()
    for meta in results.get("metadatas", []):
        fn = meta.get("filename", "")
        if pattern.search(fn):
            filenames.add(fn)
    return list(filenames)


def _detect_week_number(query: str) -> str | None:
    """Return the week number string if an explicit week reference is found."""
    m = _WEEK_RE.search(query)
    return m.group(1) if m else None


def _detect_fr_slide_number(query: str) -> str | None:
    """Return the slide-deck number string for French slide references."""
    m = _FR_SLIDE_NUM_RE.search(query)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Filename-based slide resolution
# ---------------------------------------------------------------------------

def _get_filenames_for_week(collection: chromadb.Collection, week_num: str) -> list[str]:
    """
    Return all slide filenames that explicitly reference the given week number.
    Matches "Week 2", "Week2", "Week 12", etc.
    """
    pattern = re.compile(rf"\bWeek\s*{re.escape(week_num)}\b", re.IGNORECASE)
    results = collection.get(where={"type": "slides"}, include=["metadatas"])
    filenames: set[str] = set()
    for meta in results.get("metadatas", []):
        fn = meta.get("filename", "")
        if pattern.search(fn):
            filenames.add(fn)
    return list(filenames)


def _get_filenames_for_fr_slide(collection: chromadb.Collection, slide_num: str) -> list[str]:
    """
    Return all French slide filenames whose numeric prefix matches slide_num.
    e.g. slide_num="2" matches "02_PIB.pdf".
    """
    padded = slide_num.zfill(2)  # "2" → "02"
    pattern = re.compile(rf"^{re.escape(padded)}_", re.IGNORECASE)
    results = collection.get(where={"type": "slides"}, include=["metadatas"])
    filenames: set[str] = set()
    for meta in results.get("metadatas", []):
        fn = meta.get("filename", "")
        if pattern.search(fn):
            filenames.add(fn)
    return list(filenames)


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def get_client():
    global _chroma_client
    if _chroma_client is None:
        logger.info(f"Initialising ChromaDB at {config.CHROMA_PATH}")
        _chroma_client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    return _chroma_client


def embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=config.EMBEDDING_MODEL,
        )
    return _embedding_fn


def get_collection(lang: str) -> chromadb.Collection:
    """Get or create the ChromaDB collection for a language."""
    client = get_client()
    ef = embedding_function()
    return client.get_or_create_collection(
        name=f"gsem_{lang}",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def _query_chunks(
    collection: chromadb.Collection,
    query: str,
    n: int,
    where: dict | None = None,
) -> list[dict]:
    """Run a single ChromaDB query and return similarity-filtered chunks."""
    if n <= 0:
        return []

    kwargs: dict = dict(
        query_texts=[query],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        similarity = 1 - dist  # cosine distance → similarity score
        if similarity < 0.2:
            continue
        chunks.append({
            "text": doc,
            "filename": meta.get("filename", ""),
            "page": meta.get("page", "?"),
            "type": meta.get("type", ""),
            "score": round(similarity, 3),
        })
    return chunks


def _get_all_chunks_from_files(
    collection: chromadb.Collection,
    filenames: list[str],
) -> list[dict]:
    """
    Fetch EVERY indexed page from the given files, sorted by filename then
    page number.  Used when we know exactly which document the user wants —
    the whole thing should be available, not just the top-K similar pages.
    """
    results = collection.get(
        where={"filename": {"$in": filenames}},
        include=["documents", "metadatas"],
    )
    chunks = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        chunks.append({
            "text": doc,
            "filename": meta.get("filename", ""),
            "page": meta.get("page", "?"),
            "type": meta.get("type", ""),
            "score": 1.0,
        })
    # Return in reading order
    chunks.sort(key=lambda c: (c["filename"], c["page"] if isinstance(c["page"], int) else 0))
    return chunks


def _priority_retrieve(
    collection: chromadb.Collection,
    query: str,
    n_results: int,
    primary_where: dict,
    fallback_where: dict | None = None,
    primary_filenames: list[str] | None = None,
) -> list[dict]:
    """
    Retrieve chunks, prioritising a primary set.

    If primary_filenames is provided, ALL pages from those files are fetched
    in reading order (no semantic cap) — this is used when the user asks about
    a specific week's slides or a specific problem set.

    Remaining context slots are filled with a semantic search using fallback_where.
    """
    if primary_filenames is not None:
        primary = _get_all_chunks_from_files(collection, primary_filenames)
    else:
        primary = _query_chunks(collection, query, n_results, where=primary_where)

    remaining = n_results - len(primary)
    if remaining <= 0:
        return primary
    fallback = _query_chunks(collection, query, remaining, where=fallback_where)
    return primary + fallback


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(query: str, lang: str, n_results: int = None) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query.

    Priority rules (first match wins):
    1. Problem-set query  → problem_sets docs first, rest as filler
    2. Week-N query       → slides for that specific week first, rest as filler
    3. French slide-N     → slides with that numeric prefix first, rest as filler
    4. Default            → unfiltered semantic search across all doc types

    Returns a list of dicts: text, filename, page, type, score.
    """
    if n_results is None:
        n_results = config.TOP_K_RESULTS

    collection = get_collection(lang)
    count = collection.count()
    if count == 0:
        return []

    n_results = min(n_results, count)  # ChromaDB errors if n_results > count

    # --- 1. Problem-set priority ---
    if _is_problem_set_query(query):
        ps_num = _detect_problem_set_number(query)
        if ps_num:
            filenames = _get_filenames_for_problem_set(collection, ps_num)
            if filenames:
                logger.debug(f"Specific PS/TP-{ps_num} detected → {filenames} (full fetch)")
                return _priority_retrieve(
                    collection, query, n_results,
                    primary_where={"filename": {"$in": filenames}},
                    fallback_where={"filename": {"$nin": filenames}},
                    primary_filenames=filenames,
                )
        # No specific number — prioritise all problem_sets over other types
        logger.debug("Generic problem-set query detected.")
        return _priority_retrieve(
            collection, query, n_results,
            primary_where={"type": {"$eq": "problem_sets"}},
            fallback_where={"type": {"$ne": "problem_sets"}},
        )

    # --- 2. English week-N priority ---
    week_num = _detect_week_number(query)
    if week_num:
        filenames = _get_filenames_for_week(collection, week_num)
        if filenames:
            logger.debug(f"Week-{week_num} query detected → {filenames} (full fetch)")
            return _priority_retrieve(
                collection, query, n_results,
                primary_where={"filename": {"$in": filenames}},
                fallback_where={"filename": {"$nin": filenames}},
                primary_filenames=filenames,
            )

    # --- 3. French slide-N priority ---
    if lang == "fr":
        slide_num = _detect_fr_slide_number(query)
        if slide_num:
            filenames = _get_filenames_for_fr_slide(collection, slide_num)
            if filenames:
                logger.debug(f"FR slide-{slide_num} query detected → {filenames} (full fetch)")
                return _priority_retrieve(
                    collection, query, n_results,
                    primary_where={"filename": {"$in": filenames}},
                    fallback_where={"filename": {"$nin": filenames}},
                    primary_filenames=filenames,
                )

    # --- 4. Default unfiltered search ---
    return _query_chunks(collection, query, n_results)
