FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Instalar Python y dependencias básicas
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip python3-venv \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxrandr2 \
    libcairo2 libpango-1.0-0 libatspi2.0-0 \
    xvfb \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Chrome para Ubuntu
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Chromedriver
RUN wget -q -O /tmp/chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/$(curl -sS https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | grep -o '"version":"[^"]*"' | head -1 | cut -d'"' -f4)/linux64/chromedriver-linux64.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

WORKDIR /app

# Configurar Python
RUN python3.11 -m pip install --upgrade pip

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/debug/screenshots /app/debug/html /app/output /app/data

COPY . .

# Usar Python 3.11 explícitamente
CMD sh -c "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && sleep 3 && python3.11 -m scraper.main"