# -*- coding: utf-8 -*-
# cache.py - GÜNCELLENMIŞ Redis cache yöneticisi (cleanup fonksiyonları eklendi)

import json
import hashlib
import time
from typing import List, Dict, Any, Optional
import redis
import os
from logger import get_logger

logger = get_logger("cache")

class ProductCache:
    """
    Ürün arama sonuçları için Redis tabanlı cache sistemi.
    Güncellenmiş versiyon: Pre-fetching ve cleanup desteği ile.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Redis bağlantısını başlat.
        
        Args:
            redis_url: Redis bağlantı URL'i. Belirtilmezse ortam değişkeninden alır.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                max_connections=10
            )
            # Bağlantıyı test et
            self.redis_client.ping()
            logger.info(f"Redis bağlantısı başarılı: {self.redis_url}")
            
        except Exception as e:
            logger.error(f"Redis bağlantı hatası: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, query: str, category: Optional[str] = None) -> str:
        """
        Sorgu ve kategoriye göre benzersiz cache anahtarı oluştur.
        
        Args:
            query: Arama sorgusu
            category: Ürün kategorisi (opsiyonel)
            
        Returns:
            str: Cache anahtarı
        """
        # Sorguyu normalize et
        normalized_query = query.lower().strip()
        
        # Kategori varsa ekle
        key_parts = [normalized_query]
        if category:
            key_parts.append(category.lower().strip())
        
        # Hash oluştur
        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode("utf-8")).hexdigest()
        
        return f"product_search:{key_hash}"
    
    def get(self, query: str, category: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        if not self.redis_client:
            logger.warning("Redis bağlantısı yok, cache atlanıyor")
            return None
        
        try:
            cache_key = self._generate_cache_key(query, category)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                parsed_data = json.loads(cached_data)
                
                # Metadata yapısını kontrol et
                if isinstance(parsed_data, dict) and "products" in parsed_data:
                    products = parsed_data["products"]  # ← Sadece products kısmını al
                    logger.info(f"Cache HIT: '{query}' için {len(products)} ürün bulundu")
                    return products
                elif isinstance(parsed_data, list):
                    # Eski format uyumluluğu
                    logger.info(f"Cache HIT (eski format): '{query}' için {len(parsed_data)} ürün bulundu")
                    return parsed_data
                else:
                    logger.warning(f"Cache'de beklenmeyen veri formatı: {type(parsed_data)}")
                    return None
            else:
                logger.debug(f"Cache MISS: '{query}' bulunamadı")
                return None
                
        except Exception as e:
            logger.error(f"Cache GET hatası: {e}")
            return None
    
    def set(self, query: str, products: List[Dict[str, Any]], 
            category: Optional[str] = None, ttl: int = 3600) -> bool:
        """
        Ürün verilerini cache'e kaydet.
        
        Args:
            query: Arama sorgusu
            products: Kaydedilecek ürün listesi
            category: Ürün kategorisi
            ttl: Time-to-live (saniye, varsayılan 1 saat)
            
        Returns:
            bool: İşlem başarılı ise True
        """
        if not self.redis_client:
            logger.warning("Redis bağlantısı yok, cache atlanıyor")
            return False
        
        if not products:
            logger.debug("Boş ürün listesi, cache'e kaydedilmiyor")
            return False
        
        try:
            cache_key = self._generate_cache_key(query, category)
            
            # Metadata ekle
            cache_data = {
                "timestamp": time.time(),
                "query": query,
                "category": category,
                "products": products,
                "count": len(products)
            }
            
            json_data = json.dumps(cache_data, ensure_ascii=False)
            
            # Redis'e kaydet
            success = self.redis_client.setex(cache_key, ttl, json_data)
            
            if success:
                logger.info(f"Cache SET: '{query}' için {len(products)} ürün kaydedildi (TTL: {ttl}s)")
                return True
            else:
                logger.warning(f"Cache SET başarısız: '{query}'")
                return False
                
        except Exception as e:
            logger.error(f"Cache SET hatası: {e}")
            return False
    
    def delete(self, query: str, category: Optional[str] = None) -> bool:
        """
        Belirli bir sorgunun cache'ini sil.
        
        Args:
            query: Arama sorgusu
            category: Ürün kategorisi
            
        Returns:
            bool: Silme işlemi başarılı ise True
        """
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(query, category)
            deleted = self.redis_client.delete(cache_key)
            
            if deleted:
                logger.info(f"Cache DELETE: '{query}' silindi")
                return True
            else:
                logger.debug(f"Cache DELETE: '{query}' bulunamadı")
                return False
                
        except Exception as e:
            logger.error(f"Cache DELETE hatası: {e}")
            return False
    
    def clear_all(self) -> bool:
        """
        Tüm ürün cache'ini temizle.
        
        Returns:
            bool: Temizleme başarılı ise True
        """
        if not self.redis_client:
            return False
        
        try:
            keys = self.redis_client.keys("product_search:*")
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cache CLEAR ALL: {deleted} anahtar silindi")
                return True
            else:
                logger.info("Cache CLEAR ALL: Silinecek anahtar bulunamadı")
                return True
                
        except Exception as e:
            logger.error(f"Cache CLEAR ALL hatası: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Cache istatistiklerini al.
        
        Returns:
            Dict[str, Any]: Cache istatistikleri
        """
        if not self.redis_client:
            return {"error": "Redis bağlantısı yok"}
        
        try:
            keys = self.redis_client.keys("product_search:*")
            total_keys = len(keys)
            
            # Örnek birkaç key'in detaylarını al
            sample_keys = keys[:5] if keys else []
            samples = []
            
            for key in sample_keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        parsed = json.loads(data)
                        samples.append({
                            "key": key,
                            "query": parsed.get("query", "unknown"),
                            "category": parsed.get("category"),
                            "count": parsed.get("count", 0),
                            "timestamp": parsed.get("timestamp", 0)
                        })
                except Exception:
                    continue
            
            return {
                "total_cached_queries": total_keys,
                "samples": samples,
                "redis_info": {
                    "used_memory": self.redis_client.info().get("used_memory_human"),
                    "connected_clients": self.redis_client.info().get("connected_clients")
                }
            }
            
        except Exception as e:
            logger.error(f"Cache stats hatası: {e}")
            return {"error": str(e)}
    
    # YENİ EKLENDİ: Pre-fetching ve cleanup fonksiyonları
    
    def cleanup_expired(self) -> int:
        """
        Süresi dolmuş cache kayıtlarını temizler.
        Redis TTL otomatik olarak yapsa da, bu fonksiyon manuel temizlik için.
        
        Returns:
            int: Temizlenen kayıt sayısı
        """
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys("product_search:*")
            expired_count = 0
            
            for key in keys:
                ttl = self.redis_client.ttl(key)
                # TTL = -2 means key doesn't exist, -1 means no expiration set
                if ttl == -2:
                    expired_count += 1
                elif ttl == -1:
                    # Expiration olmayan eski keyleri kontrol et
                    try:
                        data = self.redis_client.get(key)
                        if data:
                            parsed = json.loads(data)
                            timestamp = parsed.get("timestamp", 0)
                            # 24 saatten eski kayıtları sil
                            if time.time() - timestamp > 86400:
                                self.redis_client.delete(key)
                                expired_count += 1
                    except Exception:
                        # Parse edilemeyen kayıtları da sil
                        self.redis_client.delete(key)
                        expired_count += 1
            
            logger.info(f"Cache cleanup: {expired_count} eski kayıt temizlendi")
            return expired_count
            
        except Exception as e:
            logger.error(f"Cache cleanup hatası: {e}")
            return 0
    
    def get_cache_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Belirli bir pattern'e uyan cache anahtarlarını döndürür.
        
        Args:
            pattern: Redis pattern (örn: "*laptop*")
            
        Returns:
            List[str]: Eşleşen anahtarlar
        """
        if not self.redis_client:
            return []
        
        try:
            keys = self.redis_client.keys(f"product_search:*{pattern}*")
            return keys
        except Exception as e:
            logger.error(f"Pattern search hatası: {e}")
            return []
    
    def bulk_set(self, cache_data: List[Dict[str, Any]], ttl: int = 60) -> int:
        """
        Toplu cache kaydetme işlemi. Pre-fetching için optimize edilmiş.
        
        Args:
            cache_data: [{"query": str, "category": str, "products": list}, ...]
            ttl: Time-to-live saniye
            
        Returns:
            int: Başarıyla kaydedilen kayıt sayısı
        """
        if not self.redis_client or not cache_data:
            return 0
        
        success_count = 0
        
        try:
            # Pipeline kullanarak toplu işlem
            pipe = self.redis_client.pipeline()
            
            for item in cache_data:
                query = item.get("query")
                category = item.get("category")
                products = item.get("products", [])
                
                if not query or not products:
                    continue
                
                cache_key = self._generate_cache_key(query, category)
                cache_entry = {
                    "timestamp": time.time(),
                    "query": query,
                    "category": category,
                    "products": products,
                    "count": len(products)
                }
                
                json_data = json.dumps(cache_entry, ensure_ascii=False)
                pipe.setex(cache_key, ttl, json_data)
                success_count += 1
            
            # Tüm işlemleri execute et
            pipe.execute()
            logger.info(f"Bulk cache SET: {success_count} kayıt toplu olarak kaydedildi")
            return success_count
            
        except Exception as e:
            logger.error(f"Bulk cache SET hatası: {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """
        Cache sisteminin sağlık durumunu kontrol eder.
        
        Returns:
            Dict[str, Any]: Sağlık durumu raporu
        """
        try:
            if not self.redis_client:
                return {
                    "status": "unhealthy",
                    "error": "Redis client not initialized"
                }
            
            # Ping testi
            start_time = time.time()
            self.redis_client.ping()
            ping_time = (time.time() - start_time) * 1000  # ms
            
            # Test write/read
            test_key = "health_check_test"
            test_data = {"timestamp": time.time()}
            self.redis_client.setex(test_key, 60, json.dumps(test_data))
            retrieved = self.redis_client.get(test_key)
            
            if not retrieved:
                return {
                    "status": "unhealthy", 
                    "error": "Write/read test failed"
                }
            
            # İstatistikler
            info = self.redis_client.info()
            
            return {
                "status": "healthy",
                "ping_time_ms": round(ping_time, 2),
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "cache_key_count": len(self.redis_client.keys("product_search:*"))
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
            # BU FONKSİYONU cache.py DOSYASINDAKİ ProductCache SINIFININ İÇİNE EKLEYİN

    def clear_all_product_searches(self) -> int:
        """
        Sadece ürün aramalarıyla ilgili ('product_search:*' ile başlayan) 
        tüm anahtarları Redis'ten siler.
        
        Returns:
            Silinen anahtar sayısı.
        """
        if not self.redis_client:
            logger.warning("Redis bağlantısı yok, temizleme atlanıyor")
            return 0
        
        try:
            # 'product_search:*' kalıbına uyan tüm anahtarları bul.
            # Not: Büyük veritabanları için SCAN daha performanslıdır, 
            # ancak bu proje için KEYS yeterlidir.
            keys_to_delete = self.redis_client.keys("product_search:*")
            
            if not keys_to_delete:
                logger.info("Temizlenecek ürün araması cache'i bulunamadı.")
                return 0
            
            # Bulunan tüm anahtarları tek seferde sil
            deleted_count = self.redis_client.delete(*keys_to_delete)
            
            logger.info(f"{deleted_count} adet ürün araması cache'den temizlendi.")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache temizlenirken hata oluştu: {e}")
            return 0

# Singleton instance
_cache_instance = None

def get_cache() -> ProductCache:
    """Global cache instance'ı döndürür."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ProductCache()
    return _cache_instance
