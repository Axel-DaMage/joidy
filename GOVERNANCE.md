# Gobernanza

Este documento describe cómo se toman las decisiones en Joidy, quién mantiene el proyecto y qué esperar al contribuir.

## Modelo de gobernanza

Joidy es un proyecto de código abierto mantenido por una sola persona: el modelo es *single-maintainer* / BDFL (*Benevolent Dictator For Life*). No existe un consejo de gobernanza, un proceso de consenso formal ni un quorum de aprobaciones. El mantenedor principal toma las decisiones finales sobre la dirección del proyecto, el alcance de los cambios, los merges y las releases.

Este modelo se declara explícitamente para que las expectativas sean realistas:

- Las decisiones técnicas se toman en público cuando es posible (issues, PRs, `docs/adr/`).
- La aprobación final siempre corresponde al mantenedor.
- La fusión a `main`, la creación de tags y la publicación de releases son exclusivas del mantenedor.

## Mantenedores

| Rol | Nombre | GitHub |
|-----|--------|--------|
| Mantenedor principal (BDFL) | D4MAG3_WIZ4RD | [@Axel-DaMage](https://github.com/Axel-DaMage) |

La propiedad de todo el código está asignada al mantenedor principal mediante [`.github/CODEOWNERS`](.github/CODEOWNERS) (`* @Axel-DaMage`).

## Proceso de decisión

- **Issues y bugs:** se triagian con las etiquetas canónicas (`priority:P0`–`P3`, `bug`, `enhancement`, etc.) según se describe en [CONTRIBUTING.md](CONTRIBUTING.md#etiquetas-y-triage-de-issues).
- **Decisiones de arquitectura:** se documentan como ADRs en [`docs/adr/`](docs/adr/).
- **Cambios de licencia, marca o gobernanza:** solo el mantenedor puede aprobarlos.
- **Discrepancias:** si una discusión no converge, la decisión final es del mantenedor. Los argumentos quedan registrados en el issue/PR correspondiente.

## Contribuciones y revisión

Las contribuciones siguen el proceso de [CONTRIBUTING.md](CONTRIBUTING.md): fork, rama `feat/`·`fix/`·`docs/`·`chore/`, Conventional Commits, tests y Pull Request contra `development`.

Política de revisión (objetivos realistas, no SLA garantizado):

- **Todo PR requiere revisión humana del mantenedor** antes de mergearse; la CI en verde es condición necesaria pero no suficiente.
- Las contribuciones con asistencia de IA siguen la misma barra de revisión y testing que cualquier otra — ver [CONTRIBUTING.md](CONTRIBUTING.md#contribuciones-con-asistencia-de-ia).
- Issues `priority:P0` (críticos, seguridad) se priorizan sobre el resto del backlog.
- El mantenedor revisa según su disponibilidad; no hay plazos garantizados. Los PRs que permanezcan inactivos durante un periodo prolongado pueden cerrarse y reabrirse cuando el autor retome el trabajo.
- Los PRs pequeños y enfocados se revisan antes que los grandes; describe el "por qué" en la descripción del PR.

## Factor de bus y sucesión

Joidy tiene un **factor de bus de 1**: hoy el proyecto depende de una sola persona. Esto se declara abiertamente:

- Si el mantenedor no está disponible, el proyecto puede quedar temporalmente en pausa; los issues y PRs abiertos seguirán ahí.
- El código es GPL-3.0-or-later: cualquiera puede hacer fork y continuar el proyecto sin restricciones de licencia.
- El mantenedor está abierto a incorporar co-mantenedores que demuestren contribuciones sostenidas y de calidad; la sucesión se negociaría en público antes de cualquier transferencia.
- La continuidad del proyecto no está garantizada por ninguna entidad externa.

## Autoridad de releases

- Solo el mantenedor puede mergear `development` → `main`, crear tags y publicar releases.
- Las releases siguen [Versionado Semántico 2.0.0](https://semver.org/lang/es/) y el proceso descrito en [RELEASE.md](RELEASE.md) (`release.yml` automatiza el bump de versión, el tag y la GitHub Release; `publish.yml` publica las imágenes).
- Los cambios que rompen compatibilidad (API, formato de datos, configuración) solo entran en releases `MAJOR`.

## Modelo de ramas

- **`development`** — rama por defecto (integración) del repositorio; todos los PRs apuntan aquí.
- **`main`** — solo contiene código listo para producción; se actualiza desde `development` mediante PR de release.
- **`feat/*`, `fix/*`, `docs/*`, `refactor/*`, `chore/*`** — ramas de vida corta que se mergean vía PR.

## Documentos relacionados

- [CONTRIBUTING.md](CONTRIBUTING.md) — cómo contribuir, convenciones y política de contribuciones asistidas por IA.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — código de conducta.
- [SECURITY.md](SECURITY.md) — cómo reportar vulnerabilidades de seguridad de forma responsable.
- [SUPPORT.md](SUPPORT.md) — dónde pedir ayuda.
- [NOTICE](NOTICE) — avisos de copyright y licencia.
- [docs/TRADEMARKS.md](docs/TRADEMARKS.md) — marcas registradas de terceros referenciadas en la UI.
- [RELEASE.md](RELEASE.md) — proceso de versionado y publicación.
- [docs/COMMUNITY.md](docs/COMMUNITY.md) — canales de la comunidad.
