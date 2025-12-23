# web_search.py - BUDGET-AWARE VERSION (v5.1.3 - Fallback Enhancement)
# Budget-aware intelligent strategies with FALLBACK mechanism
# 4 strategies, ~15 URLs target, <2min response time
# v5.1.3: Az sonuç varsa otomatik daha genel arama yapar!
import os
import re
import requests
import json
from typing import List, Dict, Any, Optional, Tuple
import time
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from logger import (
    get_logger,
    retry_on_failure,
    handle_errors,
    monitor_performance,
    WebSearchError,
    ValidationError )
    
from budget_strategies import generate_budget_strategies

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = get_logger("web_search")

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
REQUEST_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "8"))
MAX_RETRIES = int(os.getenv("WEB_SEARCH_MAX_RETRIES", "2"))
RATE_LIMIT_DELAY = float(os.getenv("WEB_SEARCH_RATE_LIMIT", "1.2"))

# ============== API KEY ROTATION SYSTEM ==============
# Global state for round-robin API key rotation
_BRAVE_KEYS_CACHE: Optional[List[str]] = None
_CURRENT_KEY_INDEX = 0
_KEY_FAIL_COUNT = {}  # Track failures per key
_LAST_ROTATION_TIME = 0.0
# ====================================================


# ============================================================================
# KATEGORİ TANIMLAMALARI
# ============================================================================

CATEGORY_CONFIG = {
    "laptop": {
        "keywords": ["laptop", "notebook", "dizüstü", "gaming laptop", "ultrabook"],
        "sites": ["hepsiburada.com", "trendyol.com", "amazon.com.tr", "n11.com"],
        "brand_keywords": ["asus", "msi", "acer", "hp", "lenovo", "monster", "casper", "dell", "huawei", "honor"],
        "tech_specs": ["rtx", "gtx", "intel", "amd", "ryzen", "gb ram", "ssd", "core i"],
    },
    "desktop": {
        "keywords": ["masaüstü", "desktop", "gaming pc", "hazır sistem", "oyuncu bilgisayar"],
        "sites": ["gaming.gen.tr", "incehesap.com", "vatanbilgisayar.com", "itopya.com", "gamegaraj.com"],
        "brand_keywords": ["asus", "msi", "corsair", "nzxt", "custom"],
        "tech_specs": ["rtx", "gtx", "intel", "amd", "ryzen", "hazır sistem"],
    },
    "phone": {
        "keywords": ["telefon", "smartphone", "cep telefonu", "akıllı telefon"],
        "sites": ["hepsiburada.com", "trendyol.com", "n11.com", "mediamarkt.com.tr", "amazon.com.tr"],
        "brand_keywords": ["samsung", "apple", "iphone", "xiaomi", "huawei", "oppo", "realme", "redmi", "poco", "oneplus", "google", "pixel", "honor", "vivo"],
        "tech_specs": ["gb", "mp", "mah", "5g", "android", "ios", "amoled"],
        "blacklisted_brands": ["tecno", "infinix", "itel", "wiko"],
        "blacklisted_models": [
            "p10 lite", "p9", "p8",
            "galaxy a10", "galaxy a20", "galaxy a30", "galaxy a40",
            "note 8", "note 9",
            "galaxy s7", "galaxy s8", "galaxy s9",
            "iphone 6", "iphone 7", "iphone 8",
            "redmi 8", "redmi 9a", "redmi 9c",
        ]
    }
}

# ============================================================================
# URL TEMİZLEME VE DÜZELTME
# ============================================================================

def _clean_and_fix_url(url: str, site: str = "") -> Optional[str]:
    """URL temizleme ve düzeltme"""
    if not url:
        return None
    
    url = url.strip()
    
    # Kesik URL kontrolü
    if url.endswith('...') or url.endswith('…') or '...' in url:
        logger.debug(f"❌ Truncated URL rejected: {url[:60]}")
        return None
    
    # Mobil subdomain'i düzelt
    if url.startswith('http://m.') or url.startswith('https://m.'):
        url = url.replace('://m.', '://www.')
        logger.debug(f"🔧 Mobile URL fixed: m. -> www.")
    
    # URL parsing
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.debug(f"❌ URL parse error: {e}")
        return None
    
    # Site-specific URL cleaning
    domain = parsed.netloc.lower()
    
    # Tracking parametrelerini temizle
    if any(site in domain for site in ['teknosa.com', 'trendyol.com', 'n11.com', 'hepsiburada.com', 'vatanbilgisayar.com', 'mediamarkt.com.tr']):
        clean_path = parsed.path.split('?')[0]
        url = f"{parsed.scheme}://{parsed.netloc}{clean_path}"
    
    return url


def _is_valid_url_structure(url: str, site: str) -> bool:
    """URL yapı kontrolü"""
    if not url:
        return False
    
    url_lower = url.lower()
    
    # Kesik URL
    if url.endswith('...') or url.endswith('…'):
        return False
    
    # Site kontrolü
    if site and site not in url_lower:
        return False
    
    # Minimum uzunluk kontrolü
    min_lengths = {
        'teknosa.com': 50,
        'n11.com': 60,
        'vatanbilgisayar.com': 60,
        'hepsiburada.com': 50,
        'trendyol.com': 50,
        'mediamarkt.com.tr': 100,
    }
    
    site_key = next((s for s in min_lengths.keys() if s in url_lower), None)
    if site_key:
        min_len = min_lengths[site_key]
        if len(url) < min_len:
            return False
    elif len(url) < 40:
        return False
    
    # Ürün URL pattern kontrolü
    product_patterns = {
        'teknosa.com': ['-p-'],
        'n11.com': ['/urun/'],
        'trendyol.com': ['/p-', '-p-'],
        'hepsiburada.com': ['/urun/', '-p-'],
        'vatanbilgisayar.com': ['.html'],
        'mediamarkt.com.tr': ['/product/_'],
    }
    
    for site_domain, patterns in product_patterns.items():
        if site_domain in url_lower:
            if not any(pattern in url_lower for pattern in patterns):
                return False
            break
    
    # Kategori/arama sayfası değil
    reject_patterns = [
        '/kategori/', '/category/', '-c-', '/c-',
        '?q=', '?search=', '/sr?', '/s?',
        '/filtrele/', '/kampanyalar/',
        '/y-s', '-y-s',
        'fiyatlari/ozellik-',
    ]
    
    if any(pattern in url_lower for pattern in reject_patterns):
        return False
    
    return True

# ============================================================================
# BÜTÇE ÇIKARMA
# ============================================================================

def _extract_budget(query: str) -> Optional[float]:
    """Sorgudan bütçe çıkarır"""
    clean_query = query.lower()
    
    # Teknik terimleri temizle
    tech_patterns = [
        r'\b(rtx|gtx|rx)\s*[34567][0-9]{2,3}[a-z]*\b',
        r'\bi[3579][\s-]?[0-9]{4,5}[a-z]*\b',
        r'\bryzen\s*[3579][\s-]?[0-9]{4}[a-z]*\b',
        r'\b[0-9]+\s*gb\s*(ram|vram|ssd|storage)\b',
        r'\b[0-9]+\s*mp\s*kamera\b',
        r'\b[0-9]+\s*mah\b'
    ]
    
    for pattern in tech_patterns:
        clean_query = re.sub(pattern, '', clean_query)
    
    # Bütçe pattern'leri
    patterns = [
        (r'(\d+)\s*k(?:\s|$)', 1000),
        (r'(\d+)\s*bin(?:\s|$)', 1000),
        (r'(\d+)[\.,](\d+)\s*(?:tl|lira)', 1000),
        (r'(\d{4,})\s*(?:tl|lira)', 1),
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, clean_query)
        if match:
            try:
                if multiplier == 1000:
                    if '.' in match.group(0) or ',' in match.group(0):
                        val = int(match.group(1)) * 1000 + int(match.group(2))
                    else:
                        val = int(match.group(1)) * multiplier
                else:
                    val = int(match.group(1))
                
                if 1000 <= val <= 500000:
                    logger.debug(f"Budget: {val} TL from '{query}'")
                    return float(val)
            except (ValueError, IndexError):
                continue
    
    return None

# ============================================================================
# KATEGORİ TESPİTİ - v4.6.0 Enhanced
# ============================================================================

def _detect_category(query: str) -> str:
    """
    Gelişmiş kategori tespiti
    v4.6.0: Daha akıllı tespit
    """
    q = query.lower()
    
    # Önce açık belirtilmiş kategorileri kontrol et
    if any(word in q for word in ["laptop", "notebook", "dizüstü"]):
        return "laptop"
    
    if any(word in q for word in ["masaüstü", "desktop", "hazır sistem", "gaming pc"]):
        return "desktop"
    
    if any(word in q for word in ["telefon", "phone", "smartphone", "cep telefonu"]):
        return "phone"
    
    # Marka bazlı tespit - sadece telefon markaları
    phone_only_brands = ["samsung", "xiaomi", "iphone", "oppo", "realme", "poco", "vivo", "honor"]
    if any(brand in q for brand in phone_only_brands):
        if not any(word in q for word in ["laptop", "notebook", "masaüstü", "monitor"]):
            return "phone"
    
    # Özellik bazlı tespit
    if "mah" in q or "mp kamera" in q or "5g" in q or "dual sim" in q:
        return "phone"
    
    if "hazır sistem" in q or ("masaüstü" in q and ("gaming" in q or "rtx" in q)):
        return "desktop"
    
    # GPU tespiti - laptop veya desktop
    if any(word in q for word in ["rtx", "gtx", "gaming"]):
        if "laptop" in q or "notebook" in q:
            return "laptop"
        elif "masaüstü" in q or "pc" in q:
            return "desktop"
        else:
            # GPU var ama kategori belirsiz - laptop varsay
            return "laptop"
    
    logger.info("No clear category, defaulting to laptop")
    return "laptop"

# ============================================================================
# ARAMA STRATEJİLERİ - v4.6.0 ENHANCED (FROM v4_6_0.py)
# ============================================================================

def _build_search_strategies(query: str, category: str, budget: Optional[float]) -> List[Dict[str, str]]:
    """
    v5.0.0 BUDGET-AWARE: Bütçeye göre akıllı stratejiler
    budget_strategies modülü ile entegre - Marka/model spesifik stratejiler
    """
    strategies = []
    
    # Bütçe varsa budget-aware stratejiler kullan
    if budget and budget > 0:
        try:
            # Budget-aware stratejileri al (4 STRATEJİ - optimal dengeli)
            budget_strats = generate_budget_strategies(
                query=query,
                budget=budget,
                category=category.lower(),
                num_strategies=4
            )
            
            # Dict formatına çevir
            for strat_query, priority in budget_strats:
                strategies.append({
                    "query": strat_query,
                    "priority": priority
                })
            
            logger.info(
                f"✅ Budget-aware stratejiler oluşturuldu",
                extra={"strategies_count": len(strategies), "budget": budget, "category": category}
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Budget strategies hatası: {e}, fallback kullanılıyor")
            # Fallback: basit stratejiler
            strategies = _build_fallback_strategies(query, category, budget)
    else:
        # Bütçe yoksa basit stratejiler
        logger.info("ℹ️ Bütçe yok, fallback stratejiler kullanılıyor")
        strategies = _build_fallback_strategies(query, category, budget)
    
    return strategies




def _build_phone_strategies(query: str, budget: Optional[float]) -> List[Dict[str, str]]:
    """
    v5.2.2: TELEFON MARKA-AWARE STRATEJİLER
    iPhone aradıysa Samsung stratejisi üretme!
    """
    strategies = []
    q_lower = query.lower()
    
    # Telefon marka map
    phone_brands = {
        "iphone": "Apple",
        "apple": "Apple",
        "samsung": "Samsung",
        "galaxy": "Samsung",
        "xiaomi": "Xiaomi",
        "redmi": "Xiaomi",
        "poco": "Xiaomi",
        "mi ": "Xiaomi",
        "oppo": "OPPO",
        "realme": "Realme",
        "oneplus": "OnePlus",
        "pixel": "Google",
        "google": "Google",
        "huawei": "Huawei",
        "honor": "Honor",
        "vivo": "Vivo",
        "motorola": "Motorola",
        "moto": "Motorola"
    }
    
    # Marka tespit et (uzun markaları önce)
    detected_brand = None
    brand_keyword = None
    sorted_brands = sorted(phone_brands.keys(), key=len, reverse=True)
    
    for brand_key in sorted_brands:
        if brand_key in q_lower:
            detected_brand = phone_brands[brand_key]
            brand_keyword = brand_key
            logger.info(f"📱 Telefon marka tespit (strateji): '{brand_key}' → {detected_brand}")
            break
    
    # Model tespiti
    model_patterns = {
        "iphone": r'iphone\s*(\d+\s*(?:pro\s*(?:max)?)?)',
        "galaxy": r'galaxy\s*([a-z]\d+)',
        "xiaomi": r'(redmi|poco|mi)\s*(?:note\s*)?\d+',
        "note": r'note\s*\d+',
    }
    
    model_match = None
    for pattern_key, pattern in model_patterns.items():
        match = re.search(pattern, q_lower, re.IGNORECASE)
        if match:
            model_match = match.group(0).strip()
            break
    
    # STRATEJİLER
    if detected_brand and model_match:
        # Marka + Model var (en spesifik)
        strategies.append({"query": f"{model_match}", "priority": "high"})
        strategies.append({"query": f"{model_match} fiyat", "priority": "high"})
        if budget:
            strategies.append({"query": f"{model_match} {int(budget)} tl", "priority": "high"})
            strategies.append({"query": f"{brand_keyword} {int(budget)} tl", "priority": "medium"})
    
    elif detected_brand:
        # Sadece marka var
        strategies.append({"query": f"{brand_keyword} telefon", "priority": "high"})
        if budget:
            strategies.append({"query": f"{brand_keyword} {int(budget)} tl", "priority": "high"})
            strategies.append({"query": f"{int(budget)} tl {brand_keyword}", "priority": "high"})
        strategies.append({"query": f"{brand_keyword} akıllı telefon", "priority": "medium"})
    
    elif model_match:
        # Sadece model var (marka yok)
        strategies.append({"query": f"{model_match}", "priority": "high"})
        strategies.append({"query": f"{model_match} fiyat", "priority": "high"})
        if budget:
            strategies.append({"query": f"{model_match} {int(budget)} tl", "priority": "high"})
    
    else:
        # Genel telefon
        if budget:
            strategies.append({"query": f"{int(budget)} tl telefon", "priority": "medium"})
            strategies.append({"query": f"telefon {int(budget)} tl", "priority": "medium"})
        strategies.append({"query": f"{query} telefon", "priority": "low"})
    
    # Maksimum 4 strateji
    return strategies[:4]



def _build_fallback_strategies(query: str, category: str, budget: Optional[float]) -> List[Dict[str, str]]:
    """Fallback: Basit stratejiler (bütçe yoksa veya hata durumunda)"""
    strategies = []
    q_clean = query.lower()
    
    # GPU tespiti
    gpu = re.search(r'(rtx|gtx|radeon)[\s-]?(\d{4}(?:\s*ti|\s*super)?)', q_clean, re.IGNORECASE)
    
    # Marka tespiti
    if category in CATEGORY_CONFIG:
        brand = re.search(r'\b(' + '|'.join(CATEGORY_CONFIG[category]["brand_keywords"]) + r')\b', q_clean, re.IGNORECASE)
    else:
        brand = None
    
    if category == "laptop":
        if gpu:
            gpu_text = gpu.group(0).strip()
            strategies.append({"query": f"{gpu_text} gaming laptop", "priority": "high"})
            strategies.append({"query": f"{gpu_text} laptop uygun fiyat", "priority": "medium"})
            if budget:
                strategies.append({"query": f"{gpu_text} laptop {int(budget)} tl", "priority": "high"})
                lower = int(budget * 0.85)
                upper = int(budget * 1.15)
                strategies.append({"query": f"{lower} {upper} tl {gpu_text} laptop", "priority": "high"})
        elif brand:
            brand_name = brand.group(0)
            strategies.append({"query": f"{brand_name} gaming laptop", "priority": "high"})
            if budget:
                strategies.append({"query": f"{brand_name} laptop {int(budget)} tl", "priority": "high"})
        else:
            strategies.append({"query": f"gaming laptop", "priority": "medium"})
            if budget:
                strategies.append({"query": f"laptop {int(budget)} tl", "priority": "high"})
    
    elif category == "phone":
        # v5.2.2: Marka-aware telefon stratejileri
        return _build_phone_strategies(query, budget)
    
    elif category == "desktop":
        if gpu:
            gpu_text = gpu.group(0).strip()
            strategies.append({"query": f"hazır sistem {gpu_text}", "priority": "high"})
            strategies.append({"query": f"oem paket {gpu_text}", "priority": "high"})
            strategies.append({"query": f"{gpu_text} gaming pc", "priority": "high"})
            if budget:
                strategies.append({"query": f"{gpu_text} pc {int(budget)} tl", "priority": "high"})
                strategies.append({"query": f"oem {gpu_text} {int(budget)} tl", "priority": "high"})
                lower = int(budget * 0.85)
                upper = int(budget * 1.15)
                strategies.append({"query": f"{lower} {upper} tl hazır sistem {gpu_text}", "priority": "high"})
        else:
            strategies.append({"query": f"gaming pc", "priority": "medium"})
            strategies.append({"query": f"oem paket", "priority": "medium"})
            if budget:
                strategies.append({"query": f"hazır sistem {int(budget)} tl", "priority": "high"})
                strategies.append({"query": f"oem paket {int(budget)} tl", "priority": "high"})
    
    # Fallback'in fallback'i
    if not strategies:
        strategies.append({"query": query, "priority": "medium"})
    
    return strategies


def _build_general_fallback_strategies(query: str, category: str, budget: Optional[float]) -> List[Dict[str, str]]:
    """
    v5.1.3: Çok genel fallback stratejileri
    İlk aramada az sonuç bulunursa kullanılır - marka/model detayı atlanır
    """
    strategies = []
    q_clean = query.lower()
    
    # GPU tespiti
    gpu = re.search(r'(rtx|gtx|radeon)[\s-]?(\d{4}(?:\s*ti|\s*super)?)', q_clean, re.IGNORECASE)
    gpu_text = gpu.group(0).strip() if gpu else None
    
    logger.info(f"🔄 General fallback: category={category}, gpu={gpu_text}, budget={budget}")
    
    if category == "laptop":
        if gpu_text:
            # GPU varsa sadece GPU + laptop
            strategies.append({"query": f"{gpu_text} laptop", "priority": "medium"})
            if budget:
                strategies.append({"query": f"{int(budget)} tl {gpu_text} laptop", "priority": "medium"})
        else:
            # GPU yoksa sadece gaming laptop
            strategies.append({"query": "gaming laptop", "priority": "low"})
            if budget:
                strategies.append({"query": f"{int(budget)} tl gaming laptop", "priority": "medium"})
    
    elif category == "phone":
        # Telefon için genel arama
        if budget:
            strategies.append({"query": f"{int(budget)} tl telefon", "priority": "medium"})
        else:
            strategies.append({"query": "akıllı telefon", "priority": "low"})
    
    elif category == "desktop":
        if gpu_text:
            # GPU varsa sadece GPU + hazır sistem
            strategies.append({"query": f"{gpu_text} hazır sistem", "priority": "medium"})
            strategies.append({"query": f"{gpu_text} oem paket", "priority": "medium"})
            if budget:
                strategies.append({"query": f"{int(budget)} tl {gpu_text} pc", "priority": "medium"})
                strategies.append({"query": f"{int(budget)} tl oem {gpu_text}", "priority": "medium"})
        else:
            # GPU yoksa genel gaming pc
            strategies.append({"query": "gaming pc", "priority": "low"})
            strategies.append({"query": "oem paket", "priority": "low"})
            if budget:
                strategies.append({"query": f"{int(budget)} tl hazır sistem", "priority": "medium"})
                strategies.append({"query": f"{int(budget)} tl oem paket", "priority": "medium"})
    
    return strategies[:2]  # Maksimum 2 genel strateji

# ============================================================================
# İÇERİK FİLTRELEME
# ============================================================================

def _is_accessory(title: str, url: str) -> bool:
    """Aksesuar kontrolü"""
    text = f"{title} {url}".lower()
    
    accessories = [
        'kılıf', 'case', 'çanta', 'bag', 'standı', 'stand',
        'mouse', 'fare', 'klavye', 'keyboard', 'kulaklık', 'headphone',
        'şarj', 'charger', 'adaptör', 'adapter', 'kablo', 'cable',
        'cooler', 'soğutucu', 'fan', 'mousepad', 'pad',
        'temizlik', 'cleaning', 'ekran koruyucu', 'screen protector',
        'sticker', 'çıkartma', 'skin', 'dock'
    ]
    
    return any(acc in text for acc in accessories)


def _is_component(title: str, url: str, category: str) -> bool:
    """
    🔥 YENİ: İşlemci/RAM/SSD/GPU komponent kontrolü
    Laptop/Desktop ararken sadece komponent gelmesin!
    """
    if category not in ["laptop", "desktop"]:
        return False
    
    text = f"{title} {url}".lower()
    
    # 🔥 KONTROL 1: İşlemci keywordleri
    cpu_keywords = [
        'işlemci', 'processor', 'cpu',
        'işlemci (box)', 'işlemci box', 'işlemci tray',
        'socket', 'lga', 'am4', 'am5',  # İşlemci soketleri
    ]
    
    # 🔥 KONTROL 2: Ekran kartı keywordleri (sadece ekran kartı)
    gpu_keywords = [
        'ekran kartı', 'graphics card', 'video card',
        'sadece ekran kartı', 'sadece gpu',
    ]
    
    # 🔥 KONTROL 3: RAM keywordleri (sadece RAM)
    ram_keywords = [
        'sadece ram', 'ram kit', 'bellek kit',
    ]
    
    # 🔥 KONTROL 4: SSD/HDD keywordleri (sadece depolama)
    storage_keywords = [
        'sadece ssd', 'katı hal', 'harddisk',
    ]
    
    # Güvenli kelimeler (bunlar varsa komponent DEĞİL, tam ürün)
    safe_keywords = [
        'li laptop', 'li notebook', 'li gaming', 
        'lü sistem', 'lı sistem', 'lu sistem',
        'laptop', 'notebook', 'hazır sistem', 
        'gaming pc', 'oyuncu bilgisayar',
        'masaüstü', 'desktop'
    ]
    
    # Güvenli kelime varsa komponent değil
    has_safe = any(safe in text for safe in safe_keywords)
    
    # İşlemci kontrolü
    if any(kw in text for kw in cpu_keywords):
        if not has_safe:
            logger.debug(f"🚫 İşlemci komponent red: {title[:60]}")
            return True  # Komponent, red et!
    
    # Sadece GPU kontrolü
    if any(kw in text for kw in gpu_keywords):
        if not has_safe:
            logger.debug(f"🚫 GPU komponent red: {title[:60]}")
            return True
    
    # Sadece RAM kontrolü
    if any(kw in text for kw in ram_keywords):
        if not has_safe:
            logger.debug(f"🚫 RAM komponent red: {title[:60]}")
            return True
    
    # Sadece SSD kontrolü
    if any(kw in text for kw in storage_keywords):
        if not has_safe:
            logger.debug(f"🚫 SSD komponent red: {title[:60]}")
            return True
    
    return False  # Komponent değil, geçerli ürün


def _is_wrong_category(title: str, url: str, target_category: str) -> bool:
    """Yanlış kategori kontrolü"""
    text = f"{title} {url}".lower()
    
    category_indicators = {
        "laptop": ["laptop", "notebook", "dizüstü"],
        "desktop": ["masaüstü", "desktop", "pc", "hazır sistem"],
        "phone": ["telefon", "phone", "smartphone"]
    }
    
    target_indicators = category_indicators.get(target_category, [])
    
    # Hedef kategori göstergesi var mı?
    has_target = any(ind in text for ind in target_indicators)
    
    # Başka kategori göstergesi var mı?
    for cat, indicators in category_indicators.items():
        if cat != target_category:
            if any(ind in text for ind in indicators):
                if not has_target:
                    return True
    
    return False

def _is_blacklisted_phone(title: str, category: str) -> bool:
    """Telefon blacklist kontrolü"""
    if category != "phone":
        return False
    
    title_lower = title.lower()
    config = CATEGORY_CONFIG["phone"]
    
    # Blacklisted brands
    blacklisted_brands = config.get("blacklisted_brands", [])
    if any(brand in title_lower for brand in blacklisted_brands):
        logger.debug(f"Blacklisted brand: {title}")
        return True
    
    # Blacklisted models
    blacklisted_models = config.get("blacklisted_models", [])
    if any(model in title_lower for model in blacklisted_models):
        logger.debug(f"Blacklisted model: {title}")
        return True
    
    return False

def _is_graphics_card(title: str, url: str, category: str) -> bool:
    """Ekran kartı kontrolü - laptop ararken ekran kartı gelmesin"""
    if category != "laptop":
        return False
    
    text = f"{title} {url}".lower()
    
    # Ekran kartı göstergeleri
    gpu_brands = ['geforce', 'radeon', 'rx ', 'gtx', 'rtx']
    
    # Laptop göstergeleri
    laptop_indicators = ['laptop', 'notebook', 'dizüstü', 'taşınabilir']
    
    # Ekran kartı keyword'ü var mı?
    has_gpu_brand = any(brand in text for brand in gpu_brands)
    
    # Laptop keyword'ü var mı?
    has_laptop = any(word in text for word in laptop_indicators)
    
    # Eğer GPU markası var AMA laptop kelimesi yoksa = ekran kartı
    if has_gpu_brand and not has_laptop:
        return True
    
    return False

def _is_valid_product(result: Dict, category: str) -> bool:
    """Ürün geçerlilik kontrolü - Aksesuar, kategori, marka ve URL kontrolü"""
    title = result.get('title', '')
    url = result.get('url', '')
    
    # ============================================================
    # YENİ: AKILLI MARKA/MODEL KONTROLÜ
    # Budget strategies'deki negative keywords ile uyumlu
    # ============================================================
    title_lower = title.lower()
    url_lower = url.lower()
    text = f"{title_lower} {url_lower}"
    
    # Kombinasyon tabanlı engelleme - çok katı değil!
    blacklisted_patterns = [
        # ThinkBook sadece i9 ile birlikte engelle (pahalı kombinasyon)
        (["thinkbook", "i9"], "ThinkBook i9"),
        (["thinkbook", "14900"], "ThinkBook i9-14900"),
        
        # ROG Strix - genelde pahalı model
        (["rog", "strix"], "ROG Strix"),
        
        # Alienware - her zaman pahalı
        (["alienware"], "Alienware"),
        
        # Ultra-9 işlemci - çok pahalı
        (["ultra", "9"], "Intel Ultra 9"),
        (["ultra-9"], "Intel Ultra-9"),
        
        # Çok pahalı GPU kombinasyonları
        (["rtx", "4080"], "RTX 4080"),
        (["rtx4080"], "RTX4080"),
        (["rtx", "4090"], "RTX 4090"),
        (["rtx4090"], "RTX4090"),
        (["rtx", "5070"], "RTX 5070"),
        (["rtx5070"], "RTX5070"),
        (["rtx", "5080"], "RTX 5080"),
        (["rtx5080"], "RTX5080"),
        (["rtx", "5090"], "RTX 5090"),
        (["rtx5090"], "RTX5090"),
    ]
    
    for keywords, pattern_name in blacklisted_patterns:
        if all(keyword in text for keyword in keywords):
            logger.debug(f"Blacklisted pattern: {pattern_name} in {title[:50]}")
            return False
    
    # Aksesuar kontrolü
    if _is_accessory(title, url):
        logger.debug(f"Accessory: {title[:50]}")
        return False
    
    # Ekran kartı kontrolü (laptop ararken)
    if _is_graphics_card(title, url, category):
        logger.debug(f"Graphics card rejected: {title[:50]}")
        return False
    

    # 🔥 YENİ: Komponent kontrolü (işlemci, ram, ssd, gpu)
    if _is_component(title, url, category):
        logger.debug(f"Component rejected: {title[:50]}")
        return False
    
    # Kategori kontrolü
    if _is_wrong_category(title, url, category):
        logger.debug(f"Wrong category: {title[:50]}")
        return False
    
    # Blacklist kontrolü
    if _is_blacklisted_phone(title, category):
        return False
    
    # URL yapı kontrolü
    site = result.get('search_site', '')
    if not _is_valid_url_structure(url, site):
        logger.debug(f"Invalid URL structure: {url[:60]}")
        return False
    
    return True

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Adaptif rate limiter - ilk 5 istek hızlı, sonrası güvenli"""
    def __init__(self, initial_delay: float = 1.5, late_delay: float = 2.5):
        self.initial_delay = initial_delay  # İlk 5 istek için
        self.late_delay = late_delay        # Kalan istekler için
        self.last_time = 0.0
        self.request_count = 0
    
    def wait(self):
        """Gerekirse bekle - istek sayısına göre adaptif delay"""
        # İlk 5 istek hızlı, sonrası yavaş
        current_delay = self.initial_delay if self.request_count < 5 else self.late_delay
        
        now = time.time()
        elapsed = now - self.last_time
        
        if elapsed < current_delay:
            sleep_time = current_delay - elapsed
            time.sleep(sleep_time)
        
        self.last_time = time.time()
        self.request_count += 1
    
    def reset(self):
        """İstek sayacını sıfırla (her query için)"""
        self.request_count = 0

rate_limiter = RateLimiter()

# ============================================================================
# PARALEL ARAMA FONKSİYONU
# ============================================================================

def _search_with_strategies(
    strategies: List[Dict],
    sites: List[str],
    category: str,
    budget: Optional[float],
    target_count: int,
    api_key: str,
    group_name: str = "Group"
) -> List[Dict]:
    """
    Belirli stratejilerle arama yap (paralel arama için)
    Her grup kendi API key'ini kullanır
    """
    logger.info(f"🔍 {group_name}: {len(strategies)} strateji ile arama başlıyor...")
    
    all_results = []
    seen_urls = set()
    
    for strategy_idx, strategy in enumerate(strategies):
        if len(all_results) >= target_count:
            break
        
        search_query = strategy["query"]
        priority = strategy["priority"]
        
        logger.info(f"{group_name} - Strategy {strategy_idx + 1}/{len(strategies)}: '{search_query}' ({priority})")
        
        strategy_found = 0
        
        for site in sites:
            if len(all_results) >= target_count:
                break
            
            try:
                # Bu grup için özel API key kullan
                results = _brave_search(search_query, num=15, site=site, api_key=api_key)
                time.sleep(1.5)  # Rate limit: 1 sorgu/saniye (güvenli)
                
                valid_count = 0
                for result in results:
                    url = result.get('url', '').lower()
                    
                    if url in seen_urls:
                        continue
                    
                    if _is_valid_product(result, category):
                        result.update({
                            'detected_category': category,
                            'extracted_budget': budget,
                            'search_strategy': search_query,
                            'strategy_priority': priority,
                            'search_site': site,
                            'api_group': group_name
                        })
                        all_results.append(result)
                        seen_urls.add(url)
                        valid_count += 1
                        strategy_found += 1
                        
                        if len(all_results) >= target_count:
                            break
                
                if results:
                    logger.debug(f"  {site}: {valid_count}/{len(results)} valid")
            
            except Exception as e:
                logger.warning(f"  {site} failed: {e}")
        
        if strategy_found > 0:
            logger.info(f"  {group_name} Strategy: {strategy_found} products (total: {len(all_results)}/{target_count})")
    
    logger.info(f"✅ {group_name}: {len(all_results)} URL bulundu")
    return all_results

# ============================================================================
# BRAVE API İSTEĞİ
# ============================================================================

def _get_brave_keys() -> Tuple[Optional[str], Optional[str]]:
    """İki Brave API key'i al"""
    key1 = os.getenv("BRAVE_API_KEY")
    key2 = os.getenv("BRAVE_API_KEY_2")
    return key1, key2

def _get_brave_keys() -> List[str]:
    """
    .env'den tüm Brave API key'lerini alır.
    Desteklenen formatlar:
    - BRAVE_API_KEY=key1
    - BRAVE_API_KEY_2=key2
    - BRAVE_API_KEYS=key1,key2,key3 (comma-separated)
    """
    global _BRAVE_KEYS_CACHE
    
    if _BRAVE_KEYS_CACHE is not None:
        return _BRAVE_KEYS_CACHE
    
    keys = []
    
    # Method 1: Comma-separated list
    keys_str = os.getenv("BRAVE_API_KEYS")
    if keys_str:
        keys.extend([k.strip() for k in keys_str.split(",") if k.strip()])
    
    # Method 2: Individual keys (BRAVE_API_KEY, BRAVE_API_KEY_2, ...)
    for i in range(1, 11):  # Support up to 10 keys
        key_name = "BRAVE_API_KEY" if i == 1 else f"BRAVE_API_KEY_{i}"
        key = os.getenv(key_name)
        if key and key not in keys:
            keys.append(key)
    
    if not keys:
        logger.warning("No Brave API keys found in environment variables")
    else:
        logger.info(f"🔑 Loaded {len(keys)} Brave API key(s)")
    
    _BRAVE_KEYS_CACHE = keys
    return keys

def _get_brave_key(rotate_on_fail: bool = False) -> Optional[str]:
    """
    Brave API anahtarını round-robin rotation ile döndürür.
    
    Args:
        rotate_on_fail: True ise başarısız key'den sonraki key'e geç
    
    Returns:
        API key veya None
    """
    global _CURRENT_KEY_INDEX, _KEY_FAIL_COUNT, _LAST_ROTATION_TIME
    
    try:
        keys = _get_brave_keys()
    except Exception as e:
        logger.error(f"Error loading API keys: {e}")
        return None
    
    if not keys:
        return None
    
    # Rotate to next key if requested
    if rotate_on_fail and len(keys) > 1:
        old_index = _CURRENT_KEY_INDEX
        _CURRENT_KEY_INDEX = (_CURRENT_KEY_INDEX + 1) % len(keys)
        _LAST_ROTATION_TIME = time.time()
        
        # Track failure for this key
        key_prefix = keys[old_index][:8] if len(keys[old_index]) > 8 else keys[old_index]
        _KEY_FAIL_COUNT[key_prefix] = _KEY_FAIL_COUNT.get(key_prefix, 0) + 1
        
        logger.info(f"🔄 API key rotation: #{old_index + 1} → #{_CURRENT_KEY_INDEX + 1}/{len(keys)}")
        logger.warning(f"❌ Key #{old_index + 1} failed (total fails: {_KEY_FAIL_COUNT[key_prefix]})")
    
    return keys[_CURRENT_KEY_INDEX]

def get_key_rotation_stats() -> dict:
    """API key rotation istatistiklerini döndürür."""
    try:
        keys = _get_brave_keys()
        return {
            "total_keys": len(keys),
            "current_key_index": _CURRENT_KEY_INDEX,
            "fail_counts": _KEY_FAIL_COUNT,
            "last_rotation_time": _LAST_ROTATION_TIME
        }
    except:
        return {"error": "No keys configured"}

    """Eski kod uyumluluğu için - ilk key'i döndür"""
    return os.getenv("BRAVE_API_KEY")


@retry_on_failure(max_attempts=MAX_RETRIES, delay=1.0, backoff=2.0)
@monitor_performance
def _brave_search(query: str, num: int = 15, site: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict]:
    """Brave API isteği - API key parametresi ile paralel arama destekli"""
    # API key parametresi yoksa, ilk key'i kullan
    brave_key = api_key or _get_brave_key()
    if not brave_key:
        raise WebSearchError("BRAVE_API_KEY not configured")
    
    # Site spesifik sorgu
    if site:
        search_query = f"site:{site} {query}"
    else:
        search_query = query
    
    params = {
        "q": search_query,
        "count": num,
        "safesearch": "off",
        "country": "TR"
    }
    
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": brave_key
    }
    
    # NOT: rate_limiter.wait() kaldırıldı - paralel arama için
    # Delay kontrolü _search_with_strategies içinde yapılıyor (time.sleep 1.5s)
    
    try:
        response = requests.get(
            BRAVE_API_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 429:
            logger.warning("Rate limit hit")
            # Rotate to next API key
            _get_brave_key(rotate_on_fail=True)
            raise WebSearchError("Rate limit exceeded")
        
        response.raise_for_status()
        data = response.json()
        
        web_results = data.get("web", {}).get("results", [])
        
        results = []
        for item in web_results:
            url = item.get("url", "")
            if not url:
                continue
            
            # URL temizleme
            original_url = url
            cleaned_url = _clean_and_fix_url(url, site or "")
            
            if not cleaned_url:
                continue
            
            results.append({
                "title": item.get("title", ""),
                "url": cleaned_url,
                "snippet": item.get("description", ""),
                "original_url": original_url if original_url != cleaned_url else None
            })
        
        logger.debug(f"Brave: {len(results)}/{len(web_results)} valid (query: '{search_query[:50]}')")
        return results
    
    except requests.Timeout:
        logger.warning(f"Timeout: {search_query[:50]}")
        return []
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []

# ============================================================================
# ANA ARAMA FONKSİYONU
# ============================================================================

@monitor_performance
@handle_errors(default_return=[], reraise=False)
def search_products_on_web(query: str, count: int = 10, category: Optional[str] = None) -> List[Dict]:
    """
    PARALEL VERSION: 2 Brave API key ile paralel arama
    - Stratejiler 2 gruba bölünür
    - Her grup kendi API key'i ile aynı anda çalışır
    - 2x daha hızlı sonuç!
    - Default: 10 URL (target: ~18 URL topla, en iyi 10'u döndür)
    - category: Opsiyonel kategori parametresi (geçilirse query'den tespit edilmez)
    """
    if not query or not query.strip():
        raise ValidationError("Query cannot be empty")
    
    query = query.strip()
    wanted = max(1, min(30, count))
    
    # Analiz
    budget = _extract_budget(query)
    
    # Kategori geçilmemişse query'den tespit et
    if not category:
        category = _detect_category(query)
    else:
        logger.info(f"🎯 Kategori parametre ile geldi: {category} (query'den tespit edilmedi)")
        
        # Kategori normalize et (Masaüstü → desktop, Telefon → phone, Laptop → laptop)
        category_map = {
            "Masaüstü": "desktop",
            "Laptop": "laptop",
            "Telefon": "phone",
            "masaüstü": "desktop",
            "laptop": "laptop",
            "telefon": "phone",
            "Desktop": "desktop",
            "Phone": "phone"
        }
        category = category_map.get(category, category.lower())
        logger.info(f"📝 Kategori normalize edildi: {category}")
    
    strategies = _build_search_strategies(query, category, budget)
    sites = CATEGORY_CONFIG[category]["sites"]
    
    # Rate limiter'ı sıfırla (yeni query için fresh start)
    rate_limiter.reset()
    
    # API Key'leri al
    key1, key2 = _get_brave_keys()
    
    if not key1:
        raise WebSearchError("BRAVE_API_KEY not configured")
    
    logger.info(
        f"🚀 PARALEL ARAMA: category={category}, budget={budget}, "
        f"strategies={len(strategies)}, sites={len(sites)}, "
        f"api_keys={2 if key2 else 1}"
    )
    
    target_count = int(wanted * 1.8)  # Daha fazla URL topla, sonra filtrele
    
    # İki API key varsa PARALEL arama yap
    if key2 and len(strategies) > 1:
        # Stratejileri 2 gruba böl
        mid = len(strategies) // 2
        group1_strategies = strategies[:mid]
        group2_strategies = strategies[mid:]
        
        logger.info(f"📊 Grup 1: {len(group1_strategies)} strateji (API Key 1)")
        logger.info(f"📊 Grup 2: {len(group2_strategies)} strateji (API Key 2)")
        
        # Paralel çalıştır
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Her grup için ayrı görev
            future1 = executor.submit(
                _search_with_strategies,
                group1_strategies, sites, category, budget, target_count, key1, "Grup 1"
            )
            future2 = executor.submit(
                _search_with_strategies,
                group2_strategies, sites, category, budget, target_count, key2, "Grup 2"
            )
            
            # Sonuçları topla
            results1 = future1.result()
            results2 = future2.result()
        
        # Sonuçları birleştir ve deduplicate et
        all_results = []
        seen_urls = set()
        
        for result in results1 + results2:
            url = result.get('url', '').lower()
            if url not in seen_urls:
                all_results.append(result)
                seen_urls.add(url)
        
        logger.info(f"🎯 Toplam: {len(all_results)} unique URL (Grup 1: {len(results1)}, Grup 2: {len(results2)})")
    
    # Tek API key varsa sıralı arama yap (eski yöntem)
    else:
        logger.info("⚠️ Tek API key - sıralı arama yapılıyor")
        all_results = _search_with_strategies(
            strategies, sites, category, budget, target_count, key1, "Ana Grup"
        )
    
    # v5.1.3: FALLBACK MEKANİZMASI - Az sonuç varsa daha genel arama yap
    min_threshold = max(3, int(wanted * 0.6))  # En az %60 veya 3 ürün
    
    if len(all_results) < min_threshold:
        logger.warning(
            f"⚠️ Az sonuç bulundu: {len(all_results)}/{wanted} "
            f"(minimum: {min_threshold}) - FALLBACK aktif!"
        )
        
        # Daha genel fallback stratejisi oluştur
        fallback_strategies = _build_general_fallback_strategies(query, category, budget)
        
        if fallback_strategies:
            logger.info(f"🔄 FALLBACK: {len(fallback_strategies)} genel strateji deneniyor...")
            
            # Fallback ile ek arama yap (tek grup)
            fallback_results = _search_with_strategies(
                fallback_strategies, sites, category, budget, 
                target_count, key1, "Fallback"
            )
            
            # Yeni sonuçları ekle (duplicate kontrolü)
            seen_urls = {r.get('url', '').lower() for r in all_results}
            added = 0
            
            for result in fallback_results:
                url = result.get('url', '').lower()
                if url not in seen_urls:
                    all_results.append(result)
                    seen_urls.add(url)
                    added += 1
            
            logger.info(f"✅ FALLBACK: {added} yeni ürün eklendi (toplam: {len(all_results)})")
    
    final = all_results[:wanted]
    
    logger.info(f"Search completed: {len(final)} URLs found (target: {wanted}, collected: {len(all_results)})")
    
    return final

# ============================================================================
# HEALTH CHECK
# ============================================================================

def health_check() -> Dict[str, Any]:
    """Sistem durumu"""
    key = _get_brave_key()
    return {
        "api_key_configured": bool(key),
        "api_provider": "Brave Search API",
        "version": "HYBRID (v5.1.3 - Fallback, 4 strategies, <2min)",
        "timeout": REQUEST_TIMEOUT,
        "max_retries": MAX_RETRIES,
        "rate_limit": RATE_LIMIT_DELAY,
        "supported_categories": list(CATEGORY_CONFIG.keys()),
        "improvements": [
            "🔄 v5.1.3 Fallback Enhancement:",
            "  • Az sonuç varsa (<60%) otomatik genel arama",
            "  • _build_general_fallback_strategies fonksiyonu",
            "  • 'ASUS ROG' bulamazsa → 'gaming laptop' arar",
            "  • Spesifik → Genel akıllı fallback",
            "  • Daha fazla ürün, daha yüksek başarı oranı",
            "🚀 v5.1.1 Balanced Optimization:",
            "  • 4 strategies (optimal speed/quality balance)",
            "  • ~15 URL target (count * 1.8)",
            "  • <2 min consistent response time",
            "  • 8-9 ürün garantisi",
            "🔧 v5.1.0 Changes:",
            "  • Rate limit fix (removed global limiter)",
            "  • 1.5s delay between requests",
            "🎯 v4.6.0 Enhanced Strategies:",
            "  • GPU/Marka/Model tespiti",
            "  • Laptop stratejilerinde 'laptop' kelimesi garantili",
            "  • Telefon için özellik bazlı arama (kamera, gaming, 5G)",
            "  • Akıllı kategori tespiti",
            "✅ Core Features:",
            "  • Brave API kullanımı",
            "  • URL temizleme ve validasyon",
            "  • Aksesuar ve yanlış kategori filtresi",
            "  • Paralel arama (2 API keys)"
        ],
        "status": "ready" if key else "missing_api_key"
    }

# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    logger.info("Testing HYBRID web_search.py")
    
    health = health_check()
    print("\n" + "="*80)
    print("HEALTH CHECK:")
    print(json.dumps(health, indent=2, ensure_ascii=False))
    print("="*80)
    
    if health["api_key_configured"]:
        test_queries = [
            ("45000 TL RTX 4060 gaming laptop", "Laptop - GPU + bütçe"),
            ("Xiaomi 40000 TL telefon", "Telefon - marka + bütçe"),
            ("50000 TL hazır sistem rtx 4070", "Masaüstü - GPU + bütçe"),
        ]
        
        for test_query, desc in test_queries:
            print(f"\n{'='*80}")
            print(f"TEST: '{test_query}' ({desc})")
            print("="*80)
            
            try:
                results = search_products_on_web(test_query, count=5)
                
                if results:
                    print(f"\n✅ {len(results)} URL bulundu\n")
                    
                    for i, r in enumerate(results, 1):
                        print(f"{i}. {r.get('title', '')[:70]}")
                        print(f"   {r.get('url', '')}")
                        print(f"   Strategy: {r.get('search_strategy', 'N/A')}")
                        print()
                else:
                    print("\n⚠️ Hiç URL bulunamadı")
            
            except Exception as e:
                print(f"\n❌ Hata: {e}")
                
    else:
        print("\n❌ BRAVE_API_KEY yapılandırılmamış")