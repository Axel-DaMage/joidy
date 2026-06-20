# ADR 001: Usar SvelteKit para el Frontend

## Estado
Aceptado

## Contexto
Necesitamos elegir un framework para construir la interfaz de usuario de Joidy.

Opciones consideradas:
- **React + Next.js**: Popular, gran ecosistema
- **Vue + Nuxt**: Similar a nuestra experiencia
- **SvelteKit**: Framework centrado en el rendimiento

## Decisión
Usar **SvelteKit**.

### Razones
1. **Tamaño de bundle reducido**: Svelte compila a vanilla JS sin runtime
2. **Reactividad simple**: Stores integrados, sin complejidad de hooks
3. **SSR integrado**: Excelente para SEO y First Contentful Paint
4. **Hot Module Replacement**: Desarrollo rápido con Vite
5. **TypeScript**: Soporte nativo

## Consecuencias

### Positivas
- Mejor rendimiento en móviles
- Menos código boilerplate
- Curva de aprendizaje suave para desarrolladores JS

### Negativas
- Comunidad más pequeña que React
- Menos componentes de terceros
- Ecosistema de plugins menos maduro

## Referencias
- [SvelteKit Documentation](https://kit.svelte.dev)
- [Benchmarks de frameworks](https://krausest.github.io/js-framework-benchmark/)

---
*Fecha: Mayo 2026*