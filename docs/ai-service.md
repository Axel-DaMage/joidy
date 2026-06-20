# Joidy - AI Service

## Metadata

```yaml
framework: FastAPI
port: 8002
language: Python 3.12
ai_provider: Google Gemini
vector_store: sqlite-vec
```

---

## 1. Resumen

El AI Service proporciona capacidades de Inteligencia Artificial para el sistema Joidy:
- Generación de embeddings vectoriales
- Clasificación automática de notas
- Búsqueda semántica (RAG)
- Rate limiting
- Cost tracking

---

## 2. Estructura

```
ai-service/
├── main.py           # FastAPI app
├── config.py         # Settings
├── gemini_client.py  # Cliente de Gemini
├── database.py       # Read-only DB access
├── rate_limiter.py   # Rate limiting
└── cost_tracker.py   # Tracking de costos
```

---

## 3. Endpoints

### 3.1 POST /embed

**Propósito:** Generar embedding vectorial para un texto

**Request:**
```json
{
  "text": "Contenido de la nota sobre machine learning...",
  "model": "embedding-001"
}
```

**Response:**
```json
{
  "embedding": [0.123, -0.456, 0.789, ...],
  "dimensions": 768,
  "model": "embedding-001"
}
```

**Detalles:**
- Modelo: `text-embedding-004` de Gemini
- Dimensiones: 768
- Pooling: 默认 (averaging)

---

### 3.2 POST /classify

**Propósito:** Clasificar nota y sugerir tags basándose en contenido

**Request:**
```json
{
  "note_id": 42,
  "content": "Contenido de la nota...",
  "existing_tags": ["python", "data"]
}
```

**Response:**
```json
{
  "note_id": 42,
  "status": "completed",
  "suggestions": [
    {
      "tag": "machine-learning",
      "confidence": 0.92,
      "is_new": true
    },
    {
      "tag": "neural-networks",
      "confidence": 0.85,
      "is_new": true
    },
    {
      "tag": "python",
      "confidence": 0.78,
      "is_new": false
    }
  ]
}
```

**Proceso:**
1. Obtener contenido de la nota
2. Obtener tags existentes
3. Enviar a Gemini con prompt de clasificación
4. Parsear respuesta y extraer tags
5. Calcular confianza basada en posición en respuesta
6. Guardar sugerencias en DB (confidence < 1.0)

---

### 3.3 POST /rag

**Propósito:** Búsqueda semántica en notas

**Request:**
```json
{
  "query": "Cómo optimizar modelos de machine learning",
  "top_k": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "note_id": 15,
      "title": "Optimización de Modelos",
      "content": "Para optimizar modelos...",
      "score": 0.92
    },
    {
      "note_id": 23,
      "title": "Hyperparameter Tuning",
      "content": "Los hiperparámetros...",
      "score": 0.87
    }
  ]
}
```

**Proceso:**
1. Generar embedding del query
2. Buscar en sqlite-vec notas similares
3. Ordenar por score
4. Devolver top_k resultados

---

### 3.4 GET /health

**Propósito:** Health check

**Response:**
```json
{
  "status": "ok"
}
```

---

### 3.5 GET /usage

**Propósito:** Ver uso y costos

**Response:**
```json
{
  "ai_enabled": true,
  "estimated_cost_usd": 0.05
}
```

---

## 4. Cliente de Gemini

### 4.1 Ubicación

`ai-service/gemini_client.py`

### 4.2 Configuración

```python
import google.genai as genai

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel('gemini-pro')
embedding_model = genai.GenerativeModel('text-embedding-004')
```

### 4.3 Métodos

```python
class GeminiClient:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def generate_embeddings(self, text: str) -> list[float]:
        result = genai.embed_content(
            model='text-embedding-004',
            content=text
        )
        return result['embedding']

    def classify(self, content: str, existing_tags: list[str]) -> list[dict]:
        prompt = f"""
Clasifica el siguiente contenido y sugiere tags relevantes.

Contenido:
{content}

Tags existentes: {', '.join(existing_tags)}

Devuelve una lista de tags sugeridos con confianza (0-1).
"""
        response = model.generate_content(prompt)
        # Parsear respuesta y retornar lista
        return parse_response(response)

    def chat(self, prompt: str, context: str) -> str:
        """Para futuro: chat con notas como contexto"""
        response = model.generate_content(f"""
Contexto de las notas:
{context}

Pregunta del usuario:
{prompt}
""")
        return response.text
```

---

## 5. Rate Limiting

### 5.1 Ubicación

`ai-service/rate_limiter.py`

### 5.2 Implementación

```python
from fastapi import HTTPException
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}

    def check(self, api_key: str):
        now = time.time()
        minute_ago = now - 60

        # Limpiar requests viejos
        self.requests[api_key] = [
            t for t in self.requests.get(api_key, [])
            if t > minute_ago
        ]

        if len(self.requests[api_key]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )

        self.requests[api_key].append(now)
```

### 5.3 Uso en Endpoints

```python
@app.post("/embed")
async def embed(request: EmbedRequest, rate_limiter: RateLimiter = Depends()):
    rate_limiter.check(settings.gemini_api_key)

    # Procesar request
    ...
```

---

## 6. Cost Tracking

### 6.1 Ubicación

`ai-service/cost_tracker.py`

### 6.2 Implementación

```python
class CostTracker:
    def __init__(self):
        self.total_tokens = 0
        self.total_cost = 0.0
        self.month = datetime.now().month

    def add_usage(self, input_tokens: int, output_tokens: int):
        # Precios aproximados Gemini
        input_cost = input_tokens * 0.000000125  # $0.125/1M tokens
        output_cost = output_tokens * 0.0000005  # $0.50/1M tokens

        self.total_tokens += input_tokens + output_tokens
        self.total_cost += input_cost + output_cost

    def get_usage(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.total_cost, 4),
            "month": self.month
        }
```

---

## 7. Base de Datos

### 7.1 Acceso

El AI service tiene acceso de solo lectura a la DB compartida:

```python
# ai-service/database.py
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
)
```

### 7.2 Tablas Usadas

| Tabla | Acceso | Propósito |
|-------|--------|-----------|
| notes | Read | Leer contenido para classify |
| tags | Read | Obtener tags existentes |
| note_tags | Read | Join con notas |
| embedding_failures | Read/Write | Retry de embeddings |

---

## 8. Configuración

### 8.1 Variables de Entorno

```python
# ai-service/config.py
gemini_api_key: str = ""  # Required for AI features
database_url: str = "sqlite:////data/db/joidy.db"
app_env: str = "development"
```

### 8.2 Docker Compose

```yaml
ai-service:
  build:
    context: ./ai-service
    dockerfile: Dockerfile
  volumes:
    - ./data/db:/data/db
  environment:
    - GEMINI_API_KEY=${GEMINI_API_KEY}
    - DATABASE_URL=sqlite:////data/db/joidy.db
    - APP_ENV=${APP_ENV:-development}
  depends_on:
    api:
      condition: service_healthy
```

---

## 9. Errores Comunes

| Error | Código | Causa | Solución |
|-------|--------|-------|----------|
| 429 Too Many Requests | HTTP 429 | Rate limit excedido | Esperar, reintentar |
| 400 Invalid API Key | HTTP 400 | Key inválida | Verificar GEMINI_API_KEY |
| 500 Gemini Error | HTTP 500 | Error de Gemini | Reintentar más tarde |
| 503 Service Unavailable | HTTP 503 | Gemini no disponible | Verificar servicio |

---

## 10. Modelos de Gemini

| Operación | Modelo | Notas |
|-----------|--------|-------|
| Embeddings | text-embedding-004 | 768 dimensiones |
| Clasificación | gemini-pro | Prompt-based |
| Chat/RAG | gemini-pro | Con contexto |

---

## 11. Desarrollo

### 11.1 Ver Logs

```bash
make logs-ai
```

### 11.2 Shell

```bash
docker compose exec ai-service bash
```

### 11.3 Test Manual

```bash
curl -X POST http://localhost:8002/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

---

## 12. Consideraciones

### 12.1 Costos

- Embeddings: ~$0.0001/1K caracteres
- Clasificación: ~$0.001/call
- Monitorear uso con `GET /usage`

### 12.2 Privacidad

- El contenido de notas se envía a Google Gemini
- No almacenar datos sensibles en notas
- Considerar self-hosted alternativas en el futuro

### 12.3 Fallbacks

- Si Gemini no disponible: guardar en embedding_failures para retry
- Si rate limit: esperar y reintentar