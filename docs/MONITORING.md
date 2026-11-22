# Monitoring

Joidy expone métricas en formato Prometheus en el endpoint `/metrics` del API.

## Métricas disponibles

- `http_requests_total` — contador de requests por método, ruta y status.
- `http_request_duration_seconds` — histograma de latencia de requests.
- Métricas por defecto de `prometheus_client` (información del proceso, GC, etc.).

## Ejecutar Prometheus + Grafana

```bash
docker compose -p joidy -f docker-compose.monitoring.yml up -d
```

Debe ejecutarse con el mismo nombre de proyecto que la app (`joidy` por
defecto) para que Prometheus y Grafana compartan la red por defecto del
stack y puedan resolver los servicios por nombre.

URLs:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (usuario `admin`, contraseña =
  `GRAFANA_ADMIN_PASSWORD` de tu `.env`)

Prometheus scrapea `/metrics` de `api:8000`, `ai-service:8002` y
`worker:8001` (ver `monitoring/prometheus.yml`).

## Grafana

1. Inicia sesión con `admin` y tu `GRAFANA_ADMIN_PASSWORD`.
2. El datasource de Prometheus (`http://prometheus:9090`) se provisiona
   automáticamente desde `monitoring/grafana/provisioning`.
3. Importa un dashboard para FastAPI o crea paneles con las métricas de arriba.
