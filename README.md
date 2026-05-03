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

## Licencia

MIT