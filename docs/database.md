# Joidy - Base de Datos

## Metadata

```yaml
engine: SQLite
extension: sqlite-vec (vector embeddings)
location: ./data/db/joidy.db
shared: true
wal_mode: true
foreign_keys: ON
```

---

## 1. Configuración

### 1.1 engine Setup

```python
# api/database.py
from sqlalchemy import create_engine, event
import sqlite_vec

engine = create_engine(
    settings.database_url,  # sqlite:////data/db/joidy.db
    connect_args={"check_same_thread": False},
)

# SQLite extensions
def _setup_sqlite(dbapi_connection, connection_record):
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute("PRAGMA synchronous=NORMAL")

event.listen(engine, "connect", _setup_sqlite)
```

### 1.2 Optimizaciones aplicadas

| PRAGMA | Valor | Propósito |
|--------|-------|------------|
| journal_mode | WAL | Write-Ahead Logging para concurrencia |
| foreign_keys | ON | Integridad referencial |
| synchronous | NORMAL | Balance entre seguridad y velocidad |

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
    repo_id INTEGER UNIQUE,
    name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    color VARCHAR(20) DEFAULT '#888888',
    last_synced DATETIME
);
```

---

## 3. Modelos ORM

### 3.1 Located in `api/models/`

| Archivo | Modelos |
|---------|---------|
| note.py | Note, Tag, NoteTag, NoteLink, TagCooccurrence, EmbeddingFailure |
| goal.py | Goal |
| gamification.py | XPEvent, StreakRecord, UserStats |
| personal_streaks.py | PersonalStreak, StreakCheckin |
| skill.py | Skill |
| planning.py | PlanningAssignment |
| github.py | GitHubRepo |

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
| 20260421_000001_initial_schema.py | Schema inicial |
| 20260421_000002_tag_cooccurrences.py | Co-ocurrencias de tags |
| 20260421_000003_embedding_failures.py | Tabla de reintentos |
| 20260427_consolidated.py | Consolidación |
| 20260501_planning.py | Planificación |
| 20260502_github_integration.py | GitHub |
| 20260503_add_max_assignment_days.py | Max days |
| 20260504_add_source_path_to_goals.py | Source path |

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