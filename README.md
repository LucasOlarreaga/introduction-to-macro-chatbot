# IntegrAI — GSEM Chatbot

An AI teaching assistant for the Geneva School of Economics and Management (GSEM). Students ask questions about course materials; the bot answers using only the uploaded documents, with full source citations.

---

## Features

- **RAG pipeline** — answers grounded exclusively in uploaded course PDFs (slides, textbooks, problem sets, exams)
- **Two modes** — *Direct* (full answers with citations) and *Guide* (Socratic dialogue, never gives the answer outright)
- **Bilingual** — French and English course versions, each with their own document index
- **Admin panel** — upload/delete documents, edit system prompts, and select the Claude model, all without redeploying
- **Persistent vector index** — ChromaDB on a Railway volume; survives redeploys

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| LLM | Anthropic Claude (model selectable at runtime) |
| Vector DB | ChromaDB |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` |
| PDF parsing | pdfplumber |
| Deployment | Docker on Railway |

---

## Project structure

```
├── app/
│   ├── main.py        # FastAPI routes
│   ├── chat.py        # Claude API calls
│   ├── prompts.py     # Prompt & model config (load/save from /data/prompts.json)
│   ├── rag.py         # ChromaDB retrieval
│   ├── ingest.py      # PDF ingestion & chunking
│   ├── auth.py        # Token-based auth
│   └── config.py      # Environment config
├── static/
│   ├── login.html
│   ├── chat.html
│   └── admin.html
├── pdfs/              # Seed PDFs (bundled in repo, ingested on first boot)
│   ├── fr/
│   │   ├── slides/
│   │   ├── textbooks/
│   │   ├── problem_sets/
│   │   └── exams/
│   └── en/
│       └── ...
├── Dockerfile
├── railway.toml
└── requirements.txt
```

---

## Deployment (Railway)

### 1. Prerequisites

- A [Railway](https://railway.app) account
- An [Anthropic](https://console.anthropic.com) API key
- This repository pushed to GitHub

### 2. Add seed PDFs

Place course PDFs in the appropriate `pdfs/` subfolders before deploying. They are ingested automatically on first boot.

### 3. Deploy

1. Railway → **New Project** → **Deploy from GitHub repo** → select this repo
2. Railway detects the Dockerfile automatically

### 4. Environment variables

Set these in Railway → your service → **Variables**:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `CHAT_PASSWORD` | Password shared with students |
| `ADMIN_PASSWORD` | Password for the admin panel (teachers only) |
| `SECRET_KEY` | Random secret for signing auth tokens — generate once and never change |

Generate a `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Persistent volume

Railway → your service → **Volumes** → add a volume mounted at `/data`.

This stores the vector index and uploaded PDFs between deploys. **Without this, all indexed documents are lost on every redeploy.**

---

## Admin panel

Navigate to `/admin` and log in with the `ADMIN_PASSWORD`.

### Documents
Upload new PDFs (select language + document type, then drag & drop). Indexed documents are listed and can be deleted individually. Changes take effect immediately.

### Claude model
Select which Claude model to use for all responses. The dropdown is populated live from the Anthropic API, so newly released models appear automatically.

### System prompts
Edit the instructions given to MacroBot for Direct mode and Guide mode. Changes take effect on the next chat message — no restart required.

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and set:
#   CHROMA_PATH=./data/chroma
#   PDFS_PATH=./data/pdfs

# Start the server
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

---

## Updating the student password

Railway → your service → **Variables** → edit `CHAT_PASSWORD` → save. Railway redeploys automatically.
