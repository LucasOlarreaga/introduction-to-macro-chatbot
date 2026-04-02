"""
ChromaDB setup and retrieval.
One collection per language: gsem_fr, gsem_en.
"""
import logging

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from . import config

logger = logging.getLogger(__name__)

# Singleton clients — initialised once per process
_chroma_client = None
_embedding_fn = None


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
            model_name=config.EMBEDDING_MODEL
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


def retrieve(query: str, lang: str, n_results: int = None) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query in the given language.
    Returns a list of dicts with keys: text, filename, page, type.
    """
    if n_results is None:
        n_results = config.TOP_K_RESULTS

    collection = get_collection(lang)
    count = collection.count()
    if count == 0:
        return []

    # ChromaDB errors if n_results > document count
    n_results = min(n_results, count)

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Convert cosine distance to similarity score (0–1)
        similarity = 1 - dist
        if similarity < 0.2:  # Skip very irrelevant results
            continue
        chunks.append({
            "text": doc,
            "filename": meta.get("filename", ""),
            "page": meta.get("page", "?"),
            "type": meta.get("type", ""),
            "score": round(similarity, 3),
        })

    return chunks
