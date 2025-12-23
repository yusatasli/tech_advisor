# normalize.py - Apple Silicon (M1/M2/M3/M4) ve Gelişmiş Regex Desteği
# 🔥 GÜNCELLENME: 17 Aralık 2025 - İşlemci kontrolü güçlendirildi
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

# --- 🔥 GELİŞTİRİLMİŞ DONANIM REGEXLERİ ---

# CPU Pattern - Kapsamlı İşlemci Algılama
_CPU_PAT = re.compile(
    r"""
    \b(?:
        # Intel işlemciler (i3/i5/i7/i9 + model numarası)
        (?:intel\s+)?(?:core\s+)?(i[3579])[\s-]?(\d{4,5}[a-z]*)|
        
        # AMD Ryzen işlemciler
        (?:amd\s+)?ryzen\s+([3579])[\s-]?(\d{4}[a-z]*)|
        
        # 🍎 Apple Silicon (M1/M2/M3/M4 + Pro/Max/Ultra varyantları)
        (?:apple\s+)?m([1-4])(?:\s+(pro|max|ultra))?|
        
        # ARM mobil işlemciler (Snapdragon, Dimensity, Exynos)
        (snapdragon|mediatek|dimensity|exynos)\s+(\d{3,4}[a-z]*)|
        
        # Apple Bionic işlemciler (A15, A16, A17, A18)
        (?:apple\s+)?a(\d{2})\s*(bionic)?|
        
        # Genel işlemci ifadeleri (yedek pattern)
        (intel|amd|apple)\s+([\w\d\-\s]+)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE
)

# GPU Pattern - Geliştirilmiş
_GPU_PAT = re.compile(
    r"\b(nvidia|geforce|radeon|amd|intel|apple)\s+(rtx|gtx|mx|iris|arc|m[1-4]|gpu)\s*([\w\d\-\s]*)", 
    re.IGNORECASE
)

_RAM_PAT = re.compile(r"(\d+)\s*(?:gb|gb)\s*(?:ram|ddr\d+|birleşik bellek|unified memory)", re.IGNORECASE)
_SSD_PAT = re.compile(r"(\d+)\s*(?:gb|tb)\s*(?:ssd|nvme)", re.IGNORECASE)

# 🔥 GELİŞTİRİLMİŞ Donanım Anahtar Kelimeleri
HARDWARE_KEYWORDS = [
    # GPU keywords
    "rtx", "gtx", "radeon", "geforce", "nvidia", "intel", "amd",
    
    # CPU keywords - Intel/AMD
    "ryzen", "core i", "i3", "i5", "i7", "i9",
    
    # 🍎 Apple Silicon keywords
    "m1", "m2", "m3", "m4",
    "m1 pro", "m1 max", "m1 ultra",
    "m2 pro", "m2 max", "m2 ultra",
    "m3 pro", "m3 max", "m3 ultra",
    "m4 pro", "m4 max",
    "apple silicon", "apple chip", "apple m",
    
    # Apple ürün keywords
    "macbook", "macbook air", "macbook pro", "mac mini", "mac studio", "imac",
    
    # ARM mobil keywords
    "snapdragon", "dimensity", "exynos", "bionic",
    "a15", "a16", "a17", "a18",  # Apple Bionic
    
    # Genel donanım
    "gb ram", "tb ssd", "gb ssd", "inç", "inch", "hz", "fhd", "qhd", "uhd",
    "unified memory", "birleşik bellek"  # Apple RAM tanımı
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
    """Metinden marka tahmini yapar"""
    text_lower = text.lower()
    for brand in BRANDS:
        if brand.lower() in text_lower:
            return brand
    return None

def _extract_price(text: str) -> Optional[int]:
    """
    Teknik spec numaralarını filtreleyerek bütçe çıkarır
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # GPU/CPU numaralarını temizle
    tech_patterns = [
        r'\b(rtx|gtx)\s*[34567][0-9]{2,3}[a-z]*\b',
        r'\b(rx|radeon)\s*[3456789][0-9]{2,3}[a-z]*\b',
        r'\bi[3579][\s-]?[0-9]{4,5}[a-z]*\b',
        r'\bryzen\s*[3579][\s-]?[0-9]{4}[a-z]*\b',
        r'\b(ddr[345]|gddr[56])\s*[0-9]+\b',
        r'\b[0-9]+\s*gb\s*(ram|vram|ssd)\b',
    ]
    
    cleaned_text = text_lower
    for pattern in tech_patterns:
        cleaned_text = re.sub(pattern, ' ', cleaned_text)
    
    # 1. "bin" veya "k" ile ifade edilenler
    bin_patterns = [
        r'(\d+)\s*(?:bin|k)\s*(?:tl|lira|civarı|yaklaşık)',
        r'(\d+)\s*(?:bin|k)(?:\s|$)',
    ]
    
    for pattern in bin_patterns:
        match = re.search(pattern, cleaned_text)
        if match:
            try:
                value = int(match.group(1)) * 1000
                if 5000 <= value <= 500000:
                    return value
            except (ValueError, TypeError):
                continue
    
    # 2. Normal fiyat formatları
    normal_patterns = [
        r'(\d{4,6})\s*(?:tl|lira|₺)\s*(?:civarı|yaklaşık|fiyat)',
        r'(\d{4,6})\s*(?:tl|lira|₺)',
        r'(\d+)\.\d{3}\s*(?:tl|lira|₺)',
    ]
    
    for pattern in normal_patterns:
        matches = re.findall(pattern, cleaned_text)
        for match in matches:
            try:
                if '.' in str(match):
                    value = int(str(match).replace('.', ''))
                else:
                    value = int(match)
                
                if 5000 <= value <= 500000:
                    return value
            except (ValueError, TypeError):
                continue
    
    isolated_number = re.search(r'\b(\d{4,6})\b', cleaned_text)
    if isolated_number:
        try:
            value = int(isolated_number.group(1))
            if 10000 <= value <= 200000:
                return value
        except (ValueError, TypeError):
            pass
    
    return None

def _guess_category(text: str) -> Optional[str]:
    """
    🔥 GELİŞTİRİLMİŞ: Ürün kategorisini metin analizi ile tahmin eder
    MacBook özel kontrolü eklendi - her zaman Laptop döner
    """
    title_lower = text.lower()
    
    # 🍎 ÖNCELİK 1: MacBook kontrolü (Apple ürünleri her zaman Laptop)
    if any(w in title_lower for w in ["macbook", "mac book", "macbook air", "macbook pro"]):
        return "Laptop"
    
    # Telefon kontrolü
    if any(w in title_lower for w in [
        "telefon", "phone", "smartphone", "cep", "akıllı telefon", 
        "iphone", "galaxy s", "galaxy a", "redmi note", "mi ", "poco"
    ]):
        return "Telefon"
    
    # Laptop kontrolü
    if any(w in title_lower for w in [
        "laptop", "notebook", "dizüstü", "taşınabilir bilgisayar"
    ]):
        return "Laptop"
    
    # Masaüstü kontrolü
    if any(w in title_lower for w in [
        "masaüstü", "pc", "desktop", "bilgisayar kasası",
        "hazır sistem", "sistem tavsiyesi", "gaming pc", 
        "oyun bilgisayarı", "hazır sistemler", "tavsiye sistemler",
        "masaüstü pc", "oyuncu kasası"
    ]):
        return "Masaüstü"
    
    return None

def _extract_specs_from_text(text: str) -> Dict[str, str]:
    """
    🔥 GELİŞTİRİLMİŞ: Metinden teknik özellikleri çıkarır
    Apple Silicon tam desteği eklendi
    """
    specs: Dict[str, str] = {}
    
    # CPU Arama - Geliştirilmiş
    cpu_m = _CPU_PAT.search(text)
    if cpu_m:
        # Intel i3/i5/i7/i9
        if cpu_m.group(1):
            model = cpu_m.group(2) if cpu_m.group(2) else ""
            specs["CPU"] = f"Intel {cpu_m.group(1)} {model}".strip()
        
        # AMD Ryzen
        elif cpu_m.group(3):
            model = cpu_m.group(4) if cpu_m.group(4) else ""
            specs["CPU"] = f"AMD Ryzen {cpu_m.group(3)} {model}".strip()
        
        # 🍎 Apple M-Series (M1/M2/M3/M4)
        elif cpu_m.group(5):
            variant = cpu_m.group(6) if cpu_m.group(6) else ""
            specs["CPU"] = f"Apple M{cpu_m.group(5)} {variant}".strip()
        
        # ARM mobil işlemciler
        elif cpu_m.group(7):
            model = cpu_m.group(8) if cpu_m.group(8) else ""
            specs["CPU"] = f"{cpu_m.group(7)} {model}".strip()
        
        # Apple Bionic
        elif cpu_m.group(9):
            specs["CPU"] = f"Apple A{cpu_m.group(9)} Bionic".strip()
        
        # Genel fallback
        elif cpu_m.group(11):
            specs["CPU"] = f"{cpu_m.group(11)} {cpu_m.group(12)}".strip()
    
    # GPU Arama
    gpu_m = _GPU_PAT.search(text)
    if gpu_m:
        specs["GPU"] = f"{gpu_m.group(1)} {gpu_m.group(2)} {gpu_m.group(3) or ''}".strip()
    
    # RAM Arama
    ram_m = _RAM_PAT.search(text)
    if ram_m:
        specs["RAM"] = f"{ram_m.group(1)}GB"
    
    # SSD Arama
    ssd_m = _SSD_PAT.search(text)
    if ssd_m:
        specs["Depolama"] = f"{ssd_m.group(1)}{'TB' if 'tb' in text.lower() else 'GB'} SSD"
    
    return specs

def parse_query(query: str) -> ParsedQueryResult:
    """
    🔥 GELİŞTİRİLMİŞ: Kullanıcı sorgusunu analiz eder
    Apple Silicon (M1-M4) desteği eklendi
    """
    if not query:
        return ParsedQueryResult(original_query="")
    
    q_lower = query.lower()
    
    # GPU hint
    gpu_match = re.search(r'\b(rtx|gtx)\s*(\d{4})\b', q_lower)
    
    # CPU hint - Apple Silicon dahil
    cpu_match = re.search(
        r'\b(i[3579]|ryzen\s*[3579]|m[1-4](?:\s+(?:pro|max|ultra))?|snapdragon|dimensity|exynos|a\d{2}\s*bionic)\b', 
        q_lower
    )
    
    return ParsedQueryResult(
        original_query=query,
        category=_guess_category(query),
        brand=_guess_brand(query),
        gpu_hint=gpu_match.group(0) if gpu_match else None,
        cpu_hint=cpu_match.group(0) if cpu_match else None,
        budget=_extract_price(query),
        keywords=[]
    )

def normalize_web_result(item: Dict[str, Any], query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Web arama sonucunu normalize eder
    """
    title = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()
    snippet = (item.get("snippet") or "").strip()

    # Engellenen URL'ler
    blocked_url_keywords = ["forum", "blog", "sosyal", "community", "ikinci-el", "2-el", "yenilenmis"]
    if any(k in url.lower() for k in blocked_url_keywords):
        return None

    if not title or not url:
        return None

    all_text = f"{title} {snippet}"
    brand = _guess_brand(all_text)
    category = _guess_category(title)
    price = _extract_price(all_text)
    
    # Spec'leri çekmeye çalış (crash önleme)
    try:
        specs = _extract_specs_from_text(all_text)
    except Exception:
        specs = {}
    
    # 🍎 Apple ürünlerinde "RTX" gibi keywordler olmaz, o yüzden esneklik
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

# Test fonksiyonu
if __name__ == "__main__":
    test_queries = [
        "60000 TL MacBook Air M1",
        "110000 TL MacBook Pro M3 Pro 14 inç",
        "25000 TL Snapdragon 8 Gen 2 telefon",
        "45000 TL RTX 4060 laptop",
        "iPhone 15 Pro 256GB",
    ]
    
    print("\n" + "="*80)
    print("🧪 NORMALIZE.PY TEST - İşlemci Algılama")
    print("="*80)
    
    for query in test_queries:
        result = parse_query(query)
        print(f"\n📝 Sorgu: {query}")
        print(f"   ✅ Kategori: {result.category}")
        print(f"   ✅ Marka: {result.brand}")
        print(f"   ✅ CPU Hint: {result.cpu_hint}")
        print(f"   ✅ GPU Hint: {result.gpu_hint}")
        print(f"   ✅ Bütçe: {result.budget} TL")
    
    print("\n" + "="*80 + "\n")