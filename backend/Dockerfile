FROM python:3.9-slim

RUN ln -snf /usr/share/zoneinfo/Europe/Istanbul /etc/localtime && echo Europe/Istanbul > /etc/timezone

RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg chromium \
    libglib2.0-0 libnss3 libfontconfig1 libxtst6 \
    libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
