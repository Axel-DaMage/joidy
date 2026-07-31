# Joidy — Arquitectura del Frontend

Documento orientado a desarrolladores. Describe el stack, las rutas, las stores,
los componentes, la capa de API y el flujo de datos de `frontend/`.

## Stack

- **Framework**: SvelteKit 5 (con runes) + Vite
- **Lenguaje**: TypeScript
- **Estilos**: CSS global en `app.css` + estilos por componente (`<style>`)
- **Estado**: Svelte stores (`writable`, `derived`) en `lib/stores/`
- **Comunicación con backend**: cliente HTTP en `lib/api.ts`
- **Iconos**: `lucide-svelte` a través de `DynamicIcon.svelte`

## Rutas (`src/routes/`)

| Ruta | Archivo | Descripción |
|------|---------|-------------|
| `/` | `+page.svelte` | Dashboard con widgets de planta, notas, GitHub, etc. |
| `+layout.svelte` | `+layout.svelte` | Layout raíz: header, sidebar, statusbar, WebSocket, PWA. |
| `/notes` | `notes/+page.svelte` | Explorador y editor de notas con árbol de carpetas. |
| `/goals` | `goals/+page.svelte` | Objetivos: editor, today, planning, history, analytics. |
| `/streaks` | `streaks/+page.svelte` | Rachas personales con check-ins y calendario. |
| `/skills` | `skills/+page.svelte` | Árbol de habilidades basado en tags. |
| `/graph` | `graph/+page.svelte` | Grafo de conocimiento (modo dev). |
| `/ai` | `ai/+page.svelte` | Asistente de IA (modo dev). |

## Stores (`src/lib/stores/`)

Patrón principal: un archivo por dominio, exporta `writable`/`derived` y
funciones de carga/acción. Cualquier componente puede suscribirse con `$store`.

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

## Componentes (`src/lib/components/`)

### Primitivas UI

- `Card.svelte` — contenedor con elevación y borde.
- `Badge.svelte` — etiquetas de estado.
- `Button` no existe; se usan clases `.btn`, `.link-btn` desde `app.css`.
- `Modal.svelte` — modal global con `focusTrap`.
- `Toast.svelte` — notificación flotante.
- `Skeleton.svelte`, `Spinner.svelte`, `EmptyState.svelte` — estados de carga/vacío.
- `DynamicIcon.svelte` — renderiza iconos de Lucide por nombre.

### Notas

- `NoteCard.svelte` — tarjeta de nota en listados.
- `NoteEditor.svelte` — editor markdown y previsualización (migrado a Svelte 5).
- `NoteSearch.svelte` — búsqueda de notas.
- `FileTree.svelte` — árbol de carpetas/notas.
- `TagChip.svelte` — chip de tag interactivo.
- `TreeContextMenu.svelte` — menú contextual del árbol.

### Objetivos y rachas

- `GoalCard.svelte` — tarjeta de objetivo.
- `GoalEditor.svelte` — modal de edición de objetivo.
- `StreakListItem.svelte` — item de racha.
- `StreakCreateModal.svelte` — creación/edición de rachas.
- `StreakHeatmap.svelte` — calendario de check-ins.
- `StreakCounter.svelte`, `StreakStatsPanel.svelte` — estadísticas.

### Dashboard y widgets

- `Widget.svelte` — contenedor de widgets drag/drop.
- `Plant.svelte`, `CityModule.svelte`, `GalaxyModule.svelte`, `MountainModule.svelte`, `OrbitModule.svelte` — visualizadores de la planta/estado.
- `ActivityProgress.svelte`, `XPBar.svelte`, `ProgressBar.svelte` — barras de progreso.
- `GithubWidget.svelte`, `PomodoroWidget.svelte`, `WeatherWidget.svelte`, `TimeWidget.svelte` — widgets específicos.

### Navegación y config

- `SettingsPanel.svelte` — panel de ajustes e integraciones.
- `CommandPalette.svelte` — comandos rápidos.
- `Login.svelte`, `SetupWizard.svelte` — auth y onboarding.
- `TutorialOverlay.svelte` — guía de bienvenida.

### Otros

- `SkillTree.svelte` — visualización del árbol de habilidades.
- `KnowledgeGraph.svelte`, `KnowledgeGraphForce.svelte` — grafo de tags/notas.
- `IconPicker.svelte`, `ThemePicker.svelte`, `FolderPicker.svelte` — pickers.
- `ErrorBoundary.svelte`, `DeadLetterQueue.svelte` — utilidades de debug.

## Capa de API (`src/lib/api.ts`)

`api` es un objeto singleton que agrupa llamadas por dominio. Usa `fetch` hacia
`http://<host>:8000` con JWT desde `session.ts`.

```
API → req(method, path, body?) → fetch → JSON
```

Grupos principales: `auth`, `config`, `notes`, `tags`, `folders`, `goals`,
`personalStreaks`, `skills`, `gamification`, `ai`, `github`, `stats`.

## Flujo de datos

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

## Convenciones

- **Componentes**: PascalCase (`NoteEditor.svelte`), un componente por archivo.
- **Stores**: camelCase (`notes.ts`), preferiblemente dominio por archivo.
- **Rutas**: SvelteKit, carpetas con `+page.svelte`.
- **Iconos**: usar `DynamicIcon name="IconName"` en vez de importar iconos a mano.
- **Estilos**: variables CSS en `:root` (`app.css`); componentes usan `<style scoped>`.
- **Errores**: usar `logger` para consola y `showNotification` para mensajes UI.

## Cómo agregar una nueva página

1. Crear carpeta en `src/routes/<nombre>/+page.svelte`.
2. Agregar ítem en `+layout.svelte` (`navItems`) si debe aparecer en la sidebar.
3. Crear/actualizar store en `src/lib/stores/` si la página necesita estado global.
4. Agregar endpoints en `src/lib/api.ts` si consumen datos nuevos.
5. Actualizar este `ARCHITECTURE.md`.
