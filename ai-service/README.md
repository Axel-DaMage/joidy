# AI Service

FastAPI microservice providing AI features for Joidy: text embeddings, note
classification, and retrieval-augmented generation (RAG). Runs on **port 8002**.

## Tech Stack

- Python 3.12, FastAPI, Uvicorn
- Google Gemini API (default provider)
- Factory pattern supporting 6 AI providers
- Circuit breaker + rate limiter + cost tracking

## Prerequisites

- Docker + Docker Compose (recommended) or Python 3.12 + `requirements.txt`
- At least one AI provider API key in `.env` (see root [AGENTS.md](../AGENTS.md))
- The `api` service must be healthy (it calls this service)

## Development

From the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
make logs-ai      # tail AI service logs
```

Standalone container:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up ai-service
```

## Environment Variables

Key vars (see root [`.env.example`](../.env.example) for the full list):

- `GEMINI_API_KEY` — default provider (https://aistudio.google.com/)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`,
  `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL` — alternate providers
- `LLM_MODEL` — model selection in `provider:model` format
  (e.g. `gemini:gemini-2.0-flash`)
- `EMBEDDING_MODEL` — embedding model selection
- `AI_SERVICE_PORT` — override the default 8002

## Testing

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm ai-service pytest
```

## Endpoints

`POST /embed` (vector embedding), `POST /classify` (tag suggestions),
`POST /rag` (semantic search), `GET /health` (liveness).

## Project Structure

```
ai-service/
├── main.py              App entrypoint, endpoints (/embed, /classify, /rag, /health)
├── config.py            Pydantic Settings (provider + model selection)
├── database.py          Shared DB access for embeddings
├── clients/             AI provider implementations (factory pattern)
│   ├── base.py / factory.py    Abstract interface + provider selection
│   ├── gemini.py               Google Gemini (default)
│   ├── openai.py / anthropic.py / cohere.py / ollama.py / openrouter.py
│   └── prompts.py              Shared prompt templates
├── circuit_breaker.py / rate_limiter.py / cost_tracker.py
└── tests/               Test suite
```

The **factory pattern** in `clients/factory.py` selects the active provider from
`LLM_MODEL`; adding a provider only needs a new client module + factory entry.

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) — system overview and data flow
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
