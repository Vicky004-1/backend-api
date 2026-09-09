FROM python:3.11-slim

# Tesseract with Devanagari, plus the OpenCV runtime deps that the headless
# wheel still needs on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-hin libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ephe ./ephe

ENV EPHE_PATH=/srv/ephe PYTHONUNBUFFERED=1
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
