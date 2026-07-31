# ADR 006: WebSocket para Tiempo Real

## Estado
Aceptado

## Contexto
Joidy necesita notificaciones en tiempo real para:
- Conflictos de sincronización del vault
- Actualizaciones de progreso de gamificación
- Estado de tareas del worker (daily writes, sync)
- Notificaciones push

Opciones consideradas:
- **WebSocket**: Bidireccional, persistente, baja latencia
- **Server-Sent Events (SSE)**: Unidireccional, más simple
- **Polling**: Simple, pero ineficiente

## Decisión
Usar **WebSocket** para comunicación en tiempo real entre frontend y API.

### Razones
1. **Bidireccional**: El frontend puede enviar y recibir mensajes
2. **Persistente**: Una sola conexión reutilizable
3. **Baja latencia**: Sin overhead de HTTP por mensaje
4. **FastAPI nativo**: Soporte integrado via `@app.websocket("/ws")`

## Consecuencias

### Positivas
- Notificaciones instantáneas sin polling
- Menor carga del servidor que polling
- Soporte para mensajes bidireccionales

### Negativas
- Requiere manejo de reconexión en el frontend
- Difícil de escalar horizontalmente (sticky sessions o Redis pub/sub)
- Auth de WebSocket es diferente (token en query param o header inicial)

## Notas
- El endpoint `/ws` es público (sin JWT) pero valida la conexión después del handshake
- El frontend usa reconexión automática con backoff exponencial

## Referencias
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [WebSocket API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

---
*Fecha: Junio 2026*
