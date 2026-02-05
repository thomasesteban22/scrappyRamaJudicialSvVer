FROM python:3.11-slim

# Variables de entorno
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV DEBUG_SCRAPER=0

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxrandr2 \
    libcairo2 libpango-1.0-0 libatspi2.0-0 \
    xvfb xauth x11vnc xfonts-100dpi xfonts-75dpi \
    xfonts-scalable xfonts-cyrillic x11-apps \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Instalar Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar Chromedriver compatible
RUN LATEST=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$LATEST/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip \
    && chromedriver --version

# Crear directorios necesarios
RUN mkdir -p /app/debug/screenshots /app/debug/html /app/output /app/tmp_profiles \
    && chmod -R 777 /app/debug /app/output /app/tmp_profiles

WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Script de inicio integrado directamente
RUN echo '#!/bin/bash\n\
\n\
echo "=========================================="\n\
echo "  INICIANDO SCRAPER RAMA JUDICIAL"\n\
echo "  Fecha: \$(date)"\n\
echo "=========================================="\n\
\n\
# Variables de entorno\n\
export DISPLAY=:99\n\
export TZ=America/Bogota\n\
export PYTHONUNBUFFERED=1\n\
export DEBUG_SCRAPER=${DEBUG_SCRAPER:-0}\n\
\n\
echo "✅ Configuración de entorno completada"\n\
\n\
# Iniciar Xvfb con configuración robusta\n\
echo "🖥️  Iniciando servidor virtual Xvfb en display :99..."\n\
\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /tmp/xvfb.log 2>&1 &\n\
XVFB_PID=\$!\n\
\n\
# Esperar que Xvfb esté listo\n\
sleep 5\n\
\n\
# Verificar que Xvfb está funcionando\n\
if xdpyinfo -display :99 >/dev/null 2>&1; then\n\
    echo "✅ Xvfb iniciado correctamente (PID: \$XVFB_PID)"\n\
    echo "   Display: :99"\n\
    echo "   Resolución: 1920x1080"\n\
else\n\
    echo "❌ ERROR: Xvfb no se inició correctamente"\n\
    echo "=== Últimas líneas del log de Xvfb ==="\n\
    tail -20 /tmp/xvfb.log\n\
    exit 1\n\
fi\n\
\n\
# Función de limpieza\n\
cleanup() {\n\
    echo "🛑 Limpiando procesos..."\n\
    if [ ! -z "\$XVFB_PID" ]; then\n\
        kill \$XVFB_PID 2>/dev/null\n\
    fi\n\
    pkill -f "chrome" 2>/dev/null || true\n\
    echo "✅ Limpieza completada"\n\
}\n\
trap cleanup EXIT\n\
\n\
# Mostrar IP de salida\n\
echo "🌐 Obteniendo IP de salida..."\n\
IP=\$(curl -s --max-time 10 https://api.ipify.org || echo "No disponible")\n\
echo "📡 IP saliente del contenedor: \$IP"\n\
\n\
# Verificar Chrome y Chromedriver\n\
echo "🔍 Verificando Chrome..."\n\
google-chrome-stable --version || echo "⚠️ Chrome no encontrado"\n\
\n\
echo "🔍 Verificando Chromedriver..."\n\
chromedriver --version || echo "⚠️ Chromedriver no encontrado"\n\
\n\
# Iniciar aplicación principal\n\
echo "🚀 Iniciando aplicación Python..."\n\
echo "=========================================="\n\
\n\
# Ejecutar con exec para manejar señales correctamente\n\
exec python -m scraper.main\n\
' > /app/start.sh && chmod +x /app/start.sh

# Copiar código de la aplicación
COPY . .

# Comando por defecto
CMD ["/app/start.sh"]