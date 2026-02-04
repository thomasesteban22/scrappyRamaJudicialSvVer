FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation \
    libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 \
    libx11-xcb1 libdrm2 libgbm1 \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# SSH folder
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "scraper.main"]
