# Guía de Estilo

Esta guía define las convenciones de código para mantener Joidy consistente entre frontend y backend.

## Backend (Python / FastAPI)

- Usa **type hints** en parámetros y retornos de funciones.
- Prefiere `pathlib.Path` sobre manipulación de strings de ruta.
- Los nombres de variables y funciones van en `snake_case`.
- Los nombres de clases en `PascalCase`.
- Las constantes en `SCREAMING_SNAKE_CASE`.
- Separa la lógica de negocio en `services/` y los endpoints en `routers/`.
- Usa `Pydantic` para validación de configuración y request/response models.
- Usa `SQLAlchemy` con declarative mapping para modelos.
- Maneja errores con `HTTPException` y status codes apropiados.
- Los tests usan `pytest` y `TestClient` de FastAPI.

## Frontend (SvelteKit / TypeScript)

- Usa `Svelte 5 runes` (`$state`, `$derived`, `$effect`) para reactividad.
- Declara tipos explícitos en props y stores.
- Organiza imports: librerías externas primero, luego internos de `$lib/`, luego componentes relativos.
- Usa `kebab-case` para nombres de archivos de componentes.
- Mantiene componentes pequeños y enfocados.
- Accesibilidad: incluye `aria-label`, `role`, y manejo de teclado en componentes interactivos.
- CSS: usa variables definidas en `app.css` para colores, espaciado y sombras.

## Commits

- Usa prefijos descriptivos: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Escribe el título en imperativo: "add X", "fix Y", "update Z".
- Referencia el issue relacionado: `Relates to #123`.

## Pull Requests

- Enfoca cada PR en un solo cambio.
- Actualiza documentación si el cambio afecta arquitectura o uso.
- Asegúrate de que el CI pase antes de pedir revisión.
