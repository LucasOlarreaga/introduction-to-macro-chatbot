FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the multilingual embedding model so startup is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

COPY . .

# Seed PDFs are bundled with the image; uploaded PDFs go to /data/pdfs (Railway volume)
RUN mkdir -p /data/chroma /data/pdfs/fr/slides /data/pdfs/fr/textbooks \
    /data/pdfs/fr/problem_sets /data/pdfs/fr/exams \
    /data/pdfs/en/slides /data/pdfs/en/textbooks \
    /data/pdfs/en/problem_sets /data/pdfs/en/exams

EXPOSE 8000

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
