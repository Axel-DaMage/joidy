# Joidy — Guía de Instalación

Instrucciones detalladas para instalar Joidy en todos los sistemas operativos.

## Prerequisito único: Docker

Joidy corre en Docker. Instálalo antes de comenzar:

| OS | Instalador |
|----|-----------|
| Windows | [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/) + `wsl --install` |
| macOS | [Docker Desktop para Mac](https://docs.docker.com/desktop/install/mac-install/) |
| Linux | [Docker Engine](https://docs.docker.com/engine/install/) (elige tu distro) |

---

## Instalación rápida (recomendada)

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/v1.1.0-beta.8/scripts/install.sh | bash
```

> La URL apunta a un **tag de release** (inmutable), no a una rama — el
> workflow de release la actualiza en cada versión. El instalador clona la
> última release publicada; `JOIDY_BRANCH` existe solo para desarrollo.
> Para verificar el script antes de ejecutarlo, consulta
> [Verificación de integridad](#verificación-de-integridad).

El instalador:
- Resuelve el último tag de release vía la API de GitHub y clona esa versión en `~/joidy`
- Crea `.env` con secretos auto-generados
- Instala el comando `joidy` en `~/.local/bin`
- Añade `~/.local/bin` a tu PATH automáticamente

### Windows

> **Método recomendado: WSL2**
>
> Docker Desktop para Windows requiere WSL2 de todas formas.
> Usar WSL2 elimina todos los problemas de compatibilidad de PowerShell.

**Paso 1 — Instalar WSL2 con Ubuntu** (una sola vez, como Administrador):
```powershell
wsl --install
```
Reinicia cuando lo pida.

**Paso 2 — Abrir Ubuntu** desde el menú de inicio y ejecutar el instalador Linux:
```bash
curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/v1.1.0-beta.8/scripts/install.sh | bash
```

> **Alternativa: PowerShell nativo** (sin WSL2)
>
> Solo si WSL2 no está disponible (ej. entorno corporativo):
> ```powershell
> irm https://raw.githubusercontent.com/Axel-DaMage/joidy/v1.1.0-beta.8/scripts/install.ps1 | iex
> ```

---

## Configuración mínima

Después de instalar, edita `~/joidy/.env` y rellena al menos:

```env
# API key gratuita en https://aistudio.google.com/app/apikey
GEMINI_API_KEY=tu_api_key

# Ruta a tu vault de Obsidian (opcional)
OBSIDIAN_VAULT_PATH=~/Documents/MiVault
```

Los secretos (`SECRET_KEY`, `POSTGRES_PASSWORD`) se generan automáticamente durante la instalación.

---

## Primer inicio

```bash
joidy up
```

Abre http://localhost:3000 — la primera vez tarda ~2 min mientras descarga las imágenes.

---

## Comandos esenciales

```bash
joidy up       # Iniciar todos los servicios
joidy down     # Detener todos los servicios
joidy logs     # Ver logs en tiempo real
joidy pull     # Actualizar imágenes y reiniciar
joidy status   # Estado de los contenedores
joidy help     # Lista completa de comandos
```

---

## Instalación manual (avanzado)

Si prefieres no usar el instalador, clona el último tag de release
(la rama `development` es solo para contribuidores):

```bash
TAG=$(curl -fsSL "https://api.github.com/repos/Axel-DaMage/joidy/releases?per_page=1" | grep -m1 '"tag_name"' | cut -d'"' -f4)
git clone --depth 1 --branch "$TAG" https://github.com/Axel-DaMage/joidy.git ~/joidy
cd ~/joidy
cp .env.example .env
# Edita .env con tus valores
docker compose up -d
```

### Imágenes fijadas a la release (recomendado en producción)

`docker-compose.yml` usa el tag mutable `:latest`. Cada release publica
`docker-compose.release.yml` (en el repo y como asset de la release) con las
imágenes fijadas a la versión exacta:

```bash
docker compose -f docker-compose.yml -f docker-compose.release.yml up -d
# Equivalente con la CLI joidy / .env:
#   IMAGE_TAG=1.1.0-beta.8   (en .env)
```

Para una garantía aún mayor, fija por *digest* en lugar de tag
(`docker buildx imagetools inspect d4mag3/joidy-api:<tag>` →
`d4mag3/joidy-api@sha256:<digest>`).

## Verificación de integridad

Cada release adjunta `SHA256SUMS.txt` con el sha256 del tarball fuente, de
`install.sh`/`install.ps1` y de `docker-compose.release.yml`.

```bash
TAG=v1.1.0-beta.8   # tag de la release
curl -fsSL -o install.sh "https://raw.githubusercontent.com/Axel-DaMage/joidy/${TAG}/scripts/install.sh"
curl -fsSL -o SHA256SUMS.txt "https://github.com/Axel-DaMage/joidy/releases/download/${TAG}/SHA256SUMS.txt"
grep ' install\.sh$' SHA256SUMS.txt | sha256sum -c -   # → install.sh: OK
bash install.sh
```

En Arch Linux, `makepkg`/`yay`/`paru` verifican automáticamente el tarball de
la release contra el `sha256sums` del PKGBUILD publicado en AUR.

---

## Instalación vía gestores de paquetes

### Homebrew (macOS / Linux)

```bash
brew tap Axel-DaMage/homebrew-tap
brew install joidy
joidy up
```

### AUR (Arch Linux)

```bash
yay -S joidy
# o
paru -S joidy
```

---

## Actualización

```bash
joidy pull   # Actualiza imágenes Docker y reinicia
# O manualmente:
cd ~/joidy && git pull && docker compose pull && docker compose up -d
```

---

## Desinstalación

```bash
joidy down
docker compose down -v   # Elimina también los volúmenes (datos)
rm -rf ~/joidy
rm ~/.local/bin/joidy
rm -rf ~/.config/joidy
```

---

## Problemas comunes

| Síntoma | Solución |
|---------|----------|
| `joidy: command not found` | Ejecuta `source ~/.bashrc` o reinicia la terminal |
| Docker daemon no responde | Asegúrate de que Docker Desktop está iniciado |
| Puerto 3000 ocupado | Cambia `FRONTEND_PORT=3001` en `.env` |
| Sin tablas en la BD | `docker compose exec api alembic upgrade head` |
| En Windows: abre Notepad | Usa WSL2 o `joidy.cmd` en lugar de `joidy.ps1` directamente |
| En Windows: `ExecutionPolicy` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |

Para más detalles: [docs/troubleshooting.md](docs/troubleshooting.md)
