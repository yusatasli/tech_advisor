# 1. Adım: Temel imaj olarak Python 3.9'un hafif bir versiyonunu kullan
FROM python:3.9-slim

# Sistemin yerel ayarlarını ve saat dilimini yapılandır
ENV LANG C.UTF-8
ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 2. Adım: Gerekli sistem bağımlılıklarını ve Chromium'u kur
# NOT: Google Chrome yerine, Apple Silicon (ARM64) mimarisiyle uyumlu olan Chromium kuruluyor.
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    wget \
    gnupg \
    # ---- SELENIUM İÇİN GEREKLİ TARAYICI ----
    chromium \
    # ----------------------------------------
    # Chrome için gerekli olan ve Chromium'un da kullandığı temel kütüphaneler
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libxtst6 \
    # psycopg2 için gerekli
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome kurma adımları mimari uyumsuzluğu nedeniyle tamamen kaldırıldı.

# 3. Adım: Çalışma dizinini ayarla
WORKDIR /app

# 4. Adım: Python kütüphanelerini kur
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 5. Adım: Proje dosyalarının tamamını konteynerin içine kopyala
COPY . .

# 6. Adım: Uygulamayı çalıştıracak komut
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

