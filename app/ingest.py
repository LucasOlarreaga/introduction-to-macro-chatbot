"""
PDF ingestion: extract text → chunk by page → store in ChromaDB.
Called at startup for seed PDFs and via the admin upload endpoint.
"""
import os
import re
import shutil
import logging
from pathlib import Path

import pdfplumber

from . import config
from .rag import get_collection, embedding_function

logger = logging.getLogger(__name__)


def _doc_id(lang: str, doc_type: str, filename: str, page: int) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)
    return f"{lang}__{doc_type}__{safe}__p{page}"


def ingest_pdf(filepath: str, lang: str, doc_type: str) -> int:
    """
    Ingest a single PDF into ChromaDB. Returns number of pages indexed.
    Skips pages already indexed (idempotent).
    """
    filename = os.path.basename(filepath)
    collection = get_collection(lang)

    pages_added = 0
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                doc_id = _doc_id(lang, doc_type, filename, page_num)

                # Skip if already indexed
                existing = collection.get(ids=[doc_id])
                if existing["ids"]:
                    continue

                text = page.extract_text()
                if not text or len(text.strip()) < 20:
                    continue  # Skip blank/unreadable pages

                collection.add(
                    ids=[doc_id],
                    documents=[text.strip()],
                    metadatas=[{
                        "lang": lang,
                        "type": doc_type,
                        "filename": filename,
                        "page": page_num,
                        "filepath": filepath,
                    }],
                )
                pages_added += 1

    except Exception as e:
        logger.error(f"Failed to ingest {filepath}: {e}")
        raise

    logger.info(f"Ingested {filename} ({lang}/{doc_type}): {pages_added} new pages")
    return pages_added


def ingest_seed_pdfs() -> None:
    """
    On startup, copy seed PDFs from the repo's /pdfs folder to PDFS_PATH
    (the Railway volume) if they don't exist there yet, then ingest any
    that haven't been indexed.
    """
    seed_root = Path(config.SEED_PDFS_PATH)
    data_root = Path(config.PDFS_PATH)

    if not seed_root.exists():
        logger.info("No seed PDFs folder found, skipping.")
        return

    for lang in config.LANGUAGES:
        for doc_type in config.DOC_TYPES:
            src_dir = seed_root / lang / doc_type
            dst_dir = data_root / lang / doc_type
            dst_dir.mkdir(parents=True, exist_ok=True)

            if not src_dir.exists():
                continue

            for pdf_file in src_dir.glob("*.pdf"):
                dst_file = dst_dir / pdf_file.name
                # Copy to volume if not already there
                if not dst_file.exists():
                    shutil.copy2(pdf_file, dst_file)
                    logger.info(f"Copied seed PDF: {pdf_file.name} → {dst_dir}")

                # Ingest (idempotent — skips already-indexed pages)
                try:
                    ingest_pdf(str(dst_file), lang, doc_type)
                except Exception as e:
                    logger.error(f"Error ingesting seed PDF {pdf_file.name}: {e}")


def ingest_uploaded_pdf(file_bytes: bytes, filename: str, lang: str, doc_type: str) -> int:
    """Save uploaded PDF to volume and ingest it. Returns pages indexed."""
    dst_dir = Path(config.PDFS_PATH) / lang / doc_type
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / filename

    with open(dst_file, "wb") as f:
        f.write(file_bytes)

    return ingest_pdf(str(dst_file), lang, doc_type)


def list_indexed_documents() -> list[dict]:
    """Return all indexed documents grouped by filename."""
    docs = {}
    for lang in config.LANGUAGES:
        collection = get_collection(lang)
        results = collection.get(include=["metadatas"])
        for meta in results["metadatas"]:
            key = f"{meta['lang']}/{meta['type']}/{meta['filename']}"
            if key not in docs:
                docs[key] = {
                    "lang": meta["lang"],
                    "type": meta["type"],
                    "filename": meta["filename"],
                    "pages": 0,
                }
            docs[key]["pages"] += 1
    return sorted(docs.values(), key=lambda d: (d["lang"], d["type"], d["filename"]))


def delete_document(lang: str, doc_type: str, filename: str) -> int:
    """Remove all chunks for a document from ChromaDB. Returns chunks deleted."""
    collection = get_collection(lang)
    results = collection.get(where={"filename": filename}, include=["metadatas"])
    ids_to_delete = results["ids"]
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    # Also remove file from volume if present
    filepath = Path(config.PDFS_PATH) / lang / doc_type / filename
    if filepath.exists():
        filepath.unlink()

    return len(ids_to_delete)
