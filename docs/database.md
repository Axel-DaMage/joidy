# Joidy - Base de Datos

## Metadata

```yaml
engine: PostgreSQL 16
extension: pgvector (vector embeddings)
container: postgres
volume: postgres_data
shared: true
```

---

## 1. Configuración

### 1.1 Engine Setup

```python
# api/database.py
from sqlalchemy import create_engine, text

engine = create_engine(
    settings.database_url,  # postgresql://joidy:joidy@postgres:5432/joidy
)

# pgvector extension is created on init_db()
def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    _run_migrations()
```

### 1.2 Migraciones

Las migraciones se gestionan con **Alembic** (`api/alembic/versions/`). Aplicar con `make migrate`.

---

## 2. Esquema de Tablas

### 2.1 Notas y Etiquetas

#### notes

```sql
CREATE TABLE notes (
    id INTEGER PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT DEFAULT '',
    source VARCHAR(50) DEFAULT 'joidy',
    source_path VARCHAR(1000),
    is_embedded BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_notes_source_path ON notes(source_path);
```

| Campo | Tipo | Valores posibles | Descripción |
|-------|------|-----------------|-------------|
| id | INTEGER | Auto | Primary key |
| title | VARCHAR(500) | - | Título de la nota |
| content | TEXT | - | Contenido markdown |
| source | VARCHAR(50) | joidy, obsidian | Origen de la nota |
| source_path | VARCHAR(1000) | - | Ruta en Obsidian (nullable) |
| is_embedded | BOOLEAN | - | Si es nota embebida |
| created_at | DATETIME | - | Fecha de creación |
| updated_at | DATETIME | - | Fecha de modificación |

---

#### tags

```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES tags(id),
    color VARCHAR(20) DEFAULT '#888888',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| name | VARCHAR(100) | No | Nombre único |
| parent_id | INTEGER | Sí | FK a tags.id (jerarquía) |
| color | VARCHAR(20) | No | Color hexadecimal |
| created_at | DATETIME | No | Fecha de creación |

---

#### note_tags

```sql
CREATE TABLE note_tags (
    note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(20) DEFAULT 'manual',
    PRIMARY KEY (note_id, tag_id)
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| note_id | INTEGER | FK a notes.id |
| tag_id | INTEGER | FK a tags.id |
| confidence | FLOAT | 1.0 = manual, <1.0 = sugerido IA |
| source | VARCHAR(20) | manual o ai |

---

#### note_links

```sql
CREATE TABLE note_links (
    source_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    target_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    context_text TEXT,
    PRIMARY KEY (source_note_id, target_note_id)
);
```

WikiLinks entre notas.

---

#### tag_cooccurrences

```sql
CREATE TABLE tag_cooccurrences (
    tag_a_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    tag_b_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    weight INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_a_id, tag_b_id)
);
```

Precalcula co-ocurrencias para el grafo de conocimiento.

---

#### embedding_failures

```sql
CREATE TABLE embedding_failures (
    note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    attempts INTEGER DEFAULT 0,
    last_error TEXT DEFAULT '',
    next_retry_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (note_id)
);
```

Registro de reintentos de embeddings fallidos (ver `embedding_service.py`).

---

#### note_embeddings

```sql
CREATE TABLE note_embeddings (
    note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE PRIMARY KEY,
    embedding VECTOR(768)
);
```

Vector de embeddings por nota (pgvector, dimensión 768 = Gemini). Un solo embedding por nota (PK = note_id).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| note_id | INTEGER | FK a notes.id (PK, un embedding por nota) |
| embedding | VECTOR(768) | Vector semántico generado por el provider de embeddings |

Retry logic para embeddings fallidos.

---

### 2.2 Objetivos

#### goals

```sql
CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    temporality VARCHAR(20) NOT NULL,
    measurement_type VARCHAR(20) NOT NULL,
    target_value INTEGER NOT NULL,
    current_value INTEGER DEFAULT 0,
    state VARCHAR(20) DEFAULT 'ACTIVE',
    fail_config VARCHAR(20) DEFAULT 'STATIC',
    fail_emoji VARCHAR(10) DEFAULT '💪',
    color VARCHAR(20) DEFAULT '#888888',
    theme VARCHAR(100),
    note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    tag_id INTEGER REFERENCES tags(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES goals(id) ON DELETE SET NULL,
    max_assignment_days INTEGER,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Valores |
|-------|------|---------|
| temporality | VARCHAR(20) | DAILY, WEEKLY, MONTHLY, ANNUAL |
| measurement_type | VARCHAR(20) | COUNT, BOOLEAN, PERCENT |
| state | VARCHAR(20) | ACTIVE, COMPLETED, FAILED, PAUSED, CANCELLED |
| fail_config | VARCHAR(20) | STATIC, ROLLOVER, SNOWBALL |

---

### 2.3 Gamificación

#### xp_events

```sql
CREATE TABLE xp_events (
    id INTEGER PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    xp INTEGER NOT NULL,
    metadata_json VARCHAR(500) DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Tipos de eventos:**
| Evento | XP | Descripción |
|--------|-----|-------------|
| note_created | +10 | Nota creada |
| note_edited | +5 | Nota editada |
| tag_added | +3 | Tag agregado |
| topic_connected | +8 | Conexión en grafo |
| goal_completed | +50 | Objetivo completado |
| daily_activity | +15 | Actividad diaria |

---

#### streak_records

```sql
CREATE TABLE streak_records (
    id INTEGER PRIMARY KEY,
    activity_date DATE UNIQUE NOT NULL,
    xp_earned INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

#### user_stats

```sql
CREATE TABLE user_stats (
    id INTEGER PRIMARY KEY DEFAULT 1,
    total_xp INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    plant_stage INTEGER DEFAULT 0,
    last_activity_date DATE,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Tabla singleton (id=1)**

---

### 2.4 Rachas Personales

#### personal_streaks

```sql
CREATE TABLE personal_streaks (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    emoji VARCHAR(10),
    icon VARCHAR(50),
    description TEXT,
    color VARCHAR(20) DEFAULT '#888888',
    theme VARCHAR(100),
    category VARCHAR(50),
    start_date DATE,
    target_date DATE,
    offset INTEGER DEFAULT 0,
    frequency VARCHAR(20) DEFAULT 'daily',
    frequency_days INTEGER DEFAULT 1,
    is_archived BOOLEAN DEFAULT FALSE,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    total_checkins INTEGER DEFAULT 0,
    freeze_count INTEGER DEFAULT 0,
    freeze_used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

#### streak_checkins

```sql
CREATE TABLE streak_checkins (
    id INTEGER PRIMARY KEY,
    streak_id INTEGER REFERENCES personal_streaks(id) ON DELETE CASCADE,
    check_date DATE NOT NULL,
    note TEXT,
    mood INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

### 2.5 Habilidades

#### skills

```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY,
    tag_id INTEGER UNIQUE REFERENCES tags(id) ON DELETE CASCADE,
    level VARCHAR(20) DEFAULT 'seedling',
    note_count INTEGER DEFAULT 0,
    first_unlocked_at DATETIME
);
```

**Niveles:**
| Level | Descripción |
|-------|-------------|
| seedling | < 5 notas |
| sapling | 5-15 notas |
| tree | > 15 notas |

---

### 2.6 Planificación

#### planning_assignments

```sql
CREATE TABLE planning_assignments (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, goal_id)
);
```

---

### 2.7 Integración GitHub

#### github_repos

```sql
CREATE TABLE github_repos (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    full_name VARCHAR(200) UNIQUE NOT NULL,
    description TEXT,
    url VARCHAR(500) NOT NULL,
    default_branch VARCHAR(100) DEFAULT 'main',
    is_private BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'ACTIVE',       -- GitHubRepoStatus: ACTIVE | ARCHIVED
    webhook_id INTEGER,
    webhook_secret VARCHAR(100),
    last_synced_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| name | VARCHAR(200) | Nombre del repo |
| full_name | VARCHAR(200) | `owner/repo` (único) |
| description | TEXT | Descripción del repo |
| url | VARCHAR(500) | URL del repo |
| default_branch | VARCHAR(100) | Rama por defecto |
| is_private | BOOLEAN | Si es repo privado |
| status | VARCHAR(50) | ACTIVE o ARCHIVED |
| webhook_id | INTEGER | ID del webhook de GitHub |
| webhook_secret | VARCHAR(100) | Secreto para verificar firma del webhook |
| last_synced_at | DATETIME | Última sincronización |
| created_at / updated_at | DATETIME | Timestamps |

---

#### github_items

Items de GitHub sincronizados (issues/PRs) y su vínculo con goals/notas.

```sql
CREATE TABLE github_items (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES github_repos(id) ON DELETE CASCADE,
    external_id INTEGER NOT NULL,
    item_type VARCHAR(50) NOT NULL,            -- GitHubItemType: ISSUE | PULL_REQUEST
    number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    body TEXT DEFAULT '',
    state VARCHAR(20) DEFAULT 'open',
    state_reason VARCHAR(50),
    author VARCHAR(100) DEFAULT '',
    assignee VARCHAR(100),
    labels VARCHAR(500) DEFAULT '',
    url VARCHAR(500) NOT NULL,
    html_url VARCHAR(500) NOT NULL,
    goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL,
    note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| repo_id | INTEGER | FK a github_repos.id |
| external_id | INTEGER | ID del item en GitHub |
| item_type | VARCHAR(50) | ISSUE o PULL_REQUEST |
| number | INTEGER | Número en GitHub |
| title | VARCHAR(500) | Título |
| body | TEXT | Cuerpo |
| state | VARCHAR(20) | open/closed |
| state_reason | VARCHAR(50) | Motivo de cierre |
| author | VARCHAR(100) | Autor |
| assignee | VARCHAR(100) | Asignado |
| labels | VARCHAR(500) | Labels separados por coma |
| url / html_url | VARCHAR(500) | URLs del item |
| goal_id | INTEGER | FK a goals.id (opcional, item → goal) |
| note_id | INTEGER | FK a notes.id (opcional, item → nota) |

---

#### github_events

Webhook events de GitHub crudos, pendientes de procesar.

```sql
CREATE TABLE github_events (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES github_repos(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,           -- GitHubEventType: ISSUES | PULL_REQUEST | ...
    action VARCHAR(50) NOT NULL,
    sender VARCHAR(100) NOT NULL,
    item_type VARCHAR(50),
    item_number INTEGER,
    item_external_id INTEGER,
    payload JSON DEFAULT '{}',
    processed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| repo_id | INTEGER | FK a github_repos.id |
| event_type | VARCHAR(50) | Tipo de evento (issues, pull_request, ...) |
| action | VARCHAR(50) | Acción (opened, closed, ...) |
| sender | VARCHAR(100) | Usuario que disparó el evento |
| item_type | VARCHAR(50) | Tipo de item afectado |
| item_number / item_external_id | INTEGER | Identificación del item |
| payload | JSON | Payload crudo del webhook |
| processed | BOOLEAN | Si ya fue procesado por el worker |

---

### 2.8 Integración Google

#### google_tokens

Tokens de integraciones Google (Gmail, Calendar, Tasks, Contacts).

```sql
CREATE TABLE google_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1 UNIQUE,
    access_token TEXT,
    refresh_token_encrypted TEXT,
    token_type VARCHAR DEFAULT 'Bearer',
    expires_at DATETIME,
    scope TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Usuario (único, un token por usuario) |
| access_token | TEXT | Access token de OAuth |
| refresh_token_encrypted | TEXT | Refresh token cifrado |
| token_type | VARCHAR | Bearer |
| expires_at | DATETIME | Expiración del access token |
| scope | TEXT | Scopes concedidos |

---

### 2.9 Push Notifications

#### push_subscriptions

Suscripciones Web Push (VAPID) por usuario.

```sql
CREATE TABLE push_subscriptions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    endpoint VARCHAR NOT NULL,
    p256dh VARCHAR NOT NULL,
    auth VARCHAR NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Usuario |
| endpoint | VARCHAR | Endpoint de Push API |
| p256dh | VARCHAR | Clave pública del cliente |
| auth | VARCHAR | Secreto de autenticación |

---

### 2.10 Sincronización

#### sync_state

Estado de sincronización por nota (para sync bidireccional con Obsidian).

```sql
CREATE TABLE sync_state (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL,
    last_synced_at DATETIME,
    local_mtime DATETIME,
    remote_mtime DATETIME,
    conflict BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| note_id | INTEGER | Nota sincronizada |
| last_synced_at | DATETIME | Última sincronización |
| local_mtime | DATETIME | Modificación local |
| remote_mtime | DATETIME | Modificación remota |
| conflict | BOOLEAN | Si hay conflicto pendiente |

---

### 2.11 Configuración

#### system_config

Configuración clave-valor del sistema.

```sql
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY,
    key VARCHAR UNIQUE NOT NULL,
    value VARCHAR,
    updated_at DATETIME
);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| key | VARCHAR | Clave (única) |
| value | VARCHAR | Valor |
| updated_at | DATETIME | Última actualización |

---

### 2.12 Métricas de IA

#### api_usage

Tracking de uso/costo de las llamadas al servicio de IA (creada en la migración `d4e5f6a7b8c9`).

```sql
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY,
    operation VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX ix_api_usage_created_at ON api_usage(created_at);
CREATE INDEX ix_api_usage_operation ON api_usage(operation);
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | Primary key |
| operation | VARCHAR(50) | Operación (embed, classify, rag) |
| input_tokens | INTEGER | Tokens de entrada |
| output_tokens | INTEGER | Tokens de salida |
| created_at | TIMESTAMPTZ | Fecha (UTC) |

---

## 3. Modelos ORM

### 3.1 Located in `api/models/`

| Archivo | Modelos |
|---------|---------|
| note.py | Note, Tag, NoteTag, NoteLink, TagCooccurrence, EmbeddingFailure, NoteEmbedding |
| goal.py | Goal |
| gamification.py | XPEvent, StreakRecord, UserStats |
| personal_streaks.py | PersonalStreak, StreakCheckin |
| skill.py | Skill |
| planning.py | PlanningAssignment |
| github.py | GitHubRepo, GitHubItem, GitHubEvent |
| google_token.py | GoogleToken |
| sync_state.py | SyncState |
| push_subscription.py | PushSubscription |
| config.py | SystemConfig |

> `api_usage` no tiene modelo ORM; se crea vía migración (`d4e5f6a7b8c9_add_api_usage.py`) y se escribe directamente con SQLAlchemy Core en el ai-service.

### 3.2 Ejemplo de Modelo

```python
# api/models/note.py
from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(50), default="joidy")
    source_path: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    tags: Mapped[list["NoteTag"]] = relationship("NoteTag", back_populates="note", cascade="all, delete-orphan")
```

---

## 4. Migraciones

### 4.1 Alembic Setup

```python
# api/database.py
from alembic import command
from alembic.config import Config

def _run_migrations():
    alembic_ini = Path(__file__).resolve().parent / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
```

### 4.2 Comandos

```bash
# Aplicar migraciones
make migrate
# o
docker compose exec api alembic -c /app/alembic.ini upgrade head

# Ver estado
make db-health

# Crear migración
docker compose exec api alembic revision -m "description"
```

### 4.3 Migraciones existentes

| Archivo | Descripción |
|---------|-------------|
| 2f638d55375d_schema.py | Schema inicial consolidado |
| a1b2c3d4e5f6_cleanup_hex_named_tags.py | Limpieza de tags con nombres hex |
| bce8f3a471d1_add_push_subscriptions_table.py | Tabla push_subscriptions |
| c3d4e5f6a7b8_add_google_tokens.py | Tabla google_tokens |
| d4e5f6a7b8c9_add_api_usage.py | Tabla api_usage (costo IA) |
| 8261da3f5e9d_add_sync_state.py | Tabla sync_state |
| e5f6a7b8c9d0_add_missing_indexes.py | Índices faltantes (ix_notes_created_at, ix_notes_updated_at) |

---

## 5. Índices

| Tabla | Índice | Columnas |
|-------|--------|----------|
| notes | idx_notes_source_path | source_path |
| tags | (primary) | id |
| note_tags | (primary) | note_id, tag_id |
| goal | (primary) | id |
| xp_events | idx_xp_events_created | created_at |

---

## 6. Foreign Keys

Todas las tablas usan `ON DELETE CASCADE` para relaciones padre-hijo.

**Excepciones:**
- goals.note_id → SET NULL (objetivo puede existir sin nota)
- goals.tag_id → SET NULL
- goals.parent_id → SET NULL

---

## 7. Timestamps

- Todos los timestamps en UTC
- Usar `server_default=func.now()` para que la DB genere el valor
- Actualizaciones usan `onupdate=func.now()`