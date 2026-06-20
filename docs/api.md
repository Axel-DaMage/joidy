# Joidy API Reference

## Metadata

```yaml
version: 0.1.0
base_url: http://localhost:8000
docs_url: http://localhost:8000/docs
framework: FastAPI
language: Python 3.12
```

---

## 1. Autenticación

**Estado actual:** No requerida

La API currently permite acceso sin autenticación. El sistema está diseñado para uso personal local.

---

## 2. Endpoints

### 2.1 Health

#### GET /health

Verifica que la API esté funcionando.

**Response:**
```json
{
  "status": "ok",
  "service": "joidy-api"
}
```

---

#### GET /

Información básica de la API.

**Response:**
```json
{
  "name": "Joidy API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

---

### 2.2 Notas

#### GET /notes/

Lista todas las notas.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| tag | string | - | Filtrar por tag |
| limit | int | 1000 | Límite de resultados |

**Response:** `List[Note]`

```json
[
  {
    "id": 1,
    "title": "Mi Nota",
    "content": "# Contenido\n\nMarkdown...",
    "source": "joidy",
    "source_path": "/vault/folder/note.md",
    "tags": ["tag1", "tag2"],
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T12:00:00"
  }
]
```

---

#### GET /notes/{note_id}

Obtiene una nota específica.

**Response:** `Note`

---

#### POST /notes/

Crea una nueva nota.

**Request Body:**
```json
{
  "title": "Nueva Nota",
  "content": "Contenido en markdown",
  "tags": ["tag1", "tag2"]
}
```

**Response:** `Note` with embedded `GamificationResult`

```json
{
  "id": 42,
  "title": "Nueva Nota",
  "content": "...",
  "gamification": {
    "xp_awarded": 10,
    "total_xp": 1500,
    "current_streak": 5,
    "plant_stage": 2,
    "plant_stage_name": "sprout",
    "plant_stage_changed": false,
    "streak_changed": false,
    "milestone_reached": null,
    "message": "Nota creada +10 XP"
  }
}
```

---

#### PUT /notes/{note_id}

Actualiza una nota.

**Request Body:**
```json
{
  "title": "Título actualizado",
  "content": "Nuevo contenido",
  "tags": ["tag1", "nuevo"]
}
```

**Response:** `Note` with embedded `GamificationResult`

---

#### DELETE /notes/{note_id}

Elimina una nota.

**Response:** `204 No Content`

---

#### POST /notes/{note_id}/accept-tag

Acepta un tag sugerido por la IA.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| tag_name | string | Nombre del tag a aceptar |

**Response:**
```json
{
  "tag": "machine-learning",
  "gamification": {
    "xp_awarded": 3,
    "total_xp": 1503,
    ...
  }
}
```

---

#### GET /notes/{note_id}/backlinks

Obtiene notas que enlazan a esta nota.

**Response:** `List[Note]`

---

### 2.3 Etiquetas

#### GET /tags/

Lista todas las etiquetas.

**Response:**
```json
[
  {
    "id": 1,
    "name": "python",
    "parent_id": null,
    "note_count": 15
  },
  {
    "id": 2,
    "name": "machine-learning",
    "parent_id": 1,
    "note_count": 8
  }
]
```

---

#### GET /tags/graph

Obtiene el grafo de etiquetas con co-ocurrencias.

**Response:**
```json
{
  "nodes": [
    {"id": 1, "name": "python", "note_count": 15, "parent_id": null},
    {"id": 2, "name": "ml", "note_count": 8, "parent_id": 1}
  ],
  "edges": [
    {"source": 1, "target": 2, "type": "hierarchy"},
    {"source": 1, "target": 3, "type": "cooccurrence", "weight": 5}
  ]
}
```

---

#### POST /tags/

Crea una nueva etiqueta.

**Request Body:**
```json
{
  "name": "nueva-etiqueta",
  "parent_id": 1
}
```

**Response:** `Tag`

---

### 2.4 Objetivos

#### GET /goals/

Lista todos los objetivos.

**Response:** `List[Goal]`

```json
[
  {
    "id": 1,
    "title": "Ejercitar",
    "description": "Hacer ejercicio diario",
    "source_path": null,
    "temporality": "DAILY",
    "measurement_type": "BOOLEAN",
    "target_value": 1,
    "current_value": 1,
    "state": "ACTIVE",
    "fail_config": "ROLLOVER",
    "fail_emoji": "💪",
    "color": "#ff6b6b",
    "theme": "fitness",
    "note_id": null,
    "tag_id": null,
    "parent_id": null,
    "max_assignment_days": null,
    "progress_pct": 100,
    "pending_removal": false,
    "is_completed": false,
    "completed_at": null,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-15T10:00:00"
  }
]
```

---

#### GET /goals/{goal_id}

Obtiene un objetivo específico.

**Response:** `Goal`

---

#### POST /goals/

Crea un nuevo objetivo.

**Request Body:**
```json
{
  "title": "Nuevo Objetivo",
  "description": "Descripción",
  "temporality": "WEEKLY",
  "measurement_type": "COUNT",
  "target_value": 5,
  "fail_config": "ROLLOVER",
  "fail_emoji": "😢",
  "color": "#4ecdc4",
  "theme": "health"
}
```

**Response:** `Goal`

---

#### PUT /goals/{goal_id}

Actualiza un objetivo.

**Request Body:** Partial<Goal>

---

#### POST /goals/{goal_id}/complete

Completa un objetivo.

**Response:**
```json
{
  "goal": {...},
  "gamification": {
    "xp_awarded": 50,
    "total_xp": 1550,
    ...
  }
}
```

---

#### DELETE /goals/{goal_id}

Elimina un objetivo.

---

#### GET /goals/streak

Obtiene la racha de objetivos completados.

**Response:**
```json
{
  "current_streak": 7,
  "best_streak": 30
}
```

---

#### POST /goals/{goal_id}/resolve-removal

Resuelve la eliminación pendiente de un objetivo.

**Request Body:**
```json
{
  "action": "delete"  // "delete" | "manual" | "cancel"
}
```

---

#### GET /goals/{goal_id}/content

Obtiene el contenido de un objetivo.

**Response:**
```json
{
  "title": "Objetivo",
  "content": "...",
  "temporality": "DAILY",
  "measurement_type": "BOOLEAN",
  "state": "ACTIVE",
  "fail_config": "ROLLOVER",
  "fail_emoji": "😢",
  "color": "#ff6b6b"
}
```

---

#### POST /goals/{goal_id}/content

Guarda el contenido de un objetivo.

**Request Body:**
```json
{
  "title": "Título",
  "content": "Contenido",
  "temporality": "WEEKLY",
  "measurement_type": "COUNT",
  "target_value": 5,
  "state": "ACTIVE",
  "fail_config": "SNOWBALL",
  "fail_emoji": "💪",
  "color": "#4ecdc4"
}
```

---

### 2.5 Gamificación

#### GET /gamification/stats

Obtiene estadísticas de gamificación.

**Response:**
```json
{
  "total_xp": 1500,
  "current_streak": 7,
  "longest_streak": 30,
  "plant_stage": 3,
  "plant_stage_name": "sprout",
  "next_stage_xp": 2000,
  "xp_to_next_stage": 500,
  "last_activity_date": "2024-01-15"
}
```

---

#### POST /gamification/ping

Registra actividad y obtiene XP.

**Response:**
```json
{
  "xp_awarded": 15,
  "total_xp": 1515,
  "current_streak": 8,
  "longest_streak": 30,
  "plant_stage": 3,
  "plant_stage_name": "sprout",
  "plant_stage_changed": false,
  "streak_changed": true,
  "milestone_reached": null,
  "message": "¡Bienvenido de vuelta! +15 XP",
  "next_stage_xp": 2000,
  "xp_to_next_stage": 485,
  "last_activity_date": "2024-01-16"
}
```

---

#### GET /gamification/streak-history

Obtiene historial de rachas.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| days | int | 30 | Días hacia atrás |

**Response:**
```json
[
  {"date": "2024-01-15", "xp": 15},
  {"date": "2024-01-14", "xp": 20},
  ...
]
```

---

#### GET /gamification/recent-events

Obtiene eventos recientes de XP.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | Número de eventos |

**Response:**
```json
[
  {"type": "note_created", "xp": 10, "at": "2024-01-15T10:00:00"},
  {"type": "goal_completed", "xp": 50, "at": "2024-01-15T09:00:00"},
  ...
]
```

---

### 2.6 Rachas Personales

#### GET /personal-streaks/

Lista rachas personales.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| include_archived | bool | Incluir archivadas |
| category | string | Filtrar por categoría |

**Response:** `List[PersonalStreak]`

---

#### POST /personal-streaks/

Crea una nueva racha.

**Request Body:**
```json
{
  "name": "Lectura",
  "emoji": "📚",
  "icon": "BookOpen",
  "description": "Leer 30 minutos",
  "color": "#4ecdc4",
  "theme": "learning",
  "category": "education",
  "start_date": "2024-01-01",
  "target_date": "2024-12-31",
  "frequency": "daily",
  "frequency_days": 1,
  "freeze_count": 1
}
```

---

#### PUT /personal-streaks/{streak_id}

Actualiza una racha.

**Request Body:** Partial<PersonalStreak>

---

#### DELETE /personal-streaks/{streak_id}

Elimina una racha.

---

#### POST /personal-streaks/{streak_id}/checkin

Registra un check-in.

**Request Body (optional):**
```json
{
  "note": "Notas del día",
  "mood": 4,
  "check_date": "2024-01-15"
}
```

---

#### DELETE /personal-streaks/{streak_id}/checkin

Deshace el último check-in.

---

#### POST /personal-streaks/{streak_id}/freeze

Usa un freeze para mantener la racha.

---

#### GET /personal-streaks/stats

Obtiene estadísticas generales de rachas.

**Response:**
```json
{
  "total_active": 5,
  "total_archived": 2,
  "longest_ever": 45,
  "longest_name": "Ejercicio",
  "total_checkins": 150,
  "checkin_rate": 0.85,
  "days_tracked": 180
}
```

---

#### GET /personal-streaks/categories

Lista categorías disponibles.

**Response:** `List[string]`

---

#### GET /personal-streaks/{streak_id}/history

Obtiene historial de check-ins.

**Query Parameters:**
| Param | Type | Default |
|-------|------|---------|
| days | int | 90 |

**Response:**
```json
[
  {"date": "2024-01-15", "note": "...", "mood": 4, "created_at": "..."},
  ...
]
```

---

### 2.7 Habilidades

#### GET /skills/

Lista habilidades (derivadas de tags).

**Response:** `List[Skill]`

```json
[
  {
    "id": 1,
    "tag_id": 5,
    "tag_name": "python",
    "level": "sapling",
    "note_count": 15,
    "first_unlocked_at": "2024-01-01T00:00:00"
  }
]
```

---

#### GET /skills/tree

Obtiene el árbol de habilidades.

**Response:**
```json
{
  "nodes": [
    {"id": 1, "name": "Python", "level": "tree", "note_count": 50, "xp": 500},
    {"id": 2, "name": "Machine Learning", "level": "sapling", "note_count": 20, "xp": 200}
  ],
  "edges": [
    {"source": 1, "target": 2}
  ]
}
```

---

#### POST /skills/sync

Sincroniza habilidades con tags.

**Response:**
```json
{
  "synced": 15
}
```

---

### 2.8 Planificación

#### GET /planning/assignments

Obtiene asignaciones de objetivos para una fecha.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| date | string | Fecha (YYYY-MM-DD) |

**Response:**
```json
{
  "date": "2024-01-15",
  "goal_ids": [1, 2, 3]
}
```

---

#### POST /planning/assignments

Guarda asignaciones de objetivos.

**Request Body:**
```json
{
  "date": "2024-01-15",
  "goal_ids": [1, 2, 3]
}
```

---

### 2.9 Integraciones - GitHub

#### GET /integrations/github/status

Obtiene estado de conexión.

**Response:**
```json
{
  "connected": true,
  "username": "mi-usuario"
}
```

---

#### GET /integrations/github/issues

Lista issues de GitHub.

**Query Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| filter | all | "all" / "open" / "closed" |

**Response:**
```json
{
  "issues": [
    {
      "id": 1,
      "number": 42,
      "title": "Bug en el login",
      "repo": "mi-repo",
      "url": "https://github.com/...",
      "state": "open",
      "updated_at": "2024-01-15T10:00:00",
      "author": "user"
    }
  ],
  "stats": {"total": 10, "open": 5, "closed": 5},
  "filter": "all"
}
```

---

#### GET /integrations/github/pulls

Lista pull requests.

**Query Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| filter | all | "all" / "open" / "closed" |

---

#### GET /integrations/github/repos

Lista repositorios.

**Response:**
```json
{
  "repos": [
    {"id": 1, "name": "mi-repo", "full_name": "user/mi-repo", "color": "#ff6b6b"}
  ]
}
```

---

### 2.10 IA

#### POST /ai/classify

Clasifica una nota y sugiere tags.

**Request Body:**
```json
{
  "note_id": 42,
  "content": "Contenido de la nota sobre machine learning...",
  "existing_tags": ["python", "data"]
}
```

**Response:**
```json
{
  "note_id": 42,
  "status": "completed",
  "suggestions": [
    {"tag": "machine-learning", "confidence": 0.92, "is_new": true},
    {"tag": "neural-networks", "confidence": 0.85, "is_new": true},
    {"tag": "python", "confidence": 0.78, "is_new": false}
  ]
}
```

---

#### GET /ai/usage

Obtiene uso y costos de IA.

**Response:**
```json
{
  "ai_enabled": true,
  "estimated_cost_usd": 0.05
}
```

---

### 2.11 Vault

#### GET /vault/files

Lista archivos del vault.

**Response:**
```json
{
  "files": [
    {"path": "/folder/note.md", "modified": "2024-01-15T10:00:00"}
  ]
}
```

---

#### GET /vault/file/{path:path}

Obtiene contenido de un archivo.

---

#### POST /vault/sync

Fuerza sincronización del vault.

**Request Body:**
```json
{
  "source_path": "/folder/note.md",
  "content": "Contenido..."
}
```

---

### 2.12 Configuración

#### GET /config/

Obtiene configuración actual (solo valores públicos).

**Response:**
```json
{
  "gemini_api_key": null,
  "obsidian_vault_path": "/home/user/Obsidian",
  "github_username": "mi-usuario",
  "app_env": "development",
  "configured_keys": ["obsidian_vault_path", "github_username"]
}
```

---

#### POST /config/

Actualiza configuración.

**Request Body:**
```json
{
  "gemini_api_key": "AIzaSy...",
  "obsidian_vault_path": "/new/path",
  "github_token": "ghp_..."
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Configuration updated. Some changes may require a restart."
}
```

---

#### GET /config/keys

Lista claves de configuración disponibles.

**Response:**
```json
{
  "keys": [
    {"key": "gemini_api_key", "env_key": "GEMINI_API_KEY", "public": false, "description": "API key for Google Gemini AI"},
    {"key": "obsidian_vault_path", "env_key": "OBSIDIAN_VAULT_PATH", "public": true, "description": "Absolute path to your Obsidian vault"},
    ...
  ]
}
```

---

## 3. Modelos de Datos

### Note
```python
class Note(Base):
    id: int
    title: str (max 500)
    content: str (Text)
    source: str ("joidy" | "obsidian")
    source_path: str | None (max 1000)
    is_embedded: bool
    created_at: datetime
    updated_at: datetime
    tags: list[NoteTag]
```

### Goal
```python
class Goal(Base):
    id: int
    title: str
    description: str
    temporality: str ("DAILY" | "WEEKLY" | "MONTHLY" | "ANNUAL")
    measurement_type: str ("COUNT" | "BOOLEAN" | "PERCENT")
    target_value: int
    current_value: int
    state: str ("ACTIVE" | "COMPLETED" | "FAILED" | "PAUSED" | "CANCELLED")
    fail_config: str ("STATIC" | "ROLLOVER" | "SNOWBALL")
    fail_emoji: str
    color: str
    theme: str
    note_id: int | None
    tag_id: int | None
    parent_id: int | None
    max_assignment_days: int | None
    is_completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### GamificationStats
```python
class GamificationStats(BaseModel):
    total_xp: int
    current_streak: int
    longest_streak: int
    plant_stage: int
    plant_stage_name: str
    next_stage_xp: int | None
    xp_to_next_stage: int | None
    last_activity_date: str | None
```

---

## 4. Códigos de Respuesta HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

## 5. Errores

Formato estándar de error:

```json
{
  "detail": "Descripción del error"
}
```

---

## 6. Rate Limiting

El AI service implementa rate limiting. Ver `ai-service/rate_limiter.py`.