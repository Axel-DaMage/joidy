# Pendientes y Mejoras - Proyecto Joidy

## 1. Backend - Pendientes

### 1.1 Integraciones
- [ ] **GITHUB_CLIENT_SECRET**: Generar en GitHub OAuth App settings
- [ ] Implementar integraciones adicionales (Slack, Notion, Calendar)
- [ ] Webhook para sincronización bidireccional con Obsidian

### 1.2 Servicios
- [ ] Completar sistema de response_cache (`api/services/response_cache.py` está vacío)
- [ ] Implementar cache para tag co-occurrences (actualmente O(n²))
- [ ] Sistema de dead letter queue para embeddings fallidos

### 1.3 API Endpoints
- [ ] Validación más robusta con Pydantic en todos los endpoints
- [ ] Rate limiting por usuario
- [ ] Documentación OpenAPI completa

### 1.4 Base de Datos
- [ ] Sistema de migraciones con Alembic (mencionado en REPORT.md)
- [ ] Índices para optimizar queries de grafos
- [ ] Tabla de configuración centralizada (XP_TABLE hardcoded)

---

## 2. Frontend - Pendientes

### 2.1 Páginas
- [ ] Página de Settings/Configuración de usuario
- [ ] Página de Dashboard consolidado
- [ ] Página de Integraciones

### 2.2 Componentes e Interfaz
- [x] Dashboard de Historial Anual interactivo (StreakHeatmap)
- [x] Modal de metas (Goal Overlay Component)
- [x] Dashboard de Planificación unificado (SGOJ)
- [x] Personalización de íconos y colores en lista de notas (Sincronizado a YAML)
- [ ] Sistema de notificaciones/toast centralizado
- [ ] Tema oscuro/claro toggle manual
- [ ] Tutorial/onboarding para nuevos usuarios

### 2.3 Widgets
- [ ] Completar PomodoroWidget con persistencia
- [ ] Completar TimeWidget con zonas horarias
- [ ] Widget de clima (depende de API externa)

### 2.4 Obsidian Integration
- [x] Sincronización básica de notas
- [x] Edición y guardado de Frontmatter nativo (iconos, colores)
- [ ] Sync bidireccional avanzado en tiempo real
- [ ] Editor Markdown WYSIWYG completo

---

## 3. Tests - Pendientes

### 3.1 Unit Tests
- [ ] `test_note_service.py` - Missing
- [ ] `test_goal_service.py` - Missing
- [ ] `test_embedding_service.py` - Missing

### 3.2 Integration Tests
- [ ] Tests E2E de API
- [ ] Tests de sincronización with Obsidian
- [ ] Tests de worker tasks

### 3.3 Coverage
- [ ] Coverage actual: ~20% (estimado)
- [ ] Target: 70%+ coverage

---

## 4. Infrastructure - Pendientes

### 4.1 CI/CD
- [ ] GitHub Actions para CI
- [ ] Pipeline de deployment
- [ ] linter/typecheck automatizado

### 4.2 Monitoreo
- [ ] Logging estructurado
- [ ] Métricas (Prometheus/Grafana)
- [ ] Health checks avanzados

### 4.3 Seguridad
- [ ] Autenticación/JWT
- [ ] Rate limiting por API key
- [ ] Sanitización de inputs

### 4.4 DevOps
- [ ] Backup automático diario
- [ ]监控 y alertas
- [ ] Pipeline de rollback

---

## 5. Documentación - Pendientes

### 5.1 Wiki/Docs
- [ ] README.md principal
- [ ] Documentación de API endpoints
- [ ] Guía de instalación
- [ ] Contribución / Code style guide

### 5.2 Arquitectura
- [ ] Diagramas de arquitectura
- [ ] Modelo de datos
- [ ] Decisiones técnicas (ADRs)

---

## 6. Mejoras Técnicas (Roadmap)

### Alta Prioridad
- [ ] Extraer lógica de routers a service layer
- [ ] Implementar Unit of Work pattern
- [ ] Pre-calcular co-occurrences de tags
- [ ] Centralizar configuración

### Media Prioridad
- [ ] Migrar a PostgreSQL para producción
- [ ] Implementar WebSocket para real-time updates
- [ ] Cache con Redis
- [ ] Task queue con Celery

### Baja Prioridad
- [ ] Soporte multi-idioma (i18n)
- [ ] PWA para móvil
- [ ] Tema customizable
- [ ] Plugin system

---

## 7. Bugs Conocidos

- [ ] Vault watcher puede dejar tareas huérfanas en edge cases
- [ ] Embeddings fallidos no se reintentanconsistentemente
- [ ] Skill tree puede tener ciclos si se crean jerarquías circulares
- [ ] CORS allows "*" en producción

---

## 8. Features Pedientes de Diseño

- [ ] Gamificación: Logros (Achievements)
- [ ] Social: Compartir notas/pérfiles
- [ ] Analytics: Estadísticas de uso
- [ ] Export: PDF, Markdown, HTML
- [ ] Import:Desde otros sistemas (Notion, Evernote)

## 9. Integración con Google (Contexto y Arquitectura)

**Contexto del Proyecto:**
Desarrollo de una aplicación con un calendario personalizado que requiere extraer y mostrar eventos y tareas directamente desde las cuentas de Google de los usuarios finales.

**APIs y Arquitectura Requerida:**
*   **APIs Necesarias:** Google Calendar API (gestión de eventos) y Google Tasks API (gestión de tareas). Deben habilitarse desde un proyecto en la Consola de Google Cloud.
*   **Costos:** El uso de estas APIs es gratuito, operando bajo un límite de cuotas amplio (ej. 1.000.000 peticiones diarias para Calendar), suficiente para proyectos estándar.

**Flujo de Autenticación (Multi-usuario):**
*   **Protocolo:** OAuth 2.0. Permite a múltiples usuarios conectar sus cuentas sin compartir credenciales.
*   **Interfaz (UX):** El usuario interactúa con un botón en la aplicación que lo redirige a la pantalla segura de inicio de sesión y consentimiento de Google.
*   **Backend:** Tras la aprobación del usuario, Google retorna un *Access Token* y un *Refresh Token*. El sistema debe almacenar el *Refresh Token* de forma segura en la base de datos, vinculado al perfil del usuario, para mantener la sincronización de datos en segundo plano a largo plazo.

**Requisitos de Despliegue:**
*   Configuración de la "Pantalla de consentimiento de OAuth" en Google Cloud, definiendo los *scopes* (permisos) estrictamente necesarios (lectura de eventos y tareas).
*   **Verificación de Google:** Antes del lanzamiento público, la aplicación deberá someterse y aprobar el proceso de verificación de Google, ya que los *scopes* de Calendar y Tasks implican el acceso a datos de usuario sensibles. Se debe utilizar el modo de "Prueba" durante la etapa de desarrollo.

---

*Generado: Mayo 2026*