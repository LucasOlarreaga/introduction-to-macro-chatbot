import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .auth import create_token, require_user, require_admin
from .ingest import ingest_seed_pdfs, ingest_uploaded_pdf, list_indexed_documents, delete_document
from .rag import retrieve
from .chat import generate_response, format_sources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — ingesting seed PDFs...")
    try:
        ingest_seed_pdfs()
    except Exception as e:
        logger.error(f"Seed ingestion error: {e}")
    logger.info("Startup complete.")
    yield


app = FastAPI(title="IntegrAI GSEM", lifespan=lifespan)


# ── Static files ──────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(str(STATIC_DIR / "login.html"))


@app.get("/chat")
def chat_page():
    return FileResponse(str(STATIC_DIR / "chat.html"))


@app.get("/admin")
def admin_page():
    return FileResponse(str(STATIC_DIR / "admin.html"))


# ── Auth endpoints ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
def login(body: LoginRequest):
    if body.password == config.CHAT_PASSWORD:
        return {"token": create_token("user")}
    if body.password == config.ADMIN_PASSWORD:
        return {"token": create_token("admin")}
    raise HTTPException(status_code=401, detail="Invalid password")


@app.post("/api/admin/login")
def admin_login(body: LoginRequest):
    if body.password != config.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"token": create_token("admin")}


# ── Chat endpoint ─────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    language: str           # "fr" or "en"
    history: list[Message] = []


@app.post("/api/chat")
def chat(body: ChatRequest, _role: str = Depends(require_user)):
    if body.language not in config.LANGUAGES:
        raise HTTPException(status_code=400, detail="Invalid language")

    # Retrieve relevant document chunks
    chunks = retrieve(body.message, body.language)

    # Build history for Claude (exclude context injections — keep only clean turns)
    history = [{"role": m.role, "content": m.content} for m in body.history]

    # Generate response
    reply = generate_response(body.message, chunks, history, body.language)
    sources = format_sources(chunks)

    return {
        "reply": reply,
        "sources": sources,
    }


# ── Admin: document management ────────────────────────────────────────────────

@app.get("/api/admin/documents")
def get_documents(_role: str = Depends(require_admin)):
    return list_indexed_documents()


@app.post("/api/admin/upload")
async def upload_document(
    file: UploadFile = File(...),
    lang: str = Form(...),
    doc_type: str = Form(...),
    _role: str = Depends(require_admin),
):
    if lang not in config.LANGUAGES:
        raise HTTPException(status_code=400, detail="Invalid language")
    if doc_type not in config.DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    pages = ingest_uploaded_pdf(content, file.filename, lang, doc_type)
    return {"filename": file.filename, "pages_indexed": pages}


@app.delete("/api/admin/documents")
def remove_document(
    lang: str,
    doc_type: str,
    filename: str,
    _role: str = Depends(require_admin),
):
    deleted = delete_document(lang, doc_type, filename)
    return {"deleted_chunks": deleted}
