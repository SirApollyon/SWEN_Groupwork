FROM python:3.11-slim

# Install system dependencies required for pymssql (FreeTDS) and Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        freetds-dev \
        freetds-bin \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libtiff5 \
        libopenjp2-7 \
        tesseract-ocr \
        tesseract-ocr-deu \
        libtesseract-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run provides PORT; default to 8080 for local use
# The PORT is now used inside app/main.py
ENV PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# Run the application as a module so package-relative imports resolve correctly.
CMD ["python", "-m", "app.main"]
