FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99

# Instalar TOR y dependencias mínimas
RUN apt-get update && apt-get install -y \
    wget curl tor xvfb \
    gnupg ca-certificates fonts-liberation \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libx11-xcb1 libdrm2 libgbm1 \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Configurar TOR para permitir conexiones
RUN echo "SocksPort 0.0.0.0:9050" >> /etc/tor/torrc \
    && echo "ControlPort 0.0.0.0:9051" >> /etc/tor/torrc \
    && echo "CookieAuthentication 1" >> /etc/tor/torrc \
    && echo "Log notice stdout" >> /etc/tor/torrc

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install stem requests[socks]

RUN mkdir -p /app/debug /app/output /app/data

COPY . .

# Esperar a que TOR se inicie completamente antes de ejecutar
CMD sh -c "tor & sleep 10 && Xvfb :99 -screen 0 1920x1080x24 & export DISPLAY=:99 && sleep 5 && python -m scraper.main"