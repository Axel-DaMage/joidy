FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (uid 1000 matches typical host user for dev volume mounts)
RUN addgroup --system --gid 1000 app && adduser --system --uid 1000 --ingroup app app

COPY --chown=app:app . .

USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
