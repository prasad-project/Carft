FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng poppler-utils libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# More OCR languages: install e.g. tesseract-ocr-hin and set OCR_LANG=eng+hin
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m appuser && mkdir -p /data && chown appuser /data
USER appuser
ENV STORAGE_DIR=/data
EXPOSE 8000
# One worker: job state and the rate limiter are in-process (see docs/ARCHITECTURE.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
