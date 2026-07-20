# 📓 Pendientes y Mejoras - Proyecto Joidy

> [!NOTE]
> Joidy es una plataforma unificada para la gestión personal del conocimiento gamificado. Este documento registra el estado actual del roadmap, las optimizaciones pendientes y los hallazgos técnicos recientes.

---

## 🏆 1. Logros Recientes (Completados)
- [x] **Rate Limiting Avanzado**: Extender el middleware `RateLimitMiddleware` (PR #27 / Issue #27).
- [x] **Soporte de WebSocket End-to-End (Real-time)**: Conexión de Svelte a `/ws` y notificaciones reactivas (PR #27).
- [x] **Menú de Exportación en Interfaz (Frontend)**: Controles para exportar markdown/html/zip en `NoteEditor.svelte` (PR #27).
- [x] **Bug en Health Check de Caché (Backend)**: Corregido en `api/services/response_cache.py` (PR #27).
- [x] **VirtualList dinámica**: Refactorizado para admitir alturas variables (Issue #7).
- [x] **Migración Consistente a Runas Svelte 5**: Reactividad nativa en componentes (Issue #10).
- [x] **Seguridad JWT**: Autenticación nativa por JWT (Issue #14).
- [x] **Ruff + Black**: Pipeline de formateo automático y análisis estático (Issue #16).
- [x] **Dashboard de Historial Anual**: Componente `StreakHeatmap` interactivo.
- [x] **Modal de Objetivos**: Componente `GoalOverlay`.
- [x] **Dashboard de Planificación unificado (SGOJ)**.
- [x] **Tema Oscuro/Claro Manual**.
- [x] **Widget de GitHub**.

---

## 🛠️ 2. Backlog Estratégico & Tareas Abiertas

### 2.1 Integraciones & Backend
- [ ] **Calendario Personalizado (Google API)**: Implementar Google Calendar y Tasks (#2).
- [ ] **Sincronización Bidireccional con Obsidian via Webhook**: Triggers instantáneos externos (#3).
- [ ] **Migración a PostgreSQL**: Adaptar los modelos para producción (#4).
- [ ] **Integración de IA (chat/asistente)**: (#41)
- [ ] **Integración de Gmail**: (#42)
- [ ] **Integración de Contactos (Google)**: (#43)
- [ ] **Integración de Strava**: (#44)
- [ ] **Integración de Spotify**: (#45)
- [ ] **GitHub OAuth real**: (#46)
- [ ] **UI de Dead Letter Queue**: Gestión de embeddings fallidos (#49).
- [ ] **Alerting & Monitoring**: Prometheus/Grafana (#15).

### 2.2 Frontend & UX
- [ ] **WYSIWYG Editor**: Editor enriquecido Markdown (#6).
- [ ] **Filtros Interactivos y Agrupamiento en el Grafo**: (#8).
- [ ] **Accesibilidad y Foco en Modales (Focus Trapping)**: (#9).
- [ ] **Creación de carpetas en notas**: (#47).
- [ ] **Quitar dev-mode gating**: (#48).
- [ ] **Mejora WeatherWidget UX**: (#50).
- [ ] **Indicadores en navegación**: (#51).

### 2.3 Control de Calidad y Tests
- [ ] **Tests de integración / E2E API**: (#11).
- [ ] **Pruebas de Sincronización**: (#12).
- [ ] **Mejorar Cobertura General**: (#13).

---
*Última actualización: Julio 2026*
