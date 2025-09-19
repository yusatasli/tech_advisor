# web_search.py - Evrensel Ürün Arama Sistemi (İyileştirilmiş Versiyon)
import os
import re
import requests
import json
from typing import List, Dict, Any, Optional
import math
from typing import Iterable, Tuple
import time

from normalize import parse_query
from scraper import SITE_CONFIG, scrape_product_page

# Import our logging system
from logger import (
    get_logger,
    retry_on_failure,
    handle_errors,
    monitor_performance,
    WebSearchError,
    ValidationError
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Initialize logger
logger = get_logger("web_search")

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
REQUEST_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "8"))
MAX_RETRIES = int(os.getenv("WEB_SEARCH_MAX_RETRIES", "2"))
RATE_LIMIT_DELAY = float(os.getenv("WEB_SEARCH_RATE_LIMIT", "1.1"))

# Ana 3 kategori için arama stratejileri
CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "dizüstü", "gaming laptop", "iş laptopı", "ultrabook"],
    "desktop": ["masaüstü", "desktop", "gaming pc", "bilgisayar", "pc kasa", "workstation", "hazır sistem"],
    "phone": ["telefon", "smartphone", "cep telefonu", "akıllı telefon", "mobile phone"]
}

# Öncelikli siteler - desktop için ayrıldı
DESKTOP_PRIORITY_SITES = [
    "vatanbilgisayar.com",
    "incehesap.com",
    "itopya.com",
    "sinerjibilgisayar.com",
    "gaming.gen.tr",
    "gamegaraj.com"
]

# 3 ana kategori için marka eşleşmeleri
BRAND_MAPPING = {
    "laptop": ["ASUS", "MSI", "Acer", "HP", "Lenovo", "Monster", "Casper", "Dell", "Apple"],
    "desktop": ["ASUS", "MSI", "HP", "Dell", "Corsair", "NZXT", "Alienware"],
    "phone": ["Samsung", "Apple", "Xiaomi", "Huawei", "Oppo", "Realme", "OnePlus", "Google"]
}

# Alakasız sonuçları engellemek için blacklist
SEARCH_RESULT_BLACKLIST = [
    "aksesuarı", "aksesuar", "accessory", "kılıf", "çanta", "kablo",
    "şarj", "adaptör", "temizlik", "koruyucu", "stand", "mousepad"
]

def _detect_product_category(query: str) -> str:
    """
    3 ana kategoriden birini tespit eder: laptop, desktop, phone
    """
    query_lower = query.lower()

    # Öncelikli kategori kelimeleri ara
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                logger.info(f"Category detected: {category} (keyword: {keyword})")
                return category

    # Teknik özelliklerden kategori çıkar
    # GPU belirtilmişse laptop veya desktop olabilir
    if any(spec in query_lower for spec in ["rtx", "gtx", "radeon", "geforce", "nvidia", "amd radeon"]):
        if any(word in query_lower for word in ["laptop", "notebook", "dizüstü"]):
            return "laptop"
        elif any(word in query_lower for word in ["masaüstü", "desktop", "kasa", "pc"]):
            return "desktop"
        else:
            # GPU belirtilmişse muhtemelen gaming için - laptop varsayalım
            return "laptop"

    # CPU özellikleri
    if any(spec in query_lower for spec in ["intel", "amd", "ryzen", "core i"]):
        if any(word in query_lower for word in ["laptop", "notebook", "dizüstü"]):
            return "laptop"
        elif any(word in query_lower for word in ["masaüstü", "desktop", "kasa"]):
            return "desktop"
        else:
            return "laptop"  # Varsayılan laptop

    # RAM/Storage belirtilmişse
    if any(spec in query_lower for spec in ["gb ram", "ssd", "hdd", "nvme"]):
        # Telefon RAM'i genelde daha düşük
        if any(spec in query_lower for spec in ["2gb", "3gb", "4gb", "6gb", "8gb", "12gb", "16gb"]) and "ram" in query_lower:
            if any(brand in query_lower for brand in ["samsung", "apple", "iphone", "xiaomi", "huawei"]):
                return "phone"
        return "laptop"  # Yüksek RAM genelde laptop/desktop

    # Telefon özellikleri
    phone_indicators = ["mp kamera", "mah", "android", "ios", "iphone", "5g", "dual sim", "parmak izi"]
    if any(spec in query_lower for spec in phone_indicators):
        return "phone"

    # Telefon markaları
    phone_brands = ["iphone", "samsung galaxy", "xiaomi", "huawei", "oppo", "realme", "oneplus"]
    if any(brand in query_lower for brand in phone_brands):
        return "phone"

    # Varsayılan kategori - en genel olanı
    logger.info("No specific category detected, defaulting to laptop")
    return "laptop"

def _extract_budget_from_query(query: str) -> Optional[float]:
    """Sorgudan bütçeyi çıkaran fonksiyon - İYİLEŞTİRİLMİŞ: Teknik spec numaralarını daha iyi filtreler"""
    query_lower = query.lower()

    # Önce teknik spec numaralarını filtrele - bunlar bütçe değil!
    tech_patterns = [
        r'\b(rtx|gtx)\s*[34567][0-9]{2,3}[a-z]*\b',  # RTX 4060, GTX 1660 Ti vs
        r'\b(rx|radeon)\s*[3456789][0-9]{2,3}[a-z]*\b',  # RX 6600, Radeon 5700 vs
        r'\bi[3579][\s-]?[0-9]{4,5}[a-z]*\b',  # i5-13400F, i7-12700K vs
        r'\bryzen\s*[3579][\s-]?[0-9]{4}[a-z]*\b'  # Ryzen 5 5600X vs
    ]
    
    temp_query = query_lower
    for pattern in tech_patterns:
        temp_query = re.sub(pattern, '', temp_query)

    # "bin" veya "k" ile ifade edilenleri önce ara
    patterns = [
        r'(\d+)\s*(?:bin|k)\s*(?:tl|lira)',
        r'(\d+)\s*(?:bin|k)(?:\s|$)',
        r'(\d{4,})\s*(?:tl|lira)',
        r'(\d+)\.\d{3}\s*(?:tl|lira)',  # 35.000 TL gibi
    ]

    for pattern in patterns:
        m = re.search(pattern, temp_query)
        if m:
            try:
                value = float(m.group(1))
                if "bin" in pattern or "k" in pattern:
                    value *= 1000

                # Makul bütçe aralığında mı kontrol et
                if 1000 <= value <= 200000:  # 1K-200K TL arası makul
                    logger.info(f"Budget extracted: {value} TL from query: {query}")
                    return value
            except (ValueError, IndexError):
                continue

    logger.debug(f"No budget found in query: {query}")
    return None

def _build_universal_search_strategies(query: str) -> List[str]:
    """
    İYİLEŞTİRİLMİŞ: Daha iyi sıralama ve desktop için tam sistem odaklı stratejiler
    """
    category = _detect_product_category(query)
    strategies = []

    # Temizlenmiş sorgu
    clean_query = re.sub(r'\b(fiyat|civarı|yaklaşık|ortalama|tl|lira)\b', '', query, flags=re.IGNORECASE)
    clean_query = ' '.join(clean_query.split())

    # Regex eşleşmeleri
    gpu_match = re.search(r'(rtx|gtx|radeon)[\s-]?(\d{4}(?:\s*ti|\s*super)?)', query, re.IGNORECASE)
    cpu_match = re.search(r'(i[3579]|ryzen\s*[3579])[\s-]?(\d{4,}[fgkxt]*)', query, re.IGNORECASE)
    brand_match = re.search(r'\b(asus|msi|hp|acer|lenovo|samsung|apple|xiaomi)\b', query, re.IGNORECASE)

    # STRATEJİ SIRALAMASINI İYİLEŞTİR: En spesifikten genele
    
    # 1. En spesifik: Marka + GPU/CPU + Kategori
    if brand_match and (gpu_match or cpu_match) and category in CATEGORY_KEYWORDS:
        component = gpu_match.group(0) if gpu_match else cpu_match.group(0)
        if category == 'desktop':
            strategies.append(f"{brand_match.group(0)} gaming pc {component}")
            strategies.append(f"{brand_match.group(0)} hazır sistem {component}")
        else:
            strategies.append(f"{brand_match.group(0)} {CATEGORY_KEYWORDS[category][0]} {component}")

    # 2. Orjinal temizlenmiş sorgu
    if len(clean_query) > 5:
        strategies.append(clean_query)

    # 3. Desktop için özel tam sistem stratejileri
    if category == 'desktop':
        if gpu_match and cpu_match:
            strategies.append(f"gaming pc {cpu_match.group(0)} {gpu_match.group(0)}")
            strategies.append(f"hazır sistem {cpu_match.group(0)} {gpu_match.group(0)}")
        
        if cpu_match and not any(kw in query.lower() for kw in ["hazır sistem", "gaming pc"]):
            strategies.append(f"hazır sistem {cpu_match.group(0)}")
            strategies.append(f"gaming pc {cpu_match.group(0)}")
        
        if gpu_match:
            strategies.append(f"gaming pc {gpu_match.group(0)}")

    # 4. Genel bileşen kombinasyonları (desktop olmayan kategoriler için)
    elif category in CATEGORY_KEYWORDS:
        if gpu_match:
            strategies.append(f"{CATEGORY_KEYWORDS[category][0]} {gpu_match.group(0)}")
        if cpu_match:
            strategies.append(f"{CATEGORY_KEYWORDS[category][0]} {cpu_match.group(0)}")
        if brand_match:
            strategies.append(f"{brand_match.group(0)} {CATEGORY_KEYWORDS[category][0]}")

    # 5. Fallback: Orijinal sorgu
    if not strategies or len(strategies) == 0:
        strategies.append(query)

    # Benzersiz stratejileri koruyarak sınırla
    unique_strategies = []
    seen = set()
    for strategy in strategies:
        if strategy not in seen and len(strategy.strip()) > 3:
            unique_strategies.append(strategy)
            seen.add(strategy)
    
    final_strategies = unique_strategies[:8]
    logger.info(
        "Generated improved search strategies",
        original_query=query[:50],
        detected_category=category,
        strategies=[s[:60] for s in final_strategies]
    )
    return final_strategies

def _validate_result_relevance(result: Dict[str, Any], expected_category: str = "general") -> bool:
    """
    FİNAL İYİLEŞTİRME: Desktop için çok daha sıkı bileşen filtrelemesi
    """
    title = result.get('title', '').lower()
    url = result.get('url', '').lower()

    # --- KESİN RET KURALLARI ---
    url_blocklist = [
        '/sr?', '?pi=', '/liste/', '/magaza/', '/kategori', '/category',
        '/c-', '-c-', '/brand/', '/marka/', '/y-s', 'pc-toplama', '/tum-urunler',
        '/s/', '/sr/' # Trendyol'un genel arama/filtreleme sayfaları
    ]
    if any(pattern in url for pattern in url_blocklist):
        logger.debug(f"URL blocklist nedeniyle elendi: {url}")
        return False

    title_blocklist = [
        'fiyatları', 'modelleri', 'seçenekleri', 'çeşitleri', 'keşfet',
        'kategorisi', 'listesi', 'koleksiyonu', 'serisi', 'oyun keyfi',
        'ürünlerde hediye', 'tüm ürünler', 'kampanyaları', 'ile tanışın'
    ]
    if any(word in title for word in title_blocklist):
        logger.debug(f"Başlık blocklist nedeniyle elendi: {title}")
        return False

    if any(term in title for term in SEARCH_RESULT_BLACKLIST):
        logger.debug(f"Genel blacklist terimi bulundu: {title}")
        return False

    # FİNAL İYİLEŞTİRME: Kategori Çapraz Kontrolü
    if expected_category == "desktop":
        # Desktop aramasında laptop sonuçlarını ele
        if any(contaminant in title for contaminant in ["laptop", "notebook", "dizüstü"]):
            logger.debug(f"Desktop aramasında Laptop sonucu elendi: {title}")
            return False
        
        # ÇOK SIKILI BILEŞEN FILTRELEMESI - Encoding sorunları için çift kontrol
        only_component_indicators = [
            # Düzgün encoding
            'işlemci fiyati', 'cpu fiyati', 'işlemci incelemesi', 
            'kutulu işlemci', 'tray işlemci', 'box işlemci',
            'işlemci özellikleri', 'cpu özellikleri', 'cpu incelemesi',
            'ekran kartı fiyati', 'gpu fiyati', 'ekran kartı özellikleri',
            # Bozuk encoding versiyonları
            'iÅŸlemci fiyati', 'iÅŸlemci incelemesi', 'kutulu iÅŸlemci', 
            'tray iÅŸlemci', 'box iÅŸlemci', 'iÅŸlemci Ã¶zellikleri',
            'cpu Ã¶zellikleri', 'ekran kartÄ± fiyati', 'ekran kartÄ± Ã¶zellikleri',
            # Diğer bileşen belirteçleri
            'gddr6x', 'nvidia ekran kartı', 'geforce rtx', 'geforce gtx',
            'nvidia ekran kartÄ±', 'fiyatÄ±', 'Ã¶nbellek', 'soket 1700'
        ]
        
        # Eğer sadece bileşen/inceleme belirtileri varsa kesin ret
        if any(indicator in title for indicator in only_component_indicators):
            logger.debug(f"Desktop aramasında sadece bileşen/inceleme elendi: {title}")
            return False
            
        # Tam sistem belirteçleri
        system_indicators = [
            'hazır sistem', 'gaming pc', 'masaüstü bilgisayar', 'desktop pc', 
            'oyuncu bilgisayar', 'gaming bilgisayar', 'tam sistem'
        ]
        
        # Bileşen kelimeleri var ama sistem belirteci yoksa şüpheli
        component_words = ['işlemci', 'cpu', 'ekran kartı', 'gpu']
        has_component_word = any(comp in title for comp in component_words)
        has_system_word = any(sys in title for sys in system_indicators)
        
        # Bileşen var ama sistem yok + URL'de de sistem yok = ret
        if has_component_word and not has_system_word:
            if not any(sys in url for sys in ['hazirsistem', 'gaming-pc', 'bilgisayar', 'sistem']):
                logger.debug(f"Desktop aramasında belirsiz bileşen sonucu elendi: {title}")
                return False
                
    elif expected_category == "laptop":
        # Laptop için ekran kartı filtresi (sadece ekran kartıysa ele)
        if 'ekran kartı' in title and 'laptop' not in title and 'notebook' not in title:
            logger.debug(f"Laptop aramasında sadece ekran kartı elendi: {title}")
            return False
            
        if any(contaminant in title for contaminant in ["masaüstü", "desktop pc", "kasa", "hazır sistem"]):
             logger.debug(f"Laptop aramasında Desktop sonucu elendi: {title}")
             return False

    # --- POZİTİF ONAY KURALLARI ---
    is_likely_product_url = any(pattern in url for pattern in ['-p-hbcv', '-p-', '.html', '/urun/', '/product/'])
    has_specific_details = any([
        re.search(r'\d{4,}[fgkxt]?\b', title), # CPU/GPU model
        re.search(r'\b\d{1,3}\s?(gb|tb)\b', title), # RAM/Depolama
        re.search(r'\b(pro|max|ultra|plus|lite|fe)\b', title) # Telefon modelleri
    ])

    if is_likely_product_url or has_specific_details:
        logger.debug(f"Geçerli ürün bulundu: {title}")
        return True

    logger.debug(f"Yeterli ürün sinyali bulunamadı: {title} | URL: {url}")
    return False

def _get_brave_key() -> Optional[str]:
    """Brave API anahtarını .env dosyasından alır."""
    key = os.getenv("BRAVE_API_KEY")
    if not key:
        logger.warning("Brave API anahtarı 'BRAVE_API_KEY' .env dosyasında bulunamadı.")
    return key

def _validate_search_params(q: str, num: int) -> None:
    """Arama parametrelerini doğrular."""
    if not q or not q.strip():
        raise ValidationError("Arama sorgusu boş olamaz")
    if num < 1 or num > 20:
        raise ValidationError(f"Sonuç sayısı 1-20 arasında olmalı, gelen: {num}")
    if len(q) > 500:
        raise ValidationError(f"Sorgu çok uzun: {len(q)} karakter")

@retry_on_failure(
    max_attempts=MAX_RETRIES,
    delay=RATE_LIMIT_DELAY,
    exceptions=(requests.RequestException, WebSearchError)
)
@monitor_performance
@handle_errors(default_return=[], reraise=False)
def _do_brave_request(q: str, num: int = 5, site: Optional[str] = None) -> List[Dict]:
    """Brave Search API'sine isteği gerçekleştirir."""
    _validate_search_params(q, num)

    brave_key = _get_brave_key()
    if not brave_key:
        raise WebSearchError("Brave API anahtarı yapılandırılmamış.")

    params = {
        "q": q.strip(),
        "count": min(20, max(1, num)),
        "country": "tr",
        "search_lang": "tr",
        "safesearch": "off",
    }

    if site:
        params["q"] = f"{params['q']} site:{site}"
        logger.debug(f"Site-kısıtlı arama", site=site, query=params['q'])

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": brave_key
    }

    try:
        logger.info("Brave Search API isteği yapılıyor", query=params['q'][:100], num=num, site=site)

        time.sleep(RATE_LIMIT_DELAY)

        response = requests.get(
            BRAVE_API_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers=headers
        )

        if response.status_code == 429:
            raise WebSearchError("Brave API rate limit aşıldı", status_code=429)
        elif response.status_code in [401, 403, 422]:
            logger.error("Brave API anahtarı geçersiz veya kota aşıldı", details=response.text)
            raise WebSearchError("Brave API anahtarı geçersiz veya kota aşıldı", status_code=response.status_code)

        response.raise_for_status()
        data = response.json()
        items = data.get("web", {}).get("results", [])

        if not items:
            logger.info("Arama sonucu bulunamadı", query=q, site=site)
            return []

        results = [{"title": i.get("title","").strip(),"url": i.get("url",""),"snippet": i.get("description","").strip()} for i in items if i.get("title") and i.get("url")]

        logger.info("Brave API isteği tamamlandı", query=q[:50], requested=num, returned=len(results), site=site)
        return results

    except requests.exceptions.Timeout:
        raise WebSearchError(f"İstek {REQUEST_TIMEOUT}s sonra zaman aşımına uğradı", timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise WebSearchError(f"HTTP isteği başarısız: {e}", error=str(e))

@monitor_performance
@handle_errors(default_return=[], reraise=False)
def search_products_on_web(
    query: str,
    count: int = 8,
    restrict_sites: Optional[Iterable[Tuple[str, str]]] = None
) -> List[Dict]:
    """
    İYİLEŞTİRİLMİŞ: Evrensel ürün arama - daha iyi strateji sıralaması ve desktop optimizasyonu
    """
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")

    query = query.strip()
    wanted = max(1, min(30, count))
    detected_category = _detect_product_category(query)
    search_strategies = _build_universal_search_strategies(query)

    logger.info(
        "Starting improved universal product search with Brave API",
        original_query=query[:100],
        detected_category=detected_category,
        strategy_count=len(search_strategies),
        wanted_results=wanted
    )

    all_results: List[Dict] = []
    seen_urls = set()

    try:
        # İYİLEŞTİRİLMİŞ: Desktop için özel site sıralaması
        if detected_category == 'desktop':
            priority_sites = DESKTOP_PRIORITY_SITES + [site for site in SITE_CONFIG.keys() if site not in DESKTOP_PRIORITY_SITES]
        else:
            priority_sites = list(SITE_CONFIG.keys())

        for strategy_idx, strategy in enumerate(search_strategies):
            if len(all_results) >= wanted: 
                break
            logger.info(f"Trying improved strategy {strategy_idx + 1}/{len(search_strategies)}: {strategy[:80]}...")

            for site in priority_sites:
                if len(all_results) >= wanted: 
                    break
                try:
                    hits = _do_brave_request(strategy, num=4, site=site)
                    valid_hits_for_site = []
                    for hit in hits:
                        url = hit.get('url', '').lower()
                        if url and url not in seen_urls and _validate_result_relevance(hit, detected_category):
                            hit.update({
                                'search_strategy': strategy_idx + 1,
                                'search_site': site,
                                'detected_category': detected_category,
                                'search_query': strategy
                            })
                            valid_hits_for_site.append(hit)
                            seen_urls.add(url)
                    
                    if valid_hits_for_site:
                        all_results.extend(valid_hits_for_site)
                        logger.info(f"Improved strategy {strategy_idx + 1} found {len(valid_hits_for_site)} valid results from {site}")

                except Exception as e:
                    logger.warning(f"Improved strategy {strategy_idx + 1} failed for {site}: {e}")
        
        final_results = all_results[:wanted]

        logger.info(
            "Improved universal search completed",
            original_query=query[:50],
            detected_category=detected_category,
            strategies_used=len(search_strategies),
            total_found=len(all_results),
            returned=len(final_results)
        )
        return final_results

    except Exception as e:
        logger.error(
            "Improved universal search failed",
            query=query[:100],
            detected_category=detected_category,
            error=str(e),
            error_type=type(e).__name__
        )
        return []

def health_check() -> Dict[str, Any]:
    """Check if web search is properly configured for Brave API"""
    key = _get_brave_key()
    return {
        "api_key_configured": bool(key),
        "api_provider": "Brave Search API",
        "timeout": REQUEST_TIMEOUT,
        "max_retries": MAX_RETRIES,
        "rate_limit_delay": RATE_LIMIT_DELAY,
        "supported_categories": list(CATEGORY_KEYWORDS.keys()),
        "improvements": [
            "Better strategy prioritization",
            "Desktop-specific system filtering", 
            "Enhanced tech spec filtering",
            "Improved URL validation"
        ],
        "status": "ok" if key else "missing_brave_api_key"
    }

# Test fonksiyonu
if __name__ == "__main__":
    logger.info("Testing Improved Universal Product Search with Brave API")

    health = health_check()
    print("Health check:", json.dumps(health, indent=2))

    if health["api_key_configured"]:
        print("\n🧪 Testing improved universal search with different categories...")
        test_queries = [
            "40000 TL civarı RTX 4060 laptop",
            "iPhone 15 128GB fiyat",
            "Samsung Galaxy S24 256GB",
            "Gaming masaüstü RTX 4070 32GB RAM",  # Bu desktop testinde daha iyi sonuç vermeli
            "ASUS ROG laptop RTX 4080",
            "Apple iPhone 14 Pro Max",
            "İ5 13400F masaüstü bilgisayar",  # Bu da desktop için daha iyi filtreleme vermeli
            "Xiaomi 13T Pro telefon"
        ]
        for test_query in test_queries:
            print(f"\n📱 Test Query: '{test_query}'")
            try:
                search_results = search_products_on_web(test_query, count=5)
                print(f"✅ Found {len(search_results)} relevant results:")
                for i, result in enumerate(search_results, 1):
                    title = result.get('title', '')[:70]
                    url = result.get('url', '')
                    category = result.get('detected_category', 'N/A')
                    strategy = result.get('search_strategy', 'N/A')
                    site = result.get('search_site', 'N/A')
                    search_query = result.get('search_query', 'N/A')[:40]
                    print(f"  {i}. [{category}] [{site}] [S{strategy}: {search_query}...] {title}...")
                    print(f"     {url}")
            except Exception as e:
                print(f"❌ Search test failed: {e}")
            print("-" * 80)
    else:
        print("\n❌ Skipping tests - BRAVE_API_KEY is not configured in .env file")