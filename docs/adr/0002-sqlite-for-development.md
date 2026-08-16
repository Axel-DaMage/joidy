# ADR 002: SQLite + sqlite-vec para Desarrollo

## Estado
**Supercedado** — El proyecto ahora usa PostgreSQL 16 + pgvector en todos los entornos (desarrollo y producción) vía Docker. Ver [ADR-0004](0004-postgresql-pgvector.md) y `docker-compose.yml`.

## Contexto
Necesitamos elegir la base de datos para el proyecto.

Opciones consideradas:
- **SQLite**: Embebida, simple, sin servidor
- **PostgreSQL**: Robusta, escalable
- **MongoDB**: Flexible, JSON native

## Decisión
Usar **SQLite con extensión sqlite-vec** para desarrollo.

### Razones
1. **Zero-config**: No requiere servidor, funciona out-of-the-box
2. **Portabilidad**: Un solo archivo para toda la base de datos
3. **sqlite-vec**: Embeddings vectoriales para búsqueda semántica
4. **Adecuado para uso personal**: Carga de usuario único

## Por qué fue supercedado
A medida que el proyecto creció (embeddings, worker concurrente, push subscriptions, integración GitHub), las limitaciones de SQLite se volvieron problemáticas:
- Sin escrituras concurrentes (worker + API compiten)
- sqlite-vec tenía rendimiento limitado para búsqueda semántica
- Sin soporte nativo para JSON/Array types
- Migraciones Alembic orientadas a pgvector no funcionaban correctamente

La migración a PostgreSQL + pgvector se documenta en [ADR-0004](0004-postgresql-pgvector.md).

## Consecuencias

### Positivas (históricas)
- Configuración mínima durante las fases iniciales
- Backup simple (copia de archivo)
- Funciona en cualquier lugar con Python

### Negativas (que motivaron la migración)
- Concurrencia limitada
- No es ideal para múltiples usuarios simultáneos
- sqlite-vec no escalaba bien con el volumen de embeddings

## Referencias
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [SQLite vs PostgreSQL](https://sqlite.org/whentouse.html)
- [pgvector](https://github.com/pgvector/pgvector)

---
*Fecha: Mayo 2026 — Supercedado Julio 2026*
