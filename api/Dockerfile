FROM python:3.11-slim-bullseye

# Instalar Docker CLI para hablar con el daemon del host
RUN apt-get update && apt-get install -y --no-install-recommends \
        docker.io ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
