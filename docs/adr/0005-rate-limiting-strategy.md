# ADR 005: Rate Limiting en Memoria

## Estado
Aceptado

## Contexto
Joidy necesita protección contra abuso de la API (brute force de login, spam de uploads, etc.). Al ser una aplicación de usuario único desplegada típicamente en un solo host, la infraestructura es simple.

Opciones consideradas:
- **Rate limiting en memoria**: Simple, sin dependencias externas
- **Redis-based rate limiting**: Distribuido, pero añade complejidad
- **Nginx/Proxy rate limiting**: A nivel de reverse proxy, pero no visible desde la app

## Decisión
Usar **rate limiting en memoria** implementado en `api/middleware/rate_limit.py`.

### Razones
1. **Simplicidad**: Sin dependencias adicionales (no requiere Redis)
2. **Suficiente para usuario único**: La carga esperada es baja
3. **Integración con FastAPI**: Middleware nativo, fácil de configurar
4. **Visibilidad**: La app conoce el estado del rate limit y puede responder con 429 + headers

## Consecuencias

### Positivas
- Sin infraestructura adicional
- Fácil de configurar y testear
- Respuestas 429 con headers estándar (Retry-After)

### Negativas
- No funciona correctamente con múltiples instancias de la API (cada instancia tiene su propio estado)
- Se pierde el estado al reiniciar el contenedor
- No escalable horizontalmente sin cambiar a solución distribuida

## Referencias
- [FastAPI Rate Limiting](https://fastapi.tiangolo.com/tutorial/middleware/)
- [RFC 6585 - 429 Too Many Requests](https://datatracker.ietf.org/doc/html/rfc6585)

---
*Fecha: Junio 2026*
