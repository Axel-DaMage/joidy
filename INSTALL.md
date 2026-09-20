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
curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.sh | bash
```

El instalador:
- Clona el repositorio en `~/joidy`
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
curl -fsSL https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.sh | bash
```

> **Alternativa: PowerShell nativo** (sin WSL2)
>
> Solo si WSL2 no está disponible (ej. entorno corporativo):
> ```powershell
> irm https://raw.githubusercontent.com/Axel-DaMage/joidy/development/scripts/install.ps1 | iex
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

Si prefieres no usar el instalador:

```bash
git clone --depth 1 --branch development https://github.com/Axel-DaMage/joidy.git ~/joidy
cd ~/joidy
cp .env.example .env
# Edita .env con tus valores
docker compose up -d
```

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
