# /app/start.sh
#!/bin/bash

echo "=========================================="
echo "  INICIANDO SCRAPER RAMA JUDICIAL"
echo "  Fecha: $(date)"
echo "=========================================="

# Configurar entorno
export DISPLAY=:99
export TZ=America/Bogota
export PYTHONUNBUFFERED=1
export DEBUG_SCRAPER=${DEBUG_SCRAPER:-0}

echo "✅ Variables de entorno configuradas"

# Crear directorios necesarios
mkdir -p /app/debug/screenshots /app/debug/html /app/output /app/tmp_profiles
chmod -R 777 /app/debug /app/output /app/tmp_profiles

echo "✅ Directorios creados"

# Verificar dependencias
echo "🔍 Verificando dependencias..."
which Xvfb >/dev/null 2>&1 || { echo "❌ Xvfb no encontrado"; exit 1; }
which python3 >/dev/null 2>&1 || { echo "❌ Python3 no encontrado"; exit 1; }
which google-chrome >/dev/null 2>&1 || { echo "❌ Chrome no encontrado"; exit 1; }

echo "✅ Dependencias verificadas"

# Iniciar Xvfb en segundo plano
echo "🖥️  Iniciando Xvfb en display :99..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /var/log/xvfb.log 2>&1 &
XVFB_PID=$!

# Esperar a que Xvfb esté listo
sleep 3

if xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "✅ Xvfb iniciado correctamente (PID: $XVFB_PID)"
else
    echo "❌ ERROR: Xvfb no se inició correctamente"
    echo "=== Log de Xvfb ==="
    cat /var/log/xvfb.log
    exit 1
fi

# Verificar que el display funciona
echo "🔍 Verificando display..."
DISPLAY_CHECK=$(xdpyinfo -display :99 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Display :99 funcionando"
else
    echo "❌ ERROR con display: $DISPLAY_CHECK"
    exit 1
fi

# Trap para limpiar procesos al salir
cleanup() {
    echo "🛑 Limpiando procesos..."
    kill $XVFB_PID 2>/dev/null
    pkill -f "chrome" 2>/dev/null
    echo "✅ Limpieza completada"
}
trap cleanup EXIT

# Log de IP saliente
echo "🌐 Obteniendo IP de salida..."
IP=$(curl -s https://api.ipify.org || echo "No disponible")
echo "📡 IP saliente: $IP"

# Ejecutar la aplicación principal
echo "🚀 Iniciando aplicación Python..."
echo "=========================================="

cd /app
exec python -m scraper.main