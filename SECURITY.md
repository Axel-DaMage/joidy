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
