# ADR 002: SQLite + sqlite-vec para Desarrollo

## Estado
Aceptado

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

### Notas para producción
El ADR 003 documentará la migración a PostgreSQL para producción.

## Consecuencias

### Positivas
- Configuración mínima
- Backup simple (copia de archivo)
- Funciona en cualquier lugar con Python

### Negativas
- Concurrencia limitada
- No es ideal para múltiples usuarios simultáneos

## Referencias
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [SQLite vs PostgreSQL](https://sqlite.org/whentouse.html)

---
*Fecha: Mayo 2026*