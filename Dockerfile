FROM python:3.11-slim-bookworm  # Usar Bookworm (stable) en lugar de latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV CHROME_VERSION="144.0.7559.132"
ENV LANG=es_CO.UTF-8
ENV LC_ALL=es_CO.UTF-8

# Instalar dependencias del sistema - VERSIÓN COMPATIBLE
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 libxcomposite1 \
    libxdamage1 libxrandr2 libxext6 libxfixes3 \
    libxi6 libxtst6 libcairo2 libpango-1.0-0 \
    libatspi2.0-0 libxcb1 libxcb-dri3-0 \
    libxshmfence1 libgl1 libglx-mesa0 \
    libglu1-mesa libegl1 libgles2 \
    xvfb xauth x11vnc x11-utils x11-xserver-utils \
    dbus dbus-x11 \
    tzdata locales \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && sed -i '/es_CO.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen es_CO.UTF-8 \
    && update-locale LANG=es_CO.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Chrome - versión específica
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable=${CHROME_VERSION}-1 \
    && rm -rf /var/lib/apt/lists/*

# Chromedriver compatible - método mejorado
RUN CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d'.' -f1) \
    && if [ "$CHROME_MAJOR" -ge 115 ]; then \
        wget -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/; \
    else \
        wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}" && \
        LATEST=$(cat /tmp/chromedriver.zip) && \
        wget -O /tmp/chromedriver2.zip "https://chromedriver.storage.googleapis.com/${LATEST}/chromedriver_linux64.zip" && \
        unzip /tmp/chromedriver2.zip -d /usr/local/bin/; \
    fi \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios necesarios
RUN mkdir -p /app/debug/screenshots /app/debug/html /app/output /app/data \
    && chmod -R 777 /app/debug /app/output /app/data

# Copiar el resto del código
COPY . .

# Script de inicio simple
CMD sh -c "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && sleep 5 && python -m scraper.main"