#!/bin/bash
# Script de inicio para Joidy con checkeo de salud
# Ubicación: /home/d4mag3/Documents/Repos/Joidy/scripts/joidy_startup.sh

PROJECT_DIR="/home/d4mag3/Documents/Repos/Joidy"
cd "$PROJECT_DIR"

echo "🚀 Iniciando servicios de Joidy..."
# Usamos dev-d para iniciar en segundo plano (detached)
make dev-d

echo "⏳ Esperando a que los servicios se estabilicen..."
sleep 15

echo "🔍 Realizando checkeo de salud..."

# Check API
if curl -s "http://localhost:8008/health" | grep -q "ok"; then
    echo "✅ API está saludable"
else
    echo "⚠️ API podría tener problemas, revisando logs..."
    docker compose logs --tail=20 api
fi

# Check DB Health via Makefile command
make db-health

echo "✨ Joidy está listo."
