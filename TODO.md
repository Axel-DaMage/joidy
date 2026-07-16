# 📓 Pendientes y Mejoras - Proyecto Joidy

> [!NOTE]
> Joidy es una plataforma unificada para la gestión personal del conocimiento gamificado. Este documento registra el estado actual del roadmap, las optimizaciones pendientes y los hallazgos técnicos recientes.

---

## 🛠️ 1. Optimizaciones Técnicas Críticas (Nuevas)

### 🔴 Alta Prioridad
- [x] **Bug en Health Check de Caché (Backend)**: Corregido en `api/services/response_cache.py`. Se añadió `"initialized": True` a las estadísticas del caché para evitar el estado "degraded" falso en `/health/ready`.
- [x] **Menú de Exportación en Interfaz (Frontend)**: Agregar controles en la barra de herramientas de `NoteEditor.svelte` y en la vista de notas para invocar los endpoints de exportación existentes en `/export/notes/markdown`, `/export/notes/html` y `/export/notes/zip`.
- [x] **Soporte de WebSocket End-to-End (Real-time)**: Conectar el cliente Svelte al canal `/ws` implementado en el backend para recibir notificaciones reactivas sin recarga. Además, **integrar las llamadas de difusión en el backend** (como `notify_note_created`, `notify_xp_gained`, `notify_streak_updated` definidos en `api/routers/websocket.py`) en sus respectivos servicios de mutación (`note_service.py`, `gamification_engine.py`), ya que actualmente están huérfanos y no se disparan.

### 🟡 Media Prioridad
- [x] **Rate Limiting Avanzado**: Extender el middleware `RateLimitMiddleware` para soportar límites de peticiones basados en clave de API o por usuario autenticado, en lugar de límites globales únicamente.

---

## 💻 2. Backend - Estado de Desarrollo

### 2.1 Integraciones
- [x] **GITHUB_CLIENT_SECRET**: Configurado y en uso en la integración OAuth.
- [ ] **Calendario Personalizado (Google API)**: Implementar integración de eventos y tareas basada en Google Calendar y Google Tasks (Ver sección de arquitectura de Google abajo).
- [ ] **Sincronización Bidireccional con Obsidian via Webhook**: Permitir triggers instantáneos externos hacia la bóveda en lugar de depender únicamente del watcher local. (Ver: #73)

### 2.2 Servicios & Middleware
- [x] **response_cache** (`api/services/response_cache.py`): Caché TTL en memoria para endpoints costosos con estadísticas completas y eviction seguro. (✅ Implementado en #35)
- [x] **Dead Letter Queue (DLQ)**: Sistema de almacenamiento y reintento con backoff exponencial para embeddings fallidos (`embedding_failures`).
- [x] **Rate Limiting Global**: Middleware implementado a 60 req/min para salvaguardar la API.

### 2.3 Base de Datos & Modelos
- [x] **Alembic Migrations**: Sistema de migraciones robusto y automatizado en la inicialización de la app (`init_db()`).
- [x] **Índices de Rendimiento**: Índices para optimizar la velocidad en consultas complejas sobre el grafo de co-ocurrencia. (✅ Implementado en #33)
- [x] **Tabla de Configuración Centralizada**: Configuración de XP y metas extraídas de variables hardcoded a configuraciones del entorno y BD.
- [x] **Migración a PostgreSQL**: Adaptar los modelos para producción en preparación para una base de datos distribuida en lugar de SQLite (manteniendo soporte `sqlite-vec` o migrando a pgvector). (✅ Implementado en #4)

---

## 🎨 3. Frontend - Estado de Desarrollo

### 3.1 Componentes e Interfaz
- [x] **Dashboard de Historial Anual**: Componente `StreakHeatmap` interactivo y altamente visual.
- [x] **Modal de Objetivos**: Componente `GoalOverlay` e interfaz fluida de creación/edición.
- [x] **Dashboard de Planificación unificado (SGOJ)**: Integración de objetivos y planificación temporal.
- [x] **Notificaciones y Toasts**: Sistema centralizado reactivo a través de `<Toast />` y store de gamificación.
- [x] **Tema Oscuro/Claro Manual**: Selector persistente en el panel de Ajustes con transiciones fluidas.
- [x] **Tutorial y Onboarding**: Recorrido de bienvenida interactivo utilizando `TutorialOverlay.svelte` y persistencia local.
- [x] **Widget de GitHub**:
  - [x] Consolidado en un componente unificado y altamente reusable.
  - [x] Altura fija y predecible entre cambios de filtros.
  - [x] Indicador sutil de "actualizando" (pulsing blue dot) que no interrumpe la navegación.
  - [x] Carga diferida y animaciones de carga tipo Skeleton.

### 3.2 Widgets de Dashboard
- [x] **PomodoroWidget**: Temporizador persistente con debounce de guardado a 500ms.
- [x] **TimeWidget**: Selector de zonas horarias en tiempo real.
- [x] **WeatherWidget**: Widget interactivo que consume Open-Meteo basado en la geolocalización del navegador.

### 3.3 Integración con Obsidian
- [x] **Sincronización básica**: Importación automática de notas Markdown.
- [x] **Metadatos Frontmatter**: Guardado e interpretación nativa de iconos y colores mediante YAML.
- [ ] **Sincronización en tiempo real avanzada**: Detección bidireccional instantánea de conflictos de escritura. (Ver: #73)
- [ ] **Editor WYSIWYG**: Editor enriquecido para edición visual directa de Markdown. (Ver: #64)

### 3.4 Mejoras Estructurales y UX del Frontend (Nuevas)
- [x] **Interceptor Global de Errores en `api.ts`**: Manejar automáticamente token expirado (401), errores de red y propagación de toasts amigables a nivel de aplicación.
- [x] **Indicador de Conectividad en Tiempo Real**: Vincular las stores `isOnline` y `wasOffline` a un banner o píldora de estado premium y glassmorphic en la barra de herramientas principal.
- [x] **Optimización de VirtualList Dinámica**: Refactorizar `VirtualList.svelte` para admitir alturas de elemento dinámicas/variables (mediante ResizeObserver) para evitar solapamientos en notas con títulos largos. (✅ Implementado en #7)
- [ ] **Filtros Interactivos y Agrupamiento en el Grafo**: Agregar un panel lateral dentro de `/graph` para aislar nodos por etiquetas, buscar notas directamente y activar físicas avanzadas de repulsión.
- [ ] **Accesibilidad y Foco en Modales**: Implementar "focus trapping" completo en `Modal.svelte` y mejorar atributos ARIA en los widgets interactivos del dashboard. (Ver: #32)
- [x] **Migración Consistente a Runas Svelte 5**: Estandarizar la reactividad migrando paulatinamente los stores personalizados de Svelte 4 a runas nativas (`$state`, `$derived`, `$effect`) en componentes de alta frecuencia. (✅ Implementado en #10)

---

## 🧪 4. Control de Calidad y Cobertura

### 4.1 Unit Tests
- [x] `test_note_service.py` — Pruebas de persistencia y parsing de enlaces.
- [x] `test_goal_service.py` — Pruebas sobre temporización y rollover.
- [x] `test_embedding_service.py` — Pruebas de vectorización asíncrona.
- [x] `test_embedding_retry.py` — Validación del backoff exponencial en la cola de fallos.

### 4.2 Integration & E2E Tests
- [ ] **Pruebas E2E de la API**: Validación de flujos completos de usuario mediante endpoints encadenados. (Ver: #59)
- [ ] **Pruebas de Sincronización**: Simulación de escrituras en Obsidian y verificación de consistencia en DB.
- [ ] **Cobertura General**: Elevar la cobertura actual de un ~20% estimado a un **70%+ target**. (Ver: #40)

---

## 🔒 5. Infraestructura, Seguridad y DevOps

- [x] **CI/CD con GitHub Actions**: Workflow implementado (`ci.yml`) con linting, typecheck y compilación Docker automatizada.
- [x] **Logging Estructurado**: Configuración diferenciada de logs (JSON plano en producción, formato coloreado en desarrollo).
- [x] **Monitoreo & Health Checks**: Endpoint `/metrics` expuesto e integración de health checks cruzados en Docker Compose.
- [x] **Backups**: Script automatizado en python (`backup.py`) y comando `make backup`.
- [x] **Seguridad Avanzada**: Autenticación nativa por JWT y sanitización estricta ante XSS. (✅ Implementado en #14, #34)
- [ ] **Alerting & Monitoring**: Configuración de Prometheus/Grafana para consumo de métricas. (Ver: #15)

---

## 💡 6. Integración con Google (Backlog Estratégico)

> [!IMPORTANT]
> **Arquitectura OAuth 2.0 y APIs**:
> - **APIs requeridas**: Google Calendar API y Google Tasks API.
> - **UX**: Botón en panel de ajustes que redirige a la pantalla segura de consentimiento de Google.
> - **Persistencia**: Almacenamiento seguro del *Refresh Token* cifrado en la base de datos para sincronización background continua.
> - **Despliegue**: Uso de entorno "Test" en Google Cloud Console durante desarrollo. Requiere pasar la auditoría de scopes sensibles de Google antes del despliegue público.

---

## 🚀 7. Plan de Trabajo Inmediato (Próximos Pasos)

1. **[Seguridad — Alta Prioridad]**: Reemplazar la autenticación simple actual por un flujo completo JWT multiusuario con tokens seguros y almacenamiento cifrado en base de datos. ✅ Implementado en #14, #34
2. **[Calidad de Código & Automatización]**: Integrar un pipeline de formateo automático y análisis estático en el backend (`Ruff` + `Black`) para unificar el estilo de código del monorepo y evitar regresiones. ✅ Implementado en #16
3. **[Frontend UX]**: Refactorizar el componente `VirtualList.svelte` con `ResizeObserver` para soportar alturas de elementos dinámicas en la lista de notas, optimizando la fluidez de navegación. ✅ Implementado en #7

---

## 🆕 8. Issues Creados (#41–#79)

| #  | Título |
|----|--------|
| #41 | `frontend+backend: Implementar página de Inteligencia Artificial (IA/Asistente)` |
| #42 | `frontend+backend: Integración real de Gmail` |
| #43 | `frontend+backend: Integración real de Contactos (Google Contacts)` |
| #44 | `frontend+backend: Integración real de Strava` |
| #45 | `frontend+backend: Integración real de Spotify` |
| #46 | `bug: Botón 'Enlazar GitHub' en SettingsPanel es un placeholder (no hace OAuth real)` |
| #47 | `feat: Implementar creación de carpetas en notas (reemplazar alert stub)` |
| #48 | `feat: Quitar dev-mode gating de páginas Grafo y Habilidades (están funcionales)` |
| #49 | `feat: UI para gestión de embeddings fallidos (Dead Letter Queue)` |
| #50 | `bug: WeatherWidget usa geolocalización solicitando permiso cada vez que se monta` |
| #51 | `feat: Indicadores visuales en navegación lateral para páginas placeholder vs funcionales` |
| #52 | `docs: Reflejar estado real de cada integración en AGENTS.md y SettingsPanel` |
| #53 | `chore: Sincronizar estado de issues con TODO.md — mover tareas completadas a cerradas` |
| #54 | `feat: Página de Integraciones unificada (refactor de placeholders)` |
| #55 | `bug: Las notas y objetivos se eliminan sin confirmación — riesgo de pérdida de datos` |
| #56 | `bug: XSS en editor de notas — markdown renderizado sin sanitización de HTML` |
| #57 | `feat: Implementar autosave en editor de notas (con debounce y recuperación)` |
| #58 | `refactor: La página de Objetivos (goals/+page.svelte) tiene 4190 líneas — dividir en componentes` |
| #59 | `feat: Zero frontend tests — crear suite de tests para componentes y stores` |
| #60 | `feat: Diseño responsive — la app no es usable en móvil` |
| #61 | `bug: Login con datos hardcodeados — no valida usuario real, siempre es 'user'` |
| #62 | `feat: Agregar resaltado de sintaxis para bloques de código en markdown` |
| #63 | `feat: Paleta de comandos global (Cmd+K / Ctrl+K) para navegación rápida` |
| #64 | `feat: Editor markdown con toolbar de formato (negrita, cursiva, headings, listas)` |
| #65 | `feat: No hay error boundaries — un crash en cualquier componente rompe toda la app` |
| #66 | `feat: Soporte offline progresivo — mejorar service worker para funcionar sin conexión` |
| #67 | `feat: Subida de imágenes y archivos adjuntos en notas` |
| #68 | `feat: Operaciones bulk en notas — seleccionar múltiples para eliminar/etiquetar/exportar` |
| #69 | `refactor: La página de Rachas (streaks/+page.svelte) tiene 1376 líneas — extraer componentes` |
| #70 | `chore: Los 5 placeholders de integración tienen ~600 líneas de código duplicado — refactorizar` |
| #71 | `feat: Historial de versiones de notas (undo/redo en el editor)` |
| #72 | `feat: PWA — manejar evento beforeinstallprompt para guiar al usuario a instalar` |
| #73 | `feat: Sincronización bidireccional en tiempo real con Obsidian vía WebSocket` |
| #74 | `chore: El NoteEditor importa lucide-svelte entero — reemplazar por DynamicIcon` |
| #75 | `docs: Documentar todos los stores, componentes y flujos de datos del frontend` |
| #76 | `feat: Barra de progreso semanal/anual y estadísticas de actividad en dashboard` |
| #77 | `bug: WebSocket se reconecta cada 5s incluso si la pestaña está en background` |
| #78 | `feat: Dashboard widgets reordenables con drag & drop (actualmente solo botones)` |
| #79 | `feat: Notificaciones push reales para recordatorios (rachas, objetivos, pomodoro)` |

---

*Última actualización: Julio 2026*
