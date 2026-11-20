# Política de Seguridad

## Versiones soportadas

Joidy lo mantiene una sola persona, así que las correcciones de seguridad se
publican únicamente sobre la release más reciente. No se hacen backports a
versiones anteriores.

| Versión | ¿Recibe correcciones de seguridad? |
|---------|------------------------------------|
| Última release publicada (rama `main`; imágenes Docker `:latest`, AUR, Homebrew) | ✅ Sí |
| Releases anteriores (cualquier tag previo al último) | ❌ No — actualiza a la última release |
| Rama `development` (integración, sin publicar) | ⚠️ Recibe las correcciones primero, pero no es una versión soportada para despliegue |
| Forks y builds modificados | ❌ No |

A fecha de 2026-11-20 todas las
[releases publicadas](https://github.com/Axel-DaMage/joidy/releases) son
pre-releases (serie `1.1.0-beta`) y todavía no existe una release estable:
«última release» significa hoy la pre-release más reciente. El esquema de
versiones y ramas está descrito en [RELEASE.md](RELEASE.md).

## Reportar una Vulnerabilidad

Si descubres una vulnerabilidad de seguridad en Joidy, por favor **no abras un
issue, discusión ni pull request público**. Usa uno de estos canales privados:

1. **Canal principal — GitHub Private Vulnerability Reporting:**
   [reportar una vulnerabilidad](https://github.com/Axel-DaMage/joidy/security/advisories/new)
   (pestaña **Security → Report a vulnerability** del repositorio). El reporte
   solo es visible para ti y para el mantenedor, viaja cifrado en tránsito
   (HTTPS), permite preparar la corrección en privado y coordinar la
   asignación de un identificador GHSA/CVE.
2. **Alternativa — correo:** **[d4mag3@duck.com](mailto:d4mag3@duck.com)**, si
   no tienes cuenta de GitHub o no puedes usar el canal anterior. No hay clave
   PGP publicada, así que el correo no va cifrado de extremo a extremo: para
   detalles sensibles (exploit, datos, secretos) usa el canal de GitHub, o
   envía por correo solo un aviso inicial y acordamos cómo compartir el resto.

Esperamos:

- Una descripción clara del problema y de su impacto
- Componente afectado (`api`, `ai-service`, `worker`, `frontend`, CLI,
  instaladores, imágenes Docker…)
- Versión del software afectada (tag de release, tag/digest de la imagen o
  commit) y canal de instalación (Docker, AUR, Homebrew, `git clone`)
- Pasos para reproducirla o prueba de concepto (si aplica)
- Configuración relevante (`BIND_ADDR`, proxy inverso, integraciones
  activas…) — sin incluir secretos reales
- Tu recomendación para mitigarla (opcional)
- Cómo quieres que te acreditemos (opcional)

### Proceso

Los plazos son **objetivos** de un proyecto con un único mantenedor, no
garantías; si no podemos cumplir alguno, te lo diremos.

1. **Acuse de recibo** en 48 horas hábiles
2. **Evaluación** de la gravedad y alcance — objetivo: 7 días naturales desde
   el reporte, con confirmación (o descarte razonado) y gravedad estimada
3. **Parche** — trabajamos en una corrección o mitigación lo antes posible;
   objetivo: 30 días para gravedad crítica/alta y 90 días para media/baja
4. **Divulgación** coordinada — publicamos el fix y te acreditamos (si lo deseas)

Te mantendremos al tanto del avance en el mismo canal del reporte.

### Divulgación coordinada

- **Embargo:** te pedimos no divulgar los detalles hasta que exista una
  release con la corrección, con un máximo orientativo de 90 días desde el
  reporte, ampliable de mutuo acuerdo. Si hay explotación activa podemos
  publicar antes una mitigación o un aviso.
- **Avisos de seguridad:** cada vulnerabilidad corregida se publica como
  [GitHub Security Advisory](https://github.com/Axel-DaMage/joidy/security/advisories)
  (GHSA, con CVE cuando proceda) indicando versiones afectadas, gravedad,
  impacto, versión corregida y mitigaciones; la corrección figura además en
  la sección `Security` de [CHANGELOG.md](CHANGELOG.md).
- **Actualizaciones de seguridad:** se distribuyen sin demora y sin coste por
  los canales habituales de release — GitHub Releases, imágenes
  `d4mag3/joidy-*` en Docker Hub, AUR y Homebrew. Cómo aplicarlas:
  [INSTALL.md](INSTALL.md#actualización).
- **Reconocimiento:** acreditamos en el aviso a quien reportó, salvo que
  prefiera el anonimato. No hay programa de recompensas.

Estas prácticas están alineadas con las expectativas de gestión de
vulnerabilidades del Anexo I, Parte II, del
[Reglamento (UE) 2024/2847](https://eur-lex.europa.eu/eli/reg/2024/2847/oj)
(Ley de Ciberresiliencia, CRA): política de divulgación coordinada, punto de
contacto para reportes, avisos públicos de las vulnerabilidades corregidas y
actualizaciones de seguridad sin demora. No constituyen una declaración de
conformidad; está previsto un documento de cumplimiento dedicado
(`docs/security-compliance.md`) en el seguimiento del issue #1392.

Agradecemos tu ayuda para mantener Joidy seguro.

## Alcance y responsabilidad del operador

Joidy es software **autoalojado** (self-hosted): el proyecto no opera ningún
servicio alojado. Cada instancia la despliega y la administra quien la
instala, que es responsable de la postura de seguridad de su despliegue.

**En alcance:**

- El código de este repositorio: `api/`, `ai-service/`, `worker/`,
  `frontend/`, la CLI (`cli/`, `scripts/`), los instaladores y los archivos
  de compose.
- Los artefactos oficiales: imágenes `d4mag3/joidy-*` en Docker Hub, el
  paquete AUR `joidy` y la fórmula de Homebrew (`Axel-DaMage/homebrew-tap`).
- Valores por defecto inseguros: una configuración de fábrica que exponga
  datos o servicios sin que el operador lo haya pedido.

**Fuera de alcance:**

- Instancias de terceros — prueba solo contra despliegues que sean tuyos.
- Problemas que dependen únicamente de la configuración del despliegue
  (exponer Joidy a Internet sin TLS, secretos débiles o filtrados, versiones
  no soportadas).
- Vulnerabilidades de dependencias o servicios de terceros (PostgreSQL, n8n,
  proveedores de IA, Google, GitHub…) sin un vector explotable propio de
  Joidy — repórtalas al proyecto original. Si el uso que hace Joidy las
  vuelve explotables, sí están en alcance.
- Ataques que requieren acceso previo al host, al `.env`, al socket del
  motor de contenedores o a la base de datos.
- Riesgos residuales ya documentados en este archivo, salvo que demuestres
  un impacto mayor que el descrito.
- Ingeniería social, ataques físicos y denegación de servicio volumétrica.

**Responsabilidad del operador:**

- **Exposición:** los puertos publicados se enlazan por defecto a
  `127.0.0.1` (`BIND_ADDR`). Abrirlos a la LAN (`0.0.0.0`) o a Internet
  (túnel, proxy inverso) es decisión del operador.
- **TLS:** la stack sirve HTTP plano; si accedes desde fuera de `localhost`,
  termina TLS en un proxy inverso o túnel.
- **Secretos:** generar, custodiar y rotar `SECRET_KEY`, `INTERNAL_SECRET`,
  `POSTGRES_PASSWORD`, las claves de API y el archivo `.env`.
- **Actualizaciones:** aplicar las releases de seguridad (`joidy pull`);
  solo la última release recibe correcciones.
- **Host y copias:** el endurecimiento del host y del motor de contenedores,
  y la protección de las copias de seguridad (ver las secciones siguientes;
  detalle de variables en [docs/configuration.md](docs/configuration.md)).

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
