# candidates.py - GELİŞTİRİLMİŞ paralel scraping ve filtreleme
import time
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from data import products as local_products
from web_search import search_products_on_web
from normalize import normalize_web_result, parse_query
from utils import normalize_category
from logger import get_logger
from scraper import scrape_product_page
import re

logger = get_logger("candidates")

# Perakendeci domainleri
RETAILER_DOMAINS = [
    "hepsiburada.com", "trendyol.com", "n11.com", "vatanbilgisayar.com",
    "mediamarkt.com.tr", "amazon.com.tr","incehesap.com",
    "itopya.com", "gamegaraj.com", "gaming.gen.tr",
]

CATEGORY_SITES: Dict[str, List[Tuple[str, str]]] = {
    "Telefon": [
        ("trendyol.com", "cep-telefonu"),
        ("hepsiburada.com", "cep-telefonlari"),
    ],
    "Laptop": [
        ("hepsiburada.com", "dizustu-bilgisayar"),
        ("trendyol.com", "laptop"),
    ],
    "Masaüstü": [
        ("itopya.com", "hazir-sistem"),
        ("incehesap.com", "gaming-pc"),
    ],
}

CONTENT_BLOCKLIST = ["epey.com", "versus.com", "donanimhaber.com"]

# Daha az kısıtlayıcı blacklist
IRRELEVANT_PRODUCT_KEYWORDS = [
    "soğutucu", "cooling", "cooler", "stand", "mousepad", "mouse pad",
    "kılıf", "çanta", "kablo", "şarj", "adaptör", 
    "temizlik", "clean", "koruyucu", "protector", "film",
    "sticker", "çıkartma", "skin"
]

# YENİ: Yenilenmiş/ikinci el ürünleri engellemek için anahtar kelimeler
REFURBISHED_KEYWORDS = [
    "yenilenmiş", "refurbished", "ikinci el", "2. el", "teşhir", "outlet"
]

# Ana ürün kategori kontrolü
MAIN_PRODUCT_KEYWORDS = {
    "laptop": ["laptop", "notebook", "bilgisayar", "pc", "gaming", "i5", "i7", "rtx", "gtx"],
    "telefon": ["telefon", "phone", "smartphone", "iphone", "android"],
    "tablet": ["tablet", "ipad"],
    "masaüstü": ["masaüstü", "desktop", "pc", "bilgisayar", "gaming"]
}

# Bellek içi önbellek
_CACHE = {}
CACHE_TIMEOUT_SECONDS = 3600

# Paralel scraping konfigürasyonu
MAX_WORKERS = 4 
SCRAPING_TIMEOUT = 30 
# DEĞİŞİKLİK: Daha fazla URL kazımak için limiti artırdık
MAX_SCRAPE_ATTEMPTS = 15

def _dedupe_key(p: Dict[str, Any]) -> str:
    """Ürünleri isme ve markaya göre tekileştirmek için bir anahtar oluşturur."""
    name = (p.get("name") or "").strip().lower()
    brand = (p.get("brand") or "").strip().lower()
    return hashlib.sha1(f"{name}|{brand}".encode("utf-8")).hexdigest()

def _ensure_local_source(p: Dict[str, Any]) -> Dict[str, Any]:
    """Yerel ürün verisine 'source' ekler."""
    p_copy = p.copy()
    p_copy["source"] = "local_database"
    return p_copy

def _clean_hepsiburada_url(url: str) -> str:
    """
    DÜZELTİLDİ: Daha güvenilir URL temizleme
    """
    if 'hepsiburada.com' not in url:
        return url
    
    if 'HBC' in url:
        if '-p-' not in url:
            parts = url.split('-')
            if len(parts) > 1 and (parts[-1].startswith('HBC') or 'HBCV' in parts[-1]):
                product_id_part = parts[-1].split('?')[0] # Query parametrelerini temizle
                clean_url = '-'.join(parts[:-1]) + f'-p-{product_id_part}'
                logger.debug(f"HB URL temizlendi: {url} -> {clean_url}")
                return clean_url
    
    return url

def _log_filtering_decision(product_name: str, reason: str, passed: bool):
    """Debug için filtreleme kararlarını logla"""
    status = "✅ GEÇTİ" if passed else "❌ ELENDİ"
    logger.debug(f"{status}: {product_name[:50]}... | Sebep: {reason}")

def _is_relevant_product(product_name: str, target_category: str) -> bool:
    """
    GÜNCELLENDİ: Daha akıllı ve çok kategorili kategori kontrolü
    """
    if not product_name:
        return False
    
    name_lower = product_name.lower()
    
    # 1. ADIM (YENİ): Yenilenmiş/İkinci el ürünleri en başta engelle
    for refurbished_keyword in REFURBISHED_KEYWORDS:
        if refurbished_keyword in name_lower:
            _log_filtering_decision(product_name, f"Yenilenmiş ürün: {refurbished_keyword}", False)
            return False
    
    # 2. ADIM: Açık alakasız ürünleri engelle
    for irrelevant_keyword in IRRELEVANT_PRODUCT_KEYWORDS:
        if irrelevant_keyword in name_lower:
            _log_filtering_decision(product_name, f"Alakasız keyword: {irrelevant_keyword}", False)
            return False
    
    # 3. ADIM: Kategori spesifik akıllı kontrol
    if target_category and target_category.lower() == "laptop":
        laptop_positive = ["laptop", "notebook", "gaming", "taşınabilir", "portable"]
        has_laptop_signal = any(signal in name_lower for signal in laptop_positive)
        
        desktop_negative = ["masaüstü", "desktop", "hazır sistem", "gaming pc", "masa üstü"]
        has_desktop_signal = any(signal in name_lower for signal in desktop_negative)
        
        if has_desktop_signal and not has_laptop_signal:
            _log_filtering_decision(product_name, "Masaüstü ürün tespit edildi", False)
            return False
            
        if not has_laptop_signal:
            tech_keywords = ["inc", "inç", "15.6", "14", "17.3", "hz", "taşınabilir"]
            has_laptop_tech = any(keyword in name_lower for keyword in tech_keywords)
            
            if not has_laptop_tech:
                _log_filtering_decision(product_name, "Laptop sinyali bulunamadı", False)
                return False
    
    # YENİ: Masaüstü için daha sıkı kontrol
    elif target_category and target_category.lower() == "masaüstü":
        desktop_positive = ["masaüstü", "desktop", "hazır sistem", "gaming pc", "oyuncu bilgisayarı"]
        has_desktop_signal = any(signal in name_lower for signal in desktop_positive)
        
        laptop_negative = ["laptop", "notebook", "dizüstü", "taşınabilir", "portable", " inç", '"']
        has_laptop_signal = any(signal in name_lower for signal in laptop_negative)

        if has_laptop_signal and not has_desktop_signal:
            _log_filtering_decision(product_name, "Laptop ürün tespit edildi (Masaüstü bekleniyordu)", False)
            return False

    # YENİ: Telefon için daha sıkı kontrol
    elif target_category and target_category.lower() == "telefon":
        phone_positive = ["telefon", "phone", "galaxy", "iphone", "xiaomi", "redmi"]
        has_phone_signal = any(signal in name_lower for signal in phone_positive)
        
        tablet_negative = ["tablet", "ipad", "tab"]
        has_tablet_signal = any(signal in name_lower for signal in tablet_negative)

        if has_tablet_signal and not has_phone_signal:
            _log_filtering_decision(product_name, "Tablet ürün tespit edildi (Telefon bekleniyordu)", False)
            return False
    
    # 4. ADIM: Diğer kategoriler için genel kontrol
    elif target_category and target_category.lower() in MAIN_PRODUCT_KEYWORDS:
        category_keywords = MAIN_PRODUCT_KEYWORDS[target_category.lower()]
        has_main_product = any(keyword in name_lower for keyword in category_keywords)
        
        if not has_main_product:
            tech_keywords = ["gb", "tb", "ssd", "ram", "intel", "amd", "nvidia", "hz", "inc"]
            has_tech_specs = any(keyword in name_lower for keyword in tech_keywords)
            
            if not has_tech_specs:
                _log_filtering_decision(product_name, "Ne kategori ne de teknik özellik", False)
                return False
    
    # 5. ADIM: Minimum uzunluk kontrolü
    if len(product_name.strip()) < 8:
        _log_filtering_decision(product_name, "Çok kısa ürün adı", False)
        return False
    
    _log_filtering_decision(product_name, "Tüm kontrolleri geçti", True)
    return True

def _is_price_reasonable(price: Optional[int], budget: Optional[float], tolerance: float = None) -> bool:
    """
    DÜZELTİLDİ: Dinamik fiyat toleransı - YENİ VE DAHA SIKI KURALLAR
    """
    if not budget or not price:
        return True
    
    if tolerance is None:
        # YENİ MANTIK: Bütçe arttıkça toleransı düşürerek daha isabetli sonuçlar al
        if budget <= 20000:
            tolerance = 0.20  # %20 (örn: 15k için 12k-18k aralığı)
        else:
            tolerance = 0.15  # %15 (örn: 40k için 34k-46k aralığı) -> Daha mantıklı!
    
    lower_bound = budget * (1 - tolerance)
    upper_bound = budget * (1 + tolerance)
    
    is_reasonable = lower_bound <= price <= upper_bound
    
    if not is_reasonable:
        logger.debug(f"Fiyat bütçe dışı: {price} TL (beklenen: {lower_bound:.0f}-{upper_bound:.0f}, tolerans: %{tolerance*100:.0f})")
    
    return is_reasonable

def _scrape_single_url(url_data: Tuple[str, str, str]) -> Optional[Dict[str, Any]]:
    """
    Tek bir URL'yi scrape eden fonksiyon (paralel execution için)
    """
    url, category, query = url_data
    
    try:
        # URL temizleme
        cleaned_url = _clean_hepsiburada_url(url)
        logger.debug(f"Scraping başlatıldı: {cleaned_url}")
        
        # Scraping işlemi
        scraped_data = scrape_product_page(cleaned_url)
        
        # GÜNCELLENDİ: Daha detaylı loglama
        if not scraped_data:
            logger.debug(f"Scraping verisi boş döndü: {cleaned_url}")
            return None

        # URL'i güncelle
        scraped_data["url"] = cleaned_url
        scraped_data["original_query"] = query

        # Temel validasyon
        product_name = scraped_data.get("name") or ""
        price = scraped_data.get("price")
        
        # GÜNCELLENDİ: Hangi verinin eksik olduğunu belirt
        if not product_name:
            logger.debug(f"Eksik veri: Ürün adı bulunamadı. URL: {cleaned_url}")
            return None
        if not price:
            logger.debug(f"Eksik veri: Fiyat bulunamadı. URL: {cleaned_url}")
            return None
        
        logger.info(f"✅ Scraping başarılı: {product_name[:50]}... - {price} TL")
        return scraped_data
        
    except Exception as e:
        logger.warning(f"Scraping hatası {url}: {str(e)}")
        return None

def _fetch_and_filter_web_candidates_parallel(parsed_query: Any) -> List[Dict[str, Any]]:
    """
    DÜZELTİLDİ: Daha akıllı filtreleme ile paralel web scraping
    """
    query = parsed_query.original_query
    category = parsed_query.category
    budget = parsed_query.budget
    
    logger.info("Paralel web scraping başlatılıyor...", query=query)
    
    try:
        # 1. Adım: Web'de arama yapıp URL'leri topla 
        search_query = f"{query} {category or ''}"
        search_hits = search_products_on_web(search_query, count=30) 
        
        if not search_hits:
            logger.warning("Web aramasında sonuç bulunamadı")
            return []

        # 2. Adım: Scraping için URL listesi hazırla
        urls_to_scrape = []
        for hit in search_hits:
            url = hit.get("url")
            if url and not any(b in url for b in CONTENT_BLOCKLIST):
                urls_to_scrape.append((url, category, query))
        
        # Maksimum scrape sayısını sınırla
        urls_to_scrape = urls_to_scrape[:MAX_SCRAPE_ATTEMPTS]
        
        if not urls_to_scrape:
            logger.warning("Scraping için geçerli URL bulunamadı")
            return []
        
        logger.info(f"Paralel scraping başlıyor: {len(urls_to_scrape)} URL")
        
        # 3. Adım: Paralel scraping
        scraped_products = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Tüm scraping görevlerini başlat
            future_to_url = {
                executor.submit(_scrape_single_url, url_data): url_data[0] 
                for url_data in urls_to_scrape
            }
            
            # Sonuçları topla (timeout ile)
            completed_count = 0
            for future in as_completed(future_to_url, timeout=SCRAPING_TIMEOUT):
                completed_count += 1
                url = future_to_url[future]
                
                try:
                    result = future.result()
                    if result:
                        scraped_products.append(result)
                        logger.info(f"✅ [{completed_count}/{len(urls_to_scrape)}] Başarılı: {url}")
                    else:
                        logger.debug(f"❌ [{completed_count}/{len(urls_to_scrape)}] Başarısız: {url}")
                        
                except Exception as e:
                    logger.warning(f"❌ [{completed_count}/{len(urls_to_scrape)}] Hata {url}: {str(e)}")
        
        logger.info(f"Paralel scraping tamamlandı: {len(scraped_products)} ürün bulundu")
        
        # 4. ADIM: DÜZELTİLDİ - Daha akıllı filtreleme
        filtered_candidates = []
        
        for product in scraped_products:
            product_name = product.get("name", "")
            price = product.get("price")
            
            # Filtre 1: Temel alakasızlık kontrolü (akıllı)
            if not _is_relevant_product(product_name, category):
                continue
            
            # Filtre 2: Bütçe kontrolü (dinamik tolerans)
            if budget and not _is_price_reasonable(price, budget):
                continue
            
            # Filtre 3: Minimum kalite kontrolü (esnek)
            min_price = 3000
            if category and category.lower() == "laptop":
                min_price = 8000  # Laptop için biraz daha yüksek
            elif category and category.lower() == "telefon":
                min_price = 2000
                
            if not price or price < min_price:
                logger.debug(f"Minimum fiyat kontrolü eledi: {price} TL < {min_price} TL")
                continue
            
            logger.info(f"✅ Geçerli ürün: {product_name[:60]}... - {price} TL")
            filtered_candidates.append(product)
        
        logger.info(f"Filtreleme sonrası {len(filtered_candidates)} geçerli ürün")
        return filtered_candidates

    except Exception as e:
        logger.error("Paralel web scraping hatası.", error=str(e), query=query)
        return []

def calculate_product_relevance(product: Dict[str, Any], query: str) -> float:
    """
    GÜNCELLENDİ: Puanı 0-100 arasına normalize eder.
    """
    if not query or not product:
        return 0.0
    
    score = 0.0
    query_lower = query.lower().strip()
    product_name_lower = (product.get("name") or "").lower()
    specs_text = " ".join(str(v) for v in (product.get("specs") or {}).values()).lower()
    
    # Temel string matching puanı
    if query_lower in product_name_lower:
        score += 100.0
    
    # Kelime bazlı puanlama (ağırlıklı)
    query_words = set(query_lower.split())
    for word in query_words:
        if len(word) > 2:
            if word in product_name_lower:
                score += 25.0
            if word in specs_text:
                score += 10.0
    
    # Kategori uyumu kontrolü (çok önemli)
    parsed_query = parse_query(query)
    if parsed_query.category and parsed_query.category.lower() == "laptop":
        laptop_indicators = ["laptop", "notebook", "gaming", "taşınabilir", "inc", "inç"]
        desktop_indicators = ["masaüstü", "desktop", "hazır sistem", "gaming pc"]
        
        has_laptop = any(ind in product_name_lower for ind in laptop_indicators)
        has_desktop = any(ind in product_name_lower for ind in desktop_indicators)
        
        if has_desktop and not has_laptop:
            score *= 0.3  # Masaüstü ise puanı düşür
        elif has_laptop:
            score += 40.0  # Laptop ise bonus puan
    
    # GPU/İşlemci puanlaması (geliştirildi)
    gpu_terms = ["rtx", "gtx", "radeon", "intel", "amd", "nvidia", "4060", "4070", "3060", "3070"]
    for gpu in gpu_terms:
        if gpu in query_lower and gpu in product_name_lower:
            score += 40.0
    
    # Marka uyumu
    common_brands = ["msi", "asus", "hp", "acer", "lenovo", "dell", "apple", "samsung", "casper"]
    for brand in common_brands:
        if brand in query_lower and brand in product_name_lower:
            score += 20.0
    
    # Fiyat uyumu (iyileştirildi ve CEZALANDIRMA eklendi)
    price = product.get("price")
    budget_match = re.search(r'(\d+)(?:000|k|bin)', query_lower)
    
    if price and budget_match:
        budget = int(budget_match.group(1)) * 1000
        price_diff = abs(price - budget) / budget
        
        if price > budget * 1.05: # Bütçenin %5'inden fazlaysa
            # Ne kadar uzaksa o kadar cezalandır
            penalty_factor = max(0.1, 1 - (price_diff * 1.5)) # Fark arttıkça ceza artar
            score *= penalty_factor
            logger.debug(f"Fiyat cezası: {product.get('name')[:30]}... Yeni Puan: {score:.2f} (Faktör: {penalty_factor:.2f})")
        elif price <= budget:
            score += 30.0 # Bütçe altı veya eşitse daha fazla bonus puan
        elif price_diff < 0.10: # Bütçenin %10 içindeyse
            score += 15.0

    # Teknik özellik zenginliği
    specs = product.get("specs", {})
    if isinstance(specs, dict) and len(specs) > 5:
        score += 15.0
    
    # YENİ: Puanı 0-100 arasına normalize et
    MAX_SCORE = 250.0
    normalized_score = (min(score, MAX_SCORE) / MAX_SCORE) * 100
    
    return round(normalized_score, 2)

def gather_candidates(query: str, count: int = 10) -> List[Dict[str, Any]]:
    """
    DÜZELTİLDİ: Daha akıllı filtreleme ile paralel scraping
    """
    # Sorguyu en başta analiz et
    parsed_query = parse_query(query)
    category = parsed_query.category
    
    cache_key = f"{query}-{category}"
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        if time.time() - cached["timestamp"] < CACHE_TIMEOUT_SECONDS:
            logger.info("Önbellekten sonuçlar getiriliyor.", query=query)
            return cached["data"][:count]

    start_time = time.time()
    logger.info("Paralel ürün aday arama başlatılıyor.", query=query, category=category)

    # 1) WEB: Paralel scraping ve akıllı filtreleme
    web_candidates = _fetch_and_filter_web_candidates_parallel(parsed_query)
    
    # 2) LOCAL: kategori biliniyorsa daralt, değilse tümünü al
    local_filtered = (
        [p for p in local_products if (p.get("category") or "").lower() == (category or "").lower()]
        if category else list(local_products)
    )
    
    # LOCAL adayları da alakasızlık kontrolünden geçir (akıllı)
    local_relevant = []
    for p in local_filtered:
        if _is_relevant_product(p.get("name", ""), category):
            local_relevant.append(_ensure_local_source(p))
    
    # 3) BİRLEŞTİR + DEDUPE (web öncelikli)
    combined = web_candidates + local_relevant
    seen = set()
    uniq: List[dict] = []
    for p in combined:
        k = _dedupe_key(p)
        if k not in seen:
            uniq.append(p)
            seen.add(k)
    
    # 4) En iyi adayları seç ve sırala
    sorted_candidates = sorted(
        uniq, 
        key=lambda p: calculate_product_relevance(p, query), 
        reverse=True
    )
    
    # 5) Sonuçları önbelleğe kaydet
    _CACHE[cache_key] = {"timestamp": time.time(), "data": sorted_candidates}
    
    # Final log
    elapsed_time = time.time() - start_time
    logger.info(
        f"Paralel aday toplama tamamlandı",
        web_candidates=len(web_candidates),
        local_candidates=len(local_relevant),
        final_count=len(sorted_candidates[:count]),
        elapsed_seconds=f"{elapsed_time:.2f}",
        # Orijinal koddaki bu satırı koruyoruz
        performance_improvement=f"{((40-elapsed_time)/40)*100:.1f}%" if elapsed_time < 40 else "0%"
    )
    
    return sorted_candidates[:count]


if __name__ == "__main__":
    print("\n--- GELİŞTİRİLMİŞ Paralel Scraping Test: '40000 TL civarı RTX 4060 laptop' ---")
    test_query = "40000 TL civarı RTX 4060 laptop"
    
    start_time = time.time()
    candidates = gather_candidates(test_query, count=8) 
    end_time = time.time()
    
    print(f"\n🚀 Toplam süre: {end_time - start_time:.2f} saniye")
    print(f"📊 Bulunan aday sayısı: {len(candidates)}")
    
    if not candidates:
        print("Bu kriterlere uygun aday bulunamadı.")
    else:
        print("\n🎯 En İyi Adaylar:")
        for i, c in enumerate(candidates, 1):
            relevance_score = calculate_product_relevance(c, test_query)
            price = c.get('price', 'N/A')
            source = c.get('source', 'Bilinmiyor')
            name = c.get('name', 'İsimsiz')[:80]
            print(f"{i}. [{source}] {name}")
            # GÜNCELLENDİ: Etiket ve format güncellendi
            print(f"   💰 Fiyat: {price} TL | 🎯 Uygunluk Skoru: {relevance_score:.1f}/100")
            if c.get('url'):
                print(f"   🔗 {c['url']}")
            print()

