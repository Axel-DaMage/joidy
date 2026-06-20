# Joidy - Worker

## Metadata

```yaml
framework: Python asyncio
port: 8001
language: Python 3.12
tasks: vault_watcher, daily_writer
```

---

## 1. Resumen

El Worker es un servicio Python asíncrono que ejecuta tareas en background, independientemente de las requests HTTP. Su función principal es monitorear el vault de Obsidian y escribir resúmenes diarios.

---

## 2. Estructura

```
worker/
├── main.py                 # Entry point con TaskGroup
├── config.py               # Pydantic Settings
├── logging_config.py       # Configuración de logs
├── watchers/
│   ├── __init__.py
│   └── vault_watcher.py    # Observador del vault
└── tasks/
    ├── __init__.py
    └── joidy_daily_writer.py # Escritor de resúmenes
```

---

## 3. Entry Point

### 3.1 main.py

```python
import asyncio
from watchers.vault_watcher import watch_vault
from tasks.joidy_daily_writer import schedule_daily_writes

async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(watch_vault())
        tg.create_task(schedule_daily_writes())

if __name__ == "__main__":
    asyncio.run(main())
```

**Características:**
- Usa `asyncio.TaskGroup` para ejecutar tareas concurrentemente
- Ambas tareas corren indefinidamente
- Ctrl+C graceful shutdown

---

## 4. Vault Watcher

### 4.1 Propósito

Monitorea cambios en el vault de Obsidian y sincroniza automáticamente notas nuevas o modificadas.

### 4.2 Ubicación

`worker/watchers/vault_watcher.py`

### 4.3 Configuración

```python
# worker/config.py
vault_path: str = "/vault"
```

El vault se monta via Docker volume:
```yaml
worker:
  volumes:
    - ${OBSIDIAN_VAULT_PATH}:/vault
```

### 4.4 Lógica

```python
async def watch_vault():
    # Usar watchdog o polling
    event_handler = VaultEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path="/vault", recursive=True)
    observer.start()

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        observer.stop()
```

### 4.5 Event Handler

```python
class VaultEventHandler(FileSystemEventHandler):
    def __init__(self):
        self.pending = {}  # path -> debounce_timer

    def on_modified(self, event):
        if event.is_directory: return
        if not event.src_path.endswith('.md'): return

        # Debounce 2 segundos
        if event.src_path in self.pending:
            self.pending[event.src_path].cancel()

        self.pending[event.src_path] = asyncio.create_task(
            self.debounced_process(event.src_path)
        )

    async def debounced_process(self, path):
        await asyncio.sleep(2)  # Debounce

        # Calcular hash para detectar cambios reales
        hash = calculate_file_hash(path)

        # Enviar a API
        await sync_to_api(path, hash)
```

### 4.6 Detalles del Procesamiento

| Paso | Descripción |
|------|-------------|
| 1. Detectar cambio | on_modified event en archivo .md |
| 2. Debounce | 2 segundos para evitar procesos múltiples |
| 3. Hash | Calcular SHA256 del archivo |
| 4. Comparar | Verificar si cambió desde último sync |
| 5. Leer contenido | Leer archivo markdown |
| 6. Enviar a API | POST /vault/sync con contenido |
| 7. Actualizar cache | Guardar hash para próxima comparación |

### 4.7 Logging

```python
logger.info(f"[vault_watcher] Processing: {path}")
logger.info(f"[vault_watcher] Debouncing 2s: {filename}")
logger.info(f"[vault_watcher] Sending to API: {path} (hash: {hash})")
logger.info(f"[vault_watcher] Note saved via API: id={note_id}")
```

---

## 5. Daily Writer

### 5.1 Propósito

Escribe resúmenes diarios en el vault de Joidy.

### 5.2 Ubicación

`worker/tasks/joidy_daily_writer.py`

### 5.3 Ubicación del Archivo

```
vault/_joidy/daily/YYYY-MM-DD.md
```

(Según configuración `writeInObsidian` del usuario)

### 5.4 Contenido del Resumen

```markdown
# Resumen Diario - 2024-01-15

## Notas Creadas
- [[Nota 1]]
- [[Nota 2]]

## Notas Modificadas
- [[Nota 3]]
- [[Nota 4]]

## Estadísticas
- XP gained: +45
- Current streak: 7 days
- Plant stage: Sprout

## Objetivos
- ✅ Objetivo 1
- ⏳ Objetivo 2 (progress: 3/5)

## Rachas
- 📚 Lectura: 15 days
- 🏃 Ejercicio: 3 days (streak broken)
```

### 5.5 Programación

```python
async def schedule_daily_writes():
    while True:
        now = datetime.now()
        # Ejecutar a las 20:00 cada día
        next_run = now.replace(hour=20, minute=0, second=0)
        if now > next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        await write_daily_summary()
```

---

## 6. Comunicación con API

### 6.1 Cliente HTTP

```python
import httpx

async def sync_to_api(path: str, content: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.api_url}/vault/sync",
            json={
                "source_path": path,
                "content": content
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

### 6.2 Retry Logic

```python
MAX_RETRIES = 3

async def sync_to_api_with_retry(path: str, content: str):
    for attempt in range(MAX_RETRIES):
        try:
            return await sync_to_api(path, content)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## 7. Configuración

### 7.1 Variables de Entorno

```python
# worker/config.py
database_url: str = "sqlite:////data/db/joidy.db"
api_url: str = "http://api:8000"
ai_service_url: str = "http://ai-service:8002"
vault_path: str = "/vault"
app_env: str = "development"
python_unbuffered: str = "1"
```

### 7.2 Docker Compose

```yaml
worker:
  build:
    context: ./worker
    dockerfile: Dockerfile
  volumes:
    - ./data/db:/data/db
    - ${OBSIDIAN_VAULT_PATH}:/vault
  environment:
    - DATABASE_URL=sqlite:////data/db/joidy.db
    - API_URL=http://api:8000
    - AI_SERVICE_URL=http://ai-service:8002
    - VAULT_PATH=/vault
  depends_on:
    api:
      condition: service_healthy
```

---

## 8. Errores y Manejo

### 8.1 Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| Vault path not found | Ruta inválida | Verificar OBSIDIAN_VAULT_PATH |
| Permission denied | Sin permisos de lectura | chmod 755 en el directorio |
| API unreachable | API abajo | Ver logs de API |
| Hash mismatch | Archivo corrupto | Re-intentar sync |

### 8.2 Logging

```python
logger = logging.getLogger(__name__)

# Niveles:
logger.debug()  # Información detallada
logger.info()   # Eventos normales
logger.warning()# Advertencias
logger.error()  # Errores
logger.exception()  # Errores con traceback
```

---

## 9. Desarrollo

### 9.1 Shell en Worker

```bash
make shell-worker
```

### 9.2 Logs

```bash
make logs-worker
```

### 9.3 Restart

```bash
make dev-reset
```

---

## 10. Consideraciones

### 10.1 Permisos

- El worker tiene acceso de **lectura** al vault original
- Escribe en `_joidy/daily/` del vault (si `writeInObsidian` habilitado)
- **No modifica** notas existentes del usuario

### 10.2 Performance

- Debounce evita procesar el mismo archivo múltiples veces
- Hash-based change detection previene re-sync innecesario
- Async I/O para no bloquear el proceso

### 10.3 Limitaciones

- Solo procesa archivos `.md`
- No detecta archivos eliminados (solo modifica)
- Requiere API disponible para sincronizar