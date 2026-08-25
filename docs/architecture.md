# Joidy - Arquitectura del Sistema

## Metadata

```yaml
project: Joidy
type: Sistema de Gestión del Conocimiento con Gamificación
version: 0.1.3
framework: Monorepo Docker
services: 4
database: PostgreSQL 16 + pgvector
primary_language: Python (API, Worker, AI) + TypeScript (Frontend)
```

## 1. Resumen Ejecutivo

Joidy es un sistema personal de gestión del conocimiento que integra:
- **Gestión de notas** con sincronización de Obsidian
- **Grafo de conocimiento** basado en tags y co-ocurrencias
- **Sistema de objetivos** con múltiples temporalidades
- **Rachas personales** con check-ins y freezes
- **Gamificación** con XP, niveles y evolución de planta
- **IA** para embeddings, clasificación y búsqueda semántica

## 2. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JOIDY SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐               │
│   │  FRONTEND   │      │     API     │      │  AI SERVICE │               │
│   │  SvelteKit  │◀────▶│   FastAPI   │◀────▶│   Gemini    │               │
│   │  :3000      │      │   :8000     │      │   :8002     │               │
│   └──────┬──────┘      └──────┬──────┘      └──────┬──────┘               │
│          │                    │                    │                       │
│          │                    │                    │                       │
│          │              ┌────▼────────────────────▼────┐                  │
│          │              │        DATABASE               │                  │
│          │              │   PostgreSQL 16 + pgvector    │                  │
│          │              │   (postgres container)        │                  │
│          │              └───────────────────────────────┘                  │
│          │                           │                                      │
│          └───────────────────────────┼──────────────────────────────────────┤
│                                      │                                      │
│                              ┌───────▼──────┐                              │
│                              │   WORKER     │                              │
│                              │   asyncio    │                              │
│                              │   :8001      │                              │
│                              └───────┬──────┘                              │
│                                      │                                      │
│                                      │ File System                          │
│                               ┌──────▼──────┐                              │
│                               │   OBSIDIAN  │                              │
│                               │    VAULT    │                              │
│                               │  (Mount)    │                              │
│                               └─────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. Servicios

### 3.1 Frontend

| Atributo | Valor |
|----------|-------|
| Puerto | 3000 |
| Framework | SvelteKit + Vite + TypeScript |
| Puerto interno | 3000 |
| Dependencias | API (service_healthy) |

**Responsabilidades:**
- Renderizado de interfaz de usuario
- Gestión de estado con Svelte stores
- Comunicación REST con API
- Template rendering

**Rutas definidas:**
```
src/routes/
├── +page.svelte          # Dashboard principal
├── +layout.svelte        # Layout con sidebar
├── notes/                # Gestión de notas
│   └── +page.svelte      # Listado y editor
├── graph/                # Grafo de conocimiento
│   └── +page.svelte      # Visualización D3
├── skills/               # Árbol de habilidades
│   └── +page.svelte      # Skill tree
├── goals/                # Sistema de objetivos
│   ├── +page.svelte      # Listado
│   └── [id]/+page.svelte # Editor de objetivo
└── streaks/              # Rachas personales
    └── +page.svelte      # Gestión de rachas
```

**Volúmenes de desarrollo:**
```yaml
volumes:
  - ./frontend/src:/app/src    # Hot reload
  - ./frontend/static:/app/static
```

---

### 3.2 API

| Atributo | Valor |
|----------|-------|
| Puerto | 8000 |
| Framework | FastAPI (Python 3.12) |
| Puerto interno | 8000 |
| Health check | `curl -f http://localhost:8000/health` |

**Responsabilidades:**
- API REST completa
- Lógica de negocio
- Acceso a base de datos
- Integración con servicios externos
- Autenticación (futuro)

**Endpoints registrados:**
```python
# Routers incluidos en main.py
app.include_router(notes.router)           # /notes
app.include_router(tags.router)            # /tags
app.include_router(config.router)          # /config
app.include_router(skills.router)          # /skills
app.include_router(goals.router)           # /goals
app.include_router(gamification.router)    # /gamification
app.include_router(personal_streaks.router)# /personal-streaks
app.include_router(github.router)          # /integrations/github
app.include_router(vault.router)           # /vault
app.include_router(ai.router)              # /ai
app.include_router(planning.router)        # /planning
```

**Estructura de directorios:**
```
api/
├── main.py                      # FastAPI app, middleware, CORS
├── config.py                    # Pydantic Settings
├── database.py                  # SQLAlchemy engine + pgvector
├── logging_config.py            # Logging setup
├── routers/                     # Endpoints REST
│   ├── __init__.py
│   ├── notes.py                 # CRUD notas
│   ├── tags.py                  # Gestión tags
│   ├── config.py               # Configuración sistema
│   ├── goals.py                 # Objetivos
│   ├── gamification.py          # XP y stats
│   ├── personal_streaks.py      # Rachas personales
│   ├── skills.py                # Habilidades
│   ├── vault.py                 # Sync vault
│   ├── ai.py                    # IA endpoints
│   ├── planning.py              # Planificación
│   └── integrations/
│       ├── __init__.py
│       └── github.py            # GitHub integration
├── services/                    # Lógica de negocio
│   ├── gamification_engine.py   # Motor de XP
│   ├── tag_graph.py            # Grafo de tags
│   ├── skill_tree.py           # Árbol de habilidades
│   ├── embedding_service.py     # Embeddings
│   ├── embedding_retry.py       # Retry logic
│   ├── note_service.py          # Notas
│   ├── goal_service.py          # Objetivos
│   ├── github_service.py        # GitHub
│   ├── joidy_vault_writer.py    # Escritor vault
│   └── response_cache.py        # Cache (placeholder)
├── models/                      # SQLAlchemy ORM
│   ├── note.py                  # Notes, Tags, NoteTags, NoteLinks
│   ├── goal.py                  # Goals
│   ├── gamification.py          # XPEvent, StreakRecord, UserStats
│   ├── personal_streaks.py      # PersonalStreak, StreakCheckin
│   ├── skill.py                 # Skill
│   ├── planning.py              # PlanningAssignment
│   └── github.py                # GitHubRepo
└── alembic/                     # Migraciones
    ├── env.py
    └── versions/
```

**Volúmenes de desarrollo:**
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data  # PostgreSQL DB
  - ./data/uploads:/data/uploads
  - ./.env:/app/.env           # Configuración
```

**Variables de entorno:**
```python
# api/config.py
database_url: str = "postgresql://joidy:joidy@postgres:5432/joidy"
ai_service_url: str = "http://ai-service:8002"
worker_url: str = "http://worker:8001"
secret_key: str = "dev_secret_change_me"
app_env: str = "development"
github_client_id: str = ""
github_client_secret: str = ""
github_oauth_web_url: str = ""
github_token: str = ""
github_username: str = ""
github_webhook_url: str = ""
embedding_retry_max_attempts: int = 8
embedding_retry_base_seconds: int = 60
xp_table_json: str = ""
```

---

### 3.3 AI Service

| Atributo | Valor |
|----------|-------|
| Puerto | 8002 |
| Framework | FastAPI (Python 3.12) |
| Puerto interno | 8002 |
| Dependencias | API (service_healthy) |

**Responsabilidades:**
- Generación de embeddings vectoriales
- Clasificación automática de notas
- Búsqueda semántica (RAG)
- Rate limiting
- Cost tracking

**Endpoints:**
```
POST /embed          # Generar embedding
POST /classify       # Clasificar nota
POST /rag            # Búsqueda semántica
GET  /health         # Health check
GET  /usage          # Costos y uso
```

**Estructura:**
```
ai-service/
├── main.py           # FastAPI app
├── config.py         # Settings (GEMINI_API_KEY)
├── gemini_client.py  # Cliente Gemini
├── database.py       # Read-only DB access
├── rate_limiter.py   # Rate limiting
└── cost_tracker.py   # Cost tracking
```

---

### 3.4 Worker

| Atributo | Valor |
|----------|-------|
| Puerto | 8001 |
| Framework | Python asyncio |
| Puerto interno | 8001 |
| Dependencias | API (service_healthy) |

**Responsabilidades:**
- Monitoreo de vault Obsidian
- Importación automática de notas
- Escritura de resúmenes diarios
- Tareas programadas

**Estructura:**
```
worker/
├── main.py                 # Entry point (TaskGroup)
├── config.py               # Settings
├── logging_config.py
├── watchers/
│   ├── __init__.py
│   └── vault_watcher.py    # FileSystemEventHandler
└── tasks/
    ├── __init__.py
    └── joidy_daily_writer.py # Resúmenes diarios
```

**Comportamiento del Vault Watcher:**
- Observa `/vault` (mount del Obsidian vault)
- Filtro: `.md` files
- Debounce: 2 segundos
- Hash-based change detection
- Envía a API via HTTP

## 4. Flujo de Datos

### 4.1 Sincronización de Notas (Obsidian → Joidy)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Obsidian    │    │    Worker    │    │     API      │    │ PostgreSQL   │
│  Vault       │───▶│ vault_watcher│───▶│ POST /notes  │───▶│   (notes)    │
│  (.md files) │    │ (file change)│    │  (import)    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

1. Usuario/edición en Obsidian
2. Worker detecta cambio en `/vault`
3. Worker envía nota a API
4. API guarda en PostgreSQL, procesa gamificación

### 4.2 Gamificación

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │    │     API      │    │   Game       │    │ PostgreSQL   │
│  (user act)  │───▶│ POST /notes  │───▶│   Engine     │───▶│ (XP + streak)│
│              │    │              │    │ (+XP,streak) │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
        │                                       │
        ▼                                       ▼
┌──────────────┐                        ┌──────────────┐
│  XP Event    │                        │ Plant Stage  │
│  Animation   │                        │   Update     │
└──────────────┘                        └──────────────┘
```

## 5. Base de Datos

### 5.1 Configuración

**Motor:** PostgreSQL 16 con extensión `pgvector` para vectores

**Contenedor:** `postgres` (volumen `postgres_data`)

**Configuración aplicada:**
```python
# api/database.py — init_db()
CREATE EXTENSION IF NOT EXISTS vector
# Migraciones vía Alembic (make migrate)
```

### 5.2 Tablas

| Tabla | Propósito |
|-------|-----------|
| notes | Notas del sistema |
| tags | Etiquetas (estructura árbol) |
| note_tags | Relación nota-etiqueta |
| note_links | WikiLinks entre notas |
| tag_cooccurrences | Co-ocurrencias precalculadas |
| embedding_failures | Retry de embeddings |
| goals | Objetivos |
| xp_events | Registro de XP |
| streak_records | Días con actividad |
| user_stats | Stats globales (singleton) |
| personal_streaks | Rachas personalizadas |
| streak_checkins | Check-ins de rachas |
| skills | Habilidades derivadas de tags |
| planning_assignments | Asignaciones de objetivos |
| github_repos | Repos sincronizados |

## 6. Comunicación entre Servicios

| Origen | Destino | Protocolo | Endpoint |
|--------|---------|-----------|----------|
| Frontend | API | HTTP REST | http://api:8000 |
| API | AI Service | HTTP REST | http://ai-service:8002 |
| API | Worker | HTTP REST | http://worker:8001 |
| Worker | API | HTTP REST | http://api:8000 |
| Worker | Vault | FS | /vault (mount) |

## 7. Volúmenes Docker

| Volumen | Servicio | Propósito |
|---------|----------|-----------|
| postgres_data | API, AI, Worker | PostgreSQL DB compartida |
| ./data/uploads | API | Archivos subidos |
| ./data/vault | Worker | Vault temporal |
| ./frontend/src | Frontend | Hot reload |
| ./.env | API | Configuración |
| ${OBSIDIAN_VAULT_PATH} | Worker | Vault Obsidian |

## 8. Health Checks

| Servicio | Check | Intervalo |
|----------|-------|------------|
| API | curl -f http://localhost:8000/health | 10s |
| Frontend | depends_on api.condition=service_healthy | - |
| AI Service | depends_on api.condition=service_healthy | - |
| Worker | depends_on api.condition=service_healthy | - |

## 9. Entornos

### Development
- Hot reload activo
- Volúmenes montados para código fuente
- `.env` compartido

### Production
- Imágenes Docker optimizadas
- Sin mounts de código
- Configuración via env vars

## 10. Dependencias Externas

| Servicio | Proveedor | Propósito |
|----------|-----------|-----------|
| Gemini API | Google AI Studio | Embeddings, clasificación |
| Obsidian Vault | Sistema de archivos local | Sincronización de notas |
| GitHub API | github.com | Sincronización de issues/PRs |
| Telegram Bot | Telegram | Notificaciones |

## 11. Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Frontend | SvelteKit, TypeScript, CSS Variables |
| API | FastAPI, Pydantic, SQLAlchemy |
| AI | Google Gemini API |
| DB | PostgreSQL 16 + pgvector |
| Worker | Python asyncio, watchdog |
| DevOps | Docker Compose, Make |

## 12. Variables de Entorno

```bash
# Obligatorias
GEMINI_API_KEY        # API de Google Gemini
OBSIDIAN_VAULT_PATH   # Ruta absoluta al vault
SECRET_KEY            # Clave para sesiones

# Opcionales
GITHUB_CLIENT_ID      # OAuth GitHub
GITHUB_CLIENT_SECRET  # OAuth GitHub
GITHUB_TOKEN          # PAT para sincronización
TELEGRAM_BOT_TOKEN    # Bot de Telegram
```

## 13. Seguridad

- **CORS**: Configurable por entorno (`APP_ENV`)
- **Rate Limiting**: 60 req/min global
- **Sanitización**: XSS, longitud de inputs, normalización
- **Secrets**: Nunca en git (`.env` en `.gitignore`)

## 14. Scaling (Futuro)

- **DB**: PostgreSQL para producción
- **Cache**: Redis para respuestas
- **Queue**: Celery para tareas async
- **Realtime**: WebSockets para updates live