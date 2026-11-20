# SBOM y Licencias de Terceros

Desde #1386, cada release publica artefactos de *software bill of materials*
(SBOM) y un reporte de licencias de terceros para los cuatro servicios
distribuidos (`api`, `ai-service`, `worker`, `frontend`).

## Artefactos publicados

Por cada imagen `d4mag3/joidy-<servicio>` publicada en Docker Hub:

- `sbom/joidy-<servicio>.spdx.json` — SBOM en formato **SPDX-JSON**.
- `sbom/joidy-<servicio>.cdx.json` — SBOM en formato **CycloneDX-JSON**.
- `THIRD-PARTY-NOTICES.txt` — reporte `paquete → licencia → copyright`
  derivado de los SBOM (obligación de atribución de MIT/Apache/BSD).

Los artefactos se distribuyen por dos canales:

1. **GitHub Release**: adjuntos como assets descargables (job `sbom` de
   `.github/workflows/publish.yml`).
2. **OCI referrers**: adjuntos a cada imagen vía `oras attach`, consultables
   con `oras discover d4mag3/joidy-api:<tag>`.

## Generación local

```bash
make sbom          # SBOMs desde el código fuente en ./sbom/
# o directamente:
scripts/generate_sbom.sh --mode source --out-dir sbom
scripts/generate_sbom.sh --mode image --image-prefix d4mag3 --tag latest
```

El modo `source` cataloga `requirements.txt` / `package-lock.json` (metadatos
de licencia escasos). El modo `image` escanea la imagen publicada — el objeto
exacto que distribuimos — y es el modo autoritativo que usa CI.

Herramienta: [syft](https://github.com/anchore/syft), versión fijada por
`SYFT_VERSION` (default `1.57.2`). El script resuelve `syft` desde PATH,
Docker (`anchore/syft:<versión>`) o descarga verificada por sha256.

## Política de licencias

`scripts/check_licenses.py` clasifica cada componente del SBOM:

| Veredicto | Familias | Efecto |
|-----------|----------|--------|
| **DENIED** | AGPL-*, SSPL-*, GPL-1.0*, GPL-2.0-only, CC-BY-NC/ND, BUSL, Elastic, proprietary | **Fallo del pipeline** |
| **REVIEW** | LGPL-*, MPL-*, EPL-*, CDDL-*, EUPL-*, CC-BY-SA, `GPL-2.0` ambiguo, `LicenseRef-*` | Warning (falla con `--strict`) |
| **UNKNOWN** | Licencia no detectada (NOASSERTION) | Warning; falla con `--strict` |
| **ALLOWED** | MIT, Apache-2.0, BSD-*, ISC, PSF, GPL-3.0-*, GPL-2.0-or-later, CC0-1.0, Unlicense… | OK |

Rationale: Joidy es GPL-3.0-only. AGPL/SSPL extenderían copyleft de red a
nuestros servicios API; GPLv2-only no puede combinarse con GPLv3; las
familias NC/ND/BUSL no son libres para distribución de código.

Nota de orden: el chequeo corre tras el push de imágenes (`needs: docker`),
por lo que una violación detiene la publicación de assets del release pero
no retira la imagen ya publicada — la revocación del tag es manual.

## CI

- `ci.yml` job `sbom`: preview en cada PR (modo source, política en
  `--quiet`, artefactos subidos como `sbom-source-preview`).
- `publish.yml` job `sbom`: escaneo de imágenes publicadas, enforcement de
  política, generación de notices, `oras attach` y upload al release.
