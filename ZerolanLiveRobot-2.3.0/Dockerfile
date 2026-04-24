FROM python:3.10-slim

LABEL maintainer="IGEM-FBH"
LABEL description="IGEM-sama AI VTuber for Bilibili"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Data volumes
VOLUME ["/app/data", "/app/knowledge_base/docs"]

# Ports: 8080 = analytics dashboard
EXPOSE 8080

# Default: start bot
CMD ["python", "main.py"]
