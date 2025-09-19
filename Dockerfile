# Temel Python 3.9 imajını kullan
FROM python:3.9-slim

# Çalışma dizinini /app olarak ayarla
WORKDIR /app

# Gerekli Python kütüphanelerini kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm proje dosyalarını /app dizinine kopyala
COPY . .

# Uygulamanın başlayacağı komutu belirt (isteğe bağlı, sadece bilgi amaçlı)
CMD ["python", "main.py"]