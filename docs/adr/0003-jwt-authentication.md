# ADR 003: Autenticación JWT

## Estado
Aceptado

## Contexto
Joidy es una aplicación de usuario único con integraciones opcionales. Necesita un mecanismo de autenticación ligero que no requiera un store de sesiones en la base de datos.

Opciones consideradas:
- **JWT (JSON Web Tokens)**: Stateless, sin store de sesiones, auto-contenido
- **Session cookies + DB store**: Tradicional, requiere tabla de sesiones
- **API keys estáticas**: Simple, pero sin expiración ni rotación

## Decisión
Usar **JWT tokens stateless** firmados con `SECRET_KEY`. La autenticación se exige en todos los endpoints de datos/mutación, excepto `/health`, `/auth/login`, `/config/setup-status` y `/ws` (que usa su propio mecanismo de auth).

### Razones
1. **Stateless**: No requiere store de sesiones en DB
2. **Auto-contenido**: El token incluye claims sin necesidad de lookup
3. **Expiración**: Tokens de corta duración con refresh desde el frontend
4. **Simplicidad**: Un solo `SECRET_KEY` para firmar/verificar

## Consecuencias

### Positivas
- No requiere store de sesiones
- Fácil de escalar horizontalmente
- Tokens verificables sin acceso a DB

### Negativas
- `SECRET_KEY` debe rotarse en producción
- No se puede revocar un token antes de su expiración sin una blacklist
- Compromiso del `SECRET_KEY` permite forjar tokens

## Referencias
- [JWT.io](https://jwt.io)
- [FastAPI Security - OAuth2 with JWT](https://fastapi.tiangolo.com/tutorial/security/)

---
*Fecha: Junio 2026*
