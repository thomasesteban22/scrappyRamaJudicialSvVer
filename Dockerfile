FROM python:3.11-slim

# ----------------------------
# Configs básicas
# ----------------------------
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota

# ----------------------------
# Dependencias del sistema
# ----------------------------
RUN apt-get update && apt-get install -y \
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

# ----------------------------
# Chrome estable
# ----------------------------
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Chromedriver compatible
# ----------------------------
RUN LATEST=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$LATEST/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# ----------------------------
# Carpeta de trabajo
# ----------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# ----------------------------
# Comando de arranque
# ----------------------------
# Usamos Xvfb y modo unbuffered (-u) para logs en tiempo real
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", "python", "-u", "-m", "scraper.main"]