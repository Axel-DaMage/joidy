# n8n — Integraciones temporales

> **Parche personal y temporal**: hasta que joidy tenga integraciones nativas
> self-hosted (#42 Gmail). Los workflows viven versionados aquí; las credenciales
> viven SOLO dentro de n8n (cifradas con `N8N_ENCRYPTION_KEY` del `.env`).

## Servicio

`docker-compose.yml` define `n8n` bajo el profile `n8n` (opt-in, como `backup`):

```bash
make n8n          # arranca (UI en http://localhost:5678)
make n8n-down     # para
make n8n-logs     # logs
```

- Datos en el volumen `n8n_data` (SQLite propio de n8n).
- `N8N_ENCRYPTION_KEY` en `.env` — si se pierde, no se pueden descifrar credenciales.
- Variables pasadas al workflow (via env de n8n): `JOIDY_API_URL` (default
  `http://api:8000`), `JOIDY_AUTH_PASSWORD` (= `AUTH_PASSWORD` del `.env`).

## Gmail → Bandeja unificada de joidy

Workflow: `workflows/gmail-inbox-sync.json` — cada 15 min descarga los no leídos
de cada cuenta, les aplica un filtrado autónomo (reglas) y los sube a la API
(`POST /emails/`, idempotente por `account+gmail_id`). La pestaña **Correos** del
frontend muestra todas las cuentas fusionadas con sus filtros.

### Setup (una vez)

1. Primera visita a `localhost:5678` → crear la cuenta owner de n8n.
2. Necesitas credenciales Gmail OAuth2:
   - Crea (o usa) un proyecto en Google Cloud Console → APIs & Services →
     habilita **Gmail API** → credencial OAuth `Web application`
     con redirect `http://localhost:5678/rest/oauth2-credential/callback`.
   - En n8n: **Credentials → New → Gmail OAuth2** → autoriza con el correo.
   - Cada cuenta extra = una credencial Gmail OAuth2 más (una autorización por cuenta).
3. Importa el workflow: **Workflows → Import from File** →
   `n8n/workflows/gmail-inbox-sync.json`.
4. En cada nodo `Gmail cuenta X` selecciona su credencial y edita la constante
   `ACCOUNT` del nodo **Puntúa cuenta X** con el correo de esa cuenta.
   - ¿Tienes más cuentas? Duplica el sub-branch `Gmail cuenta X → Puntúa cuenta X`
     y conéctalo también desde `Joidy Login` antes de `POST a Joidy`.
5. Personaliza las reglas en los nodos Code (`OWN_SENDERS`, `IMPORTANT_SUBJECT`,
   `PROMO_RX`, ...). Por defecto: allowlist manual, labels `IMPORTANT`/`FLAGGED`
   y keywords de asunto marcan como importante; promo/bots quedan degradados.
6. Activa el workflow. Verifica en la pestaña **Correos** que llegan mensajes.

### Notas

- `POST /emails/` es upsert: los reenvíos no duplican (unique `account+gmail_id`).
- Los correos **no se marcan como leídos en Gmail** (no invasor). El nodo
  deshabilitado al final del workflow es una plantilla por si quieres hacerlo.
- Al borrar un correo desde la UI de joidy solo desaparece de la vista local;
  el buzón real no se toca.
- Sin reglas relevantes el correo igualmente se guarda y aparece con el filtro
  "Importantes" desactivado.

## Roadmap (cuando se haga nativo en joidy)

El parche toca solo la API pública de joidy (`/emails/`), así que reemplazar n8n
por integraciones nativas es un swap del productor: mismas tablas, misma UI.
Para self-hosted total: IMAP/JMAP propio (p.ej. Stalwart) sustituye al nodo Gmail
y OAuth de Google desaparece.
