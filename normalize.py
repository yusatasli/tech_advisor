# normalize.py - Enhanced with more robust parsing and filtering
import re
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Bilinen markalar
BRANDS: List[str] = [
    "Apple", "Samsung", "Xiaomi", "Asus", "Acer", "Lenovo", "MSI", "HP", "Dell",
    "Razer", "Google", "Huawei", "Casper", "OnePlus", "Honor", "Realme", "Oppo",
    "Vivo", "Nokia", "Nothing", "Monster", "Gigabyte", "Microsoft"
]

# Fiyat regex
_PRICE_PAT = re.compile(
    r"(?:₺|\bTL\b|\bTRY\b|euro|eur|\$)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\b|\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:₺|\bTL\b|\bTRY\b|euro|eur|\$)",
    re.IGNORECASE
)

# Donanım regexleri
_CPU_PAT = re.compile(r"\b(intel|amd|ryzen|snapdragon|mediatek|exynos)\s+([\w\d\-\s]+)", re.IGNORECASE)
_GPU_PAT = re.compile(r"\b(nvidia|geforce|radeon|amd|intel)\s+(rtx|gtx|mx|iris|arc)\s*([\w\d\-\s]+)", re.IGNORECASE)
_RAM_PAT = re.compile(r"(\d+)\s*(?:gb|gb)\s*(?:ram|ddr\d+)", re.IGNORECASE)
_SSD_PAT = re.compile(r"(\d+)\s*(?:gb|tb)\s*(?:ssd|nvme)", re.IGNORECASE)

# Donanım anahtar kelimeleri
HARDWARE_KEYWORDS = [
    "rtx", "gtx", "radeon", "geforce", "nvidia", "intel", "amd", "ryzen", "core i", "m1", "m2", "m3",
    "gb ram", "tb ssd", "gb ssd", "inç", "inch", "hz", "fhd", "qhd", "uhd"
]

@dataclass
class ParsedQueryResult:
    """Sorgu analizi sonuçlarını tutan veri sınıfı."""
    original_query: str
    category: Optional[str] = None
    brand: Optional[str] = None
    gpu_hint: Optional[str] = None
    cpu_hint: Optional[str] = None
    budget: Optional[int] = None
    keywords: List[str] = field(default_factory=list)

def _guess_brand(text: str) -> Optional[str]:
    text_lower = text.lower()
    for brand in BRANDS:
        if brand.lower() in text_lower:
            return brand
    return None

def _extract_price(text: str) -> Optional[int]:
    m = _PRICE_PAT.search(text)
    if m:
        price_str = m.group(1) or m.group(2)
        clean_price_str = re.sub(r'[.,]\d{2}$', '', price_str)
        clean_price_str = re.sub(r'[.,]', '', clean_price_str)
        try:
            price = int(clean_price_str)
            if 1000 < price < 500000:
                return price
        except (ValueError, TypeError):
            return None
    return None

def _guess_category(text: str) -> Optional[str]:
    title_lower = text.lower()
    if any(w in title_lower for w in ["telefon", "phone", "smartphone", "cep"]):
        return "Telefon"
    if any(w in title_lower for w in ["laptop", "notebook", "dizüstü"]):
        return "Laptop"
    if any(w in title_lower for w in ["masaüstü", "pc", "desktop"]):
        return "Masaüstü"
    return None

def _extract_specs_from_text(text: str) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    if cpu_m := _CPU_PAT.search(text): 
        specs["CPU"] = cpu_m.group(0).strip()
    if gpu_m := _GPU_PAT.search(text): 
        specs["GPU"] = gpu_m.group(0).strip()
    if ram_m := _RAM_PAT.search(text): 
        specs["RAM"] = f"{ram_m.group(1)}GB"
    if ssd_m := _SSD_PAT.search(text): 
        specs["Depolama"] = f"{ssd_m.group(1)}{'TB' if 'tb' in text.lower() else 'GB'} SSD"
    return specs

def parse_query(query: str) -> ParsedQueryResult:
    """Kullanıcı sorgusunu analiz ederek yapılandırılmış verileri çıkarır."""
    if not query:
        return ParsedQueryResult(original_query="")
    
    q_lower = query.lower()
    gpu_match = re.search(r'\b(rtx|gtx)\s*(\d{4})\b', q_lower)
    cpu_match = re.search(r'\b(i[3579]|ryzen\s*[3579])\b', q_lower)
    
    return ParsedQueryResult(
        original_query=query,
        category=_guess_category(query),
        brand=_guess_brand(query),
        gpu_hint=gpu_match.group(0) if gpu_match else None,
        cpu_hint=cpu_match.group(0) if cpu_match else None,
        budget=_extract_price(query),
        keywords=[]  # Boş liste olarak başlatıyoruz
    )

def normalize_web_result(item: Dict[str, Any], query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    title = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()
    snippet = (item.get("snippet") or "").strip()

    blocked_url_keywords = ["forum", "blog", "sosyal", "community", "ikinci-el", "2-el", "yenilenmis"]
    if any(k in url.lower() for k in blocked_url_keywords):
        return None

    if not title or not url:
        return None

    all_text = f"{title} {snippet}"
    brand = _guess_brand(all_text)
    category = _guess_category(title)
    
    category_keywords = ["fiyatları", "modelleri", "kategori"]
    if any(w in title.lower() for w in category_keywords):
        return None

    price = _extract_price(all_text)
    specs = _extract_specs_from_text(all_text)
    
    has_hardware_keyword = any(k in all_text.lower() for k in HARDWARE_KEYWORDS)

    if not brand:
        return None

    if not (price is not None and has_hardware_keyword):
        return None

    uid = hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()
    
    return {
        "id": f"web::{uid[:16]}",
        "category": category,
        "name": title,
        "brand": brand,
        "price": price,
        "specs": specs,
        "source": "web:cse",
        "url": url,
        "snippet": snippet,
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }