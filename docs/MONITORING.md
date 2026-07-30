# Monitoring

Joidy expone métricas en formato Prometheus en el endpoint `/metrics` del API.

## Métricas disponibles

- `http_requests_total` — contador de requests por método, ruta y status.
- `http_request_duration_seconds` — histograma de latencia de requests.
- Métricas por defecto de `prometheus_client` (información del proceso, GC, etc.).

## Ejecutar Prometheus + Grafana

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

URLs:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin / admin)

Prometheus se conecta al servicio `api` en el puerto 8000 del contenedor.

## Grafana

1. Inicia sesión con admin / admin.
2. Añade Prometheus como datasource (`http://prometheus:9090`).
3. Importa un dashboard para FastAPI o crea paneles con las métricas de arriba.
