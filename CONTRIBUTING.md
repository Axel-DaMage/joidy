# Guía de Contribución - Joidy

## Introducción

Gracias por tu interés en contribuir a Joidy. Este documento establece las convenciones y estándares del proyecto.

## Estructura del Proyecto

```
joidy/
├── api/              # FastAPI (Python 3.12)
│   ├── main.py      # App FastAPI
│   ├── config.py    # Configuración Pydantic
│   ├── database.py  # SQLAlchemy + sqlite-vec
│   ├── models/      # Modelos ORM
│   ├── routers/     # Endpoints API
│   ├── services/    # Lógica de negocio
│   ├── alembic/     # Migraciones
│   └── tests/       # Tests unitarios
├── frontend/         # SvelteKit + TypeScript
│   ├── src/
│   │   ├── routes/  # Páginas SvelteKit
│   │   └── lib/
│   │       ├── components/  # Componentes UI
│   │       ├── stores/       # Svelte stores
│   │       ├── api.ts        # Cliente API
│   │       └── utils/        # Utilidades
│   └── package.json
├── worker/           # Python asyncio
└── ai-service/       # FastAPI + Gemini
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

- **Nombrado**: `camelCase` variables, `PascalCase` componentes
- **TypeScript**: Preferir tipos explícitos sobre `any`
- **Componentes**: `<script lang="ts">`, estilo en `<style>`
- **Stores**: Nombrar como `camelCase` (ej: `notes`, `gamification`)

```svelte
<script lang="ts">
  import { notes } from '$lib/stores/notes';
  import type { Note } from '$lib/api';

  export let note: Note;
</script>

<Card>{note.title}</Card>
```

## Reglas de Estilo

### Python

- 100 caracteres máximo por línea
- 4 espacios para indentación (no tabs)
- 双 comillas para strings
- coma trailing en últimos elementos

### Frontend

- 100 caracteres máximo por línea
- 2 espacios para indentación
- CSS: variables CSS personalizadas, no inline styles

## Patrones de Arquitectura

### Backend: Routers → Services → Models

```
routers/notes.py → services/note_service.py → models/note.py
```

- **Routers**: endpoints HTTP, validación Pydantic
- **Services**: lógica de negocio, acceso a DB
- **Models**: esquemas SQLAlchemy

### Frontend: Stores + Componentes

- **Stores**: estado reactivo (writable/derived)
- **Componentes**: UI reusable, reciben props
- **API Client**: wrapper alrededor de fetch

## Commits

- Prefijos: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Mensajes claros y descriptivos
- Un cambio por commit cuando sea posible

```
feat: add tutorial onboarding component
fix: resolve embedding retry logic
docs: update API documentation
```

## Testing

### Backend

```bash
make test-api
# Un solo test
docker compose run --rm api sh -c "PYTHONPATH=/app python -m unittest tests.test_name"
```

### Frontend

```bash
cd frontend && npm run check  # svelte-check (tipos)
```

## Configuración de Desarrollo

```bash
make setup           # Primera vez: copiar .env
make dev             # Iniciar servicios
make logs            # Ver logs
make shell-api       # Entrar al contenedor API
```

## Reglas Importantes

1. **Nunca hacer commit de `.env`** — ya está en `.gitignore`
2. **Nunca hacer commit de `data/`** — ya está en `.gitignore`
3. **Validar tipos** — ejecutar `npm run check` y `make test-api`
4. **Probar locally** — verificar que los servicios inicien antes de push

## 获取 Ayuda

- Revisa `AGENTS.md` para comandos de desarrollo
- Revisa `TODO.md` para tareas pendientes
- Consulta la API docs en `http://localhost:8000/docs`