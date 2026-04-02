# IntegrAI GSEM — Setup Guide

## First-time deployment on Railway

### 1. Prerequisites
- A [Railway](https://railway.app) account
- An [Anthropic](https://console.anthropic.com) API key
- This project pushed to a GitHub repository

---

### 2. Add your PDFs
Place your course PDFs in the correct folders **before deploying**:

```
pdfs/
├── fr/
│   ├── slides/          ← French lecture slides
│   ├── textbooks/       ← French textbooks
│   ├── problem_sets/    ← French problem sets & corrections
│   └── exams/           ← French past exams
└── en/
    ├── slides/
    ├── textbooks/
    ├── problem_sets/
    └── exams/
```

### 3. Add your logo
Place your logo file at: `static/logo.jpg`

---

### 4. Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select this repository
3. Railway will detect the Dockerfile automatically

#### Add environment variables (Railway dashboard → your service → Variables):

| Variable | Value | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | From Anthropic console |
| `CHAT_PASSWORD` | e.g. `gsem2025` | Shared with students |
| `ADMIN_PASSWORD` | e.g. `admin-secret` | Teachers only |
| `SECRET_KEY` | random 32-char string | Generate once, never change |

To generate a `SECRET_KEY`, run in any terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### Add a persistent volume (Railway dashboard → your service → Volumes):
- Mount path: `/data`
- This stores uploaded PDFs and the vector index between deploys

---

### 5. Changing the student password each year

1. Go to Railway dashboard → your service → **Variables**
2. Find `CHAT_PASSWORD` → click **Edit** → type the new password → **Save**
3. Railway will automatically redeploy with the new password

---

### 6. Adding new documents (without redeploying)

1. Go to `https://your-app.railway.app/admin`
2. Log in with your **Admin Password**
3. Select language and document type
4. Drag & drop the PDF → click **Upload & Index**

The document is available to the chatbot immediately.

---

### 7. Local development (optional)

```bash
# Clone repo and install dependencies
pip install -r requirements.txt

# Copy and fill in the env file
cp .env.example .env
# Edit .env with your API keys

# Run locally
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000
```

> **Note:** For local development, update `.env` to set:
> ```
> CHROMA_PATH=./data/chroma
> PDFS_PATH=./data/pdfs
> ```
> Then copy your PDFs into `pdfs/` before starting.
