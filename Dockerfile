FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99
ENV TOR_SOCKS_PORT=9050
ENV TOR_CONTROL_PORT=9051
ENV HTTP_PROXY_PORT=8118

# 1. Instalar solo lo esencial (mínimo para TOR + Chrome)
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    tor privoxy \
    xvfb \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libx11-xcb1 libdrm2 libgbm1 \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 2. Chrome minimal
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 3. Configurar TOR para máxima rotación
RUN echo "SocksPort 0.0.0.0:9050" >> /etc/tor/torrc \
    && echo "ControlPort 0.0.0.0:9051" >> /etc/tor/torrc \
    && echo "CookieAuthentication 1" >> /etc/tor/torrc \
    && echo "MaxCircuitDirtiness 600" >> /etc/tor/torrc \  # Cambiar IP cada 10 min
    && echo "NewCircuitPeriod 600" >> /etc/tor/torrc \
    && echo "NumEntryGuards 3" >> /etc/tor/torrc \
    && echo "UseEntryGuards 1" >> /etc/tor/torrc

# 4. Configurar Privoxy (SOCKS5 → HTTP)
RUN echo "forward-socks5 / 127.0.0.1:9050 ." >> /etc/privoxy/config \
    && echo "listen-address 0.0.0.0:8118" >> /etc/privoxy/config \
    && echo "toggle 0" >> /etc/privoxy/config \
    && echo "enable-remote-toggle 0" >> /etc/privoxy/config \
    && echo "enable-edit-actions 0" >> /etc/privoxy/config

WORKDIR /app

# 5. Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install stem requests[socks]  # Para controlar TOR

# 6. Directorios
RUN mkdir -p /app/debug /app/output /app/data

COPY . .

# 7. Script de inicio optimizado
CMD sh -c "/etc/init.d/tor start && /etc/init.d/privoxy start && Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && sleep 10 && python -m scraper.main"