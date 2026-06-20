# Joidy - Guía de Desarrollo

## Metadata

```yaml
for: Desarrolladores
requirements: Docker, Git, make (Linux/Mac) / PowerShell (Windows)
```

---

## 1. Primeros Pasos

### 1.1 Requisitos

| Requisito | Descripción |
|-----------|-------------|
| Docker | https://docs.docker.com/desktop/install/ |
| Docker Compose | Incluido en Docker Desktop |
| Git | `git --version` |
| make (Linux/Mac) | Incluido en sistemas Unix |
| PowerShell (Windows) | Incluido en Windows |

### 1.2 Clonar y Setup

```bash
# 1. Clonar repositorio
git clone https://github.com/Axel-DaMage/joidy.git
cd joidy

# 2. Setup inicial (copia .env)
make setup

# 3. Editar configuración
nano .env
#   - GEMINI_API_KEY (requerido para IA)
#   - OBSIDIAN_VAULT_PATH (ruta a tu vault)

# 4. Iniciar servicios
make dev
```

---

## 2. Estructura del Proyecto

```
joidy/
├── api/                    # Backend FastAPI
│   ├── main.py              # App FastAPI
│   ├── config.py           # Settings
│   ├── database.py          # DB setup
│   ├── routers/            # Endpoints REST
│   ├── services/           # Lógica de negocio
│   ├── models/             # ORM
│   ├── alembic/            # Migraciones
│   ├── tests/              # Tests unitarios
│   └── requirements.txt    # Dependencias
│
├── ai-service/             # Servicio de IA
│   ├── main.py
│   ├── config.py
│   ├── gemini_client.py
│   ├── database.py
│   ├── rate_limiter.py
│   └── cost_tracker.py
│
├── worker/                 # Tareas background
│   ├── main.py             # Entry point
│   ├── config.py
│   ├── watchers/
│   │   └── vault_watcher.py
│   └── tasks/
│       └── joidy_daily_writer.py
│
├── frontend/              # Frontend SvelteKit
│   ├── src/
│   │   ├── routes/
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   ├── stores/
│   │   │   └── api.ts
│   │   └── app.css
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                  # Documentación
├── data/                  # Datos (DB, uploads)
├── docker-compose.yml    # Definición de servicios
├── docker-compose.dev.yml # Overrides desarrollo
├── Makefile              # Comandos
├── start.ps1             # Script Windows
└── .env.example          # Plantilla configuración
```

---

## 3. Comandos de Desarrollo

### 3.1 Linux/Mac (Makefile)

| Comando | Descripción |
|---------|-------------|
| `make start` | Setup + iniciar servicios (interactivo) |
| `make dev` | Iniciar en modo desarrollo |
| `make dev-d` | Iniciar en background |
| `make dev-reset` | Reiniciar desde cero (borra datos) |
| `make stop` | Detener servicios |
| `make restart` | Reiniciar servicios |
| `make logs` | Ver todos los logs |
| `make logs-api` | Solo API |
| `make logs-ai` | Solo AI service |
| `make logs-worker` | Solo worker |
| `make shell-api` | Shell en contenedor API |
| `make shell-worker` | Shell en contenedor worker |
| `make migrate` | Ejecutar migraciones |
| `make db-health` | Verificar base de datos |
| `make test-api` | Ejecutar tests |
| `make build` | Rebuild imágenes |
| `make clean` | Limpiar contenedores |

### 3.2 Windows (PowerShell)

```powershell
# Quick start
powershell -ExecutionPolicy Bypass -File start.ps1

# Iniciar
docker compose up -d

# Ver logs
docker compose logs -f

# Detener
docker compose down

# Reiniciar desde cero
docker compose down --remove-orphans --volumes
docker compose up -d --build
```

---

## 4. Desarrollo de la API

### 4.1 Estructura

```
api/
├── main.py              # App FastAPI, middleware, CORS
├── config.py            # Pydantic Settings
├── database.py         # SQLAlchemy + sqlite-vec
├── routers/             # Endpoints
│   ├── notes.py        # CRUD notas
│   ├── tags.py         # Tags
│   ├── config.py       # Configuración
│   └── ...
├── services/           # Lógica de negocio
│   ├── gamification_engine.py
│   ├── tag_graph.py
│   └── ...
└── models/             # ORM
    ├── note.py
    └── ...
```

### 4.2 Agregar un Endpoint

**Paso 1: Crear router**

```python
# api/routers/myrouter.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/my-resource", tags=["my-resource"])

@router.get("/")
def list_resources():
    return [{"id": 1, "name": "resource1"}]

@router.get("/{resource_id}")
def get_resource(resource_id: int):
    return {"id": resource_id, "name": "resource"}

@router.post("/")
def create_resource(data: dict):
    return {"id": 42, **data}
```

**Paso 2: Registrar en main.py**

```python
# api/main.py
from routers import myrouter

app.include_router(myrouter.router)
```

---

### 4.3 Agregar un Modelo

**Paso 1: Crear modelo**

```python
# api/models/mymodel.py
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class MyModel(Base):
    __tablename__ = "my_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
```

**Paso 2: Crear migración**

```bash
docker compose exec api alembic revision -m "add my model"
```

**Paso 3: Editar migración**

```python
# alembic/versions/xxx_add_my_model.py
def upgrade():
    op.create_table('my_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
    )

def downgrade():
    op.drop_table('my_models')
```

**Paso 4: Aplicar**

```bash
make migrate
```

---

## 5. Desarrollo del Frontend

### 5.1 Estructura

```
frontend/src/
├── routes/              # File-based routing
│   ├── mypage/
│   │   ├── +page.svelte    # Página
│   │   └── +page.ts        # Datos (opcional)
├── lib/
│   ├── api.ts         # Cliente API
│   ├── components/    # Componentes
│   │   └── MyComponent.svelte
│   └── stores/        # Estado global
│       └── mystore.ts
└── app.css            # Estilos
```

### 5.2 Agregar una Página

```svelte
<!-- routes/mypage/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let data: any = null;

  onMount(async () => {
    data = await api.notes.list();
  });
</script>

<div>
  <h1>Mi Página</h1>
  {#if data}
    <p>Total notas: {data.length}</p>
  {/if}
</div>
```

### 5.3 Agregar un Store

```typescript
// lib/stores/mystore.ts
import { writable } from 'svelte/store';

interface MyState {
  count: number;
}

function createMyStore() {
  const { subscribe, set, update } = writable<MyState>({
    count: 0
  });

  return {
    subscribe,
    increment: () => update(s => ({ ...s, count: s.count + 1 })),
    reset: () => set({ count: 0 })
  };
}

export const myStore = createMyStore();
```

---

## 6. Desarrollo del Worker

### 6.1 Vault Watcher

Editar `worker/watchers/vault_watcher.py`:

```python
# Agregar lógica de procesamiento personalizado
async def process_file(self, path: str):
    # Tu código aquí
    pass
```

### 6.2 Daily Writer

Editar `worker/tasks/joidy_daily_writer.py`:

```python
# Personalizar contenido del resumen
async def generate_summary():
    # Tu código aquí
    pass
```

---

## 7. Testing

### 7.1 API Tests

```bash
# Todos los tests
make test-api

# Test específico
docker compose exec api python -m unittest tests.test_embedding_retry

# Tests disponibles:
# - test_embedding_retry.py
# - test_gamification_config.py
# - test_tag_graph_service.py
# - test_skill_tree_service.py
```

### 7.2 Frontend

```bash
cd frontend
npm run check   # TypeScript check
npm run build   # Build
```

---

## 8. Debugging

### 8.1 Ver Logs

```bash
# Todos
make logs

# Filtrar errores
make logs 2>&1 | grep -i error

# Específicos
make logs-api
make logs-ai
make logs-worker
```

### 8.2 Shell Interactivo

```bash
# API
make shell-api

# Worker
make shell-worker
```

### 8.3 Base de Datos

```bash
# Con SQLite CLI
sqlite3 data/db/joidy.db

# O con DBeaver/TablePlus
# Conectar a: ./data/db/joidy.db
```

---

## 9. Estilo de Código

### 9.1 Python

- **Variables:** `snake_case`
- **Funciones:** `snake_case` con type hints
- **Clases:** `PascalCase`
- **Docstrings:** En servicios y funciones públicas
- **Imports:** Ordenados lógicamente

```python
# Bien
def get_user(user_id: int) -> User | None:
    """Obtiene un usuario por ID."""
    return db.query(User).filter(User.id == user_id).first()

# Mal
def GetUser(id):
    return db.query(User).filter(User.id == id).first()
```

### 9.2 Svelte/TypeScript

- **Componentes:** `PascalCase.svelte`
- **Script:** `<script lang="ts">`
- **Props:** `export let propName: string`

```svelte
<!-- Bien -->
<script lang="ts">
  export let title: string;
  export let count: number = 0;
</script>

<h1>{title}</h1>
<p>Count: {count}</p>

<!-- Mal -->
<script>
  export let Title;
</script>

<h1>{Title}</h1>
```

---

## 10. Commands Reference

| Comando | Equivalente Docker |
|---------|-------------------|
| `make start` | `start.ps1` |
| `make dev` | `docker compose up` |
| `make stop` | `docker compose down` |
| `make logs` | `docker compose logs -f` |
| `make shell-api` | `docker compose exec api bash` |
| `make migrate` | `docker compose exec api alembic upgrade head` |

---

## 11. Tips

### 11.1 Hot Reload

El código fuente está montado como volumen:
- Frontend: `frontend/src` → `/app/src`
- API: `api` → `/app`
- Worker: `worker` → `/app`

Los cambios se reflejan automáticamente.

### 11.2 Verificar DB

```bash
make db-health
```

Muestra tablas y estado de migraciones.

### 11.3 Reset Completo

```bash
make dev-reset
```

Útil cuando hay problemas de estado.