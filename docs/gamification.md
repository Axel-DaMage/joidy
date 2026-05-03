# Joidy - Sistema de Gamificación

## Metadata

```yaml
module: api/services/gamification_engine.py
xp_events_table: xp_events
user_stats_table: user_stats
streak_records_table: streak_records
```

---

## 1. Resumen del Sistema

El sistema de gamificación de Joidy motiva el uso consistente a través de:

1. **XP (Experience Points):** Puntos obtenidos por acciones
2. **Niveles:** Progresión basada en XP acumulada
3. **Streaks:** Rachas de actividad diaria
4. **Planta:** Evolución visual según XP total

---

## 2. Sistema de XP

### 2.1 Eventos que Otorgan XP

| Evento | XP | Trigger | metadata_json |
|--------|-----|---------|----------------|
| note_created | +10 | POST /notes/ | `{title: string}` |
| note_edited | +5 | PUT /notes/{id} | `{title: string, changes: number}` |
| tag_added | +3 | POST notes/{id}/accept-tag | `{tag: string}` |
| topic_connected | +8 | (futuro) Grafo | `{connection_type: string}` |
| goal_completed | +50 | POST /goals/{id}/complete | `{goal_title: string}` |
| daily_activity | +15 | POST /gamification/ping | `{streak: number}` |

### 2.2 Tabla de Niveles

**Ubicación:** `api/services/gamification_engine.py`

```python
XP_TABLE = {
    1: 0,
    2: 100,
    3: 250,
    4: 500,
    5: 1000,
    6: 2000,
    7: 3500,
    8: 5500,
    9: 8000,
    10: 12000,
    11: 17000,
    12: 23000,
    13: 30000,
    14: 38000,
    15: 47000,
    16: 57000,
    17: 68000,
    18: 80000,
    19: 95000,
    20: 115000,
}
```

### 2.3 Cálculo de Nivel

```python
def get_level_from_xp(total_xp: int) -> int:
    for level, xp_required in sorted(XP_TABLE.items(), reverse=True):
        if total_xp >= xp_required:
            return level
    return 1
```

---

## 3. Sistema de Rachas

### 3.1 Rachas de Actividad Global

| Métrica | Descripción |
|---------|-------------|
| current_streak | Días consecutivos con actividad |
| longest_streak | Récord histórico |
| last_activity_date | Fecha del último check-in |

### 3.2 Grace Period

**Configuración:** 1 día forgivable por semana

```python
GRACE_PERIOD_DAYS = 1
GRACE_PERIOD_FREQUENCY = 7  # Una vez por semana
```

**Lógica:**
- Si el usuario pierde un día, se perdona si no ha usado el grace period esta semana
- El grace period se resetea cada 7 días

### 3.3 Milestones de Racha

| Días | Bonus XP | Evento |
|------|----------|--------|
| 7 | +100 | streak_7 |
| 30 | +100 | streak_30 |
| 100 | +100 | streak_100 |
| 365 | +100 | streak_365 |

---

## 4. Sistema de Planta

### 4.1 Etapas

| Stage | Index | XP Mínimo | Nombre | Descripción |
|-------|-------|-----------|--------|-------------|
| 0 | seed | 0 | Seed | Semilla初始 |
| 1 | sprout | 50 | Sprout | Broto |
| 2 | seedling | 150 | Seedling | Plántula |
| 3 | young | 350 | Young | Joven |
| 4 | mature | 700 | Mature | Adulta |
| 5 | flowering | 1200 | Flowering | Floresciendo |
| 6 | tree | 2000 | Tree | Árbol |

### 4.2 Código

```python
PLANT_STAGES = [
    {"index": 0, "name": "seed", "xp_min": 0},
    {"index": 1, "name": "sprout", "xp_min": 50},
    {"index": 2, "name": "seedling", "xp_min": 150},
    {"index": 3, "name": "young", "xp_min": 350},
    {"index": 4, "name": "mature", "xp_min": 700},
    {"index": 5, "name": "flowering", "xp_min": 1200},
    {"index": 6, "name": "tree", "xp_min": 2000},
]

def get_plant_stage(total_xp: int) -> int:
    for stage in reversed(PLANT_STAGES):
        if total_xp >= stage["xp_min"]:
            return stage["index"]
    return 0
```

---

## 5. API de Gamificación

### 5.1 GET /gamification/stats

**Endpoint:** `GET /gamification/stats`

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

**Lógica:**
1. Lee UserStats (singleton id=1)
2. Calcula nivel desde XP total
3. Calcula etapa de planta
4. Calcula XP para siguiente nivel

---

### 5.2 POST /gamification/ping

**Endpoint:** `POST /gamification/ping`

**Propósito:** Registrar actividad diaria

**Lógica:**
```python
def process_event(db, event_type: str, metadata: dict) -> GamificationResult:
    # 1. Obtener XP del evento
    xp = XP_EVENTS.get(event_type, 0)

    # 2. Actualizar UserStats
    user_stats.total_xp += xp
    user_stats.current_streak = calculate_streak()
    user_stats.plant_stage = get_plant_stage(user_stats.total_xp)
    user_stats.last_activity_date = today

    # 3. Guardar XPEvent
    xp_event = XPEvent(event_type=event_type, xp=xp, metadata_json=json.dumps(metadata))
    db.add(xp_event)

    # 4. Guardar StreakRecord
    streak_record = StreakRecord(activity_date=today, xp_earned=xp)
    db.add(streak_record)

    # 5. Verificar milestones
    milestone = check_milestone(user_stats.current_streak)
    if milestone:
        user_stats.total_xp += milestone_bonus

    # 6. Commit y return result
```

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

## 6. Rachas Personales

### 6.1 Estructura

Las rachas personales son independientes de la racha global de actividad.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| name | VARCHAR(100) | Nombre de la racha |
| emoji | VARCHAR(10) | Emoji representativo |
| frequency | VARCHAR(20) | daily, weekly, monthly |
| frequency_days | INTEGER | Días entre check-ins |
| freeze_count | INTEGER | Congelamientos disponibles |
| current_streak | INTEGER | Racha actual |
| longest_streak | INTEGER | Mejor racha |

### 6.2 Check-in

```python
POST /personal-streaks/{id}/checkin
```

```json
{
  "note": "Notas del día (opcional)",
  "mood": 4 (1-5, opcional),
  "check_date": "2024-01-15 (opcional, default: today)"
}
```

### 6.3 Freeze

```python
POST /personal-streaks/{id}/freeze
```

Usa un freeze para mantener la racha cuando no se puede hacer check-in.

---

## 7. Base de Datos

### 7.1 Tablas

**xp_events:**
```sql
CREATE TABLE xp_events (
    id INTEGER PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    xp INTEGER NOT NULL,
    metadata_json VARCHAR(500) DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**streak_records:**
```sql
CREATE TABLE streak_records (
    id INTEGER PRIMARY KEY,
    activity_date DATE UNIQUE NOT NULL,
    xp_earned INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**user_stats:**
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

---

## 8. Configuración

### 8.1 Parámetros Ajustables

**En `api/config.py`:**

```python
embedding_retry_max_attempts: int = 8
embedding_retry_base_seconds: int = 60
xp_table_json: str = ""  # Override de tabla de XP
```

**En `api/services/gamification_engine.py`:**

```python
GRACE_PERIOD_DAYS = 1
GRACE_PERIOD_FREQUENCY = 7
XP_TABLE = {...}
PLANT_STAGES = [...]
```

---

## 9. Frontend

### 9.1 Stores

```typescript
// lib/stores/gamification.ts
totalXP: Writable<number>
globalLevel: Writable<number>
nextStageXP: Writable<number | null>
plantStage: Writable<number>
```

### 9.2 Componentes

| Componente | Descripción |
|------------|-------------|
| XPBar | Barra de progreso hacia siguiente nivel |
| Plant | Visualización de la planta según etapa |
| StreakCounter | Contador de racha actual |

### 9.3 Example UI

```svelte
<div class="gamification">
  <XPBar current={$totalXP} next={$nextStageXP} />
  <Plant stage={$plantStage} />
  <span class="level">Nivel {$globalLevel}</span>
  <StreakCounter streak={streak} />
</div>
```

---

## 10. Diagramas de Flujo

### 10.1 Flujo de Actividad

```
User Action
    │
    ▼
POST /gamification/ping
    │
    ▼
process_event()
    │
    ├──► XP_EVENTS[event_type] ──► XP awarded
    │
    ├──► Calculate streak ──► current_streak
    │
    ├──► Check milestone ──► Bonus XP?
    │
    ├──► get_plant_stage() ──► plant_stage
    │
    ├──► Save XPEvent
    │
    ├──► Save StreakRecord
    │
    └──► Update UserStats
          │
          ▼
        Response with GamificationResult
```

### 10.2 Cálculo de Racha

```
Check last_activity_date
    │
    ├──► Today? ──► streak unchanged
    │
    ├──► Yesterday? ──► streak + 1
    │
    ├──► Within grace period? ──► streak unchanged (grace used)
    │
    └──► Older than grace ──► streak = 1
```