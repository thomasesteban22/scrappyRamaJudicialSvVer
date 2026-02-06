FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV CHROME_VERSION="144.0.7559.132"

RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxrandr2 \
    libcairo2 libpango-1.0-0 libatspi2.0-0 \
    xvfb xauth \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Instalar Chrome versión específica
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable=${CHROME_VERSION}-1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver COMPATIBLE con Chrome 144
# Método 1: Usar webdriver-manager (recomendado)
RUN pip install webdriver-manager

# Método 2: Instalar ChromeDriver manualmente para versión 144
RUN CHROME_MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d'.' -f1) \
    && wget -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios debug
RUN mkdir -p /app/debug/screenshots /app/debug/html /app/output

COPY . .

# Comando simple con Xvfb
CMD sh -c "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && sleep 3 && python -m scraper.main"