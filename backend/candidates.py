# -*- coding: utf-8 -*-
# candidates.py - GÜNCELLENMİŞ (Bütçe Filtreli ve Hız Odaklı v3.0)
from logging import Logger
import time
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from data import products as local_products
import importlib.util
spec = importlib.util.spec_from_file_location("web_search", "web_search.py")
web_search_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web_search_module)
search_products_on_web = web_search_module.search_products_on_web
from normalize import parse_query
from logger import get_logger
from scraper import scrape_product_page
from budget_strategies import generate_budget_strategies
import re
import asyncio
from asyncio import Semaphore
import aiohttp

# Cache modülünü import ediyoruz
from cache import ProductCache

logger = get_logger("candidates")
cache = ProductCache()

# AI filter removed - not used

_last_brave_request_time = 0
_brave_request_lock = asyncio.Lock() 

# --- SABİTLER ---
CONTENT_BLOCKLIST = ["epey.com", "versus.com", "donanimhaber.com", "cimri.com", "akakce.com"]
IRRELEVANT_PRODUCT_KEYWORDS = [
    "soğutucu", "cooling", "cooler", "stand", "mousepad", "mouse pad",
    "kılıf", "çanta", "kablo", "şarj", "adaptör",
    "temizlik", "clean", "koruyucu", "protector", "film",
    "sticker", "çıkartma", "skin"
]
REFURBISHED_KEYWORDS = [
    "yenilenmiş", "refurbished", "ikinci el", "2. el", "teşhir", "outlet"
]
SMART_BRAND_STRATEGY = {
    "laptop": {
        "budget_friendly": ["MSI", "Lenovo", "HP", "Acer"],
        "premium": ["ASUS", "Dell", "Alienware"],
        "gaming_focused": ["MSI", "ASUS ROG", "Lenovo Legion", "HP Omen"]
    },
    "desktop": {
        "budget_friendly": ["MSI", "HP", "Acer"],
        "premium": ["ASUS", "Dell", "Alienware"],
        "gaming_focused": ["MSI", "ASUS", "HP Omen"]
    },
    "telefon": {
        "budget_friendly": ["Xiaomi", "Realme", "Honor"],
        "premium": ["iPhone", "Samsung Galaxy", "Google Pixel"],
        "gaming_focused": ["ASUS ROG", "Red Magic", "Black Shark"]
    }
}
PRICE_BASED_BRAND_PRIORITY = {
    "laptop": {
        (0, 25000): ["MSI", "Lenovo", "HP", "Acer"],
        (25000, 50000): ["MSI", "ASUS TUF", "Lenovo", "HP Omen"],
        (50000, 100000): ["ASUS ROG", "MSI", "Dell", "Alienware"],
        (100000, float('inf')): ["ASUS ROG", "Alienware", "MSI", "Dell"]
    }
}
CATEGORY_SITES = {
    "Laptop": [
        "hepsiburada.com", "trendyol.com", "vatanbilgisayar.com", "incehesap.com",
        "amazon.com.tr", "mediamarkt.com.tr", "n11.com", "itopya.com",
        "gaming.gen.tr", "gamegaraj.com"
    ],
    "Masaüstü": [
        "vatanbilgisayar.com", "incehesap.com", "itopya.com",
        "gaming.gen.tr", "gamegaraj.com", "hepsiburada.com", "trendyol.com",
        "amazon.com.tr", "mediamarkt.com.tr", "n11.com"
    ],
    "Telefon": [
        "hepsiburada.com", "trendyol.com", "vatanbilgisayar.com", "amazon.com.tr",
        "mediamarkt.com.tr", "n11.com"
    ]
}


async def _rate_limited_brave_call(query: str, count: int, category: Optional[str] = None) -> List[Any]:
    """
    Brave API'ye saniyede 1'den fazla istek gönderilmesini engeller.
    category: Opsiyonel kategori parametresi (search_products_on_web'e geçilir)
    """
    global _last_brave_request_time
    
    async with _brave_request_lock:
        now = time.time()
        elapsed = now - _last_brave_request_time
        
        if elapsed < 1.0:
            wait_time = 1.0 - elapsed
            # logger.debug(f"⏱️ Rate limit koruması: {wait_time:.2f}s bekleniyor...")
            await asyncio.sleep(wait_time)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, search_products_on_web, query, count, category)
        
        _last_brave_request_time = time.time()
        
        return result

def _generate_smart_search_queries(original_query: str, parsed_query: Any) -> List[str]:
    """
    v6.0: Budget Strategies entegrasyonu ile akıllı sorgu üretimi
    iPhone Air, MacBook Pro gibi özel modeller için hedefli aramalar
    """
    queries = []
    base_query = original_query.strip()
    category = parsed_query.category
    budget = parsed_query.budget
    
    # 🔥 Budget Strategies kullan (iPhone, MacBook özel stratejileri dahil!)
    if category:
        logger.info(f"🎯 Budget Strategies kullanılıyor: {budget} TL, {category}")
        try:
            # Category'yi budget_strategies formatına çevir
            category_map = {
                "Laptop": "laptop",
                "Telefon": "phone", 
                "Masaüstü": "desktop"
            }
            budget_category = category_map.get(category, category.lower())
            
            # Budget strategies'den akıllı sorgular al
            strategies = generate_budget_strategies(
                query=base_query,
                budget=budget if budget else 0,  # Bütçe yoksa 0
                category=budget_category,
                num_strategies=5
            )
            
            if strategies:
                logger.info(f"✅ Budget Strategies: {len(strategies)} strateji oluşturuldu")
                for strategy_query, priority in strategies:
                    queries.append(strategy_query)
                    logger.debug(f"  [{priority}] {strategy_query}")
                
                # Base query'yi de ekle (güvenlik için)
                if base_query not in queries:
                    queries.insert(0, base_query)
                    
                logger.info(f"🎯 Toplam {len(queries)} sorgu hazır")
                return queries[:5]  # En iyi 5 strateji
        except Exception as e:
            logger.error(f"❌ Budget Strategies hatası: {e}")
            # Hata durumunda eski mantığa düş
    
    # Fallback: Eski mantık (Budget strategies çalışmazsa)
    logger.warning("⚠️ Budget Strategies kullanılamadı, fallback mantığa geçiliyor")
    queries.append(base_query)
    
    if category and category.lower() in SMART_BRAND_STRATEGY:
        brand_groups = SMART_BRAND_STRATEGY[category.lower()]
        if budget:
            target_brands = []
            for price_range, brands in PRICE_BASED_BRAND_PRIORITY.get(category.lower(), {}).items():
                if price_range[0] <= budget <= price_range[1]:
                    target_brands = brands
                    break
            if not target_brands:
                target_brands = brand_groups.get("budget_friendly", [])
        else:
            target_brands = (brand_groups.get("budget_friendly", []) + brand_groups.get("gaming_focused", []))
        
        for brand in target_brands[:3]:
            brand_query = f"{brand} {base_query}".strip()
            if brand_query not in queries:
                queries.append(brand_query)
    
    unique_queries, seen = [], set()
    for q in queries:
        if q.lower() not in seen:
            unique_queries.append(q)
            seen.add(q.lower())
    
    logger.info(f"🎯 Fallback: {len(unique_queries)} farklı sorgu oluşturuldu")
    return unique_queries[:5]

def _dedupe_key(p: Dict[str, Any]) -> str:
    name = (p.get("name") or "").strip().lower()
    brand = (p.get("brand") or "").strip().lower()
    return hashlib.sha1(f"{name}|{brand}".encode("utf-8")).hexdigest()


def _ensure_local_source(p: Dict[str, Any]) -> Dict[str, Any]:
    p_copy = p.copy()
    p_copy["source"] = "local_database"
    return p_copy



def _get_site_priority(category: Optional[str] = None) -> Dict[str, int]:
    """
    Kategoriye göre site öncelik sıralaması
    
    Priority ne kadar düşükse o kadar öncelikli!
    1 = EN ÖNCELİKLİ
    """
    category_lower = category.lower() if category else ""
    
    if category_lower == "laptop":
        return {
            "trendyol.com": 1,
            "hepsiburada.com": 2,
            "amazon.com.tr": 3,
            "incehesap.com": 4,
            "mediamarkt.com.tr": 5,
            "n11.com": 6,
            "gamegaraj.com": 7,
            "vatanbilgisayar.com": 8
        }
    elif category_lower in ["phone", "telefon"]:
        return {
            "trendyol.com": 1,
            "hepsiburada.com": 2,
            "vatanbilgisayar.com": 3,
            "n11.com": 4,
            "amazon.com.tr": 5,
            "incehesap.com": 6,
            "mediamarkt.com.tr": 7
        }
    elif category_lower in ["desktop", "masaüstü"]:
        return {
            "itopya.com": 1,
            "incehesap.com": 2,
            "gaming.gen.tr": 3,
            "gamegaraj.com": 3,
            "vatanbilgisayar.com": 4,
            "trendyol.com": 5,
            "hepsiburada.com": 6,
            "n11.com": 7,
            "amazon.com.tr": 8
        }
    else:
        # Default (genel)
        return {
            "trendyol.com": 1,
            "hepsiburada.com": 2,
            "incehesap.com": 3,
            "amazon.com.tr": 4,
            "n11.com": 5,
            "vatanbilgisayar.com": 6
        }


def _clean_hepsiburada_url(url: str) -> str:
    if 'hepsiburada.com' not in url:
        return url
    if 'HBC' in url and '-p-' not in url:
        parts = url.split('-')
        if len(parts) > 1 and (parts[-1].startswith('HBC') or 'HBCV' in parts[-1]):
            product_id_part = parts[-1].split('?')[0]
            clean_url = '-'.join(parts[:-1]) + f'-p-{product_id_part}'
            return clean_url
    return url


def _log_filtering_decision(product_name: str, reason: str, passed: bool):
    status = "✅ GEÇTİ" if passed else "❌ ELENDİ"
    logger.debug(f"{status}: {product_name[:50]}... | Sebep: {reason}")


def _is_price_reasonable(
    price: Optional[float], 
    budget: Optional[float], 
    tolerance_lower: float = 0.60,  # ESKİ: 0.35 -> YENİ: 0.60 (%60 daha ucuza izin ver)
    tolerance_upper: float = 0.25,  # ESKİ: 0.20 -> YENİ: 0.25
    tolerance: float = None 
) -> bool:
    """
    Fiyatın bütçeye uygun olup olmadığını kontrol eder.
    GÜNCELLEME: Alt limit toleransı %60'a çıkarıldı (Fırsat ürünlerini kaçırmamak için).
    """
    if not budget or not price: 
        return True
    
    try:
        price_f = float(price)
        budget_f = float(budget)
        
        # 60k bütçe için -> 24k'ya kadar inebilsin (M1/M2 Air'leri yakalamak için)
        lower_bound = budget_f * (1 - tolerance_lower)  
        upper_bound = budget_f * (1 + tolerance_upper) 
        
        is_reasonable = lower_bound <= price_f <= upper_bound
        
        return is_reasonable
        
    except (ValueError, TypeError) as e:
        logger.error(f"💰 Fiyat hesaplama hatası: {e}")
        return False


def _scrape_single_url(url_data: Tuple[str, Optional[str], str]) -> Optional[Dict[str, Any]]:
    url, category, query = url_data
    site_priority = _get_site_priority(category)
    site_domain = next((domain for domain in site_priority.keys() if domain in url), "unknown")
    priority = site_priority.get(site_domain, 10)
    
    try:
        cleaned_url = _clean_hepsiburada_url(url)
        # 2dk hedefi için timeout 35 saniyeye ayarlandı
        scraped_data = scrape_product_page(cleaned_url, custom_timeout=35)
        if not scraped_data:
            return None
        
        product_name = scraped_data.get("name", "").strip()
        price = scraped_data.get("price")
        
        if not product_name or len(product_name) < 5 or not price or price < 500:
            return None
        
        scraped_data.update({
            "url": cleaned_url,
            "original_query": query,
            "site_priority": priority,
            "source": f"{scraped_data.get('source', 'unknown')}_scraped"
        })
        
        logger.info(f"✅ Scraping başarılı: {product_name[:40]}... - {price} TL")
        return scraped_data
        
    except Exception as e:
        logger.warning(f"❌ [P{priority}] Scraping hatası ({site_domain}): {str(e)}")
        return None


def _is_relevant_product_enhanced(product_name: str, target_category: Optional[str], original_query: str) -> bool:
    if not product_name or len(product_name.strip()) < 8:
        return False
    
    name_lower, query_lower = product_name.lower(), original_query.lower()
    
    if any(k in name_lower for k in REFURBISHED_KEYWORDS):
        _log_filtering_decision(product_name, "Yenilenmiş ürün", False)
        return False
    
    if any(k in name_lower for k in IRRELEVANT_PRODUCT_KEYWORDS):
        _log_filtering_decision(product_name, "Alakasız ürün anahtar kelimesi", False)
        return False
    
    # GPU kontrolü - SADECE laptop ve desktop için
    gpu_terms = ["rtx", "gtx", "radeon", "nvidia", "amd"]
    if target_category and target_category.lower() in ["laptop", "desktop", "masaüstü"]:
        if any(t in query_lower for t in gpu_terms) and not any(t in name_lower for t in gpu_terms):
            _log_filtering_decision(product_name, "GPU aranıyor ama üründe yok", False)
            return False
    
    # LAPTOP KONTROLÜ
    if target_category and target_category.lower() == "laptop":
        laptop_indicators = ["laptop", "notebook", " nb ", "nb", "dizüstü", "gaming", "inç", "hz", "taşınabilir", "taşınabilir bilgisayar", "portable", "gaming laptop"]
        desktop_indicators = ["masaüstü", "desktop", "hazır sistem", "kasa"]
        
        has_laptop = any(i in name_lower for i in laptop_indicators)
        has_desktop = any(i in name_lower for i in desktop_indicators)
        
        if has_desktop and not has_laptop:
            _log_filtering_decision(product_name, "Laptop aranıyor ama bu bir masaüstü", False)
            return False
        
        if not has_laptop and not any(t in name_lower for t in ["rtx", "gtx", "intel", "amd", "gb"]):
            _log_filtering_decision(product_name, "Laptop sinyali yok", False)
            return False
    
    # TELEFON KONTROLÜ
    elif target_category and target_category.lower() == "telefon":
        phone_indicators = ["telefon", "phone", "akıllı", "cep", "smartphone", "galaxy", "iphone", "xiaomi", "redmi", "poco", "realme", "oppo"]
        non_phone = ["laptop", "tablet", "bilgisayar", "ekran kartı", "masaüstü", "mouse", "klavye"]
        
        has_phone = any(i in name_lower for i in phone_indicators)
        has_non_phone = any(n in name_lower for n in non_phone)
        
        if has_non_phone:
            _log_filtering_decision(product_name, "Telefon aranıyor ama bu telefon değil", False)
            return False
        
        # 🔥 TELEFON MARKA KONTROLÜ (v5.2.1)
        # iPhone aradıysa Samsung gelmemeli!
        phone_brands = {
            "iphone": "apple",
            "apple": "apple",
            "samsung": "samsung",
            "galaxy": "samsung",
            "xiaomi": "xiaomi",
            "redmi": "xiaomi",
            "poco": "xiaomi",
            "mi ": "xiaomi",
            "oppo": "oppo",
            "realme": "realme",
            "oneplus": "oneplus",
            "google pixel": "google",
            "pixel": "google",
            "huawei": "huawei",
            "honor": "honor",
            "vivo": "vivo",
            "motorola": "motorola",
            "moto": "motorola",
            "nokia": "nokia",
            "asus": "asus",
            "sony": "sony",
            "lg": "lg",
            "htc": "htc"
        }
        
        # Sorgudan marka çıkar (uzun markaları önce)
        detected_brand = None
        sorted_brands = sorted(phone_brands.keys(), key=len, reverse=True)
        
        for brand_key in sorted_brands:
            if brand_key in query_lower:
                detected_brand = phone_brands[brand_key]
                logger.debug(f"📱 Marka tespit: '{brand_key}' → {detected_brand}")
                break
        
        # Marka kontrolü
        if detected_brand:
            brand_in_name = False
            
            for brand_key, brand_value in phone_brands.items():
                if brand_value == detected_brand and brand_key in name_lower:
                    brand_in_name = True
                    logger.debug(f"✅ Marka uyumlu: {detected_brand}")
                    break
            
            if not brand_in_name:
                _log_filtering_decision(
                    product_name, 
                    f"Marka uyumsuz: Aranan={detected_brand}", 
                    False
                )
                return False

        if not has_phone:
            # GB/RAM varsa muhtemelen telefon
            if not any(t in name_lower for t in ["gb", "ram", "128", "256", "512"]):
                _log_filtering_decision(product_name, "Telefon sinyali yok", False)
                return False
    
    # DESKTOP KONTROLÜ - Komponent Bazlı Akıllı Algılama
    elif target_category and target_category.lower() in ["desktop", "masaüstü"]:
        # Hazır sistem göstergeleri
        system_keywords = ["hazır sistem", "gaming pc", "oyuncu bilgisayar", "sistem tavsiyesi", "oem paket"]
        
        # Laptop göstergeleri
        laptop_indicators = ["laptop", "notebook", " nb ", "nb", "dizüstü", "taşınabilir", "taşınabilir bilgisayar", "portable", "gaming laptop"]
        
        # Komponent analizi - Hazır sistem mi yoksa sadece ekran kartı mı?
        has_cpu = any(cpu in name_lower for cpu in ["ryzen", "intel", "core i", "core ultra", "threadripper", "xeon"])
        has_gpu = any(gpu in name_lower for gpu in ["rtx", "gtx", "radeon", "geforce"])
        has_ram = any(ram in name_lower for ram in ["gb ram", "gb ddr", "ddr4", "ddr5", "16gb", "32gb"])
        has_storage = any(storage in name_lower for storage in ["ssd", "nvme", "m.2", "tb ssd", "gb ssd"])
        
        # Ekran kartı-only göstergeleri (ağır)
        explicit_gpu_only = any(term in name_lower for term in ["ekran kartı", "graphics card", "vga", "gpu only", "sadece kart"])
        
        # Sistem keyword'ü var mı?
        has_system_keyword = any(kw in name_lower for kw in system_keywords)
        
        # KARAR AĞACI:
        # 1. Laptop ise → RED
        if any(li in name_lower for li in laptop_indicators):
            _log_filtering_decision(product_name, "Desktop aranıyor ama bu laptop", False)
            return False
        
        # 2. Açıkça "ekran kartı" yazıyorsa → RED (sadece sistem keyword'ü varsa geçer)
        if explicit_gpu_only and not has_system_keyword:
            _log_filtering_decision(product_name, "Açıkça sadece ekran kartı olarak işaretli", False)
            return False
        
        # 3. CPU + GPU + RAM + SSD varsa → HAZIR SİSTEM! ✅
        if has_cpu and has_gpu and has_ram and has_storage:
            _log_filtering_decision(product_name, "Komponent analizi: Tam hazır sistem (CPU+GPU+RAM+SSD)", True)
            return True
        
        # 4. Sistem keyword'ü varsa ve en az 2 komponent varsa → HAZIR SİSTEM! ✅
        component_count = sum([has_cpu, has_gpu, has_ram, has_storage])
        if has_system_keyword and component_count >= 2:
            _log_filtering_decision(product_name, f"Sistem keyword + {component_count} komponent var", True)
            return True
        
        # 5. Sadece GPU varsa (CPU/RAM/SSD yok) → Muhtemelen ekran kartı → RED
        if has_gpu and not (has_cpu or has_ram or has_storage):
            _log_filtering_decision(product_name, "Sadece GPU var - ekran kartı olabilir", False)
            return False
        
        # 6. Hiçbir desktop sinyali yoksa → RED
        if not (has_system_keyword or has_cpu or has_gpu):
            _log_filtering_decision(product_name, "Desktop sinyali yok", False)
            return False
    
    # Sorgu kelime örtüşmesi kontrolü (esnek)
    important_words = [w for w in set(query_lower.split()) if len(w) > 3 and w not in ["için", "olan", "fiyat", "civarı", "gaming", "oyuncu"]]
    if len(important_words) > 3 and not any(w in name_lower for w in important_words):
        _log_filtering_decision(product_name, "Sorgu kelimeleriyle örtüşme yok", False)
        return False
    
    _log_filtering_decision(product_name, "Gelişmiş kontrollerden geçti", True)
    return True


def _quality_check_product(product: Dict[str, Any], category: Optional[str]) -> bool:
    name, price = product.get("name", ""), product.get("price", 0)
    min_price = {
        "laptop": 12000,
        "desktop": 15000,
        "masaüstü": 15000,
        "telefon": 3000
    }.get(category.lower() if category else "", 5000)
    
    if not price or price < min_price:
        logger.debug(f"Kalite kontrolü: Çok düşük fiyat {price} < {min_price}")
        return False
    
    if not name or len(name) < 10:
        logger.debug(f"Kalite kontrolü: Çok kısa isim: '{name}'")
        return False
    
    return True


async def _fetch_single_query_async(query: str, semaphore: Semaphore, category: Optional[str] = None):
    """
    Rate limit koruması _rate_limited_brave_call içinde
    category: Opsiyonel kategori parametresi (web search'e geçilir)
    """
    async with semaphore:
        try:
            result = await _rate_limited_brave_call(query, 15, category)
            
            if result:
                logger.info(f"  ✅ '{query}' için {len(result)} sonuç bulundu")
            else:
                logger.info(f"  ❌ '{query}' için sonuç bulunamadı")
            return result
            
        except Exception as e:
            logger.warning(f"  ⚠️ '{query}' araması sırasında hata: {str(e)}")
            return []


async def _run_parallel_searches(smart_queries: List[str], category: Optional[str] = None) -> List[Any]:
    semaphore = Semaphore(1)
    tasks = [_fetch_single_query_async(query, semaphore, category) for query in smart_queries]
    results_from_all_tasks = await asyncio.gather(*tasks)
    return [hit for hit_list in results_from_all_tasks if hit_list for hit in hit_list]


def _fetch_and_filter_web_candidates_parallel(parsed_query: Any) -> List[Dict[str, Any]]:
    query, category = parsed_query.original_query, parsed_query.category
    
    cached_results = cache.get(query, category)
    if cached_results:
        logger.info("Adaylar Redis cache'den başarıyla alındı.")
        return cached_results
    
    logger.info("🚀 Akıllı çoklu arama stratejisi başlatılıyor...", query=query)
    
    try:
        smart_queries = _generate_smart_search_queries(query, parsed_query)
        all_search_hits = asyncio.run(_run_parallel_searches(smart_queries, category))
        
        if not all_search_hits:
            logger.warning("Hiçbir akıllı aramada sonuç bulunamadı")
            return []
        
        logger.info(f"📊 Toplam {len(all_search_hits)} ham sonuç toplandı (Paralel arama ile)")
        
        site_priority = {
            "incehesap.com": 1,
            "hepsiburada.com": 2,
            "mediamarkt.com.tr": 3,
            "itopya.com": 4,
            "gamegaraj.com": 5,
            "gaming.gen.tr": 6,
            "vatanbilgisayar.com": 7,
            "n11.com": 8,
            "trendyol.com": 9,
            "amazon.com.tr": 10
        }
        
        prioritized_urls, seen_urls = [], set()
        for hit in all_search_hits:
            url = hit.get("url", "")
            if not url or url in seen_urls or any(b in url for b in CONTENT_BLOCKLIST):
                continue
            seen_urls.add(url)
            site_domain = next((d for d in site_priority.keys() if d in url), "unknown")
            priority = site_priority.get(site_domain, 15)
            prioritized_urls.append((priority, url, category, query))
        
        prioritized_urls.sort(key=lambda x: x[0])
        
        # Hız için 12 URL'ye sınırla
        urls_to_scrape = [(u, c, q) for _, u, c, q in prioritized_urls[:20]]
        
        if not urls_to_scrape:
            logger.warning("Scraping için geçerli URL bulunamadı")
            return []
        
        logger.info(f"🕷️ Paralel scraping başlıyor: {len(urls_to_scrape)} benzersiz URL (8 worker + erken durma)")
        
        scraped_products, successful_count = [], 0
        # Max workers 8 yapıldı (2dk hedefi için optimize)
        with ThreadPoolExecutor(max_workers=12) as executor:
            future_to_url = {executor.submit(_scrape_single_url, url_data): url_data[0] for url_data in urls_to_scrape}
            try:
                # Timeout 120 saniye yapıldı
                for future in as_completed(future_to_url, timeout=120):
                    try:
                        result = future.result(timeout=45)
                        if result:
                            scraped_products.append(result)
                            successful_count += 1
                            if successful_count >= 8: # 6'dan 8'e çıkarıldı
                                logger.info(f"Erken durma: {successful_count} başarılı sonuç yeterli")
                                for f in future_to_url:
                                    if not f.done():
                                        f.cancel()
                                break
                    except FutureTimeoutError:
                        logger.warning(f"⏱️ URL timeout (45s): {future_to_url[future]}")
                    except Exception as e:
                        logger.debug(f"Future sonucu alınırken hata: {str(e)}")
            except FutureTimeoutError:
                logger.warning("⏱️ Global timeout (120s) - devam ediliyor")
        
        logger.info(f"🎉 Paralel scraping tamamlandı: {len(scraped_products)} ürün ({successful_count} başarılı)")
        
        logger.info(f"🔍 Senkron filtreleme başlıyor: {len(scraped_products)} ürün")
        
        filtered_candidates = []
        for idx, product in enumerate(scraped_products, 1):
            name = product.get("name", "")[:60]
            price = product.get("price", 0)
            
            logger.debug(f"[{idx}/{len(scraped_products)}] İşleniyor: {name}")
            
            if not _is_relevant_product_enhanced(product.get("name", ""), category, query):
                logger.warning(f"  ❌ Relevance failed: {name}")
                continue
            
            if parsed_query.budget and not _is_price_reasonable(price, parsed_query.budget):
                logger.warning(f"  ❌ Budget failed: {name} - {price} TL (Budget: {parsed_query.budget})")
                continue
            
            if not _quality_check_product(product, category):
                logger.warning(f"  ❌ Quality failed: {name}")
                continue
            
            logger.info(f"  ✅ SYNC PASSED: {name} - {price} TL")
            filtered_candidates.append(product)
            # 🔥 MODEL-AWARE FİLTRELEME (iPhone Air, Pro Max gibi spesifik modeller için)
        query_lower = query.lower()
        if "iphone" in query_lower:
            # Kullanıcı spesifik iPhone modeli mi arıyor?
            model_keywords = []
            if "air" in query_lower: 
                model_keywords.append("air")
            if "pro max" in query_lower: 
                model_keywords.extend(["pro max"])
            elif "pro" in query_lower: 
                model_keywords.append("pro")
            if "plus" in query_lower: 
                model_keywords.append("plus")
            
            # Model keyword varsa filtrele
            if model_keywords:
                model_filtered = []
                for product in filtered_candidates:
                    product_name_lower = product.get("name", "").lower()
                    # Model keyword'lerinden biri var mı?
                    if any(keyword in product_name_lower for keyword in model_keywords):
                        model_filtered.append(product)
                    else:
                        logger.debug(f"  ⏭️ Model uyumsuz: {product.get('name', '')[:50]}")
                
                logger.info(f"📱 iPhone model filtresi uygulandı: {len(model_filtered)}/{len(filtered_candidates)} ürün kaldı (Aranan: {model_keywords})")
                filtered_candidates = model_filtered
        
        logger.info(f"✨ Senkron filtreleme sonucu: {len(filtered_candidates)}/{len(scraped_products)} ürün geçti")
        
        if filtered_candidates:
            cache.set(query, filtered_candidates, category)
            logger.info(f"💾 {len(filtered_candidates)} ürün cache'e kaydedildi")
        
        logger.info(f"✨ Akıllı filtreleme sonrası {len(filtered_candidates)} kaliteli ürün")
        return filtered_candidates
        
    except Exception as e:
        logger.error("Akıllı paralel web scraping hatası.", error=str(e), query=query)
        return []


def calculate_product_relevance_enhanced(product: Dict[str, Any], query: str, parsed_query: Any) -> float:
    if not query or not product:
        return 0.0
    
    score, query_lower = 0.0, query.lower().strip()
    product_name_lower = (product.get("name") or "").lower()
    specs_text = " ".join(str(v) for v in (product.get("specs") or {}).values()).lower()
    
    if query_lower in product_name_lower:
        score += 40.0
    
    important_words = [w for w in query_lower.split() if len(w) > 2 and w not in ['için', 'olan', 'fiyat', 'civarı', 'tl', 'laptop']]
    for word in important_words:
        if word in product_name_lower:
            score += 8.0
        elif word in specs_text:
            score += 4.0
    
    gpu_patterns = {
        "rtx 5090": ["rtx 5090", "rtx5090"],
        "rtx 5080": ["rtx 5080", "rtx5080"],
        "rtx 5070": ["rtx 5070", "rtx5070"],
        "rtx 5070 ti": ["rtx 5070 ti", "rtx5070ti", "rtx 5070ti"],
        "rtx 5060 ti": ["rtx 5060 ti", "rtx5060ti", "rtx 5060ti"],
        "rtx 5060": ["rtx 5060", "rtx5060"],
        "rtx 4090": ["rtx 4090", "rtx4090"],
        "rtx 4080": ["rtx 4080", "rtx4080"],
        "rtx 4070 ti": ["rtx 4070 ti", "rtx4070ti", "rtx 4070ti"],
        "rtx 4070": ["rtx 4070", "rtx4070"],
        "rtx 4060 ti": ["rtx 4060 ti", "rtx4060ti", "rtx 4060ti"],
        "rtx 4060": ["rtx 4060", "rtx4060"],
        "rtx 4060ti": ["rtx 4060ti", "rtx4060ti"],
        "rtx 4050": ["rtx 4050", "rtx4050"],
        "rtx 3070": ["rtx 3070", "rtx3070"],
        "rtx 3060": ["rtx 3060", "rtx3060"],
        "rtx 3060 ti": ["rtx 3060 ti", "rtx3060ti", "rtx 3060ti"],
        "rtx 3050": ["rtx 3050", "rtx3050"]
    }
    for gpu_key, gpu_variants in gpu_patterns.items():
        if any(v in query_lower for v in gpu_variants) and any(v in product_name_lower for v in gpu_variants):
            score += 35.0
            break
    
    # 🔥 GELİŞTİRİLMİŞ CPU PATTERNS - Apple Silicon + ARM mobil işlemci desteği
    cpu_patterns = {
        # Intel işlemciler
        "i3": ["i3-", "intel i3", "core i3"],
        "i5": ["i5-", "intel i5", "core i5"],
        "i7": ["i7-", "intel i7", "core i7"],
        "i9": ["i9-", "intel i9", "core i9"],
        
        # AMD Ryzen işlemciler
        "ryzen 3": ["ryzen 3", "r3"],
        "ryzen 5": ["ryzen 5", "r5"],
        "ryzen 7": ["ryzen 7", "r7"],
        "ryzen 9": ["ryzen 9", "r9"],
        
        # 🍎 APPLE SILICON - M1 Serisi
        "m1": ["m1", "apple m1", "m1 chip", " m1 "],
        "m1 pro": ["m1 pro", "apple m1 pro"],
        "m1 max": ["m1 max", "apple m1 max"],
        "m1 ultra": ["m1 ultra", "apple m1 ultra"],
        
        # 🍎 APPLE SILICON - M2 Serisi
        "m2": ["m2", "apple m2", "m2 chip", " m2 "],
        "m2 pro": ["m2 pro", "apple m2 pro"],
        "m2 max": ["m2 max", "apple m2 max"],
        "m2 ultra": ["m2 ultra", "apple m2 ultra"],
        
        # 🍎 APPLE SILICON - M3 Serisi
        "m3": ["m3", "apple m3", "m3 chip", " m3 "],
        "m3 pro": ["m3 pro", "apple m3 pro"],
        "m3 max": ["m3 max", "apple m3 max"],
        "m3 ultra": ["m3 ultra", "apple m3 ultra"],
        
        # 🍎 APPLE SILICON - M4 Serisi (en yeni)
        "m4": ["m4", "apple m4", "m4 chip", " m4 "],
        "m4 pro": ["m4 pro", "apple m4 pro"],
        "m4 max": ["m4 max", "apple m4 max"],
        # Not: M4 Ultra henüz piyasada yok
        
        # 📱 ARM Mobil İşlemciler (Telefon için)
        "snapdragon": ["snapdragon", "qualcomm"],
        "snapdragon 8": ["snapdragon 8", "sd 8"],
        "dimensity": ["dimensity", "mediatek dimensity"],
        "exynos": ["exynos", "samsung exynos"],
        
        # 🍎 Apple Bionic (iPhone için)
        "bionic": ["bionic", "apple bionic"],
        "a15": ["a15", "a15 bionic"],
        "a16": ["a16", "a16 bionic"],
        "a17": ["a17", "a17 pro", "a17 bionic"],
        "a18": ["a18", "a18 pro", "a18 bionic"]
    }
    
    # CPU eşleşme kontrolü + debug logging
    for cpu_key, cpu_variants in cpu_patterns.items():
        if any(v in query_lower for v in cpu_variants) and any(v in product_name_lower for v in cpu_variants):
            score += 15.0
            logger.debug(f"✅ CPU eşleşti: {cpu_key} → +15 puan")
            break
    
    category = parsed_query.category
    if category:
        category_keywords = {
            "laptop": (
                ["laptop", "notebook", "dizüstü"],
                ["masaüstü", "desktop", "ekran kartı", "graphics card"]
            ),
            "desktop": (
                ["masaüstü", "desktop", "hazır sistem", "gaming pc", "oyuncu bilgisayar"],
                ["laptop", "notebook", "ekran kartı", "graphics card", "sadece ekran kartı"]
            ),
            "telefon": (
                ["telefon", "phone", "akıllı telefon", "cep telefonu", "smartphone"],
                ["laptop", "tablet", "bilgisayar", "ekran kartı"]
            )
        }
        if category.lower() in category_keywords:
            pos, neg = category_keywords[category.lower()]
            if any(p in product_name_lower for p in pos) and not any(n in product_name_lower for n in neg):
                score += 20.0
            elif any(n in product_name_lower for n in neg):
                score *= 0.3
        
        # Telefon için özel performans kontrolü (gaming = güçlü telefon)
        if category.lower() == "telefon":
            # Güçlü işlemci kontrolü (Gaming olmasa da performanslı telefonlar)
            powerful_processors = [
                "snapdragon 8", "snapdragon 7 gen 2", "dimensity 9", "dimensity 8200",
                "apple a16", "apple a17", "apple a15","apple a14","snapdragon 888","snapdragon 8 gen 1"
            ]
            # Yüksek refresh rate (oyun için iyi)
            high_refresh = ["120hz", "144hz", "165hz", "90hz"]
            # Flagship seriler (performanslı)
            flagship_series = [
                "galaxy s23", "galaxy s24", "xiaomi 13", "xiaomi 14", 
                "poco f", "realme gt", "oneplus 11", "oneplus 12",
                "pixel 8", "iphone 13", "iphone 14", "iphone 15",
                "redmi note 14", "redmi note 13","redmi note 14 ultra"
            ]
            # Özel gaming telefonlar (ekstra bonus)
            dedicated_gaming = ["rog phone", "black shark", "legion", "red magic"]
            
            # Güçlü işlemci varsa bonus
            if any(proc in product_name_lower or proc in specs_text for proc in powerful_processors):
                score += 20.0
            
            # Yüksek refresh rate varsa bonus
            if any(hz in product_name_lower or hz in specs_text for hz in high_refresh):
                score += 10.0
            
            # Flagship serilerden biriyse bonus
            if any(fs in product_name_lower for fs in flagship_series):
                score += 15.0
            
            # Özel gaming telefon ise ekstra bonus (ama zorunlu değil!)
            if any(gp in product_name_lower for gp in dedicated_gaming):
                score += 10.0
        
        # Desktop için komponent bazlı akıllı algılama
        if category.lower() in ["desktop", "masaüstü"]:
            # Sistem keyword'leri
            system_keywords = ["hazır sistem", "gaming pc", "oyuncu bilgisayar", "sistem tavsiyesi", "oem paket"]
            
            # Komponent analizi
            has_cpu = any(cpu in product_name_lower for cpu in ["ryzen", "intel", "core i", "core ultra", "threadripper", "xeon"])
            has_gpu = any(gpu in product_name_lower for gpu in ["rtx", "gtx", "radeon", "geforce"])
            has_ram = any(ram in product_name_lower for ram in ["gb ram", "gb ddr", "ddr4", "ddr5", "16gb", "32gb","16","32","8gb","8","64gb","64"])
            has_storage = any(storage in product_name_lower for storage in ["ssd", "nvme", "m.2", "tb ssd", "gb ssd"])
            
            # Ekran kartı-only göstergeleri
            explicit_gpu_only = any(term in product_name_lower for term in ["ekran kartı", "graphics card", "vga", "gpu only", "sadece kart"])
            
            # Sistem keyword'ü var mı?
            has_system_keyword = any(kw in product_name_lower for kw in system_keywords)
            
            # SKOR HESAPLAMA:
            # 1. CPU + GPU + RAM + SSD = Tam hazır sistem → Bonus!
            component_count = sum([has_cpu, has_gpu, has_ram, has_storage])
            if component_count >= 3:
                score += 25.0  # Tam sistem bonusu
            
            # 2. Sistem keyword'ü varsa → Bonus
            if has_system_keyword:
                score += 20.0
            
            # 3. Açıkça "ekran kartı" yazıyorsa ama sistem keyword'ü yoksa → AĞIR CEZA
            if explicit_gpu_only and not has_system_keyword and component_count < 3:
                score *= 0.05  # %95 ceza - neredeyse elensin
            
            # 4. Sadece GPU varsa (CPU/RAM/SSD yok) → Muhtemelen ekran kartı → Ceza
            elif has_gpu and not (has_cpu or has_ram or has_storage):
                score *= 0.1  # %90 ceza
    
    brand_mapping = {
        "asus": ["asus", "rog", "tuf"],
        "msi": ["msi"]
    }
    for brand_key, brand_variants in brand_mapping.items():
        if brand_key in query_lower and any(v in product_name_lower for v in brand_variants):
            score += 10.0
            break
    
    return min(score, 100.0)


def gather_candidates(query: str, count: int = 10) -> List[Dict[str, Any]]:
    parsed_query = parse_query(query)
    if not parsed_query:
        logger.error(f"Sorgu ayrıştırılamadı: {query}")
        return []
    
    logger.info(f"🎯 Akıllı arama başlatılıyor | Bütçe: {parsed_query.budget} TL | Kategori: {parsed_query.category}")
    
    start_time = time.time()
    web_candidates = _fetch_and_filter_web_candidates_parallel(parsed_query)
    
    category = parsed_query.category
    local_filtered = [p for p in local_products if (p.get("category") or "").lower() == category.lower()] if category else []
    
    # 🔥 Senkron versiyon için düzeltme: Yerel ürünlerde bütçe kontrolü
    local_relevant = []
    for p in local_filtered:
        if not _is_relevant_product_enhanced(p.get("name", ""), category, query):
            continue
            
        # Bütçe kontrolü
        price = p.get("price")
        if parsed_query.budget and price:
            if not _is_price_reasonable(price, parsed_query.budget):
                continue
        
        local_relevant.append(p)
    
    combined = web_candidates + [_ensure_local_source(p) for p in local_relevant]
    seen = set()
    uniq = [p for p in combined if (k := _dedupe_key(p)) not in seen and not seen.add(k)]
    
    sorted_candidates = sorted(uniq, key=lambda p: calculate_product_relevance_enhanced(p, query, parsed_query), reverse=True)
    
    elapsed_time = time.time() - start_time
    logger.info(f"🎉 Akıllı aday toplama tamamlandı ({elapsed_time:.2f}s)", final_count=len(sorted_candidates[:count]))
    
    return sorted_candidates[:count]


# ------------------------------------------------------------------------------------
# YENİ: STREAMING DESTEĞİ İÇİN ASENKRON FONKSİYONLAR
# ------------------------------------------------------------------------------------

async def _fetch_and_filter_web_candidates_parallel_async(parsed_query: Any):
    query, category = parsed_query.original_query, parsed_query.category

    logger.info(f"🔍 Cache kontrolü yapılıyor - Query: '{query[:50]}', Category: '{category}'")

    cached_results = cache.get(query, category)

    if cached_results:
        logger.info(f"⚡ CACHE HIT! {len(cached_results)} ürün cache'den döndürülüyor")
        logger.info(f"📦 Cache'den gelen ürünler: {[p.get('name', 'N/A')[:40] for p in cached_results[:3]]}")
    
    # 🔥 FIX: "complete" event olarak yield et, "cache_hit" değil!
        yield {
            "status": "filtering_complete",  # ← FIXED: Cache HIT için doğru event
            "products": cached_results
        }
        return  # ✅ Artık "complete" event yield edildi, return güvenli

    logger.info(f"❌ CACHE MISS - Web search başlatılıyor...")

    logger.info("🚀 Async akıllı çoklu arama stratejisi başlatılıyor...", query=query)
    yield {"status": "searching_web", "message": "Akıllı sorgularla web araması başlatılıyor..."}

    try:
        smart_queries = _generate_smart_search_queries(query, parsed_query)
        all_search_hits = await _run_parallel_searches(smart_queries, category)

        if not all_search_hits:
            logger.warning("Hiçbir akıllı aramada sonuç bulunamadı (async)")
            yield {"status": "no_results", "message": "Web araması sonuç vermedi."}
            return

        url_count = len(set(hit.get("url", "") for hit in all_search_hits if hit.get("url")))
        logger.info(f"📊 Toplam {len(all_search_hits)} ham sonuç toplandı (Async Paralel arama ile)")
        yield {"status": "scraping_urls", "count": url_count, "message": f"{url_count} potansiyel ürün URL'i bulundu. Detaylar inceleniyor..."}

        site_priority = {
            "incehesap.com": 1,
            "hepsiburada.com": 2,
            "mediamarkt.com.tr": 3,
            "itopya.com": 4,
            "gamegaraj.com": 5,
            "gaming.gen.tr": 6,
            "vatanbilgisayar.com": 7,
            "n11.com": 8,
            "trendyol.com": 9,
            "amazon.com.tr": 10
        }
        
        # URL'leri önceliklendir ve hit bilgilerini sakla
        prioritized_urls, seen_urls, url_to_hit = [], set(), {}
        for hit in all_search_hits:
            url = hit.get("url", "")
            if not url or url in seen_urls or any(b in url for b in CONTENT_BLOCKLIST):
                continue
            seen_urls.add(url)
            site_domain = next((d for d in site_priority.keys() if d in url), "unknown")
            priority = site_priority.get(site_domain, 15)
            prioritized_urls.append((priority, url, category, query))
            # Hit bilgilerini sakla (AI filter için)
            url_to_hit[url] = {
                "url": url,
                "title": hit.get("title", ""),
                "snippet": hit.get("snippet", "")
            }

        prioritized_urls.sort(key=lambda x: x[0])
        
        # Hız için 12 URL
        urls_to_scrape = [(u, c, q) for _, u, c, q in prioritized_urls[:12]]
        
        # Scrape edilecek URL'leri sınırla
        urls_to_scrape = urls_to_scrape[:15]


        logger.info(f"🕷️ Scraping başlatılıyor: {len(urls_to_scrape)} URL (8 paralel worker + erken durma)")

        scraped_products, successful_count = [], 0
        # Max workers 8 yapıldı
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(_scrape_single_url, url_data): url_data[0] for url_data in urls_to_scrape}
            try:
                # Global timeout 120s
                for future in as_completed(future_to_url, timeout=120):
                    try:
                        result = future.result(timeout=35)
                        if result:
                            scraped_products.append(result)
                            successful_count += 1
                            # Erken durma: 8 başarılı ürün yeterli
                            if successful_count >= 8:
                                logger.info(f"⚡ Erken durma: {successful_count} başarılı ürün yeterli")
                                for f in future_to_url:
                                    if not f.done():
                                        f.cancel()
                                break
                    except FutureTimeoutError:
                        logger.warning(f"⏱️ URL timeout (35s): {future_to_url.get(future, 'unknown')}")
                    except Exception as e:
                        logger.debug(f"Scraping error: {str(e)}")
            except FutureTimeoutError:
                logger.warning("⏱️ Global timeout (120s) - devam ediliyor")
        
        logger.info(f"🎉 Paralel scraping tamamlandı: {len(scraped_products)} ürün ({successful_count} başarılı)")

        logger.info(f"🔍 Async filtreleme başlıyor: {len(scraped_products)} ürün")

        filtered_candidates = []
        for idx, product in enumerate(scraped_products, 1):
            name = product.get("name", "")[:60]
            price = product.get("price", 0)

            logger.debug(f"[{idx}/{len(scraped_products)}] İşleniyor: {name}")

            if not _is_relevant_product_enhanced(product.get("name", ""), category, query):
                logger.warning(f"  ❌ Async Relevance failed: {name}")
                continue

            if parsed_query.budget and not _is_price_reasonable(price, parsed_query.budget):
                logger.warning(f"  ❌ Async Budget failed: {name} - {price} TL (Budget: {parsed_query.budget})")
                continue

            if not _quality_check_product(product, category):
                logger.warning(f"  ❌ Async Quality failed: {name}")
                continue

            logger.info(f"  ✅ ASYNC PASSED: {name} - {price} TL")
            filtered_candidates.append(product)

        logger.info(f"✨ Async filtreleme sonucu: {len(filtered_candidates)}/{len(scraped_products)} ürün geçti")

        if filtered_candidates:
            cache.set(query, filtered_candidates, category)
            logger.info(f"💾 {len(filtered_candidates)} ürün cache'e kaydedildi")

        logger.info(f"✨ Akıllı filtreleme sonrası {len(filtered_candidates)} kaliteli ürün (async)")
        yield {"status": "filtering_complete", "products": filtered_candidates, "count": len(filtered_candidates)}
        logger.info(f"🎯 DEBUG: filtering_complete yield edildi! Ürün sayısı: {len(filtered_candidates)}")

    except Exception as e:
        logger.error("Async akıllı paralel web scraping hatası.", error=str(e), query=query)
        yield {"status": "error", "message": f"Arama sırasında hata oluştu: {str(e)}"}


async def gather_candidates_async(query: str, count: int = 10, explicit_budget: Optional[float] = None):
    """
    Async streaming versiyonu - gather_candidates fonksiyonunun
    
    GÜNCELLEME (v5.3): Web-First, Local-Fallback Mantığı
    - Eğer Web sonuçları bulunursa, ÖNCELİK Web sonuçlarınındır.
    - Eğer Web sonuçları bulunamazsa (veya 0 dönerse), Local (yerel) sonuçlar devreye girer.
    """
    parsed_query = parse_query(query)
    if not parsed_query:
        logger.error(f"Sorgu ayrıştırılamadı: {query}")
        yield {"status": "error", "message": "Sorgu ayrıştırılamadı"}
        return

    # Explicit budget varsa onu kullan
    if explicit_budget is not None and explicit_budget > 0:
        logger.info(f"💰 API'den gelen explicit bütçe kullanılıyor: {explicit_budget} TL")
        parsed_query.budget = explicit_budget
    
    logger.info(f"🎯 Async akıllı arama başlatılıyor | Bütçe: {parsed_query.budget} TL | Kategori: {parsed_query.category}")
    
    yield {"status": "query_parsed", "budget": parsed_query.budget, "category": parsed_query.category}

    start_time = time.time()

    # 1. ADIM: Web adaylarını asenkron olarak topla
    web_candidates = []
    async for update in _fetch_and_filter_web_candidates_parallel_async(parsed_query):
        if update.get("status") == "filtering_complete":
            web_candidates = update.get("products", [])
        yield update  # Tüm güncellemeleri yukarı aktar

    # 2. ADIM: Local adayları hazırla (Henüz birleştirme!)
    category = parsed_query.category
    local_filtered = [p for p in local_products if (p.get("category") or "").lower() == category.lower()] if category else []
    
    local_relevant = []
    for p in local_filtered:
        # İsim/Alaka Kontrolü
        if not _is_relevant_product_enhanced(p.get("name", ""), category, query):
            continue
            
        # Bütçe Kontrolü (Local ürünler için)
        price = p.get("price")
        if parsed_query.budget and price:
            if not _is_price_reasonable(price, parsed_query.budget):
                logger.debug(f"💰 Local ürün bütçe dışı elendi: {p.get('name')} ({price} TL)")
                continue
        
        local_relevant.append(p)
    
    # Local adayları kaynak etiketiyle hazırla
    local_candidates_processed = [_ensure_local_source(p) for p in local_relevant]

    # 🔥 KRİTİK DEĞİŞİKLİK: WEB ÖNCELİKLİ MANTIK (WEB-FIRST FALLBACK)
    combined = []
    
    if web_candidates and len(web_candidates) > 0:
        # SENARYO A: Web sonuçları var -> Web'i kullan
        logger.info(f"🌍 Web öncelikli mod: {len(web_candidates)} adet web sonucu bulundu ve kullanılıyor.")
        
        # Opsiyonel Güvenlik: Eğer webden çok az (örn: 3'ten az) sonuç geldiyse, listeyi boş bırakmamak için yerel ile doldur.
        if len(web_candidates) < 3:
             logger.info("⚠️ Web sonuçları az olduğu için (3'ten az) yerel verilerle destekleniyor.")
             combined = web_candidates + local_candidates_processed
        else:
             # Web sonuçları yeterliyse SADECE web sonuçlarını kullan (En güncel veri)
             combined = web_candidates
    else:
        # SENARYO B: Web sonucu yok -> Local devreye girer (Fallback)
        logger.info("🏠 Web sonucu bulunamadı/boş döndü. Yerel veritabanı (Fallback) devreye giriyor.")
        combined = local_candidates_processed

    # 3. ADIM: Birleştirme ve Sıralama
    seen = set()
    # Deduplikasyon (Aynı ürünün hem web hem localde olma ihtimaline karşı)
    uniq = [p for p in combined if (k := _dedupe_key(p)) not in seen and not seen.add(k)]

    # Sırala (Puanlama fonksiyonu artık daha adil çalışacak çünkü listeler karışık değil)
    sorted_candidates = sorted(
        uniq,
        key=lambda p: calculate_product_relevance_enhanced(p, query, parsed_query),
        reverse=True
    )

    elapsed_time = time.time() - start_time
    final_candidates = sorted_candidates[:count]

    logger.info(f"🎉 Async akıllı aday toplama tamamlandı ({elapsed_time:.2f}s)", final_count=len(final_candidates))

    yield {
        "status": "complete",
        "products": final_candidates,
        "count": len(final_candidates),
        "elapsed_time": elapsed_time
    }