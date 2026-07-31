# ADR 004: PostgreSQL + pgvector como base de datos principal

## Estado
Aceptado

## Contexto
A medida que el proyecto creció (embeddings, worker concurrente, push subscriptions, integración GitHub), las limitaciones de SQLite se volvieron problemáticas:
- Sin escrituras concurrentes (worker + API compiten)
- sqlite-vec tenía rendimiento limitado para búsqueda semántica
- Sin soporte nativo para JSON/Array types
- Migraciones Alembic orientadas a pgvector no funcionaban correctamente con SQLite

Opciones consideradas:
- **Mantener SQLite + sqlite-vec**: Simple, pero limitado
- **PostgreSQL + pgvector**: Robusto, concurrente, vector search nativo
- **MongoDB + Atlas Vector Search**: Flexible, pero diferente paradigma

## Decisión
Usar **PostgreSQL 16 con la extensión pgvector** en todos los entornos (desarrollo y producción) vía Docker. La imagen `pgvector/pgvector:pg16` proporciona PostgreSQL y la extensión vector out of the box.

### Razones
1. **Concurrencia**: Soporte completo ACID con escrituras concurrentes
2. **pgvector**: Búsqueda de similitud vectorial eficiente con índice HNSW
3. **JSON/Array nativo**: Tipos flexibles para evolución del schema
4. **Estándar**: PostgreSQL es la base de datos relacional más avanzada
5. **Docker**: Fácil de levantar via `docker compose`

## Consecuencias

### Positivas
- Escrituras concurrentes sin contención
- Vector search eficiente para embeddings
- Tipos JSON/Array para campos flexibles
- Migraciones Alembic funcionan correctamente

### Negativas
- Requiere un proceso PostgreSQL corriendo (manejado por Docker Compose)
- Mayor uso de memoria que SQLite
- SQLite sigue soportándose para tests CI, pero las migraciones son pgvector-oriented

## Notas
- SQLite se mantiene como fallback para CI (`DATABASE_URL=sqlite:////tmp/joidy-test.db`)
- `api/database.py` detecta SQLite y salta migraciones pgvector
- Ver ADR-002 (superceded) para el contexto histórico de SQLite

## Referencias
- [pgvector](https://github.com/pgvector/pgvector)
- [PostgreSQL 16 Release Notes](https://www.postgresql.org/docs/16/release-16.html)
- [pgvector/pgvector Docker image](https://hub.docker.com/r/pgvector/pgvector)

---
*Fecha: Julio 2026 — Supercede ADR-002*
