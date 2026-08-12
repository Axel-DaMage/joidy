FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Switch apt sources to HTTPS (Fastly 403s on HTTP from Docker build network)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (uid 1000 matches typical host user for dev volume mounts)
RUN addgroup --system --gid 1000 app && adduser --system --uid 1000 --ingroup app app

COPY --chown=app:app . .

USER app

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import os, signal; os.kill(1, 0)" || exit 1

CMD ["python", "main.py"]
