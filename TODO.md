# 📓 Pendientes y Mejoras - Proyecto Joidy

> [!NOTE]
> Joidy es una plataforma unificada para la gestión personal del conocimiento gamificado. Este documento registra el estado actual del roadmap, las optimizaciones pendientes y los hallazgos técnicos recientes.

---

## 🛠️ 1. Optimizaciones Técnicas Críticas (Nuevas)

### 🔴 Alta Prioridad
- [x] **Bug en Health Check de Caché (Backend)**: Corregido en `api/services/response_cache.py`. Se añadió `"initialized": True` a las estadísticas del caché para evitar el estado "degraded" falso en `/health/ready`.
- [ ] **Menú de Exportación en Interfaz (Frontend)**: Agregar controles en la barra de herramientas de `NoteEditor.svelte` y en la vista de notas para invocar los endpoints de exportación existentes en `/export/notes/markdown`, `/export/notes/html` y `/export/notes/zip`.
- [ ] **Soporte de WebSocket End-to-End (Real-time)**: Conectar el cliente Svelte al canal `/ws` implementado en el backend para recibir notificaciones reactivas sin recarga. Además, **integrar las llamadas de difusión en el backend** (como `notify_note_created`, `notify_xp_gained`, `notify_streak_updated` definidos en `api/routers/websocket.py`) en sus respectivos servicios de mutación (`note_service.py`, `gamification_engine.py`), ya que actualmente están huérfanos y no se disparan.

### 🟡 Media Prioridad
- [ ] **Rate Limiting Avanzado**: Extender el middleware `RateLimitMiddleware` para soportar límites de peticiones basados en clave de API o por usuario autenticado, en lugar de límites globales únicamente.

---

## 💻 2. Backend - Estado de Desarrollo

### 2.1 Integraciones
- [x] **GITHUB_CLIENT_SECRET**: Configurado y en uso en la integración OAuth.
- [ ] **Calendario Personalizado (Google API)**: Implementar integración de eventos y tareas basada en Google Calendar y Google Tasks (Ver sección de arquitectura de Google abajo).
- [ ] **Sincronización Bidireccional con Obsidian via Webhook**: Permitir triggers instantáneos externos hacia la bóveda en lugar de depender únicamente del watcher local.

### 2.2 Servicios & Middleware
- [x] **response_cache** (`api/services/response_cache.py`): Caché TTL en memoria para endpoints costosos con estadísticas completas y eviction seguro.
- [x] **Dead Letter Queue (DLQ)**: Sistema de almacenamiento y reintento con backoff exponencial para embeddings fallidos (`embedding_failures`).
- [x] **Rate Limiting Global**: Middleware implementado a 60 req/min para salvaguardar la API.

### 2.3 Base de Datos & Modelos
- [x] **Alembic Migrations**: Sistema de migraciones robusto y automatizado en la inicialización de la app (`init_db()`).
- [x] **Índices de Rendimiento**: Índices para optimizar la velocidad en consultas complejas sobre el grafo de co-ocurrencia.
- [x] **Tabla de Configuración Centralizada**: Configuración de XP y metas extraídas de variables hardcoded a configuraciones del entorno y BD.
- [ ] **Migración a PostgreSQL**: Adaptar los modelos para producción en preparación para una base de datos distribuida en lugar de SQLite (manteniendo soporte `sqlite-vec` o migrando a pgvector).

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
- [ ] **Sincronización en tiempo real avanzada**: Detección bidireccional instantánea de conflictos de escritura.
- [ ] **Editor WYSIWYG**: Editor enriquecido para edición visual directa de Markdown.

---

## 🧪 4. Control de Calidad y Cobertura

### 4.1 Unit Tests
- [x] `test_note_service.py` — Pruebas de persistencia y parsing de enlaces.
- [x] `test_goal_service.py` — Pruebas sobre temporización y rollover.
- [x] `test_embedding_service.py` — Pruebas de vectorización asíncrona.
- [x] `test_embedding_retry.py` — Validación del backoff exponencial en la cola de fallos.

### 4.2 Integration & E2E Tests
- [ ] **Pruebas E2E de la API**: Validación de flujos completos de usuario mediante endpoints encadenados.
- [ ] **Pruebas de Sincronización**: Simulación de escrituras en Obsidian y verificación de consistencia en DB.
- [ ] **Cobertura General**: Elevar la cobertura actual de un ~20% estimado a un **70%+ target**.

---

## 🔒 5. Infraestructura, Seguridad y DevOps

- [x] **CI/CD con GitHub Actions**: Workflow implementado (`ci.yml`) con linting, typecheck y compilación Docker automatizada.
- [x] **Logging Estructurado**: Configuración diferenciada de logs (JSON plano en producción, formato coloreado en desarrollo).
- [x] **Monitoreo & Health Checks**: Endpoint `/metrics` expuesto e integración de health checks cruzados en Docker Compose.
- [x] **Backups**: Script automatizado en python (`backup.py`) y comando `make backup`.
- [ ] **Seguridad Avanzada**: Autenticación nativa por JWT y sanitización estricta ante XSS.
- [ ] **alerting & Monitoring**: Configuración de Prometheus/Grafana para consumo de métricas.

---

## 💡 6. Integración con Google (Backlog Estratégico)

> [!IMPORTANT]
> **Arquitectura OAuth 2.0 y APIs**:
> - **APIs requeridas**: Google Calendar API y Google Tasks API.
> - ** UX**: Botón en panel de ajustes que redirige a la pantalla segura de consentimiento de Google.
> - **Persistencia**: Almacenamiento seguro del *Refresh Token* cifrado en la base de datos para sincronización background continua.
> - **Despliegue**: Uso de entorno "Test" en Google Cloud Console durante desarrollo. Requiere pasar la auditoría de scopes sensibles de Google antes del despliegue público.

---

## 🚀 7. Plan de Trabajo Inmediato

1. **[Backlog]** Corregir el bug del Health Check de Caché en el backend para reportar estados correctos de salud de la infraestructura.
2. **[Frontend]** Crear controles y UI interactiva para la exportación de notas directamente desde la barra de herramientas de `NoteEditor.svelte`.
3. **[Frontend]** Conectar el cliente Svelte al WebSocket del backend para lograr reactividad en tiempo real de XP y alertas.

---

*Última actualización: Mayo 2026*
