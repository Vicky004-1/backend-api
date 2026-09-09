FROM python:3.11-slim

WORKDIR /app

# Install C-compiler tools required for Swiss Ephemeris (pyswisseph)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create empty ephemeris directory in case the code references it
RUN mkdir -p /srv/ephe

# Copy requirements and install dependencies
COPY requirements* ./
RUN pip install --no-cache-dir -r requirements*

# Copy all project code into the container
COPY . .

ENV EPHE_PATH=/srv/ephe
ENV PYTHONUNBUFFERED=1

# Start FastAPI using the dynamic PORT provided by Render
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
