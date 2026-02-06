# Dockerfile - Aumentar tiempos de espera para TOR
FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y \
    wget curl tor xvfb \
    gnupg ca-certificates \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/debug /app/output /app/data

COPY . .

# AUMENTAR TIEMPOS DE ESPERA: TOR tarda ~2.5 minutos
CMD sh -c "tor & sleep 180 && Xvfb :99 -screen 0 1920x1080x24 & export DISPLAY=:99 && sleep 10 && python -m scraper.main"