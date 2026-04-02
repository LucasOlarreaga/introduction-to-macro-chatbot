import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
CHAT_PASSWORD: str = os.environ.get("CHAT_PASSWORD", "gsem2025")
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "gsem-admin-2025")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
CHROMA_PATH: str = os.environ.get("CHROMA_PATH", "/data/chroma")
PDFS_PATH: str = os.environ.get("PDFS_PATH", "/data/pdfs")

# Seed PDFs bundled in the repo — copied to PDFS_PATH on first boot if not already there
SEED_PDFS_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdfs")

EMBEDDING_MODEL: str = "paraphrase-multilingual-mpnet-base-v2"
CLAUDE_MODEL: str = "claude-sonnet-4-6"
TOP_K_RESULTS: int = 5

DOC_TYPES = ["slides", "textbooks", "problem_sets", "exams"]
LANGUAGES = ["fr", "en"]
