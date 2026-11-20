# API test suite — environment independence (#1463)

The suite must be green in **both** environments:

- **CI** — fresh postgres, `-n auto`, bare env (`SECRET_KEY` exported,
  nothing else).
- **Inside a real running dev stack** — `docker compose exec api pytest tests/`,
  where the container env carries the deployment's values
  (`AI_SERVICE_ENABLED=true`, `POWER_MANAGEMENT_ENABLED=false`,
  `UPLOAD_DIR=/data/uploads`, `OBSIDIAN_VAULT_PATH=/vault` mounted to a real
  user vault, no `SECRET_KEY` in the process env).

`conftest.py` enforces that independence before importing `main`:

| Env var | Mode | Why |
|---|---|---|
| `JOIDY_ENV_FILE` | forced → session tmp file | the deployment `.env` must not leak secrets into the suite (#991) |
| `APP_ENV` | forced `test` | dev compose exports `development`; the test env disables the vault auto-restore |
| `SECRET_KEY` | `setdefault` test key | `EncryptedText` columns derive a Fernet key from it; the container only has it inside the isolated `.env` |
| `POWER_MANAGEMENT_ENABLED` | forced `true` | registers the real `/system/power` routes; the disabled stub is tested standalone in `test_routers_system.py` |
| `AI_SERVICE_URL` | forced `http://127.0.0.1:1` | unmocked ai-service calls (e.g. `trigger_embedding` fired by note creates) fail fast instead of hitting a live service |
| `OBSIDIAN_VAULT_PATH` | forced → session tmpdir | the mounted `/vault` is real user data; writes must never touch it |
| `UPLOAD_DIR` | forced → session tmpdir | the container's `/data/uploads` is root-owned and unwritable for the test UID |

## Vault isolation

Per test, the autouse `_isolated_vault` fixture points
`settings.obsidian_vault_path` at a fresh `tmp_path` and installs a
`/vault/...` → `<test vault>/...` alias on `resolve_confined_source_path`
at each of its import sites (`routers.notes`, `services.note_service`,
`services.sync_service`, `services.webhook_sync` — `from ... import` binds
the name at import time). Stored `source_path` values keep the canonical
container domain; only filesystem access is redirected. Tests that need a
custom vault root monkeypatch `settings.obsidian_vault_path` themselves
(see the `vault` fixture in `test_vault_confinement.py`).

## Rules for new tests

- Never assert on live-stack state: docker-socket presence, ai-service
  reachability, VAPID keys, DNS results, or leftover DB rows. Mock at the
  client/transport boundary (`http_client`, `webpush`, `_resolve_ips`,
  aiodocker) or assert the conditional behaviour
  (`docker_available: false → 404`).
- If a test genuinely needs an external capability, guard it with a
  documented `pytest.mark.skipif` marker — never let an env difference
  turn into a red suite.
- DB writes that escape the per-test savepoint (`SessionLocal` background
  paths, `@pytest.mark.real_commit`) are wiped by the conftest probes —
  but filesystem writes are not: keep them inside the isolated vault or
  `tmp_path`.
