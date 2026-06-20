# Joidy - Frontend

## Metadata

```yaml
framework: SvelteKit + Vite + TypeScript
port: 3000
language: TypeScript
routing: file-based
state_management: Svelte stores
css: Custom CSS with variables
```

---

## 1. Estructura del Proyecto

```
frontend/
├── src/
│   ├── app.html                    # Entry HTML
│   ├── app.css                     # Estilos globales
│   ├── routes/                     # File-based routing
│   │   ├── +page.svelte            # Dashboard
│   │   ├── +layout.svelte         # Layout principal
│   │   ├── notes/
│   │   │   └── +page.svelte       # Notas
│   │   ├── graph/
│   │   │   └── +page.svelte       # Grafo
│   │   ├── skills/
│   │   │   └── +page.svelte       # Habilidades
│   │   ├── goals/
│   │   │   ├── +page.svelte       # Objetivos
│   │   │   └── [id]/
│   │   │       └── +page.svelte  # Editor objetivo
│   │   └── streaks/
│   │       └── +page.svelte       # Rachas
│   └── lib/
│       ├── api.ts                  # Cliente API
│       ├── components/             # Componentes
│       ├── stores/                 # Svelte stores
│       ├── utils/                  # Utilidades
│       └── actions/                # Svelte actions
├── package.json
├── vite.config.ts
├── svelte.config.js
└── Dockerfile
```

---

## 2. Rutas

### 2.1 / - Dashboard

**Archivo:** `routes/+page.svelte`

**Propósito:** Página principal con widgets de gamificación

**Componentes:**
- Plant (visualización de etapa)
- XPBar (barra de progreso)
- NotaCard (notas recientes)
- StreakCounter (racha actual)
- PomodoroWidget (temporizador)

---

### 2.2 /notes - Notas

**Archivo:** `routes/notes/+page.svelte`

**Propósito:** Gestión completa de notas

**Funcionalidades:**
- Listado de notas con búsqueda
- Editor de notas (markdown)
- Gestión de tags
- Vista de árbol de archivos (Vault)
- Sugerencias de IA

**Componentes:**
- FileTree
- NoteEditor
- NoteCard
- TagChip

---

### 2.3 /graph - Grafo de Conocimiento

**Archivo:** `routes/graph/+page.svelte`

**Propósito:** Visualización del grafo de etiquetas y notas

**Funcionalidades:**
- Zoom y pan
- Clustering por co-ocurrencia
- Click para expandir
- Búsqueda de nodos

**Componente:** KnowledgeGraph (D3-based)

---

### 2.4 /skills - Habilidades

**Archivo:** `routes/skills/+page.svelte`

**Propósito:** Árbol de habilidades derivado de tags

**Funcionalidades:**
- Vista de árbol jerárquica
- Progreso por nivel
- XP por habilidad
- Desbloqueo progresivo

**Componente:** SkillTree

---

### 2.5 /goals - Objetivos

**Archivo:** `routes/goals/+page.svelte`

**Propósito:** Sistema de objetivos

**Funcionalidades:**
- Listado de objetivos
- Filtrado por estado
- Progreso visual
- Editor de objetivos

**Archivo (detalle):** `routes/goals/[id]/+page.svelte`

---

### 2.6 /streaks - Rachas Personales

**Archivo:** `routes/streaks/+page.svelte`

**Propósito:** Gestión de rachas personales

**Funcionalidades:**
- Crear/editar/eliminar rachas
- Check-in diario
- Heatmap de actividad
- Estadísticas
- Freeze management

**Componentes:**
- StreakHeatmap
- StreakCreateModal
- StreakStatsPanel
- StreakCounter

---

## 3. Layout Principal

**Archivo:** `routes/+layout.svelte`

```svelte
<script lang="ts">
  // Header con logo, XP, nivel, settings
  // Sidebar con navegación
  // Main content
  // Footer con estado (tiempo, tareas, pomodoro)
  // SettingsPanel (modal)
</script>

<div class="app-shell">
  <header class="app-header">
    <span class="logo">JOIDY</span>
    <span class="xp-display">{$totalXP} / {$nextStageXP} xp</span>
    <button settings>⚙️</button>
  </header>

  <nav class="app-sidebar">
    <!-- Links: Inicio, Notas, Grafo, Habilidades, Objetivos, Rachas -->
  </nav>

  <main>
    <slot />
  </main>

  <footer>
    <!-- Status bar -->
  </footer>

  <SettingsPanel bind:open />
</div>
```

---

## 4. Componentes

### 4.1 UI Core

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| DynamicIcon | components/DynamicIcon.svelte | Iconos dinámicos (Lucide, Phosphor, Material) |
| Widget | components/Widget.svelte | Contenedor de widget |
| TagChip | components/TagChip.svelte | Chip de etiqueta con color |
| IconPicker | components/IconPicker.svelte | Selector de iconos |

### 4.2 Gamificación

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| XPBar | components/XPBar.svelte | Barra de progreso de XP |
| Plant | components/Plant.svelte | Visualización de planta según etapa |
| StreakCounter | components/StreakCounter.svelte | Contador de racha |

### 4.3 Notas

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| NoteCard | components/NoteCard.svelte | Tarjeta de previsualización |
| NoteEditor | components/NoteEditor.svelte | Editor markdown |
| FileTree | components/FileTree.svelte | Árbol de archivos del vault |

### 4.4 Objetivos

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| GoalEditor | components/GoalEditor.svelte | Editor de objetivos |

### 4.5 Rachas

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| StreakHeatmap | components/StreakHeatmap.svelte | Heatmap de actividad |
| StreakCreateModal | components/StreakCreateModal.svelte | Modal de creación |
| StreakStatsPanel | components/StreakStatsPanel.svelte | Panel de estadísticas |
| StreakIcon | components/StreakIcon.svelte | Icono de racha |

### 4.6 Otros

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| SettingsPanel | components/SettingsPanel.svelte | Panel de configuración |
| PomodoroWidget | components/PomodoroWidget.svelte | Widget Pomodoro |
| KnowledgeGraph | components/KnowledgeGraph.svelte | Grafo D3 |
| SkillTree | components/SkillTree.svelte | Árbol de habilidades |
| TimeWidget | components/TimeWidget.svelte | Widget de tiempo |

---

## 5. Stores

### 5.1 gamification.ts

```typescript
// Stores de gamificación
totalXP: Writable<number>
globalLevel: Writable<number>
nextStageXP: Writable<number | null>
plantStage: Writable<number>

// Funciones
loadStats(): Promise<void>
pingActivity(): Promise<GamificationResult>
```

### 5.2 notes.ts

```typescript
// Estado de notas
notes: Writable<Note[]>
selectedNote: Writable<Note | null>
loading: Writable<boolean>

// Funciones
loadNotes(tag?: string): Promise<void>
getNote(id: number): Promise<Note>
createNote(data): Promise<Note>
updateNote(id, data): Promise<Note>
deleteNote(id): Promise<void>
```

### 5.3 pomodoro.ts

```typescript
// Estado Pomodoro
running: Writable<boolean>
secondsLeft: Writable<number>
phase: Writable<'work' | 'shortBreak' | 'longBreak'>

// Funciones
startPomodoro(): void
stopPomodoro(): void
resetPomodoro(): void
```

### 5.4 settings.ts

```typescript
// Configuración de usuario
accentColors: Writable<string[]>
activeIconPack: Writable<'lucide' | 'phosphor' | 'material'>
use24HourClock: Writable<boolean>
writeInObsidian: Writable<boolean>
showFrontmatter: Writable<boolean>
showHiddenFiles: Writable<boolean>
showTrash: Writable<boolean>
hideTagsLine: Writable<boolean>

// Funciones
accentColors.setColor(index, color)
accentColors.addColor()
accentColors.removeColor(index)
```

### 5.5 graph.ts

```typescript
// Estado del grafo
nodes: Writable<GraphNode[]>
edges: Writable<GraphEdge[]>

// Funciones
loadGraph(): Promise<GraphData>
```

### 5.6 layout.ts

```typescript
// Estado del layout
sidebarCollapsed: Writable<boolean>
```

---

## 6. API Client

### 6.1 Configuración

```typescript
// lib/api.ts
const BASE = browser
  ? import.meta.env.VITE_API_URL || 'http://localhost:8000'
  : import.meta.env.VITE_INTERNAL_API_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000'
```

### 6.2 Helper

```typescript
async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined
  })
  if (!res.ok) throw new Error(...)
  if (res.status === 204) return undefined as T
  return res.json()
}
```

### 6.3 Métodos Disponibles

```typescript
api.notes.list(tag?, limit?)          // GET /notes/
api.notes.get(id)                     // GET /notes/{id}
api.notes.create(data)                // POST /notes/
api.notes.update(id, data)           // PUT /notes/{id}
api.notes.delete(id)                  // DELETE /notes/{id}
api.notes.acceptTag(noteId, tag)     // POST /notes/{id}/accept-tag
api.notes.backlinks(id)              // GET /notes/{id}/backlinks

api.tags.list()                       // GET /tags/
api.tags.graph()                      // GET /tags/graph
api.tags.create(name, parentId)       // POST /tags/

api.gamification.stats()              // GET /gamification/stats
api.gamification.ping()               // POST /gamification/ping
api.gamification.history(days)        // GET /gamification/streak-history
api.gamification.events(limit)        // GET /gamification/recent-events

api.skills.list()                     // GET /skills/
api.skills.tree()                     // GET /skills/tree
api.skills.sync()                     // POST /skills/sync

api.goals.list()                      // GET /goals/
api.goals.get(id)                     // GET /goals/{id}
api.goals.create(data)                // POST /goals/
api.goals.update(id, data)            // PUT /goals/{id}
api.goals.complete(id)               // POST /goals/{id}/complete
api.goals.delete(id)                  // DELETE /goals/{id}

api.personalStreaks.list(opts)        // GET /personal-streaks/
api.personalStreaks.create(data)      // POST /personal-streaks/
api.personalStreaks.update(id, data)  // PUT /personal-streaks/{id}
api.personalStreaks.delete(id)        // DELETE /personal-streaks/{id}
api.personalStreaks.checkin(id, data)// POST /personal-streaks/{id}/checkin
api.personalStreaks.undo(id)          // DELETE /personal-streaks/{id}/checkin
api.personalStreaks.freeze(id)        // POST /personal-streaks/{id}/freeze

api.ai.classify(noteId, content, tags) // POST /ai/classify
api.ai.usage()                        // GET /ai/usage

api.config.get()                      // GET /config/
api.config.update(data)              // POST /config/
api.config.keys()                     // GET /config/keys
```

---

## 7. Estilos

### 7.1 Variables CSS

```css
/* app.css */
:root {
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --xp: #c8a96e;
  --accent: var(--xp);
  --surface: #1a1a1a;
  --elevated: #252525;
  --border: #333;
  --border-light: #444;
  --text-primary: #eee;
  --text-secondary: #aaa;
  --text-muted: #666;
  --success: #4ecdc4;
  --error: #ff6b6b;
  --r: 6px;
  --t-fast: 100ms;
  --t-normal: 200ms;
}
```

### 7.2 Temas

Soporte para tema oscuro y claro vía `data-theme` attribute.

---

## 8. Scripts de npm

```json
{
  "scripts": {
    "dev": "vite dev --port 3000",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-check --tsconfig ./tsconfig.json"
  }
}
```

---

## 9. Configuración de Desarrollo

### 9.1 Hot Reload

```yaml
# docker-compose.dev.yml
frontend:
  volumes:
    - ./frontend/src:/app/src
    - ./frontend/static:/app/static
```

### 9.2 Environment

```env
VITE_API_URL=http://localhost:8000
```

---

## 10. Tipos de Datos

### 10.1 TypeScript Interfaces

```typescript
interface Note {
  id: number
  title: string
  content: string
  source: string
  source_path: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

interface Goal {
  id: number
  title: string
  description: string
  temporality: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL'
  measurement_type: 'COUNT' | 'BOOLEAN' | 'PERCENT'
  target_value: number
  current_value: number
  state: 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'PAUSED' | 'CANCELLED'
  // ... más campos
}

interface PersonalStreak {
  id: number
  name: string
  emoji: string
  icon: string
  description: string
  color: string
  current_streak: number
  longest_streak: number
  today_checked: boolean
  history: StreakDay[]
  // ... más campos
}
```