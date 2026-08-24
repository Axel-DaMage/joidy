# Joidy - Documentación Completa

## Metadata

```yaml
project: Joidy
type: Sistema de Gestión del Conocimiento con Gamificación
version: 0.2.0
framework: Monorepo Docker
docs_version: 2.0
```

---

## Resumen

Joidy es un sistema personal de gestión del conocimiento que integra:
- Gestión de notas con sincronización de Obsidian
- Grafo de conocimiento basado en tags y co-ocurrencias
- Sistema de objetivos con múltiples temporalidades
- Rachas personales con check-ins y freezes
- Gamificación con XP, niveles y evolución de planta
- IA para embeddings, clasificación y búsqueda semántica

---

## Índice de Documentación

### Documentación Principal

| # | Documento | Descripción |
|---|-----------|-------------|
| 1 | [Arquitectura](architecture.md) | Visión general del sistema, servicios, base de datos y comunicación |
| 2 | [API Reference](api.md) | Endpoints completos, modelos de datos, códigos de respuesta |
| 3 | [Base de Datos](database.md) | Esquema de tablas, modelos ORM, migraciones, índices |
| 4 | [Frontend](frontend.md) | Rutas, componentes, stores, API client, estilos |
| 5 | [Worker](worker.md) | Vault watcher, daily writer, tareas asíncronas |
| 6 | [AI Service](ai-service.md) | Embeddings, clasificación, RAG, Gemini |
| 7 | [Configuración](configuration.md) | Variables de entorno, archivos de config |
| 8 | [Gamificación](gamification.md) | XP, niveles, rachas, planta, milestones |
| 9 | [Desarrollo](development.md) | Guía para desarrolladores |
| 10 | [Troubleshooting](troubleshooting.md) | Errores comunes y soluciones |

### Guías y Referencias

| # | Documento | Descripción |
|---|-----------|-------------|
| 11 | [Accesibilidad](A11Y.md) | Criterios WCAG 2.1 AA, patrones a11y aplicados en el frontend |
| 12 | [Internacionalización](I18N.md) | Estado actual del i18n y estrategia para multi-idioma |
| 13 | [Guía de Estilo](STYLE_GUIDE.md) | Convenciones de código para frontend y backend |
| 14 | [Monitoring](MONITORING.md) | Métricas Prometheus, endpoint `/metrics`, Grafana |
| 15 | [Comunidad](COMMUNITY.md) | Canales de participación, contribuciones, código de conducta |
| 16 | [Real-Time & Security](realtime-security.md) | WebSockets, error handling, rate limiting, seguridad |

### Architecture Decision Records

| # | Documento | Descripción |
|---|-----------|-------------|
| 17 | [ADRs](adr/README.md) | Índice de Architecture Decision Records (0001–0006) |

---

## Quick Start

### Linux/Mac

```bash
make start
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

---

## Servicios

| Servicio | Puerto | Framework | Descripción |
|----------|--------|-----------|-------------|
| Frontend | 3000 | SvelteKit | Interfaz de usuario |
| API | 8000 | FastAPI | Backend REST |
| AI Service | 8002 | FastAPI | Embeddings y clasificación |
| Worker | 8001 | Python asyncio | Tareas background |

---

## Enlaces Útiles

| Recurso | URL |
|---------|-----|
| Web App | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| GitHub | https://github.com/Axel-DaMage/joidy |

---

## Comandos de Desarrollo

```bash
# Iniciar
make dev

# Logs
make logs

# Detener
make stop

# Reiniciar desde cero
make dev-reset

# Verificar DB
make db-health
```