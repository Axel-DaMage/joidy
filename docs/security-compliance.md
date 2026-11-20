<!--
SPDX-FileCopyrightText: 2025 D4MAG3_WIZ4RD and contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Cumplimiento de Seguridad — Autoevaluación CRA y EU AI Act

> **Aviso importante:** este documento es una **autoevaluación informativa**
> realizada por el mantenedor del proyecto. **No constituye asesoramiento
> legal** ni una declaración de conformidad con ningún reglamento. Las
> conclusiones de aplicabilidad son una lectura razonada del texto legal y
> deben revalidarse antes de cada hito normativo y ante cualquier cambio de
> modelo de negocio o distribución.

**Fecha de la evaluación:** 2026-11-20 · **Issue de seguimiento:** [#1392](https://github.com/Axel-DaMage/joidy/issues/1392)

---

## 1. Propósito y alcance

Joidy es un sistema personal de gestión del conocimiento autoalojado
(self-hosted), distribuido gratuitamente bajo licencia **GPL-3.0-or-later**
por los siguientes canales:

- **GitHub Releases** — código fuente (tarball), instaladores
  (`install.sh` / `install.ps1`), `SHA256SUMS.txt` y
  `docker-compose.release.yml`.
- **Docker Hub** — imágenes `d4mag3/joidy-{api,ai-service,worker,frontend}`.
- **AUR** — paquete `joidy` (`aur/PKGBUILD`, publicación vía `aur-publish.yml`).
- **Homebrew** — fórmula en `Axel-DaMage/homebrew-tap` (job `homebrew` de
  `publish.yml`).
- **`git clone`** — instalación desde fuente para desarrollo.

Este documento resume (a) la aplicabilidad del **Reglamento (UE) 2024/2847**
(«Cyber Resilience Act», CRA) y del **Reglamento (UE) 2024/1689** («EU AI
Act»), (b) la política de gestión de vulnerabilidades del proyecto en los
términos del Anexo I del CRA, y (c) una tabla de brechas (gap assessment)
contra los requisitos esenciales del CRA, con la evidencia verificable en el
repositorio.

El proyecto lo mantiene **una sola persona, sin ánimo de lucro** ni
monetización: no hay versión de pago, suscripción, soporte contratado ni
servicio alojado. Esa circunstancia es determinante para la aplicabilidad
(§2.2).

---

## 2. Reglamento (UE) 2024/2847 — Ley de Ciberresiliencia (CRA)

### 2.1 Calendario de aplicación (verificado en el texto oficial)

| Hito | Fecha | Base legal |
|------|-------|------------|
| Publicación en el Diario Oficial de la UE | 20.11.2024 | DO L, 2024/2847 |
| Entrada en vigor | **10.12.2024** | Art. 71.1 (vigésimo día tras la publicación) |
| Capítulo IV (órganos de evaluación de la conformidad, arts. 35–51) | **11.06.2026** | Art. 71.2 |
| Obligaciones de notificación del **Art. 14** (vulnerabilidades explotadas activamente e incidentes graves) | **11.09.2026** | Art. 71.2 — **ya vigentes** a fecha de este documento |
| Resto de obligaciones (requisitos esenciales del Anexo I, declaración UE de conformidad, marcado CE…) | **11.12.2027** | Art. 71.2 |

El texto completo está disponible en EUR-Lex:
<https://eur-lex.europa.eu/eli/reg/2024/2847/oj>. Resumen oficial de la
Comisión Europea:
<https://digital-strategy.ec.europa.eu/en/policies/cra-summary>.

### 2.2 ¿Aplica el CRA a Joidy?

**Concepto clave — «puesta a disposición en el mercado» (Art. 3.22):** el
suministro de un producto con elementos digitales para su distribución o uso
en el mercado de la UE **en el marco de una actividad comercial**, con
independencia de que haya precio. El considerando 15 precisa que la actividad
comercial puede existir **sin cobrar** (monetización indirecta, soporte de
pago más allá del coste, tratamiento de datos no vinculado a la seguridad del
producto, donaciones que excedan los costes de desarrollo). A la inversa, las
donaciones **sin ánimo de lucro** no son actividad comercial, y el
considerando 18 añade que el software libre **no monetizado por su
fabricante** no debe considerarse actividad comercial, que las entregas
regulares por sí solas no implican carácter comercial y que el mero hospedaje
en repositorios o gestores de paquetes (considerando 20) no constituye por sí
solo «puesta a disposición en el mercado».

**Evaluación para Joidy:**

- Joidy se distribuye **gratuitamente**, sin monetización, sin soporte
  pagado y sin servicio alojado → lo más probable es que **quede fuera del
  ámbito del CRA** por no mediar actividad comercial.
- La distribución vía Docker Hub, AUR y Homebrew son gestores/registro de
  paquetes: por sí mismos no convierten la distribución en comercial
  (considerando 20).
- **Escenarios que cambiarían la aplicabilidad** (revisar §6): aceptar
  donaciones que excedan los costes, cobrar por soporte, ofrecer una
  instancia gestionada/SaaS, integrar Joidy en productos comerciales de
  terceros, o cualquier monetización futura.
- **«Open-source software steward» (Art. 3.14 y Art. 24):** régimen
  «light-touch» para **personas jurídicas** que apoyan de forma sostenida
  software libre **destinado a actividades comerciales** (p. ej. para
  integrarlo en servicios o productos monetizados). Joidy es hoy un proyecto
  de persona física sin ánimo comercial, por lo que este régimen
  probablemente tampoco aplica. Si en el futuro el proyecto se constituyera
  como entidad (fundación, asociación) con stewards, el Art. 24 exigiría una
  política de ciberseguridad documentada y verificable, fomento del reporte
  voluntario de vulnerabilidades y cooperación con las autoridades de
  vigilancia del mercado.

**Conclusión prudente:** aunque la aplicabilidad es improbable, el coste de
mantener las prácticas técnicas que el CRA exige es bajo y ya está en gran
parte implementado; este documento las deja registradas para que la
re-evaluación sea trivial si el modelo de negocio cambia.

### 2.3 Obligaciones relevantes si el CRA aplicara

Resumen de lo que recaería sobre el «fabricante» (Art. 13) y sobre el régimen
de notificación ya vigente (Art. 14), para contextualizar la tabla de §4:

- **Evaluación de riesgos de ciberseguridad** documentada y actualizada
  durante el periodo de soporte (Art. 13.2–13.3).
- **Debida diligencia** con componentes de terceros y **notificar
  vulnerabilidades detectadas en componentes ajenos** a su mantenedor
  (Art. 13.5–13.6).
- **Manejo efectivo de vulnerabilidades** conforme al Anexo I, Parte II,
  durante un **periodo de soporte** que, salvo uso esperado inferior a 5
  años, debe ser **de al menos 5 años** (Art. 13.8).
- Cada **actualización de seguridad** debe seguir disponible un mínimo de
  **10 años** o el resto del periodo de soporte, lo que resulte mayor
  (Art. 13.9). Para versiones sustancialmente modificadas basta cumplir la
  última si los usuarios de versiones anteriores acceden a ella
  **gratuitamente** (Art. 13.10) — compatible con la política de «solo la
  última release» de SECURITY.md.
- **Declaración UE de conformidad** y **marcado CE** (arts. 28–30); la
  documentación técnica y la declaración deben conservarse ≥10 años o el
  periodo de soporte (Art. 13.13).
- **Notificación obligatoria (Art. 14, vigente desde 11.09.2026):**
  - Vulnerabilidad **explotada activamente**: aviso temprano ≤24 h,
    notificación ≤72 h e informe final ≤14 días tras la medida correctiva.
  - **Incidente grave**: aviso temprano ≤24 h, notificación ≤72 h e informe
    final ≤1 mes.
  - Ambas se remiten a través de la **plataforma única de notificación**
    (SRP) que opera ENISA/los CSIRT designados como coordinadores (Art. 16).
- **Reporte voluntario (Art. 15):** cualquier persona puede notificar
  vulnerabilidades o incidentes de forma voluntaria a un CSIRT coordinador o
  a ENISA; hacerlo no genera obligaciones adicionales al notificante.

---

## 3. Política de gestión de vulnerabilidades

La política operativa del proyecto vive en [SECURITY.md](../SECURITY.md),
endurecida en el PR [#1428](https://github.com/Axel-DaMage/joidy/pull/1428)
(ya fusionado; cierra el issue
[#1389](https://github.com/Axel-DaMage/joidy/issues/1389)).

### 3.1 Recepción de reportes (Anexo I, Parte II, punto 6)

Canales privados, por orden de preferencia:

1. **GitHub Private Vulnerability Reporting (PVR)** — «Security → Report a
   vulnerability» del repositorio. El reporte solo es visible para el
   reportero y el mantenedor, permite coordinar la corrección en privado y
   la asignación de identificador **GHSA/CVE**. Verificado: el PVR está
   habilitado en el repositorio.
2. **Correo** — `d4mag3@duck.com`, para quien no pueda usar GitHub. No hay
   clave PGP publicada; para detalles sensibles se recomienda el canal de
   GitHub.

**Nunca** abrir issues, discusiones ni PRs públicos con detalles de
vulnerabilidades.

### 3.2 Triaje y objetivos de corrección

Los plazos son **objetivos** de un proyecto con un único mantenedor, no
garantías contractuales:

| Etapa | Objetivo |
|-------|----------|
| Acuse de recibo | 48 horas hábiles |
| Evaluación (gravedad + alcance) | 7 días naturales |
| Parche (crítica/alta) | 30 días |
| Parche (media/baja) | 90 días |
| Embargo de divulgación | hasta 90 días o hasta que exista release con el fix |

### 3.3 Divulgación coordinada y avisos (Anexo I, Parte II, puntos 4 y 5)

- Cada vulnerabilidad corregida se publica como **GitHub Security Advisory**
  (GHSA; CVE cuando proceda) con versiones afectadas, gravedad, impacto,
  versión corregida y mitigaciones; la corrección figura además en la
  sección `Security` de [CHANGELOG.md](../CHANGELOG.md).
- Se pide a los reporteros no divulgar hasta que exista la release con el
  fix (embargo orientativo de 90 días, ampliable de mutuo acuerdo; en caso
  de explotación activa puede adelantarse una mitigación o aviso).
- No hay programa de recompensas; se acredita al reportero salvo anonimato.

### 3.4 Versiones soportadas y periodo de soporte

- Solo la **última release publicada** recibe correcciones de seguridad; no
  hay backports a versiones anteriores ni a forks/builds modificados
  (tabla de versiones soportadas en SECURITY.md).
- Todas las releases actuales son pre-releases de la serie `1.1.0-beta`; no
  existe aún una release estable.
- **Nota CRA:** el Art. 13.10 permite cumplir solo con la última versión
  sustancialmente modificada siempre que los usuarios de versiones
  anteriores accedan a la última **gratis** — los canales de actualización
  (§3.5) son gratuitos. El requisito de periodo de soporte ≥5 años del
  Art. 13.8 queda como **decisión pendiente** si el CRA llegara a aplicar
  (§4, última fila): un proyecto personal probablemente no podría mantener
  5 años de soporte activo; la mitigación natural sería publicar el código
  (ya es GPL) para que terceros asuman el manejo de vulnerabilidades tras el
  periodo de soporte (considerando 61).

### 3.5 Actualizaciones y canales de distribución

Las correcciones se distribuyen **sin demora y sin coste** por los canales
habituales:

- **GitHub Releases**: cada release adjunta `SHA256SUMS.txt`
  (tarball fuente, instaladores y `docker-compose.release.yml`) —
  instrucciones de verificación en [INSTALL.md](../INSTALL.md).
- **Docker Hub**: imágenes `d4mag3/joidy-*`; `docker-compose.release.yml`
  fija los tags de la release y `IMAGE_TAG`/`@sha256:<digest>` permiten
  despliegues reproducibles.
- **AUR**: el `PKGBUILD`/`.SRCINFO` llevan el `sha256sums` real del tarball
  de la release, inyectado por el pipeline de release (`release.yml`);
  `makepkg` lo verifica automáticamente.
- **Homebrew**: `publish.yml` actualiza la fórmula con la URL y el `sha256`
  del tarball de la release.
- **Actualización en el host**: `joidy pull` (descarga las últimas imágenes)
  / reinstalación según [INSTALL.md](../INSTALL.md#actualización).

No existe mecanismo de actualización automática: el operador decide cuándo
actualizar. Para un software autoalojado esto es coherente; el requisito
CRA de «actualizaciones automáticas de seguridad cuando proceda» (Anexo I,
Parte I.2.c) se evaluaría como «no aplicable» salvo que se añada un
mecanismo de auto-update en el futuro.

---

## 4. Evaluación de brechas frente al Anexo I del CRA

Estados: ✅ implementado · ⚠️ parcial/pendiente de merge · ❌ ausente.

| Área (Anexo I CRA) | Estado | Evidencia | Siguiente paso |
|---|---|---|---|
| **SBOM** de artefactos distribuidos (Parte II.1) | ⚠️ Parcial | Pipeline fusionado en PR [#1420](https://github.com/Axel-DaMage/joidy/pull/1420) (issue [#1386](https://github.com/Axel-DaMage/joidy/issues/1386) cerrada): `scripts/generate_sbom.sh` (SPDX + CycloneDX vía syft), `scripts/check_licenses.py`, `scripts/generate_notices.py`, `docs/sbom.md`, job `sbom` en `publish.yml` (SBOMs como referrers OCI + assets de release) y preview source-mode en `ci.yml` | Verificar que la próxima release publique los SBOMs adjuntos a imágenes y release |
| **Divulgación coordinada** (Parte II.5) | ✅ Hecho | [SECURITY.md](../SECURITY.md) endurecido en PR [#1428](https://github.com/Axel-DaMage/joidy/pull/1428) (fusionado; [#1389](https://github.com/Axel-DaMage/joidy/issues/1389) cerrada): PVR + correo, plazos, embargo 90 días, GHSA. PVR habilitado (verificado vía API de GitHub) | — |
| **Configuración segura por defecto** (Parte I.2.b) | ✅ Hecho | `BIND_ADDR` por defecto `127.0.0.1` ([docker-compose.yml](../docker-compose.yml)); `POWER_MANAGEMENT_ENABLED=false` por defecto (socket Docker no montado, rutas de mutación no registradas — SECURITY.md); contenedores como usuario no-root (`USER app`/`node` en los Dockerfiles); cabeceras de seguridad (`api/middleware/security_headers.py`); JWT obligatorio en endpoints de datos; rate limiting (`api/middleware/rate_limit.py`) | — |
| **Releases firmados / verificables y procedencia** | ⚠️ Parcial | `SHA256SUMS.txt` por release, instaladores fijados a tags inmutables, sha256 en AUR/Homebrew, etiquetas OCI (`licenses`, `source`, `revision`, `vendor`) en `publish.yml`, `gh release create --verify-tag`. **Sin firma criptográfica ni attestations** — issue [#1297](https://github.com/Axel-DaMage/joidy/issues/1297) (cosign/provenance/SHA-pinning) sigue abierto | Implementar provenance/attestations en #1297 |
| **Integridad de canales de instalación** | ✅ Hecho | PR [#1419](https://github.com/Axel-DaMage/joidy/pull/1419) fusionado: instaladores fijados a releases, checksums, AUR con sha256 real, compose pineado, etiquetas OCI; workflow `dist-smoke.yml` cubre los caminos de distribución en CI; imágenes base pineadas por digest multiarquitectura (PR [#1427](https://github.com/Axel-DaMage/joidy/pull/1427) fusionado, [#1391](https://github.com/Axel-DaMage/joidy/issues/1391) cerrada) | — |
| **Monitorización de dependencias y vulnerabilidades** | ✅ Hecho | [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) (SAST Python + JS/TS, semanal + PR); [`.github/dependabot.yml`](../.github/dependabot.yml) (actualizaciones agrupadas pip/npm/actions semanales, docker mensual); [`.github/workflows/dependabot-alerts.yml`](../.github/workflows/dependabot-alerts.yml) (gate diario de alertas HIGH/CRITICAL >7 días); job `security` de `ci.yml`: bandit, pip-audit ×3, `npm audit --audit-level=high`, **trivy** filesystem scan (HIGH/CRITICAL bloqueante, `.trivyignore` para excepciones revisadas) | Mantener; vigilar falsos positivos de trivy |
| **Identificación de licencias** | ✅ Hecho | [LICENSE](../LICENSE) con el texto completo GPL-3.0 ([#1383](https://github.com/Axel-DaMage/joidy/issues/1383) cerrada vía #1413); `NOTICE` con identificador SPDX `GPL-3.0-or-later`; GitHub detecta `GPL-3.0` (verificado vía API); etiqueta OCI `licenses`; campo `license` SPDX en manifiestos (`pyproject.toml`, `frontend/package.json`, `aur/PKGBUILD` — [#1388](https://github.com/Axel-DaMage/joidy/issues/1388) cerrada vía #1429); anotación REUSE masiva en `REUSE.toml` + gate `reuse lint` en CI (`.github/workflows/reuse.yml`, PR [#1429](https://github.com/Axel-DaMage/joidy/pull/1429) fusionado). Pendientes: cabeceras SPDX por archivo — fase 2 de [#1384](https://github.com/Axel-DaMage/joidy/issues/1384); decisión AGPL ([#1396](https://github.com/Axel-DaMage/joidy/issues/1396)) | Fase 2 de #1384 cuando se toque cada archivo |
| **Cifrado de datos en reposo** (Parte I.2.e) | ✅ Hecho | Sección «Cifrado de datos en reposo» de [SECURITY.md](../SECURITY.md) (#1286, #1329): Fernet (AES-128-CBC + HMAC) vía `EncryptedText` (`api/encryption.py`), migración `f8a9b0c1d2e3`, excepciones documentadas; `BACKUP_ENCRYPTION_KEY` cifra volcados (`*.dump.enc`, AES-256-CBC/PBKDF2) | — |
| **Registro y monitorización** (Parte I.2.l) | ⚠️ Parcial | `/metrics` Prometheus en la API ([docs/MONITORING.md](MONITORING.md), `docker-compose.monitoring.yml` con Prometheus + Grafana); `/metrics` y `/health` en worker; rate limiting con logging. **No existe un log de auditoría de seguridad dedicado** (accesos, eventos de autenticación) | Evaluar si un audit log dedicado aporta; documentar retención |
| **Mecanismo de actualización** (Parte I.2.c, Parte II.7–8) | ⚠️ Parcial | `joidy pull`/`joidy up` ([scripts/joidy.sh](../scripts/joidy.sh)); releases en todos los canales; `docker-compose.release.yml` pineado; sin auto-actualización (modelo pull del operador). Las actualizaciones son gratuitas y sin demora | Documentar como decisión de diseño; reevaluar si se añade auto-update |
| **Periodo de soporte ≥5 años** (Art. 13.8, solo si aplica) | ❌ No implementado | Política actual: solo la última release recibe fixes, sin backports (SECURITY.md). Compatible con Art. 13.10 pero no con un periodo de soporte formal de 5 años | Decisión consciente del proyecto; si el CRA aplicara, valorar publicar EOL/source-available handoff (considerando 61) |

\* Los estados reflejan el repositorio a fecha 2026-11-20. Los PRs de
cumplimiento citados (#1419, #1420, #1427, #1428, #1429) ya están fusionados;
los issues que cerraron (#1386, #1388, #1389, #1391) figuran como cerrados.
Este documento debe actualizarse cuando cambien los estados restantes (§6).

---

## 5. Reglamento (UE) 2024/1689 — EU AI Act (resumen)

El AI Act entró en vigor en agosto de 2024 con aplicación por fases
(prohibiciones desde feb. 2025, obligaciones para modelos GPAI desde
ago. 2025, la mayoría del resto desde 2026–2027). Aplicabilidad para Joidy
(issue [#1395](https://github.com/Axel-DaMage/joidy/issues/1395)):

- `ai-service` es un **integrador/desplegador** de modelos GPAI de terceros
  (Gemini por defecto; OpenAI, Anthropic, Cohere, Ollama y OpenRouter
  opcionales). Las obligaciones a nivel de modelo pesan sobre los
  proveedores.
- El conjunto de funciones actual **no parece de alto riesgo** (Anexo III:
  sin perfiles, biometría ni automatización de decisiones) → las obligaciones
  del deployer son ligeras.
- **Art. 50 (transparencia):** los usuarios que interactúan con un sistema de
  IA deben saberlo. El chat `/ai` lo implica; las operaciones silenciosas en
  segundo plano (embeddings, clasificación de notas) se documentan en
  [docs/ai-transparency.md](ai-transparency.md) (PR
  [#1441](https://github.com/Axel-DaMage/joidy/pull/1441)): qué datos se
  envían a qué proveedor, modelos por defecto y comportamiento opt-out — con
  `GEMINI_API_KEY` vacío las funciones de IA se desactivan limpiamente. La
  divulgación en la UI se implementó con el componente `AiDisclosure`
  (issue [#1395](https://github.com/Axel-DaMage/joidy/issues/1395), cerrada).
- **Reevaluar** si futuras funciones derivan hacia territorio del Anexo III.

---

## 6. Cadencia de revisión

Este documento debe re-evaluarse:

1. **Antes del 11.12.2027** (aplicación general del CRA) — revisar la tabla
   de §4 y la conclusión de §2.2.
2. **Ante cualquier cambio de modelo de negocio o distribución**: monetización
   (donaciones superiores a costes, soporte pagado), SaaS/instancias
   gestionadas, integración comercial por terceros, cambio de licencia
   (decisión #1396 sobre AGPL) o nuevos canales de distribución.
3. **Tras cada release mayor** o cuando cambie la política de versiones
   soportadas (impacto en el requisito de periodo de soporte del Art. 13.8).
4. **Cuando se fusionen** los trabajos aún abiertos citados aquí (la fase 2
   de #1384, la decisión #1396 y el issue #1297 de procedencia de releases),
   para actualizar estados y enlaces.

Issues que alimentan esta revisión: [#1392](https://github.com/Axel-DaMage/joidy/issues/1392)
(CRA, paraguas — sigue abierto), [#1396](https://github.com/Axel-DaMage/joidy/issues/1396)
(licencia AGPL — decisión pendiente), [#1384](https://github.com/Axel-DaMage/joidy/issues/1384)
(cabeceras SPDX por archivo, fase 2) y
[#1297](https://github.com/Axel-DaMage/joidy/issues/1297)
(procedencia/firma de releases). Ya cerrados merced a este esfuerzo:
[#1386](https://github.com/Axel-DaMage/joidy/issues/1386) (SBOM),
[#1388](https://github.com/Axel-DaMage/joidy/issues/1388) (metadatos de
licencia), [#1389](https://github.com/Axel-DaMage/joidy/issues/1389)
(SECURITY.md), [#1391](https://github.com/Axel-DaMage/joidy/issues/1391)
(digest pinning de imágenes base) y
[#1395](https://github.com/Axel-DaMage/joidy/issues/1395) (EU AI Act —
transparencia y divulgaciones UI en #1441).

---

## 7. Fuentes

- Reglamento (UE) 2024/2847 (CRA), texto completo en EUR-Lex:
  <https://eur-lex.europa.eu/eli/reg/2024/2847/oj>
- Resumen oficial del CRA (Comisión Europea):
  <https://digital-strategy.ec.europa.eu/en/policies/cra-summary>
- Entrada en vigor del CRA (nota de prensa, 10.12.2024):
  <https://digital-strategy.ec.europa.eu/en/news/cyber-resilience-act-enters-force-make-europes-cyberspace-safer-and-more-secure>
- Plataforma única de notificación CRA (ENISA):
  <https://www.enisa.europa.eu/news/the-cra-single-reporting-platform-is-launched>
- Reglamento (UE) 2024/1689 (EU AI Act):
  <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- Documentos relacionados del repositorio: [SECURITY.md](../SECURITY.md),
  [INSTALL.md](../INSTALL.md), [RELEASE.md](../RELEASE.md),
  [PRIVACY.md](../PRIVACY.md), [docs/MONITORING.md](MONITORING.md),
  [docs/configuration.md](configuration.md).
