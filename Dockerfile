FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV CHROME_VERSION="144.0.7559.132"

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libgtk-3-0-common \
    libx11-xcb1 libdrm2 libgbm1 libxcomposite1 \
    libxdamage1 libxrandr2 libxext6 libxfixes3 \
    libxi6 libxtst6 libcairo2 libpango-1.0-0 \
    libatspi2.0-0 libxcb1 libxcb-dri3-0 \
    libxshmfence1 libgl1 libgl1-mesa-glx libglx-mesa0 \
    libglu1-mesa libegl1-mesa libgles2-mesa \
    xvfb xauth x11vnc x11-utils x11-xserver-utils \
    dbus dbus-x11 pulseaudio pulseaudio-utils \
    tzdata locales \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && locale-gen es_CO.UTF-8 \
    && update-locale LANG=es_CO.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable=${CHROME_VERSION}-1 \
    && rm -rf /var/lib/apt/lists/*

# Chromedriver compatible
RUN CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d'.' -f1) \
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios
RUN mkdir -p /app/debug/screenshots /app/debug/html /app/output \
    && chmod -R 777 /app/debug /app/output

COPY . .

# Script de inicio optimizado
CMD sh -c "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && sleep 5 && python -m scraper.main"