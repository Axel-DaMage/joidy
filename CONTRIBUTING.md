# Guía de Contribución

¡Gracias por tu interés en contribuir a Joidy! Este documento te guiará a través del proceso.

## Índice

- [Código de Conducta](#código-de-conducta)
- [Cómo Empezar](#cómo-empezar)
- [Primeros Pasos para Contribuir](#primeros-pasos-para-contribuir)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Convenciones de Código](#convenciones-de-código)
- [Guías de Estilo](#guías-de-estilo)
- [Commits](#commits)
- [Testing](#testing)
- [Pull Requests](#pull-requests)
- [Reportar Bugs](#reportar-bugs)
- [Solicitar Funcionalidades](#solicitar-funcionalidades)
- [Ayuda](#ayuda)

---

## Código de Conducta

Este proyecto sigue un [Código de Conducta](CODE_OF_CONDUCT.md). Al participar, se espera que mantengas un ambiente respetuoso e inclusivo.

## Cómo Empezar

### 1. Fork & Clone

```bash
git clone https://github.com/tu-usuario/Joidy.git
cd Joidy
```

### 2. Configura tu entorno

```bash
cp .env.example .env
# Edita .env con tus claves (GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc.)
make dev
```

### 3. Crea una rama

```bash
git checkout -b feat/mi-nueva-funcionalidad
```

Usa prefijos descriptivos:

| Prefijo   | Ejemplo                          |
|-----------|----------------------------------|
| `feat/`   | `feat/tutorial-onboarding`       |
| `fix/`    | `fix/embedding-retry-logic`      |
| `refactor/` | `refactor/gamification-engine` |
| `docs/`   | `docs/api-authentication`        |
| `chore/`  | `chore/update-dependencies`      |

## Primeros Pasos para Contribuir

Si no sabes por dónde empezar, prueba con:

- **Good First Issues** — Tareas etiquetadas como [`good-first-issue`](https://github.com/d4mag3/Joidy/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-issue) — bugs pequeños, mejoras de documentación, tests
- **TODO.md** — Tareas pendientes listadas en el proyecto
- **AGENTS.md** — Notas detalladas de arquitectura y desarrollo

## Estructura del Proyecto

```
joidy/
├── api/              # FastAPI (Python 3.12)
│   ├── main.py       # App FastAPI
│   ├── config.py     # Configuración Pydantic
│   ├── database.py   # SQLAlchemy + sqlite-vec
│   ├── models/       # Modelos ORM
│   ├── routers/      # Endpoints API
│   ├── services/     # Lógica de negocio
│   ├── alembic/      # Migraciones
│   └── tests/        # Tests unitarios
├── frontend/          # SvelteKit + TypeScript
│   ├── src/
│   │   ├── routes/   # Páginas SvelteKit
│   │   └── lib/
│   │       ├── components/  # Componentes UI
│   │       ├── stores/      # Svelte stores
│   │       ├── api.ts       # Cliente API
│   │       └── utils/       # Utilidades
│   └── package.json
├── worker/            # Python asyncio
├── ai-service/        # FastAPI + Gemini
├── .github/           # Templates y CI
├── Makefile           # Comandos (Linux/Mac)
├── start.ps1          # Script (Windows)
└── docker-compose.yml
```

## Convenciones de Código

### Python (Backend)

- **Nombrado**: `snake_case` para variables y funciones, `PascalCase` para clases
- **Type hints**: Obligatorios en servicios y routers
- **Docstrings**: Requeridos en funciones públicas de servicios
- **Imports**: Orden: stdlib → third-party → local

```python
# Correcto
from typing import Optional
from fastapi import APIRouter
from sqlalchemy.orm import Session

from api.services.gamification_engine import process_event

router = APIRouter()
```

### TypeScript / Svelte (Frontend)

- **Nombrado**: `camelCase` para variables, `PascalCase` para componentes
- **TypeScript**: Preferir tipos explícitos sobre `any`
- **Componentes**: `<script lang="ts">`, estilos en `<style>`
- **Stores**: Nombrar como `camelCase` (ej: `notes`, `gamification`)

```svelte
<script lang="ts">
  import { notes } from '$lib/stores/notes';
  import type { Note } from '$lib/api';

  export let note: Note;
</script>

<Card>{note.title}</Card>
```

## Guías de Estilo

### Python

| Regla | Estándar |
|-------|----------|
| Máx. línea | 100 caracteres |
| Indentación | 4 espacios |
| Strings | Comillas dobles |
| Coma trailing | Obligatoria en tuplas/listas multi-línea |
| Linter | `make lint-api` |

### Frontend

| Regla | Estándar |
|-------|----------|
| Máx. línea | 100 caracteres |
| Indentación | 2 espacios |
| CSS | Variables CSS personalizadas, no inline styles |
| Typecheck | `npm run check` |

El proyecto usa `.editorconfig` para mantener consistencia. La mayoria de editores lo soportan nativamente o mediante plugin.

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <descripción corta>
```

Tipos: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `style:`

```bash
feat: add tutorial onboarding component
fix: resolve embedding retry infinite loop
docs: update API authentication docs
test: add gamification engine edge cases
```

**Reglas:**
- Un cambio lógico por commit
- Mensajes en presente imperativo ("add", no "added")
- No mezclar cambios de código con cambios de formato
- Para WIP usa `wip:` como prefijo y no hagas PR hasta que esté listo

## Testing

### Backend

```bash
make test-api
# Un solo test
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api \
  sh -c "PYTHONPATH=/app python -m unittest tests.test_embedding_retry"
```

### Frontend

```bash
cd frontend && npm run check   # svelte-check (tipos)
```

### Todos los tests

```bash
make test
```

**Directrices:**
- Escribe tests para código nuevo cuando sea práctico
- No rompas tests existentes
- Si arreglas un bug, considera añadir un test que lo cubra

## Pull Requests

### Antes de Abrir

1. Asegúrate de que tu fork está actualizado con `main`
2. Ejecuta los tests y verifica que pasen: `make test`
3. Verifica lint: `make lint`
4. Si tu cambio afecta la UI, incluye capturas (opcional pero útil)

### Proceso

1. Abre un Pull Request desde tu rama a `main`
2. Rellena el template describiendo:
   - Qué cambia y por qué
   - Qué issue resuelve (si aplica)
   - Cómo se probó
3. Un mantenedor revisará tu PR y puede pedir cambios
4. Una vez aprobado, se mergeará

### Consejos para una Revisión Rápida

- PRs pequeños y enfocados se revisan más rápido
- Explica el "por qué" detrás del cambio
- Responde a los comentarios de revisión
- Mantén el PR actualizado con `main`

## Reportar Bugs

Usa la [plantilla de bug report](https://github.com/d4mag3/Joidy/issues/new?template=bug_report.md).

Incluye siempre:

- Versión del SO y navegador
- Pasos para reproducir
- Comportamiento esperado vs real
- Logs o capturas si están disponibles

**Importante:** Para bugs de seguridad, no abras un issue público. Sigue la [política de seguridad](SECURITY.md).

## Solicitar Funcionalidades

Usa la [plantilla de feature request](https://github.com/d4mag3/Joidy/issues/new?template=feature_request.md) o abre una [discusión](https://github.com/d4mag3/Joidy/discussions) para ideas más abiertas.

## Reglas Importantes

1. **Nunca hagas commit de `.env`** — ya está en `.gitignore`
2. **Nunca hagas commit de `data/`** — ya está en `.gitignore`
3. **No incluyas API keys, tokens o secrets** en ningún archivo del repo
4. **Valida tipos** — ejecuta `npm run check` y `make test-api`
5. **Prueba localmente** — verifica que los servicios inicien antes del PR

## Ayuda

| Recurso | Dónde |
|---------|-------|
| Issues | [github.com/d4mag3/Joidy/issues](https://github.com/d4mag3/Joidy/issues) |
| Discusiones | [github.com/d4mag3/Joidy/discussions](https://github.com/d4mag3/Joidy/discussions) |
| AGENTS.md | Comandos de desarrollo y notas de arquitectura |
| TODO.md | Tareas pendientes |
| API Docs | http://localhost:8000/docs (servicio corriendo) |
| Email | d4mag3@duck.com |
