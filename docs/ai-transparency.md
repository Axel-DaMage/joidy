# Joidy - Transparencia de IA

## Metadata

```yaml
framework: FastAPI (ai-service) + FastAPI (api) + SvelteKit (frontend)
scope: EU AI Act — obligaciones de transparencia para deployers de GPAI
language: Español
related: PRIVACY.md, ai-service.md, configuration.md
```

---

## 1. Propósito y alcance

Este documento describe **qué datos salen de tu despliegue, hacia qué
proveedor de IA, cuándo y por qué**, tal como lo implementa el código actual.
Su objetivo es cubrir las obligaciones de transparencia del **Reglamento
(UE) 2024/1689 (AI Act)** que aplican a quien despliega un sistema de IA —
en este caso, el operador self-hosted de Joidy — y servir de base para la
[política de privacidad](../PRIVACY.md).

> **Aviso legal:** este documento es informativo, no asesoramiento legal.
> La aplicabilidad concreta del AI Act depende de tu jurisdicción, del uso
> que hagas del software y de tu condición (desarrollador, deployer o
> usuario final). Consulta a un profesional si tu despliegue tiene
> audiencia en la UE.

### Aplicabilidad del AI Act (resumen)

- Joidy actúa como **deployers/integradores de modelos GPAI** (Gemini,
  OpenAI, Anthropic, Cohere, OpenRouter, Ollama). Las obligaciones a nivel
  de modelo (documentación técnica, copyright, resumen de entrenamiento)
  recaen sobre los **proveedores de los modelos**, no sobre Joidy.
- Con el set de funciones actual (notas, chat, embeddings, clustering),
  Joidy **no entra en el Anexo III** (sistemas de alto riesgo: biometría,
  profiling, decisiones automatizadas con efecto legal, etc.). No se
  requiere evaluación de conformidad.
- Lo que sí aplica es la **transparencia del Art. 50**: las personas que
  interactúan con el sistema deben saber que interactúan con IA y, cuando
  corresponde, que el contenido es generado por IA. Este documento y los
  avisos de la interfaz cubren esa obligación.
- Las obligaciones por fases del Reglamento (prohibiciones desde feb-2025,
  deberes GPAI desde ago-2025, resto de obligaciones de sistemas desde
  ago-2026/2027) se aplican al despliegue, no al código en sí.
- **Reevaluar** si futuras funciones se acercan a territorio de Anexo III
  (profiling de usuarios, decisiones automatizadas sobre personas,
  biometría).

---

## 2. Arquitectura del flujo de datos

```
┌────────────┐   HTTPS/JWT    ┌──────────┐   HTTP interno   ┌─────────────┐   HTTPS   ┌──────────┐
│  Frontend  │ ─────────────► │   api    │ ───────────────► │ ai-service │ ────────► │ Provider │
│  (SvelteKit│                │ (FastAPI)│  X-Internal-     │  (FastAPI,  │           │ (nube o  │
│   :3000)   │                │  :8000   │  Secret header   │  :8002, sin │           │  local)  │
└────────────┘                └──────────┘                  │  puerto     │           └──────────┘
       ▲                            ▲                       │  publicado) │
       │                            │                       └──────┬──────┘
┌────────────┐   HTTP + token      │                              │ SQL
│  Telegram  │ ────────────────────┤                              ▼
│    Bot     │  /telegram/webhook  │                       ┌─────────────┐
└────────────┘                     │                       │ PostgreSQL  │
                                   │                       │ (pgvector)  │
                            ┌──────┴──────┐                └─────────────┘
                            │   worker    │  sync vault → POST /notes →
                            │  (watcher)  │  dispara embeddings vía api
                            └─────────────┘
```

Puntos clave del diseño (verificables en código):

- **ai-service no publica puerto al host** (`docker-compose.yml`): solo es
  alcanzable en la red interna de Docker. La API lo llama con el header
  `X-Internal-Secret` (`INTERNAL_SECRET`); en `APP_ENV=production` el
  servicio rechaza todo lo que no sea `/health`/`/metrics` si el secreto
  falta (fail-closed, #1277).
- **La API es el único camino** hacia ai-service desde el frontend y el
  worker; Telegram también pasa por `api/services/telegram_service.py`.
- **Sin credenciales de proveedor, no sale nada**: `ai-service/config.py`
  solo registra un proveedor en `provider_config` si su API key/base URL
  está definida. Sin `GEMINI_API_KEY` ni alternativas, `is_ai_enabled`
  es `false` y todos los endpoints devuelven `status: "disabled"`.
- **Capas de activación** (todas deben estar ON para que salga data):
  1. Contenedor ai-service corriendo (en producción es opt-in:
     `docker compose --profile ai up -d`).
  2. `AI_SERVICE_ENABLED=true` en la API (default `false` en
     `docker-compose.yml`, `true` en `docker-compose.dev.yml`).
  3. Al menos un proveedor configurado cuyas credenciales existan
     (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc. o `OLLAMA_BASE_URL`).

---

## 3. Proveedores soportados y selección de modelo

El formato de configuración es `PROVEEDOR:modelo` (`ai-service/config.py`):

| Proveedor | Variable de credencial | ¿Embeddings? | Privacidad del proveedor |
|-----------|------------------------|--------------|--------------------------|
| Gemini (default) | `GEMINI_API_KEY` | Sí (`models/text-embedding-004`) | [Términos Gemini API](https://ai.google.dev/gemini-api/terms) · [Privacidad Google](https://policies.google.com/privacy) |
| OpenAI / compatible | `OPENAI_API_KEY` (+`OPENAI_BASE_URL` opcional para routers compatibles: LiteLLM, vLLM, OpenRouter-style) | Sí (si el modelo lo soporta) | [Uso de datos en API](https://platform.openai.com/docs/guides/your-data) |
| Anthropic | `ANTHROPIC_API_KEY` | No → embeddings caen a Ollama si está disponible | [Privacidad Anthropic](https://www.anthropic.com/privacy) |
| Cohere | `COHERE_API_KEY` | Sí | [Privacidad Cohere](https://cohere.com/privacy) |
| OpenRouter | `OPENROUTER_API_KEY` | No → embeddings caen a Ollama | [Privacidad OpenRouter](https://openrouter.ai/privacy) |
| Ollama (local) | `OLLAMA_BASE_URL` (default `http://localhost:11434`; `.env.example` usa `http://host.docker.internal:11434`) | Sí | [Privacidad Ollama](https://ollama.com/privacy) — el cómputo ocurre en tu host |

Modelos por defecto (`.env.example`, `ai-service/config.py`):

- `LLM_MODEL=gemini:gemini-2.0-flash`
- `EMBEDDING_MODEL=gemini:models/text-embedding-004`

Comportamientos relevantes para privacidad:

- **Fallback a Ollama (#568):** si el proveedor primario falla (key
  inválida, cuota, red) y `OLLAMA_BASE_URL` está configurado, el cliente
  envuelve las llamadas en `FallbackLLMClient`/`FallbackEmbeddingClient`
  y reintenta contra Ollama local (`llama3` / `nomic-embed-text`). El
  contenido viaja entonces a tu propio host — nunca a un tercero extra.
- **`OLLAMA_BASE_URL` siempre cuenta como "disponible"** si está definida
  (aunque el servidor no responda): `available_providers` refleja
  *configuración*, no reachability. `/health` reporta
  `status: "degraded"` cuando el proveedor configurado no está disponible.
- **Base URLs remotas exigen `https://`** (#1330): `http://` solo se
  acepta para loopback (`localhost`, `127.0.0.0/8`, `::1`,
  `host.docker.internal`, `host.containers.internal`) salvo
  `ALLOW_INSECURE_BASE_URLS=true`.
- **Caché de respuestas en memoria:** `/embed` y `/classify` cachean por
  TTL (default 3600 s) dentro del proceso ai-service; no hay almacén
  externo ni persistencia del contenido cacheado.
- **Rate limit:** `MAX_REQUESTS_PER_MINUTE` (default 12) por endpoint;
  circuit breakers por tipo de carga (embeddings vs LLM).

---

## 4. Matriz funcionalidad × datos × proveedor

| Función | Disparador | Datos enviados al proveedor | Proveedor | Se almacena |
|---------|-----------|------------------------------|-----------|-------------|
| **Embeddings de notas** | **Automático** al crear/editar una nota (background task en `api/routers/notes.py` → `services/embedding_service.py`); también al sincronizar archivos del vault (worker → `POST /notes`); reintentos manuales vía `POST /notes/embeddings/retry-failed` | Contenido completo de la nota (`max_embed_content_chars`, default 100k) | `EMBEDDING_MODEL` (def. Gemini) | Vector en tabla `note_embeddings` (pgvector); fallos en `embedding_failures` (dead-letter tras 8 intentos) |
| **Búsqueda semántica** | Acción del usuario: `POST /notes/search/semantic` | La consulta de búsqueda del usuario | `EMBEDDING_MODEL` | Sin persistencia adicional |
| **Auto-tagging (sugerencias)** | **Automático con debounce** de 2 s mientras se edita una nota con contenido ≥ 20 chars (`NoteEditor.svelte` → `POST /ai/classify`) | Contenido de la nota + tags existentes | `LLM_MODEL` (def. Gemini) | Sugerencias no persisten; solo respuesta en caché en memoria |
| **Chat `/ai`** | Acción del usuario en la página `/ai` (`POST /ai/chat` o `/ai/chat/stream`) | Mensajes del chat + contexto personal (títulos/estado/valores de metas activas — progreso se envía como 0 —, racha actual, XP total, top-5 tags, títulos de últimas 10 notas) + extractos de notas relevantes vía RAG (top-5, ≤2000 chars c/u). La última pregunta además se embebe para retrieval | `EMBEDDING_MODEL` (pregunta) + `LLM_MODEL` (respuesta) | Conversación completa en `chat_sessions`; contadores de tokens en `api_usage` |
| **`/ask` de Telegram** | Comando del usuario al bot (`POST /telegram/webhook` → `api/services/telegram_service.py`) | La pregunta (≤1000 chars) + extractos de notas vía RAG | `EMBEDDING_MODEL` + `LLM_MODEL` | Log del comando en `telegram_events` |
| **Resumen diario** | **Automático al abrir el dashboard** después de las 20:00 locales (`DailyRecap.svelte` → `POST /ai/daily-recap`) | Contadores del día (notas creadas/editadas, racha, metas completadas; `xp_gained` y `focus_time_minutes` se envían como 0 — aún no persistidos por día) + títulos de hasta 10 notas creadas ese día | `LLM_MODEL` | Sin persistencia del contenido generado |
| **Clustering de temas** | Acción del usuario en `/graph` (`TopicClusters.svelte` → `POST /ai/cluster`) | **Nada sale de la máquina**: DBSCAN corre localmente en ai-service sobre los vectores ya almacenados en `note_embeddings` | Ninguno (CPU local) | Sin persistencia |
| **Plan-suggest** | Acción del usuario en `/calendar` (`POST /ai/plan-suggest`) | Títulos/prioridad/duración de tareas abiertas + bloques ocupados del Google Calendar cacheado + rango semanal + timezone + hint opcional | `LLM_MODEL` | Sin persistencia |

Notas sobre la matriz:

- **"Se almacena" se refiere a datos derivados del contenido enviado**, no a
  la respuesta cruda del proveedor (salvo chat, ver arriba).
- Los **embeddings** son representaciones vectoriales del contenido;
  revertibles solo de forma aproximada, pero siguen siendo dato derivado
  del usuario y se almacenan en tu propia base de datos.
- `api_usage` guarda únicamente `(operación, tokens_entrada,
  tokens_salida)` por llamada — sin contenido.
- `/usage` y `/health` del ai-service no envían datos de usuario.

---

## 5. Procesamiento silencioso en segundo plano (Art. 50)

Estas funciones envían datos a un proveedor **sin una acción explícita del
usuario en el momento** — el caso relevante para la transparencia del
Art. 50:

1. **Embeddings automáticos de notas.** Crear o editar una nota —incluida
   una nota que aparece por sincronización del vault de Obsidian vía el
   watcher del worker— dispara `trigger_embedding` en background. El
   contenido completo viaja al proveedor de embeddings configurado.
   *No hay toggle por feature*: se desactiva junto con todo el AI stack
   (`AI_SERVICE_ENABLED=false`, sin ai-service corriendo, o sin
   `EMBEDDING_MODEL` válido → `is_embedding_configured=false`).
2. **Auto-tagging al editar.** Cada pausa de 2 s de escritura en el editor
   de notas (contenido ≥ 20 caracteres) envía el contenido al LLM para
   sugerir tags. Las sugerencias aparecen como chips "ia:" en la barra de
   tags; nunca se aplican solas.
3. **Resumen diario.** Basta con abrir la app después de las 20:00 para
   que se envíen los contadores del día y títulos de notas al LLM. Se
   descarta con una vez por día (`localStorage`); no se reenvía.

Las funciones restantes (chat, `/ask`, plan-suggest, clustering, búsqueda
semántica) requieren acción explícita del usuario.

---

## 6. Opt-out y desactivación

De más a menos agresivo:

| Nivel | Cómo | Efecto |
|-------|------|--------|
| **Todo el AI stack** | `AI_SERVICE_ENABLED=false` en `.env` y no iniciar el perfil `ai` (`docker compose --profile ai up -d` lo habilita en producción) | La API responde `status: "disabled"` en todos los endpoints `/ai/*` y omite los triggers de embedding. Nada sale del deployment. |
| **Solo nube → local** | Configurar únicamente `OLLAMA_BASE_URL` con `LLM_MODEL=ollama:<modelo>` y `EMBEDDING_MODEL=ollama:<modelo>` | Todo el procesamiento ocurre en tu host; ningún dato sale de tu máquina. |
| **Sin IA (default seguro)** | No definir ninguna API key de proveedor | ai-service arranca pero `is_ai_enabled=false`; todos los endpoints devuelven `disabled`. La app funciona completa sin IA. |
| **Feature concreta** | Chat: botón "Limpiar conversación" (`DELETE /ai/chat/history`) borra `chat_sessions`. Telegram: no usar `/ask` o no configurar `TELEGRAM_BOT_TOKEN`. Embeddings existentes: borrar filas de `note_embeddings` / `embedding_failures`. | Elimina el rastro almacenado; el flujo hacia el proveedor ya ocurrió. |
| **Borrar todo** | `docker compose down -v` / `make dev-reset` elimina `postgres_data` (incluye `note_embeddings`, `chat_sessions`, `api_usage`, `embedding_failures`, `telegram_events`) | Borra todo dato derivado de IA junto con el resto. |

Consideraciones:

- **No hay consentimiento por feature ni banner de opt-in**: la
  transparencia se hace vía documentación (este archivo + `PRIVACY.md`) y
  avisos en la UI. Si tu despliegue sirve a terceros (p. ej. un espacio
  compartido), evalúa si necesitas capa de consentimiento adicional — el
  AI Act no la exige para este perfil de sistema, pero GDPR podría
  requerirla según la base jurídica que invoques.
- **`GEMINI_API_KEY` vacío degrada con elegancia**: la API sigue sana y el
  frontend muestra "IA inactiva" en `/ai`.
- **Los fallos de embedding no bloquean notas**: quedan en
  `embedding_failures` con reintentos exponenciales y dead-letter
  visible en la sección dev de `/ai`.

---

## 7. Avisos en la interfaz

Las superficies que generan o muestran output de IA llevan un aviso
ligero (icono + texto i18n + enlace a este documento), sin modales ni
paredes de consentimiento:

- `/ai` — aviso bajo el encabezado del chat.
- Editor de notas — chips de sugerencias etiquetados "ia:" con tooltip
  de divulgación.
- Dashboard — tarjeta "Resumen del día" marcada como generada por IA.
- `/graph` — panel "Temas detectados" (clustering) marcado como IA.

---

## 8. Relación con otros documentos

- [`PRIVACY.md`](../PRIVACY.md) — política de privacidad general: qué datos
  se almacenan, integraciones OAuth y retención. Este documento profundiza
  solo en el flujo hacia proveedores de IA.
- [`ai-service.md`](ai-service.md) — referencia técnica del servicio.
- [`configuration.md`](configuration.md) — todas las variables de entorno.
- La nota de aplicabilidad del AI Act dentro del marco de cumplimiento
  (CRA) se documenta en `docs/security-compliance.md` (PR paralelo de
  compliance).

---

*Última actualización: derivado del código en `development` (nov-2026).*
