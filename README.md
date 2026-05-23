# Joidy

> Tu sistema personal de gestión del conocimiento con gamificación.

Joidy es un monorepo Docker que combina:
- **Frontend** — Interfaz web construída con SvelteKit
- **API** — Backend REST con FastAPI
- **AI Service** — Embeddings y clasificación con Gemini
- **Worker** — Tareas en background (sincronización con Obsidian, resúmenes diarios)

---

## 🚀 Quick Start

### Linux / macOS

```bash
# Un comando lo hace todo:
make start
```

### Windows

```powershell
# En PowerShell:
powershell -ExecutionPolicy Bypass -File start.ps1
```

Esto akaná:
1. Crear directorios necesarios
2. Configurar `.env` interactivamente
3. Iniciar todos los servicios

---

## Prerrequisitos

| Requisito | Notas |
|-----------|-------|
| **Docker** | [Instalar Docker Desktop](https://docs.docker.com/desktop/install/) |
| **Docker Compose** | Incluido en Docker Desktop |

Verifica tu setup con:
- **Linux/Mac:** `make doctor`
- **Windows:** `.\start.ps1 -Check` (pronto)

---

## Configuración

### Variables Obligatorias

Edita el archivo `.env` después de ejecutar el setup:

| Variable | Descripción | Cómo obtenerla |
|----------|-------------|----------------|
| `GEMINI_API_KEY` | Clave para IA | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `OBSIDIAN_VAULT_PATH` | Ruta absoluta a tu bóveda de Obsidian | Ej: `/home/tu usuario/Documents/Obsidian` |
| `SECRET_KEY` | Clave de sesión (se genera automáticamente) | Se genera en primer setup |

### Variables Opcionales

```env
# GitHub (sincronización)
GITHUB_TOKEN=
GITHUB_USERNAME=

# Telegram (notificaciones)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
```

---

## Comandos

### Linux / macOS (Makefile)

| Comando | Descripción |
|---------|-------------|
| `make start` | Setup + iniciar servicios (modo interactivo) |
| `make doctor` | Verificar que todo esté configurado correctamente |
| `make dev` | Iniciar servicios en modo desarrollo |
| `make stop` | Detener todos los servicios |
| `make logs` | Ver logs en tiempo real |
| `make dev-reset` | Reiniciar todo desde cero |

### Windows (PowerShell)

| Script | Descripción |
|--------|-------------|
| `.\start.ps1` | Quick start interactivo |
| `docker compose up -d` | Iniciar servicios |
| `docker compose down` | Detener servicios |

---

## Acceso a la App

Una vez iniciados los servicios:

| Servicio | URL |
|----------|-----|
| **Web App** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **AI Service** | http://localhost:8002 |

---

## Solución de Problemas

### "Docker not found"
 Asegúrate de tener Docker Desktop instalado y ejecutándose.

### "Port already in use"
Edita `.env` para cambiar los puertos:
```env
FRONTEND_PORT=3001
API_PORT=8001
```

### La base de datos no inicia
Ejecuta las migraciones:
```bash
make migrate
```

### Verificar estado de servicios
```bash
make db-health
```

---

## Estructura del Proyecto

```
.
├── api/              # FastAPI backend
├── ai-service/       # Servicio de IA (Gemini)
├── worker/           # Tareas background
├── frontend/         # SvelteKit web app
├── data/             # Datos (DB, uploads, vault)
├── docker-compose.yml
├── Makefile          # Comandos (Linux/Mac)
├── start.ps1         # Script (Windows)
└── .env              # Configuración (no commits)
```

---

## 🎖️ Calidad de Código

El proyecto Joidy mantiene una arquitectura robusta de microservicios. A continuación se presenta un análisis honesto y riguroso de la calidad del código, categorizado por áreas utilizando el sistema de grados (SSS, S, A, B, C, F):

### 🛡️ Seguridad — Grado: C (Mejorable)
*   **Puntos Fuertes:** Implementación de utilidades globales de sanitización XSS (`sanitizer.py`) en notas y middleware de Rate Limiting global limitado a 60 req/min.
*   **Debilidades Críticas:** **El sistema de autenticación JWT (`auth_service.py` / `routers/auth.py`) está completamente implementado pero no está integrado ni enforced en ningún endpoint de la API.** Cualquiera puede interactuar con el backend sin credenciales. Adicionalmente, CORS está configurado con comodín (`*`) por defecto en entornos que no sean estrictamente de producción.

### 🌐 DevOps e Infraestructura — Grado: S (Excelente)
*   **Puntos Fuertes:** Orquestación impecable mediante Docker Compose con perfiles de desarrollo independientes. Inicialización interactiva mediante `Makefile` y `start.ps1` que detectan variables de entorno faltantes de forma amigable. Scripts automatizados para la realización de copias de seguridad de base de datos (`backup.py`) y endpoints integrados de salud y métricas `/health/ready` cruzados listos para producción.

### 🧠 Servicio de IA (AI & RAG) — Grado: S (Excelente)
*   **Puntos Fuertes:** Estructura desacoplada y escalable bajo un patrón Factory (`ClientFactory`) con soporte nativo para 6 proveedores (Gemini, OpenAI, Anthropic, Cohere, Ollama, OpenRouter). Robustez extrema con reintentos automáticos ante rate-limits y cola de fallos con backoff exponencial. Búsqueda semántica (RAG) integrada con base de datos vectorial de alto rendimiento local (`sqlite-vec`).
*   **Optimización Reciente:** Se ha eliminado código heredado obsoleto (`gemini_client.py`) y se ha unificado la lógica de clasificación y parseo de JSON en la clase abstracta base `BaseLLMClient`, eliminando redundancia en todos los conectores.

### ⚙️ Backend (API y Lógica) — Grado: A (Muy Alto)
*   **Puntos Fuertes:** Arquitectura orientada a servicios limpia. Los controladores (`routers`) únicamente parsean esquemas Pydantic y delegan el flujo de negocio completo a la capa de servicios (`services/`). Motor de gamificación altamente estructurado que procesa eventos de XP, cálculo de rachas diarias y lógica avanzada de fallas (Rollover y Snowball) en los objetivos.
*   **Debilidades:** Duplicidad menor en validaciones personalizadas de esquemas Pydantic y la persistencia actual en SQLite (lo que requiere una futura migración a PostgreSQL/pgvector para escenarios distribuidos reales).

### 🎨 Frontend (Interfaz y UX) — Grado: A (Muy Alto)
*   **Puntos Fuertes:** Interfaz web premium construida con SvelteKit y TypeScript. Estructuración consistente de stores reactivas globales, transiciones fluidas de color (Dark/Light mode manual persistente) y componentes complejos e independientes de alta usabilidad (Pomodoro, StreakHeatmap, widgets de tiempo, tutorial interactivo con onboarding).
*   **Debilidades:** Requiere culminar la migración progresiva del estado reactivo clásico de Svelte 4 a runas nativas de Svelte 5 (`$state`, `$effect`) en los widgets más pesados, e implementar control de foco ("focus trapping") en modales avanzados.

### 🔄 Worker (Procesos en Background) — Grado: A (Muy Alto)
*   **Puntos Fuertes:** Monitoreo y watcher asíncrono debilitado en 2 segundos (`watchfiles`) para prevenir lecturas parciales durante la edición interactiva en Obsidian. Flush reactivo de la cola de eventos y generación automatizada del resumen del diario directamente en formato Markdown en el vault del usuario.

---

## Licencia

MIT