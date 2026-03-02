FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Bogota

RUN apt-get update && apt-get install -y \
    wget curl ca-certificates tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/debug/screenshots /app/debug/html \
             /app/debug/responses /app/output /app/data /app/logs

COPY . .

CMD ["python", "-m", "scraper.main"]