# 1) Base image
FROM python:3.12-slim

# 2) Variables de entorno para no-interactivo
ENV DEBIAN_FRONTEND=noninteractive

# 3) Instala dependencias de sistema + Google Chrome para Selenium
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      wget gnupg2 fonts-liberation libappindicator3-1 libasound2 \
      libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 \
      libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
      libxcursor1 libxdamage1 libxi6 libxrandr2 libxss1 libxtst6 \
      xdg-utils locales && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# 4) Directorio de trabajo
WORKDIR /app

# 5) Copia e instala dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6) Copia los selectores, los datos y el código
COPY selectors.json .
COPY data ./data
COPY scraper ./scraper

# 7) Expone el puerto de la app
EXPOSE 5000

# 8) Comando por defecto
CMD ["python", "-m", "scraper.main"]
