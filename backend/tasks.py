# -*- coding: utf-8 -*-
# tasks.py - Celery ile arka plan görevleri ve otomatik cache doldurma

import os
import time
import asyncio
from typing import List, Dict, Any
from celery import Celery, group
from celery.schedules import crontab
from dotenv import load_dotenv

# Ortam değişkenlerini yükle
load_dotenv()

# Redis URL'ini al
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery uygulamasını yapılandır
celery_app = Celery(
    "tech_advisor_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

# Celery yapılandırması
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 dakika maksimum
    task_soft_time_limit=300,  # 5 dakika soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
)

# Zamanlanmış görevler
celery_app.conf.beat_schedule = {
    'prefetch-popular-queries-hourly': {
        'task': 'tasks.prefetch_popular_queries',
        'schedule': crontab(minute=0),  # Her saat başı çalışır
    },
    'prefetch-trending-queries-daily': {
        'task': 'tasks.prefetch_trending_queries', 
        'schedule': crontab(hour=2, minute=0),  # Her gün saat 02:00'da
    },
    'cleanup-old-cache-daily': {
        'task': 'tasks.cleanup_old_cache',
        'schedule': crontab(hour=4, minute=0),  # Her gün saat 04:00'da
    }
}

# Gerekli modülleri import et
from candidates import gather_candidates_async
from cache import ProductCache
from logger import get_logger

logger = get_logger("celery_tasks")
cache = ProductCache()

# Popüler arama sorguları - Kategorilere göre organize edilmiş
POPULAR_QUERIES = {
    "laptop": [
        "40000 TL gaming laptop", "50000 TL RTX 4060 laptop", "30000 TL iş laptop",
        "RTX 4070 laptop", "MSI gaming laptop", "ASUS ROG laptop", "öğrenci laptop 25000 TL",
        "hafif laptop 35000 TL", "dizüstü bilgisayar RTX 4050", "notebook 45000 TL",
    ],
    "desktop": [
        "60000 TL gaming PC", "RTX 4070 hazır sistem", "AMD Ryzen 7 PC", "Intel i7 masaüstü",
        "oyuncu bilgisayarı 80000 TL", "RTX 4060 Ti sistem", "iş istasyonu 50000 TL",
        "content creator PC", "streaming PC setup", "budget gaming PC 40000 TL",
    ],
    "telefon": [
        "iPhone 15 Pro", "Samsung Galaxy S24", "25000 TL akıllı telefon", "Google Pixel 8",
        "iPhone 14", "Samsung A55", "Xiaomi 14", "kamerası iyi telefon",
        "gaming telefon", "bütçe dostu telefon 15000 TL",
    ]
}

# Trend analizi için dinamik sorgular
TRENDING_QUERIES = [
    "RTX 4090 laptop", "Intel 13th gen laptop", "AMD Ryzen 9 PC", "iPhone 16", "Samsung S25",
    "144Hz gaming laptop", "OLED laptop", "DDR5 RAM PC", "PCIe 5.0 SSD laptop", "WiFi 7 laptop",
]

@celery_app.task(bind=True, name="tasks.prefetch_single_query")
def prefetch_single_query(self, query: str, category: str = None):
    """
    Tek bir sorguyu ön yükler ve cache'e kaydeder.
    """
    start_time = time.time()
    try:
        logger.info(f"Ön yükleme başlatıldı: '{query}' (Kategori: {category})")
        
        # Mevcut cache kontrolü
        cached_result = cache.get(query, category)
        if cached_result:
            logger.info(f"'{query}' zaten cache'de mevcut, atlanıyor")
            return {"status": "skipped", "query": query, "reason": "already_cached"}
        
        # Asenkron fonksiyonu doğrudan ve güvenli bir şekilde asyncio.run() ile çalıştır
        candidates = asyncio.run(gather_candidates_async(query, count=12))
            
        if candidates:
            # Cache'e kaydet - 2 saat TTL
            cache.set(query, candidates, category, ttl=7200)
            logger.info(f"✅ '{query}' başarıyla ön yüklendi ({len(candidates)} ürün)")
            
            return {
                "status": "success",
                "query": query, 
                "category": category,
                "products_count": len(candidates),
                "execution_time": time.time() - start_time
            }
        else:
            logger.warning(f"⚠️ '{query}' için ürün bulunamadı")
            return {"status": "no_results", "query": query, "category": category}
            
    except Exception as e:
        logger.error(f"❌ '{query}' ön yükleme hatası: {str(e)}")
        return {"status": "error", "query": query, "error": str(e)}

@celery_app.task(bind=True, name="tasks.prefetch_popular_queries")
def prefetch_popular_queries(self):
    """
    Popüler sorguları ön yükler - Saatlik çalışır.
    Deadlock'u önlemek için alt görevleri sıralı olarak çalıştırır.
    """
    logger.info("🚀 Saatlik popüler sorgu ön yüklemesi başlatıldı")
    results = {"successful": 0, "failed": 0, "skipped": 0}
    
    try:
        queries_to_process = []
        for category, query_list in POPULAR_QUERIES.items():
            queries_to_process.extend(
                (query, category) for query in query_list[:5]
            )
        
        # Görevleri paralel değil, sıralı olarak doğrudan çağır
        for query, category in queries_to_process:
            try:
                # .delay() ve .get() yerine doğrudan fonksiyon çağrısı yapıyoruz
                outcome = prefetch_single_query(query, category)
                
                status = outcome.get("status", "error")
                if status == "success":
                    results["successful"] += 1
                elif status == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(f"'{query}' görevi çalıştırılırken hata: {e}")
                results["failed"] += 1
        
        logger.info(f"✅ Saatlik ön yükleme tamamlandı: {results}")
        return results
        
    except Exception as e:
        logger.error(f"❌ Saatlik ön yükleme genel hatası: {str(e)}")
        return {"error": str(e)}

@celery_app.task(bind=True, name="tasks.prefetch_trending_queries")  
def prefetch_trending_queries(self):
    """
    Trend sorguları ön yükler - Günlük çalışır.
    Deadlock'u önlemek için alt görevleri sıralı olarak çalıştırır.
    """
    logger.info("🔥 Günlük trend sorgu ön yüklemesi başlatıldı")
    results = {"successful": 0, "failed": 0, "skipped": 0}
    
    try:
        queries_to_process = TRENDING_QUERIES[:8]
        
        for query in queries_to_process:
            try:
                # .delay() ve .get() yerine doğrudan fonksiyon çağrısı yapıyoruz
                outcome = prefetch_single_query(query)

                status = outcome.get("status", "error")
                if status == "success":
                    results["successful"] += 1
                elif status == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(f"Trend '{query}' görevi çalıştırılırken hata: {e}")
                results["failed"] += 1
        
        logger.info(f"🔥 Günlük trend ön yüklemesi tamamlandı: {results}")
        return results
        
    except Exception as e:
        logger.error(f"❌ Günlük trend ön yüklemesi genel hatası: {str(e)}")
        return {"error": str(e)}


@celery_app.task(bind=True, name="tasks.cleanup_old_cache")
def cleanup_old_cache(self):
    """
    Eski cache verilerini temizler - Günlük çalışır.
    """
    logger.info("🧹 Günlük cache temizliği başlatıldı")
    
    try:
        # Cache modülünün cleanup metodunu çağır
        cleaned_count = cache.cleanup_expired()
        logger.info(f"✅ Cache temizliği tamamlandı: {cleaned_count} eski kayıt silindi")
        
        return {
            "status": "success",
            "cleaned_entries": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"❌ Cache temizliği hatası: {str(e)}")
        return {"error": str(e)}

@celery_app.task(bind=True, name="tasks.health_check")
def health_check(self):
    """
    Celery worker'ın sağlık durumunu kontrol eder.
    """
    try:
        # Basit bir test sorgusu çalıştır
        cache.set("health_check_test", {"timestamp": time.time()}, ttl=60)
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "worker_id": self.request.id
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": time.time()
        }

if __name__ == "__main__":
    celery_app.start()

