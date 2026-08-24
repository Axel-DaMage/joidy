# AI Service

FastAPI microservice providing AI-powered features for Joidy: text embeddings,
note classification, and retrieval-augmented generation (RAG). Runs on
**port 8002**.

## Tech Stack

- **Python 3.12**, FastAPI, Uvicorn
- Google Gemini API (default provider)
- Factory pattern supporting 6 AI providers
- Circuit breaker + rate limiter + cost tracking

## Prerequisites

- Docker + Docker Compose (recommended)
- Or Python 3.12 with `requirements.txt` for local dev
- At least one AI provider API key in `.env` (see root [AGENTS.md](../AGENTS.md))
- The `api` service must be healthy (it calls this service)

## Development

Start the full stack with hot reload from the repo root:

```bash
make dev          # all services, hot reload (Ctrl+C to stop)
make logs-ai      # tail AI service logs only
```

To run the AI service container alone:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up ai-service
```

## Environment Variables

Key variables consumed by this service (see root [`.env.example`](../.env.example)
for the full list — do not duplicate here):

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

- `POST /embed` — generate a vector embedding for text
- `POST /classify` — suggest tags / classify a note
- `POST /rag` — semantic search over stored embeddings
- `GET /health` — liveness check

## Project Structure

```
ai-service/
├── main.py              App entrypoint, endpoints (/embed, /classify, /rag, /health)
├── config.py            Pydantic Settings (provider + model selection)
├── database.py          Shared DB access for embeddings
├── clients/             AI provider implementations (factory pattern)
│   ├── base.py          Abstract client interface
│   ├── factory.py       Provider selection by LLM_MODEL
│   ├── gemini.py        Google Gemini (default)
│   ├── openai.py        OpenAI
│   ├── anthropic.py     Anthropic
│   ├── cohere.py        Cohere
│   ├── ollama.py        Local Ollama models
│   ├── openrouter.py    OpenRouter gateway
│   └── prompts.py       Shared prompt templates
├── circuit_breaker.py   Resilience for provider calls
├── rate_limiter.py      Per-provider rate limiting
├── cost_tracker.py      Token / cost accounting
└── tests/               Test suite
```

The **factory pattern** in `clients/factory.py` selects the active provider
based on `LLM_MODEL`, so adding a new provider only requires a new client module
plus a factory entry.

## See Also

- [Architecture](../docs/architecture.md) — system overview and data flow
- [AGENTS.md](../AGENTS.md) — agent instructions, commands, known issues
- [docs/](../docs/) — architecture decision records and guides
