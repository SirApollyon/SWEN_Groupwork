FROM python:3.11-slim

# Install system dependencies required for pymssql (FreeTDS) and Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        freetds-dev \
        freetds-bin \
        tesseract-ocr \
        tesseract-ocr-deu \
        libtesseract-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run provides PORT; default to 8080 for local use
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
