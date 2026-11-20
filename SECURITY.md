# Política de Seguridad

## Reportar una Vulnerabilidad

Si descubres una vulnerabilidad de seguridad en Joidy, por favor repórtala enviando un correo a **[d4mag3@duck.com](mailto:d4mag3@duck.com)** en lugar de abrir un issue público.

Esperamos:

- Una descripción clara del problema
- Pasos para reproducirla (si aplica)
- Versión del software afectada
- Tu recomendación para mitigarla (opcional)

### Proceso

1. **Acuse de recibo** en 48 horas hábiles
2. **Evaluación** de la gravedad y alcance
3. **Parche** — trabajamos en una corrección lo antes posible
4. **Divulgación** coordinada — publicamos el fix y te acreditamos (si lo deseas)

Agradecemos tu ayuda para mantener Joidy seguro.

## Gestión de energía (docker.sock) — función opt-in (#1278)

El panel **Ajustes → Servicios** (`/system/power/*`) permite listar y
hibernar/despertar/apagar los servicios de la stack. Para funcionar, la API
necesita acceso al socket del motor de contenedores (`/var/run/docker.sock`
en Docker; el socket rootless por-usuario en Podman).

**Está desactivado por defecto** (`POWER_MANAGEMENT_ENABLED=false`): el socket
no se monta dentro del contenedor `api` y las rutas de mutación
(`/system/power/sleep|wake|shutdown`) ni siquiera se registran — solo existe un
stub de `GET /system/power/status` que responde `docker_available: false` para
que la UI degrade de forma limpia.

### Riesgo residual al activarlo

El socket del engine equivale a **root en el host**: cualquier proceso que
pueda hablar con él puede crear contenedores privilegiados, montar el sistema
de archivos del host y controlar el daemon por completo. Al activar
`POWER_MANAGEMENT_ENABLED=true` aceptas que:

- Una compromiso de la API (ejecución de código dentro del contenedor, SSRF o
  request-smuggling que alcance el socket) escala a control total del host.
- Los endpoints están detrás de autenticación y solo operan sobre los
  contenedores del propio proyecto de compose (allowlist: `postgres`, `api`,
  `ai-service`, `worker`, `frontend`), pero **el socket en sí no está
  restringido**: cualquier código con acceso a él tiene control total del
  daemon, no solo de los servicios de Joidy.

### Cómo activarlo de forma consciente

```bash
# .env
POWER_MANAGEMENT_ENABLED=true
DOCKER_GID=<GID del grupo docker>   # getent group docker | cut -d: -f3
joidy up                          # añade docker-compose.power.yml automáticamente
```

- `joidy up` detecta `DOCKER_GID` automáticamente; el overlay
  (`docker-compose.power.yml`) exige un GID real mediante `${DOCKER_GID:?}` y
  falla con un error claro si está vacío — nunca cae al grupo 0 (root).
- En Podman rootless se monta el socket por-usuario (`podman.sock`) sin
  `group_add`; el radio de explosión queda limitado al usuario, no a root.
- Alternativa manual equivalente:
  `docker compose -f docker-compose.yml -f docker-compose.power.yml up -d`

Mitigación preferida a futuro: un sidecar mínimo que exponga una API estrecha
(start/stop de una lista blanca de servicios) en lugar de montar el socket
completo dentro de la API.

## Integridad de los canales de instalación (#1296, #1394)

- **Instaladores (`install.sh` / `install.ps1`):** las URL documentadas
  apuntan a un **tag de release** (inmutable), no a una rama. El instalador
  clona el último tag publicado resolviéndolo vía la API de releases de
  GitHub; `JOIDY_BRANCH` es un override solo para desarrollo.
- **Checksums:** cada release adjunta `SHA256SUMS.txt` (tarball fuente,
  instaladores y `docker-compose.release.yml`). Instrucciones de
  verificación en [INSTALL.md](INSTALL.md#verificación-de-integridad).
- **AUR:** el `PKGBUILD`/`.SRCINFO` publicados llevan el `sha256sums` real
  del tarball de la release — `makepkg` lo verifica automáticamente. Las
  sumas se calculan en el pipeline sobre el artefacto publicado, no desde el
  checkout.
- **Imágenes Docker:** `docker-compose.yml` usa `:latest` (mutable). Para
  despliegues reproducibles usa `docker-compose.release.yml` (adjunto a cada
  release e instalado por el paquete AUR), `IMAGE_TAG=<release>` en `.env`, o
  fija por digest `imagen@sha256:<digest>`.
## Cifrado de datos en reposo (#1286, #1329)

Los campos sensibles se almacenan cifrados con **Fernet** (AES-128-CBC + HMAC)
usando una clave derivada de `SECRET_KEY` mediante SHA-256. El tipo
`EncryptedText` (`api/encryption.py`) cifra al escribir y descifra al leer de
forma transparente; las filas escritas antes del cambio se reescriben cifradas
en la migración `f8a9b0c1d2e3` y, como red de seguridad, cualquier resto de
texto plano se descifra de forma tolerante (migración perezosa).

Campos cifrados actualmente:

| Tabla | Columnas |
|-------|----------|
| `google_tokens` | `access_token`, `refresh_token_encrypted` |
| `email_messages` | `body_text` |
| `github_repos` | `webhook_secret` |
| `push_subscriptions` | `endpoint`, `p256dh`, `auth` |
| `google_calendar_events` | `summary`, `description`, `location` |
| `google_calendar_sync_state` | `sync_token` |

**Permanecen en texto plano a propósito** (Fernet no es determinista — el
ciphertext nunca coincide con filtros de igualdad ni `ILIKE`):

- `email_messages.subject/sender/snippet` — los busca el filtro `q` del inbox.
- Contenido de notas, `google_calendar_events.html_link` y metadatos en
  general (títulos, etiquetas, timestamps).

**Rotación de `SECRET_KEY`:** invalida todos los campos cifrados a la vez
(tokens OAuth incluidos — habría que reconectar Google). No existe un path de
re-cifrado automático; rota solo con migración manual planificada.

### Copias de seguridad

Los volcados `pg_dump -Fc` contienen la base de datos completa — incluidos
los secretos no cifrados a nivel de columna — y por defecto se escriben **en
texto plano** en el disco del host (`<data>/backups`, permisos `0600`/`umask
077` desde su creación, #1281). Trátalos como material sensible: cifra el
directorio de backups a nivel de SO o, mejor, define `BACKUP_ENCRYPTION_KEY`
en `.env` para que el sidecar y `joidy backup` escriban `*.dump.enc`
(AES-256-CBC/PBKDF2 vía openssl — el texto plano nunca toca disco).
`joidy restore <archivo.dump.enc>` descifra con la misma clave. **Sin la clave,
los volcados cifrados son irrecuperables.**
