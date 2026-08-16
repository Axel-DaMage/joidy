# Joidy - Base de Datos

## Metadata

```yaml
engine: PostgreSQL 16
extension: pgvector (vector embeddings)
container: postgres
volume: postgres_data
shared: true
```

> **Fuente de verdad:** El código en `api/models/*.py` y las migraciones de
> Alembic son la definición autoritativa del esquema. Este documento es una
> referencia legible para humanos y puede quedarse atrás respecto al código. En
> caso de duda, lee los modelos y las migraciones.

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

## 3. Enums

Estos tipos `enum.Enum` (subclase de `str`) respaldan columnas `Enum` de SQLAlchemy.

### `GoalTemporality` (`api/models/goal.py`)
| Valor | Descripción |
|-------|-------------|
| `DAILY` | Objetivo diario |
| `WEEKLY` | Objetivo semanal |
| `MONTHLY` | Objetivo mensual |
| `ANNUAL` | Objetivo anual |

### `GoalMeasurement` (`api/models/goal.py`)
| Valor | Descripción |
|-------|-------------|
| `COUNT` | Medido por conteo |
| `BOOLEAN` | Hecho / no hecho |
| `PERCENT` | Medido como porcentaje |

### `GoalState` (`api/models/goal.py`)
| Valor | Descripción |
|-------|-------------|
| `ACTIVE` | En progreso |
| `COMPLETED` | Finalizado con éxito |
| `FAILED` | Fallado |
| `PAUSED` | Pausado temporalmente |
| `CANCELLED` | Cancelado |

### `GoalFailConfig` (`api/models/goal.py`)
| Valor | Descripción |
|-------|-------------|
| `STATIC` | Comportamiento de fallo estático |
| `ROLLOVER` | Arrastre al fallar |
| `SNOWBALL` | Acumulación tipo bola de nieve |

### `GitHubRepoStatus` (`api/models/github.py`)
| Valor | Descripción |
|-------|-------------|
| `ACTIVE` | El repo se está sincronizando |
| `PAUSED` | Sincronización pausada |
| `DISABLED` | Sincronización deshabilitada |

### `GitHubItemType` (`api/models/github.py`)
| Valor | Descripción |
|-------|-------------|
| `ISSUE` | Issue de GitHub |
| `PR` | Pull request |
| `COMMIT` | Commit |

### `GitHubSyncStatus` (`api/models/github.py`)
| Valor | Descripción |
|-------|-------------|
| `SYNCED` | Item sincronizado |
| `PENDING` | Sincronización pendiente |
| `FAILED` | Sincronización fallida |

### `GitHubEventType` (`api/models/github.py`)
| Valor | Descripción |
|-------|-------------|
| `issues` | Evento de issue |
| `pull_request` | Evento de pull request |
| `issue_comment` | Evento de comentario de issue |
| `push` | Evento de push |

---

## 4. Diagrama Entidad-Relación

```mermaid
erDiagram
    notes ||--o{ note_tags : "has"
    tags   ||--o{ note_tags : "has"
    notes ||--o{ note_links : "source"
    notes ||--o{ note_links : "target"
    tags  ||--o{ tags : "parent"
    notes ||--|| note_embeddings : "embedded"
    notes ||--o{ embedding_failures : "fails"
    notes ||--o| sync_state : "synced"

    tags ||--o{ tag_cooccurrences : "tag_a"
    tags ||--o{ tag_cooccurrences : "tag_b"

    tags   ||--o| skills : "tracks"
    goals  }o--o| notes : "note_id"
    goals  }o--o| tags  : "tag_id"
    goals  }o--o| goals : "parent_id"
    goals  ||--o{ planning_assignments : "assigned"
    goals  ||--o{ github_items : "goal_id"
    notes  ||--o{ github_items : "note_id"

    github_repos ||--o{ github_items : "contains"
    github_repos ||--o{ github_events : "receives"

    personal_streaks ||--o{ streak_checkins : "checkins"

    notes {
        integer id PK
        string title
        text content
        string source
        string source_path
        boolean is_embedded
        datetime created_at
        datetime updated_at
    }
    note_embeddings {
        integer note_id PK
        vector embedding
    }
    tags {
        integer id PK
        string name
        integer parent_id
        string color
        datetime created_at
    }
    note_tags {
        integer note_id PK
        integer tag_id PK
        float confidence
        string source
    }
    note_links {
        integer source_note_id PK
        integer target_note_id PK
        text context_text
    }
    tag_cooccurrences {
        integer tag_a_id PK
        integer tag_b_id PK
        integer weight
        datetime updated_at
    }
    embedding_failures {
        integer note_id PK
        integer attempts
        text last_error
        datetime next_retry_at
        datetime updated_at
    }
    sync_state {
        integer id PK
        integer note_id
        datetime last_synced_at
        datetime local_mtime
        datetime remote_mtime
        boolean conflict
        datetime created_at
        datetime updated_at
    }
    goals {
        integer id PK
        string title
        text description
        enum temporality
        enum measurement_type
        float target_value
        float current_value
        integer max_assignment_days
        enum state
        enum fail_config
        string fail_emoji
        string color
        string theme
        integer note_id
        integer tag_id
        integer parent_id
        boolean pending_removal
        boolean is_completed
        datetime completed_at
        string source_path
        datetime created_at
        datetime updated_at
    }
    planning_assignments {
        integer id PK
        date date
        integer goal_id
        datetime created_at
    }
    skills {
        integer id PK
        integer tag_id
        integer note_count
        string level
        integer xp
        datetime first_unlocked_at
        datetime updated_at
    }
    personal_streaks {
        integer id PK
        string name
        string emoji
        string icon
        string description
        string color
        string theme
        string category
        date start_date
        date target_date
        integer offset
        string frequency
        integer frequency_days
        boolean is_archived
        integer best_streak
        integer total_checkins
        integer freeze_count
        integer freeze_used
        datetime created_at
    }
    streak_checkins {
        integer id PK
        integer streak_id
        date check_date
        string note
        integer mood
        datetime created_at
    }
    xp_events {
        integer id PK
        string event_type
        integer xp
        string metadata_json
        datetime created_at
    }
    streak_records {
        integer id PK
        date activity_date
        integer xp_earned
        datetime created_at
    }
    user_stats {
        integer id PK
        integer total_xp
        integer current_streak
        integer longest_streak
        integer plant_stage
        date last_activity_date
        datetime updated_at
    }
    system_config {
        integer id PK
        string key
        string value
        datetime updated_at
    }
    push_subscriptions {
        integer id PK
        integer user_id
        string endpoint
        string p256dh
        string auth
        datetime created_at
    }
    github_repos {
        integer id PK
        string name
        string full_name
        text description
        string url
        string default_branch
        boolean is_private
        enum status
        integer webhook_id
        string webhook_secret
        datetime last_synced_at
        datetime created_at
        datetime updated_at
    }
    github_items {
        integer id PK
        integer repo_id
        integer external_id
        enum item_type
        integer number
        string title
        text body
        string state
        string state_reason
        string author
        string assignee
        string labels
        string url
        string html_url
        integer goal_id
        integer note_id
        datetime synced_at
        datetime created_at
        datetime updated_at
    }
    github_events {
        integer id PK
        integer repo_id
        enum event_type
        string action
        string sender
        enum item_type
        integer item_number
        integer item_external_id
        json payload
        boolean processed
        datetime created_at
    }
    google_tokens {
        integer id PK
        integer user_id
        text access_token
        text refresh_token_encrypted
        string token_type
        datetime expires_at
        text scope
        datetime created_at
        datetime updated_at
    }
    api_usage {
        integer id PK
        string operation
        integer input_tokens
        integer output_tokens
        datetime created_at
    }
```

---

## 5. Modelos ORM

### 5.1 Located in `api/models/`

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

### 5.2 Ejemplo de Modelo

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

## 6. Migraciones

### 6.1 Alembic Setup

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

### 6.2 Comandos

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

### 6.3 Migraciones existentes

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

## 7. Índices

| Tabla | Índice | Columnas |
|-------|--------|----------|
| notes | idx_notes_source_path | source_path |
| tags | (primary) | id |
| note_tags | (primary) | note_id, tag_id |
| goal | (primary) | id |
| xp_events | idx_xp_events_created | created_at |

---

## 8. Foreign Keys

Todas las tablas usan `ON DELETE CASCADE` para relaciones padre-hijo.

**Excepciones:**
- goals.note_id → SET NULL (objetivo puede existir sin nota)
- goals.tag_id → SET NULL
- goals.parent_id → SET NULL

---

## 9. Timestamps

- Todos los timestamps en UTC
- Usar `server_default=func.now()` para que la DB genere el valor
- Actualizaciones usan `onupdate=func.now()`

---

## 10. Notas Técnicas

- **pgvector:** La columna `note_embeddings.embedding` usa `Vector(768)`,
  coincidiendo con la dimensión de embeddings de Gemini. Esto requiere la
  extensión `pgvector`, que está habilitada en el contenedor de PostgreSQL.
- **App mono-usuario:** `user_stats` es un singleton (`id = 1`) y
  `google_tokens` tiene una sola fila (`user_id = 1`).
- **Comportamiento de cascada:** La mayoría de las foreign keys hacia `notes` y
  `tags` usan `CASCADE` para registros hijos (ej. `note_tags`,
  `note_embeddings`) y `SET NULL` para referencias opcionales (ej.
  `goals.note_id`, `github_items.goal_id`).
- **Índices:** Las primary keys y las columnas con `index=True` explícito se
  indexan automáticamente por SQLAlchemy. Las restricciones unique (ej.
  `tags.name`, `github_repos.full_name`,
  `streak_checkins(streak_id, check_date)`) también crean índices. La migración
  `e5f6a7b8c9d0_add_missing_indexes.py` añadió índices explícitos en columnas
  frecuentemente filtradas/ordenadas: `notes.created_at`, `notes.updated_at`,
  `note_links.target_note_id`, `embedding_failures.next_retry_at`,
  `goals.parent_id`, `goals.note_id`, `goals.tag_id`, `goals.state`,
  `personal_streaks.is_archived`, `personal_streaks.category`. La tabla
  `api_usage` tiene índices en `created_at` y `operation`.