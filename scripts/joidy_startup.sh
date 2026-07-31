#!/bin/bash
# Script de inicio para Joidy con checkeo de salud
# Ubicación: scripts/joidy_startup.sh (dentro del repo)
# Uso: bash scripts/joidy_startup.sh  (o vía joidy.service)

# Resolver el directorio del proyecto desde la ubicación del script
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Iniciando servicios de Joidy..."
# Usamos dev-d para iniciar en segundo plano (detached)
make dev-d

echo "⏳ Esperando a que los servicios se estabilicen..."
sleep 15

echo "🔍 Realizando checkeo de salud..."

# Check API (puerto por defecto 8000, configurable via API_PORT)
API_PORT="${API_PORT:-8000}"
if curl -s "http://localhost:${API_PORT}/health" | grep -q "ok"; then
    echo "✅ API está saludable"
else
    echo "⚠️ API podría tener problemas, revisando logs..."
    docker compose logs --tail=20 api
fi

# Check DB Health via Makefile command
make db-health

echo "✨ Joidy está listo."
