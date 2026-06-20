# Joidy - Solución de Problemas

## Metadata

```yaml
last_updated: 2024
version: 1.0
```

---

## 1. Problemas de Inicio

### 1.1 Docker Not Found

**Síntoma:**
```
bash: docker: command not found
```

**Causa:** Docker no está instalado o no está en PATH.

**Solución:**

1. **Instalar Docker Desktop:**
   - macOS: https://docs.docker.com/desktop/install/mac-install/
   - Windows: https://docs.docker.com/desktop/install/windows-install/
   - Linux: https://docs.docker.com/engine/install/

2. **Verificar instalación:**
   ```bash
   docker --version
   docker compose version
   ```

3. **Reiniciar terminal** después de instalar.

---

### 1.2 Port Already in Use

**Síntoma:**
```
Error response from daemon: port is already allocated
```

**Causa:** Otro servicio está usando el puerto.

**Solución:**

Editar `.env` y cambiar los puertos:

```env
FRONTEND_PORT=3001
API_PORT=8001
AI_SERVICE_PORT=8003
WORKER_PORT=8002
```

Luego reiniciar:
```bash
make dev-reset
```

---

### 1.3 .env File Not Found

**Síntoma:**
```
Error: .env file not found
```

**Causa:** El archivo `.env` no existe.

**Solución:**

```bash
make setup
```

Esto copia `.env.example` a `.env`.

---

### 1.4 OBSIDIAN_VAULT_PATH Not Set

**Síntoma:**
```
⚠ OBSIDIAN_VAULT_PATH not set in .env
```

**Causa:** La ruta del vault no está configurada.

**Solución:**

1. Editar `.env`:
   ```env
   OBSIDIAN_VAULT_PATH=/home/usuario/Documents/Obsidian
   ```

2. O usar el setup interactivo:
   ```bash
   make start  # Linux/Mac
   start.ps1   # Windows
   ```

---

---

## 2. Problemas de la API

### 2.1 Service 'api' Failed to Start

**Síntoma:**
```
api_1  | Error: Service failed to start
```

**Causa:** Error en la base de datos o migraciones.

**Solución:**

1. Ver logs:
   ```bash
   make logs-api
   ```

2. Verificar DB:
   ```bash
   make db-health
   ```

3. Reconstruir desde cero:
   ```bash
   make dev-reset
   ```

---

### 2.2 GEMINI_API_KEY Not Configured

**Síntoma:**
```
⚠ GEMINI_API_KEY not set in .env
```

**Causa:** Falta la API key de Gemini.

**Solución:**

1. Obtener key: https://aistudio.google.com/app/apikey
2. Editar `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```
3. Reiniciar:
   ```bash
   make dev-reset
   ```

---

### 2.3 Database Locked

**Síntoma:**
```
database is locked
```

**Causa:** Múltiples procesos escribiendo simultáneamente.

**Solución:**

```bash
make stop
make dev-d
```

El código ya usa WAL mode para minimizar bloqueos.

---

### 2.4 Migrations Not Applied

**Síntoma:**
```
Table 'table_name' doesn't exist
```

**Causa:** Migraciones no se ejecutaron.

**Solución:**

```bash
make migrate
```

O verificar estado:
```bash
make db-health
```

---

### 2.5 Health Check Failed

**Síntoma:**
```
healthcheck failed
```

**Causa:** La API no responde al health check.

**Solución:**

```bash
# Verificar manualmente
curl http://localhost:8000/health

# Ver logs
make logs-api
```

---

---

## 3. Problemas del Frontend

### 3.1 Cannot Connect to API

**Síntoma:**
```
Failed to fetch
NetworkError
```

**Causa:** El frontend no puede comunicarse con la API.

**Solución:**

1. Verificar que la API esté corriendo:
   ```bash
   make logs-api
   ```

2. Verificar VITE_API_URL:
   ```bash
   echo $VITE_API_URL
   # Debe ser: http://localhost:8000
   ```

3. Reiniciar servicios:
   ```bash
   make dev-reset
   ```

---

### 3.2 Module Not Found

**Síntoma:**
```
Cannot find module './lib/...'
```

**Causa:** Dependencias no instaladas.

**Solución:**

```bash
cd frontend
npm install
```

---

### 3.3 TypeScript Errors

**Síntoma:**
```
Type error: ...
```

**Solución:**

```bash
cd frontend
npm run check
```

---

---

## 4. Problemas del Worker

### 4.1 Vault Path Does Not Exist

**Síntoma:**
```
FileNotFoundError: /vault
```

**Causa:** La ruta del vault en OBSIDIAN_VAULT_PATH es inválida.

**Solución:**

1. Verificar que el path exista:
   ```bash
   ls -la /path/to/vault
   ```

2. Usar ruta absoluta (no relativa):
   ```env
   OBSIDIAN_VAULT_PATH=/home/user/Documents/Obsidian
   ```

3. Actualizar `.env` y reiniciar:
   ```bash
   make dev-reset
   ```

---

### 4.2 Permission Denied on Vault

**Síntoma:**
```
PermissionError: [Errno 13] Permission denied
```

**Causa:** El worker no tiene permisos de lectura.

**Solución:**

```bash
# Linux: dar permisos
chmod -R 755 /path/to/vault

# O cambiar owner
sudo chown -R $USER:$USER /path/to/vault
```

---

### 4.3 Notes Not Syncing

**Síntoma:** Notas de Obsidian no aparecen en Joidy.

**Solución:**

1. Verificar worker logs:
   ```bash
   make logs-worker
   ```

2. Verificar vault mount:
   ```bash
   docker compose exec worker ls -la /vault
   ```

3. Forzar sync manual:
   ```bash
   curl -X POST http://localhost:8000/vault/sync
   ```

---

---

## 5. Problemas del AI Service

### 5.1 Rate Limit Exceeded

**Síntoma:**
```
429 Too Many Requests
Rate limit exceeded
```

**Causa:** Demasiadas requests a la API de Gemini.

**Solución:**

1. Esperar un minuto
2. Reducir uso de clasificación automática
3. Ver detalles:
   ```bash
   make logs-ai
   ```

---

### 5.2 Invalid API Key

**Síntoma:**
```
400 Bad Request
Invalid API key
```

**Causa:** La API key de Gemini es inválida o está revocada.

**Solución:**

1. Verificar en Google AI Studio: https://aistudio.google.com/
2. Si está revocada, crear nueva
3. Actualizar `.env`:
   ```env
   GEMINI_API_KEY=NuevaKey
   ```
4. Reiniciar:
   ```bash
   make dev-reset
   ```

---

### 5.3 AI Service Unreachable

**Síntoma:**
```
Connection refused to ai-service:8002
```

**Solución:**

```bash
make logs-ai
# Verificar que el servicio esté corriendo
```

---

---

## 6. Problemas de Base de Datos

### 6.1 Table Not Found

**Síntoma:**
```
sqlite3.OperationalError: no such table: table_name
```

**Causa:** Migraciones no aplicadas o base corrupta.

**Solución:**

```bash
make migrate
make db-health
```

O reconstruir (borra datos):
```bash
make dev-reset
```

---

### 6.2 Integrity Constraint Failed

**Síntoma:**
```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**Causa:** Violación de foreign key.

**Solución:**

El código usa CASCADE deletes. Esto no debería ocurrir. Reportar como bug con logs.

---

### 6.3 Database Corrupted

**Síntoma:**
```
database disk image is malformed
```

**Solución:**

1. Backup:
   ```bash
   cp data/db/joidy.db data/db/joidy.db.backup
   ```

2. Eliminar y recrear:
   ```bash
   rm data/db/joidy.db
   make dev-reset
   ```

3. Restaurar si hay backup:
   ```bash
   # Restaurar desde backup
   ```

---

---

## 7. Comandos de Diagnóstico

### 7.1 Verificar Salud de Servicios

```bash
# API
curl http://localhost:8000/health

# Verificar DB
make db-health
```

### 7.2 Ver Logs

```bash
# Todos los servicios
make logs

# Solo errores
make logs 2>&1 | grep -i error

# Específicos
make logs-api
make logs-ai
make logs-worker
```

### 7.3 Reiniciar Desde Cero

```bash
make dev-reset
```

---

---

## 8. Información para Bugs

Al reportar un problema, incluir:

1. **Sistema operativo:** `uname -a`
2. **Docker:** `docker --version` y `docker compose version`
3. **Output de logs:** `make logs`
4. **Contenido de .env** (sin claves sensibles):
   ```bash
   cat .env | grep -v KEY
   ```
5. **Pasos para reproducir**
6. **Comportamiento esperado vs actual**

---

---

## 9. Quick Fixes

### 9.1 Reset Completo

```bash
make dev-reset
```

### 9.2 Solo API

```bash
docker compose restart api
```

### 9.3 Solo Frontend

```bash
docker compose restart frontend
```

### 9.4 Verificar Puertos

```bash
lsof -i :3000 -i :8000 -i :8001 -i :8002
```