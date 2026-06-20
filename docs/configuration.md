# Joidy - Configuración

## Metadata

```yaml
config_files:
  - .env (root)
  - api/config.py
  - ai-service/config.py
  - worker/config.py
config_method: Environment variables + Pydantic Settings
```

---

## 1. Archivo .env

### 1.1 Ubicación

El archivo `.env` debe estar en la raíz del proyecto:

```
joidy/
├── .env              # ← Este archivo
├── api/
├── ai-service/
├── worker/
├── frontend/
└── docker-compose.yml
```

### 1.2 Generación

```bash
# Linux/Mac
make setup

# Windows
powershell -ExecutionPolicy Bypass -File start.ps1
```

Esto copia `.env.example` a `.env`.

### 1.3 Variables Disponibles

```env
# ═══════════════════════════════════════════════════════════
# Joidy - Environment Variables
# ═══════════════════════════════════════════════════════════

# ── AI ─────────────────────────────────────────────────────
# Obtén tu clave gratis en: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# ── Obsidian Vault ─────────────────────────────────────────
# Ruta absoluta a tu bóveda de Obsidian
# Ejemplos:
#   Linux:   /home/username/Documents/Obsidian
#   macOS:   /Users/username/Documents/Obsidian
#   Windows:  C:\Users\username\Documents\Obsidian
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault

# ── GitHub OAuth (Device Flow) ────────────────────────────
# Obtén en: https://github.com/settings/developers
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_OAUTH_WEB_URL=

# ── GitHub PAT (legacy) ───────────────────────────────────
GITHUB_TOKEN=
GITHUB_USERNAME=
GITHUB_WEBHOOK_URL=

# ── Telegram Bot (opcional) ───────────────────────────────
# Crea con @BotFather en Telegram
TELEGRAM_BOT_TOKEN=
# Obtén tu ID de @userinfobot
TELEGRAM_ALLOWED_USER_ID=

# ── Aplicación ───────────────────────────────────────────
# Clave para firmar sesiones (se genera automáticamente)
SECRET_KEY=change_this_to_a_random_secret_key
APP_ENV=development

# ── Puertos (cambiar si hay conflictos) ──────────────────
FRONTEND_PORT=3000
API_PORT=8000
AI_SERVICE_PORT=8002
WORKER_PORT=8001
```

---

## 2. Variables Detalladas

### 2.1 AI

| Variable | Requerido | Tipo | Descripción |
|----------|-----------|------|-------------|
| GEMINI_API_KEY | No* | string | API key de Google Gemini |

*Sin esta clave, las funciones de IA (embeddings, clasificación, RAG) no estarán disponibles, pero la app funcionará normalmente.

**Obtención:**
1. Ir a [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Crear nueva API key
3. Copiar a `.env`

---

### 2.2 Obsidian Vault

| Variable | Requerido | Tipo | Descripción |
|----------|-----------|------|-------------|
| OBSIDIAN_VAULT_PATH | Sí | string | Ruta absoluta al vault |

**Ejemplos de rutas:**

| OS | Ejemplo |
|----|---------|
| Linux | `/home/username/Documents/Obsidian` |
| macOS | `/Users/username/Documents/Obsidian` |
| Windows | `C:\Users\username\Documents\Obsidian` |

**Importante:**
- Debe ser una ruta absoluta, no relativa
- El directorio debe existir
- El worker necesita permisos de lectura

---

### 2.3 GitHub

| Variable | Requerido | Tipo | Descripción |
|----------|-----------|------|-------------|
| GITHUB_CLIENT_ID | No | string | Client ID de OAuth App |
| GITHUB_CLIENT_SECRET | No | string | Client Secret de OAuth App |
| GITHUB_OAUTH_WEB_URL | No | string | Redirect URL para web flow |
| GITHUB_TOKEN | No | string | Personal Access Token |
| GITHUB_USERNAME | No | string | Tu username |
| GITHUB_WEBHOOK_URL | No | string | URL para webhooks |

**Obtención de OAuth:**
1. Ir a GitHub Settings → Developer settings → OAuth Apps
2. New OAuth App
3. Application name: Joidy
4. Homepage URL: http://localhost:3000
5. Authorization callback URL: http://localhost:8000/integrations/github/callback
6. Device authorization callback URL: http://localhost:8000/integrations/github/device

**Obtención de PAT:**
1. GitHub Settings → Developer settings → Personal access tokens
2. Tokens (classic) → Generate new token
3. Scopes: `repo`, `read:user`

---

### 2.4 Telegram

| Variable | Requerido | Tipo | Descripción |
|----------|-----------|------|-------------|
| TELEGRAM_BOT_TOKEN | No | string | Token del bot |
| TELEGRAM_ALLOWED_USER_ID | No | string | Tu user ID |

**Obtención:**
1. Buscar `@BotFather` en Telegram
2. `/newbot` para crear bot
3. Copiar token
4. Buscar `@userinfobot` para obtener tu ID

---

### 2.5 Aplicación

| Variable | Default | Tipo | Descripción |
|----------|---------|------|-------------|
| SECRET_KEY | (auto-generated) | string | Clave de sesión |
| APP_ENV | development | string | Entorno |

**SECRET_KEY:**
Se genera automáticamente en el primer inicio si no está configurada. Para generar manualmente:

```bash
# Linux/Mac
openssl rand -hex 32

# Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### 2.6 Puertos

| Variable | Default | Descripción |
|----------|---------|-------------|
| FRONTEND_PORT | 3000 | Puerto del frontend |
| API_PORT | 8000 | Puerto de la API |
| AI_SERVICE_PORT | 8002 | Puerto del AI service |
| WORKER_PORT | 8001 | Puerto del worker |

**Cambiar si hay conflictos:**

```env
FRONTEND_PORT=3001
API_PORT=8001
```

---

## 3. Archivos de Configuración del Código

### 3.1 API (api/config.py)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite:////data/db/joidy.db"

    # Services
    ai_service_url: str = "http://ai-service:8002"
    worker_url: str = "http://worker:8001"

    # Security
    secret_key: str = "dev_secret_change_me"

    # Environment
    app_env: str = "development"

    # GitHub
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_web_url: str = ""
    github_token: str = ""
    github_username: str = ""
    github_webhook_url: str = ""

    # AI
    embedding_retry_max_attempts: int = 8
    embedding_retry_base_seconds: int = 60
    xp_table_json: str = ""

settings = Settings()
```

### 3.2 AI Service (ai-service/config.py)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    database_url: str = "sqlite:////data/db/joidy.db"
    app_env: str = "development"

settings = Settings()
```

### 3.3 Worker (worker/config.py)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:////data/db/joidy.db"
    api_url: str = "http://api:8000"
    ai_service_url: str = "http://ai-service:8002"
    vault_path: str = "/vault"
    app_env: str = "development"
    python_unbuffered: str = "1"

settings = Settings()
```

---

## 4. Configuración desde la Web

### 4.1 Panel de Settings

Accesible via el ícono de engranaje en el header.

**Secciones:**

1. **Apariencia**
   - Tema (oscuro/claro)
   - Formato de hora (12h/24h)
   - Colores de acento
   - Paquete de iconos (Lucide/Phosphor/Material)

2. **Vault**
   - Directorio del vault
   - Carpeta Joidy
   - Escribir en vault nativo

3. **Integraciones**
   - GitHub Token
   - Telegram Bot
   - Telegram User ID

4. **IA**
   - Gemini API Key

### 4.2 API Endpoints

```bash
# Obtener configuración
GET /config/

# Actualizar configuración
POST /config/

# Lista de claves disponibles
GET /config/keys
```

---

## 5. Docker Compose

### 5.1 Environment del API

```yaml
api:
  environment:
    - DATABASE_URL=sqlite:////data/db/joidy.db
    - AI_SERVICE_URL=http://ai-service:8002
    - WORKER_URL=http://worker:8001
    - SECRET_KEY=${SECRET_KEY}
    - APP_ENV=${APP_ENV:-development}
    - GITHUB_TOKEN=${GITHUB_TOKEN:-}
    - GITHUB_USERNAME=${GITHUB_USERNAME:-}
    - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID:-}
    - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET:-}
```

### 5.2 Volúmenes

```yaml
api:
  volumes:
    - ./.env:/app/.env  # Montar .env para escritura
```

---

## 6. Desarrollo vs Producción

### 6.1 Development

```env
APP_ENV=development
```

- Hot reload activo
- Volúmenes montados para código
- Debug logs habilitados

### 6.2 Production

```env
APP_ENV=production
```

- Imágenes optimizadas
- Sin mounts de código
- Logs optimizados

---

## 7. Seguridad

### 7.1 No Commitear .env

El archivo `.env` está en `.gitignore`:

```gitignore
# .env
data/
```

### 7.2 Keys Sensibles

Las siguientes variables no deben compartirse:
- SECRET_KEY
- GEMINI_API_KEY
- GITHUB_CLIENT_SECRET
- GITHUB_TOKEN
- TELEGRAM_BOT_TOKEN

---

## 8. Troubleshooting

### 8.1 Vault Path no existe

```
Error: Vault path does not exist
```

**Solución:** Verificar que la ruta existe y es absoluta.

### 8.2 API Key inválida

```
Error: Invalid API key
```

**Solución:** Verificar key en Google AI Studio.

### 8.3 Puerto en uso

```
Error: Port already in use
```

**Solución:** Cambiar puertos en `.env`.