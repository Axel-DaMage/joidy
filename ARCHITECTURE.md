# Arquitectura - Joidy

## Visión General

Joidy es un sistema de gestión de conocimiento personal con gamificación. Es un monorepo con 4 servicios Docker que se comunican entre sí.

```
┌─────────────────────────────────────────────────────────────────────┐
│                              HOST                                   │
│                                                                     │
│   ┌────────────────────────────────────────────────────────────┐  │
│   │                    Docker Network (joidy)                   │  │
│   │                                                            │  │
│   │   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌───────┐  │  │
│   │   │ frontend│    │   API   │    │  AI S.  │    │ Worker│  │  │
│   │   │ :3000   │    │  :8000  │    │  :8002  │    │:8001  │  │  │
│   │   └────┬────┘    └────┬────┘    └────┬────┘    └───┬───┘  │  │
│   │        │              │              │             │      │  │
│   │        └──────────────┴──────────────┴─────────────┘      │  │
│   │                         │                                  │  │
│   │                  ┌──────┴──────┐                            │  │
│   │                  │  SQLite DB  │                            │  │
│   │                  │  (sqlite-   │                            │  │
│   │                  │   vec)      │                            │  │
│   │                  └─────────────┘                            │  │
│   └────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐ │
│   │  OBSIDIAN VAULT (/vault mount)                              │ │
│   └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Servicios

### Frontend (SvelteKit + Vite + TypeScript)

- **Puerto**: 3000
- **Propósito**: Interfaz de usuario
- **Stack**: SvelteKit, TypeScript, CSS variables
- **Comunicación**: HTTP REST hacia API

### API (FastAPI + Python 3.12)

- **Puerto**: 8000
- **Propósito**: REST API principal
- **Stack**: FastAPI, SQLAlchemy, Pydantic, Alembic
- **Responsabilidades**:
  - Endpoints CRUD para notas, tags, habilidades, metas
  - Gamificación (XP, rachas, etapas de planta)
  - Autenticación OAuth GitHub
  - Integración con Obsidian vault

### AI Service (FastAPI + Gemini)

- **Puerto**: 8002
- **Propósito**: Embeddings y clasificación de notas
- **Stack**: FastAPI, Google Gemini API
- **Endpoints**:
  - `/embed` - Genera vector embedding de texto
  - `/classify` - Clasifica nota con tags sugeridos
  - `/rag` - Búsqueda semántica

### Worker (Python asyncio)

- **Puerto**: 8001
- **Propósito**: Tareas en background
- **Stack**: Python asyncio, watchdog
- **Responsabilidades**:
  - Vault watcher: detecta cambios en archivos .md
  - Daily writer: escribe resúmenes diarios

## Flujo de Datos

### Sincronización de Notas (Obsidian → Joidy)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Obsidian    │    │    Worker    │    │     API      │    │  SQLite DB   │
│  Vault       │───▶│ vault_watcher│───▶│ POST /notes  │───▶│   (notes)    │
│  (.md files) │    │ (file change)│    │  (import)    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

1. Usuario/edición en Obsidian
2. Worker detecta cambio en `/vault`
3. Worker envía nota a API
4. API guarda en SQLite, procesa gamificación

### Gamificación

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │    │     API      │    │   Game       │    │  SQLite DB   │
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

## Base de Datos

### Esquema Principal

```
┌─────────────────────────────────────────────────────────────────────┐
│                              NOTES                                  │
├─────────────┬─────────────────┬─────────────┬──────────────────────┤
│     id      │     title       │   content   │     source_path      │
├─────────────┼─────────────────┼─────────────┼──────────────────────┤
│     1       │  "Mi nota"      │  "# Cont..." │ /vault/notes/n1.md  │
└─────────────┴─────────────────┴─────────────┴──────────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────────┐     ┌─────────────────────┐
│     NOTETAGS        │     │        TAGS          │
├─────────────────────┼─────┼──────────────────────┤
│ note_id │  tag_id  │     │  id  │     name       │
└─────────────────────┘     └──────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
                         ┌─────────────────────┐
                         │   TAGCOOCCURRENCES   │
                         ├─────────────────────┤
                         │ tag_a │ tag_b │ weight│
                         └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                            USERSTATS (singleton)                    │
├─────────────┬──────────────┬─────────────┬─────────────────────────┤
│ total_xp    │current_streak│plant_stage │ last_activity_date      │
├─────────────┼──────────────┼─────────────┼─────────────────────────┤
│   15420     │      7       │     3      │    2026-05-09           │
└─────────────┴──────────────┴─────────────┴─────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                              GOALS                                  │
├─────────────┬──────────────┬─────────────┬─────────────────────────┤
│     id      │    title    │ target_date│      completed          │
├─────────────┼──────────────┼─────────────┼─────────────────────────┤
│     1       │ "Aprender   │ 2026-06-01 │         false           │
│             │  Python"    │            │                         │
└─────────────┴──────────────┴─────────────┴─────────────────────────┘
```

## Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Frontend | SvelteKit, TypeScript, CSS Variables |
| API | FastAPI, Pydantic, SQLAlchemy |
| AI | Google Gemini API |
| DB | SQLite + sqlite-vec |
| Worker | Python asyncio, watchdog |
| DevOps | Docker Compose, Make |

## Variables de Entorno

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

## Seguridad

- **CORS**: Configurable por entorno (`APP_ENV`)
- **Rate Limiting**: 60 req/min global
- **Sanitización**: XSS, longitud de inputs, normalización
- **Secrets**: Nunca en git (`.env` en `.gitignore`)

## Scaling (Futuro)

- **DB**: PostgreSQL para producción
- **Cache**: Redis para respuestas
- **Queue**: Celery para tareas async
- **Realtime**: WebSockets para updates live