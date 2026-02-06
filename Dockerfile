FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99

# Instalar TOR con bridges (para evitar bloqueos)
RUN apt-get update && apt-get install -y \
    wget curl tor obfs4proxy xvfb \
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

# Configurar TOR con bridges (OBFS4 para evitar censura)
RUN echo "SocksPort 127.0.0.1:9050" > /etc/tor/torrc \
    && echo "ControlPort 127.0.0.1:9051" >> /etc/tor/torrc \
    && echo "CookieAuthentication 1" >> /etc/tor/torrc \
    && echo "Log notice stdout" >> /etc/tor/torrc \
    && echo "UseBridges 1" >> /etc/tor/torrc \
    && echo "ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy" >> /etc/tor/torrc \
    && echo "Bridge obfs4 193.11.166.194:27015 2D9C7B0BE860BE6B62ACC5B1E8DFB94E68D74F41 cert=lyQNhtsA0lCTzqnl6T7WQX0kh5T8F3VZ5tGWjJxmV1MmS8E0LLBpX8OdtKQx59G8eYsg iat-mode=0" >> /etc/tor/torrc \
    && echo "Bridge obfs4 37.218.245.14:38224 D9A82D2F9C2F65A18407B1D2B764F130847F8B5D cert=bjRaMrr1BRiAW8IE9U5z27fQaYgOhX1UCmOpg2pFpoMvo6ZgQMzLsaTzzQNTlm7hNcbSg iat-mode=0" >> /etc/tor/torrc \
    && echo "Bridge obfs4 85.31.186.98:443 011F2599C0E9B27EE74B353155E244813763C3E5 cert=ayq0XzCwhpdysn5o0EyDUbmSOx3X/oTEbzDMvczHOdBJKlvIdHHLJGkZARtT4dcBFArPPg iat-mode=0" >> /etc/tor/torrc

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install stem requests[socks]

RUN mkdir -p /app/debug /app/output /app/data

COPY . .

# Esperar más tiempo para que TOR se inicialice con bridges
CMD sh -c "tor & sleep 30 && Xvfb :99 -screen 0 1920x1080x24 & export DISPLAY=:99 && sleep 5 && python -m scraper.main"