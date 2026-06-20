# Joidy

> Tu sistema personal de gestion del conocimiento con gamificacion.

[![CI](https://github.com/d4mag3/Joidy/actions/workflows/ci.yml/badge.svg)](https://github.com/d4mag3/Joidy/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-Svelte-ff3e00.svg)](https://kit.svelte.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

Joidy es un monorepo Docker que combina:

- **Frontend** — Interfaz web construida con SvelteKit
- **API** — Backend REST con FastAPI
- **AI Service** — Embeddings y clasificacion con Gemini
- **Worker** — Tareas en background (sincronizacion con Obsidian, resumenes diarios)

---

## Quick Start

### Linux / macOS

```bash
make start
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

Esto creara los directorios necesarios, configurara `.env` interactivamente e iniciara todos los servicios.

---

## Prerrequisitos

| Requisito | Notas |
|-----------|-------|
| **Docker** | [Instalar Docker Desktop](https://docs.docker.com/desktop/install/) |
| **Docker Compose** | Incluido en Docker Desktop |

Verifica tu setup con:

- **Linux/Mac:** `make doctor`
- **Windows:** `.\start.ps1 -Check`

---

## Configuracion

### Variables Obligatorias

Edita el archivo `.env` despues de ejecutar el setup:

| Variable | Descripcion | Como obtenerla |
|----------|-------------|----------------|
| `GEMINI_API_KEY` | Clave para IA | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `OBSIDIAN_VAULT_PATH` | Ruta absoluta a tu boveda de Obsidian | Ej: `/home/usuario/Documents/Obsidian` |
| `SECRET_KEY` | Clave de sesion (se genera automaticamente) | Se genera en primer setup |

### Variables Opcionales

```env
# GitHub (sincronizacion)
GITHUB_TOKEN=
GITHUB_USERNAME=

# Telegram (notificaciones)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
```

---

## Comandos

### Linux / macOS (Makefile)

| Comando | Descripcion |
|---------|-------------|
| `make start` | Setup + iniciar servicios (modo interactivo) |
| `make doctor` | Verificar que todo este configurado correctamente |
| `make dev` | Iniciar servicios en modo desarrollo |
| `make stop` | Detener todos los servicios |
| `make logs` | Ver logs en tiempo real |
| `make dev-reset` | Reiniciar todo desde cero |
| `make test` | Ejecutar todos los tests |
| `make migrate` | Ejecutar migraciones de base de datos |

### Windows (PowerShell)

| Script | Descripcion |
|--------|-------------|
| `.\start.ps1` | Quick start interactivo |
| `docker compose up -d` | Iniciar servicios |
| `docker compose down` | Detener servicios |

---

## Acceso a la App

| Servicio | URL |
|----------|-----|
| **Web App** | http://localhost:3000 |
| **API Docs** | http://localhost:8000/docs |
| **AI Service** | http://localhost:8002 |

---

## Solucion de Problemas

### "Docker not found"
Asegurate de tener Docker Desktop instalado y ejecutandose.

### "Port already in use"
Edita `.env` para cambiar los puertos:

```env
FRONTEND_PORT=3001
API_PORT=8001
```

### "La base de datos no inicia"
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
└── .env              # Configuracion (no commits)
```

---

## Contribuir

Las contribuciones son bienvenidas. Revisa la [Guia de Contribucion](CONTRIBUTING.md) para detalles sobre el flujo de trabajo, estandares de codigo y proceso de PR.

Busca issues etiquetados como [`good-first-issue`](https://github.com/d4mag3/Joidy/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-issue) para empezar.

---

## Licencia

Distribuido bajo **GNU General Public License v3.0**. Ver [LICENSE](LICENSE) para mas informacion.

---

Creado por [D4MAG3_WIZ4RD](https://github.com/d4mag3). Gracias a todos los [contribuyentes](https://github.com/d4mag3/Joidy/graphs/contributors) y a la comunidad [HackTheWorld-Team](https://github.com/HackTheWorld-Team).
