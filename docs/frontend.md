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

### 4.0 Primitivas UI

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| Card | components/Card.svelte | Contenedor con elevación y borde. |
| Badge | components/Badge.svelte | Etiquetas de estado. |
| Modal | components/Modal.svelte | Modal global con `focusTrap`. |
| Toast | components/Toast.svelte | Notificación flotante. |
| Skeleton | components/Skeleton.svelte | Placeholder de carga. |
| Spinner | components/Spinner.svelte | Indicador de carga giratorio. |
| EmptyState | components/EmptyState.svelte | Estado de vacío (sin datos). |

> **Nota:** `Button` no existe como componente; se usan clases `.btn`, `.link-btn`
> desde `app.css`.

### 4.1 UI Core

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| DynamicIcon | components/DynamicIcon.svelte | Iconos dinámicos (Lucide, Phosphor, Material) |
| Widget | components/Widget.svelte | Contenedor de widgets drag/drop |
| TagChip | components/TagChip.svelte | Chip de etiqueta con color |
| IconPicker | components/IconPicker.svelte | Selector de iconos |

### 4.2 Gamificación

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| XPBar | components/XPBar.svelte | Barra de progreso de XP |
| Plant | components/Plant.svelte | Visualización de planta según etapa |
| StreakCounter | components/StreakCounter.svelte | Contador de racha |
| ActivityProgress | components/ActivityProgress.svelte | Barra de progreso de actividad |
| ProgressBar | components/ProgressBar.svelte | Barra de progreso genérica |

### 4.3 Notas

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| NoteCard | components/NoteCard.svelte | Tarjeta de previsualización |
| NoteEditor | components/NoteEditor.svelte | Editor markdown y previsualización (migrado a Svelte 5) |
| NoteSearch | components/NoteSearch.svelte | Búsqueda de notas |
| FileTree | components/FileTree.svelte | Árbol de archivos del vault |
| TagChip | components/TagChip.svelte | Chip de tag interactivo |
| TreeContextMenu | components/TreeContextMenu.svelte | Menú contextual del árbol de carpetas/notas |

### 4.4 Objetivos

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| GoalCard | components/GoalCard.svelte | Tarjeta de objetivo |
| GoalEditor | components/GoalEditor.svelte | Editor de objetivos |

### 4.5 Rachas

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| StreakListItem | components/StreakListItem.svelte | Item de racha en listados |
| StreakHeatmap | components/StreakHeatmap.svelte | Heatmap de actividad (calendario de check-ins) |
| StreakCreateModal | components/StreakCreateModal.svelte | Modal de creación/edición |
| StreakStatsPanel | components/StreakStatsPanel.svelte | Panel de estadísticas |
| StreakIcon | components/StreakIcon.svelte | Icono de racha |

### 4.6 Dashboard y Widgets

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| Widget | components/Widget.svelte | Contenedor de widgets drag/drop |
| Plant | components/Plant.svelte | Visualizador de etapa de planta |
| CityModule | components/CityModule.svelte | Visualizador de estado tipo ciudad |
| GalaxyModule | components/GalaxyModule.svelte | Visualizador de estado tipo galaxia |
| MountainModule | components/MountainModule.svelte | Visualizador de estado tipo montaña |
| OrbitModule | components/OrbitModule.svelte | Visualizador de estado tipo órbita |
| GithubWidget | components/GithubWidget.svelte | Widget de issues/PRs de GitHub |
| PomodoroWidget | components/PomodoroWidget.svelte | Widget Pomodoro |
| WeatherWidget | components/WeatherWidget.svelte | Widget de clima |
| TimeWidget | components/TimeWidget.svelte | Widget de tiempo |

### 4.7 Navegación y Config

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| SettingsPanel | components/SettingsPanel.svelte | Panel de ajustes e integraciones |
| CommandPalette | components/CommandPalette.svelte | Comandos rápidos (palette) |
| Login | components/Login.svelte | Autenticación de usuario |
| SetupWizard | components/SetupWizard.svelte | Asistente de configuración inicial (onboarding) |
| TutorialOverlay | components/TutorialOverlay.svelte | Guía de bienvenida superpuesta |

### 4.8 Otros

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| SkillTree | components/SkillTree.svelte | Árbol de habilidades |
| KnowledgeGraph | components/KnowledgeGraph.svelte | Grafo de tags/notas (D3) |
| KnowledgeGraphForce | components/KnowledgeGraphForce.svelte | Grafo de tags/notas con simulación de fuerzas |
| ThemePicker | components/ThemePicker.svelte | Selector de tema |
| FolderPicker | components/FolderPicker.svelte | Selector de carpeta |
| ErrorBoundary | components/ErrorBoundary.svelte | Captura de errores de componente |
| DeadLetterQueue | components/DeadLetterQueue.svelte | Utilidad de debug para mensajes fallidos |

---

## 5. Stores

Patrón principal: un archivo por dominio, exporta `writable`/`derived` y
funciones de carga/acción. Cualquier componente puede suscribirse con `$store`.

### 5.0 Catálogo completo

| Store | Tipo | Persistencia | Propósito |
|-------|------|--------------|-----------|
| `achievements.ts` | `writable` | `localStorage` | Logros desbloqueables del usuario. |
| `analytics.ts` | `writable` | memoria | Eventos de analytics y pageviews. |
| `connection.ts` | `writable` | escucha `navigator.onLine` | Estado online/offline. |
| `gamification.ts` | `writable + derived` | `localStorage` + API | XP, rachas, etapas de planta. |
| `githubCache.ts` | `writable` | `localStorage` | Cache de issues/PRs de GitHub. |
| `graph.ts` | `writable` | memoria | Datos del grafo de tags y nodo seleccionado. |
| `iconPicker.ts` | factory | memoria | Búsqueda y paginación de iconos Lucide. |
| `layout.ts` | `writable` | `localStorage` | Layout de widgets del dashboard. |
| `notes.ts` | `writable + derived` | API | Lista de notas, nota actual, selección masiva. |
| `notifications.ts` | `writable` | memoria | Cola de toasts/notificaciones UI. |
| `onboarding.ts` | `writable` | `localStorage` | Pasos del tutorial de bienvenida. |
| `pageSnapshots.ts` | `writable` | memoria | Guarda scroll/state al navegar. |
| `pagination.ts` | factory | memoria | Paginación reutilizable. |
| `pomodoro.ts` | `writable + derived` | `localStorage` | Temporizador Pomodoro global. |
| `pwa.ts` | `writable` | eventos del navegador | Prompt de instalación PWA. |
| `routeCache.ts` | writable + helper | `localStorage` | Cache TTL por ruta. |
| `session.ts` | `writable` | `localStorage` | Token y estado de autenticación. |
| `settings.ts` | `writable + derived` | `localStorage` | Colores, tema, icon pack, preferencias. |
| `theme.ts` | `writable` | `localStorage` | Temas predefinidos y switcher. |
| `ui.ts` | `writable` | memoria | Toasts, modal global, sidebar. |

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

### 5.7 achievements.ts

Logros desbloqueables del usuario. Persiste en `localStorage`.

### 5.8 analytics.ts

Eventos de analytics y pageviews. Mantiene los datos en memoria.

### 5.9 connection.ts

Estado online/offline. Escucha `navigator.onLine` para reflejar la conectividad
del navegador en tiempo real.

### 5.10 githubCache.ts

Cache de issues/PRs de GitHub. Persiste en `localStorage` para reducir llamadas
a la API.

### 5.11 iconPicker.ts

Factory de store para búsqueda y paginación de iconos Lucide. Datos en memoria.

### 5.12 notifications.ts

Cola de toasts/notificaciones UI. Datos en memoria.

### 5.13 onboarding.ts

Pasos del tutorial de bienvenida. Persiste en `localStorage`.

### 5.14 pageSnapshots.ts

Guarda scroll/state al navegar entre rutas para restaurar la posición. Datos en
memoria.

### 5.15 pagination.ts

Factory de store reutilizable para paginación. Datos en memoria.

### 5.16 pwa.ts

Prompt de instalación PWA. Escucha eventos del navegador
(`beforeinstallprompt`).

### 5.17 routeCache.ts

Cache TTL por ruta. Persiste en `localStorage` con helpers de expiración.

### 5.18 session.ts

Token y estado de autenticación. Persiste en `localStorage`.

### 5.19 theme.ts

Temas predefinidos y switcher. Persiste en `localStorage`.

### 5.20 ui.ts

Toasts, modal global y estado del sidebar. Datos en memoria.

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

---

## 11. Flujo de Datos

```
Usuario ──► Componente Svelte ──► Store ──► api.ts ──► Backend (FastAPI)
                │                   │
                ▼                   ▼
            UI reactiva ($store)   cache/localStorage
```

1. El usuario interactúa con un componente.
2. El componente invoca una función de un store (p. ej. `createNote`).
3. La función del store llama a `api.notes.create(...)`.
4. Si la respuesta es OK, el store actualiza su `writable`.
5. Los componentes suscritos (`$notes`, `$currentNote`) se re-renderizan.
6. Algunos stores persisten en `localStorage` o `routeCache` para reducir llamadas.

---

## 12. Convenciones

- **Componentes**: PascalCase (`NoteEditor.svelte`), un componente por archivo.
- **Stores**: camelCase (`notes.ts`), preferiblemente dominio por archivo.
- **Rutas**: SvelteKit, carpetas con `+page.svelte`.
- **Iconos**: usar `DynamicIcon name="IconName"` en vez de importar iconos a mano.
- **Estilos**: variables CSS en `:root` (`app.css`); componentes usan `<style scoped>`.
- **Errores**: usar `logger` para consola y `showNotification` para mensajes UI.

---

## 13. Cómo agregar una nueva página

1. Crear carpeta en `src/routes/<nombre>/+page.svelte`.
2. Agregar ítem en `+layout.svelte` (`navItems`) si debe aparecer en la sidebar.
3. Crear/actualizar store en `src/lib/stores/` si la página necesita estado global.
4. Agregar endpoints en `src/lib/api.ts` si consumen datos nuevos.
5. Actualizar esta documentación.