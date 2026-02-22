#!/bin/bash
set -e

echo "════════════════════════════════════════"
echo "  INICIANDO SCRAPER RAMA JUDICIAL"
echo "  $(date '+%d/%m/%Y %H:%M:%S')"
echo "════════════════════════════════════════"

# ── 1. Iniciar Xvfb (display virtual) ────────────────────────────────────────
echo "[1/3] Iniciando display virtual (Xvfb)..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99

# Esperar a que Xvfb esté listo
for i in $(seq 1 10); do
    if xdpyinfo -display :99 > /dev/null 2>&1; then
        echo "    ✅ Xvfb listo"
        break
    fi
    echo "    Esperando Xvfb... ($i/10)"
    sleep 1
done

# ── 2. Verificar Chrome ───────────────────────────────────────────────────────
echo "[2/3] Verificando Chrome..."
CHROME_VERSION=$(google-chrome --version 2>/dev/null || echo "No encontrado")
echo "    ✅ $CHROME_VERSION"

# ── 3. Iniciar scraper ────────────────────────────────────────────────────────
echo "[3/3] Iniciando scraper..."
echo "════════════════════════════════════════"

exec python -m scraper.main