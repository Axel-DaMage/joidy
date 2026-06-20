FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for sqlite-vec and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["/bin/sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --timeout-keep-alive ${UVICORN_TIMEOUT_KEEP_ALIVE:-5} --proxy-headers --forwarded-allow-ips='*'"]
