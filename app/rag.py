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

# Matches any mention of problem sets in French or English, with or without a number.
# Examples: PS, PS1, PS 2, TP, TP3, TP 4, problem set, exercice, correction, travaux pratiques
_PROBLEM_SET_RE = re.compile(
    r"\b("
    r"ps\s*\d*"
    r"|tp\s*\d*"
    r"|problem\s+sets?"
    r"|exercices?"
    r"|exercises?"
    r"|corrections?"
    r"|travaux\s+pratiques?"
    r")\b",
    re.IGNORECASE,
)


def _is_problem_set_query(query: str) -> bool:
    return bool(_PROBLEM_SET_RE.search(query))


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
    """Run a single ChromaDB query and return filtered chunks."""
    if n <= 0:
        return []

    kwargs = dict(
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
        similarity = 1 - dist  # cosine distance → similarity
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


def retrieve(query: str, lang: str, n_results: int = None) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query in the given language.

    If the query references problem sets (PS / TP / exercice / …), problem_set
    documents are fetched first and fill the available slots; remaining slots are
    filled with any other doc type.  For all other queries the search is unfiltered.

    Returns a list of dicts with keys: text, filename, page, type, score.
    """
    if n_results is None:
        n_results = config.TOP_K_RESULTS

    collection = get_collection(lang)
    count = collection.count()
    if count == 0:
        return []

    # ChromaDB errors if n_results > document count
    n_results = min(n_results, count)

    if _is_problem_set_query(query):
        logger.debug("Problem-set query detected — prioritising problem_sets doc type.")

        # 1. Get as many problem_set chunks as possible (up to n_results)
        ps_chunks = _query_chunks(
            collection, query, n_results,
            where={"type": {"$eq": "problem_sets"}},
        )

        # 2. Fill remaining slots with non-problem-set chunks
        remaining = n_results - len(ps_chunks)
        other_chunks = []
        if remaining > 0:
            other_chunks = _query_chunks(
                collection, query, remaining,
                where={"type": {"$ne": "problem_sets"}},
            )

        return ps_chunks + other_chunks

    # Default: unfiltered search across all doc types
    return _query_chunks(collection, query, n_results)
