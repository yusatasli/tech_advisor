# -*- coding: utf-8 -*-
"""
budget_strategies.py - Final Budget-Based Smart Search Strategies v6.1

v6.1 Final Özellikleri:
✅ v2.2'den: Kapsamlı laptop/desktop/phone stratejileri, fiyat öncelikli
✅ v2.3'ten: Tüm RTX 4080/4090/5070/5080/5090 negative keywords
✅ v5.0'dan: User Intent Detection, Spec Conflict Engelleme
✅ YENİ: 5 marka stratejisi (3'ten artırıldı)
✅ YENİ: Kullanıcı fiyat yazdıysa tekrar eklenmez
✅ YENİ: Kullanıcı GPU yazdıysa spec conflict engellenir
✅ YENİ v6.1: Dinamik 3 fiyat stratejisi (alt, orta, üst limit)
❌ ÇIKARILDI: iPhone özel stratejisi (genel telefon stratejisi yeterli)
❌ ÇIKARILDI: Telefon marka kontrolü (gereksiz karmaşıklık)
"""

from typing import List, Tuple, Dict, Any
import re

def get_budget_range(budget: float, category: str) -> str:
    """Bütçeye göre aralık döndür"""
    if category == "laptop":
        if budget < 30000:
            return "20000-30000"
        elif budget < 40000:
            return "30000-40000"
        elif budget < 50000:
            return "40000-50000"
        elif budget < 65000:
            return "50000-65000"
        elif budget < 85000:
            return "65000-85000"
        else:
            return "85000+"
    elif category == "phone":
        if budget < 20000:
            return "10000-20000"
        elif budget < 30000:
            return "20000-30000"
        elif budget < 45000:
            return "30000-45000"
        elif budget < 60000:
            return "45000-60000"
        elif budget < 85000:
            return "60000-85000"
        else:
            return "85000+"
    elif category == "desktop":
        if budget < 35000:
            return "25000-35000"
        elif budget < 50000:
            return "35000-50000"
        elif budget < 70000:
            return "50000-70000"
        elif budget < 100000:
            return "70000-100000"
        else:
            return "100000+"
    else:
        return "40000-50000"


# ===== LAPTOP STRATEJILERI =====
LAPTOP_STRATEGIES = {
    "20000-30000": {
        "include_brands": [
            "Monster Abra", "Casper Nirvana", "HP 15s", "Lenovo V15", 
            "Dell Inspiron", "Asus Vivobook"
        ],
        "include_specs": [
            "rtx 3050", "gtx 1650", "intel iris xe", "radeon 680m",
            "i3-12", "i5-11", "i5-12", "ryzen 5-5"
        ],
        "negative_keywords": "thinkbook rog alienware legion razer i9 rtx4060 rtx4070 rtx4080 rtx4090 rtx5060 rtx5070 rtx5080 rtx5090"
    },
    "30000-40000": {
        "include_brands": [
            "HP Victus", "Acer Aspire", "Lenovo IdeaPad Gaming",
            "Monster Tulpar", "Casper Excalibur", "MSI GF"
        ],
        "include_specs": [
            "rtx 3050", "rtx 3060", "rtx 4050", "gtx 1650 ti",
            "i5-12", "i5-13", "ryzen 5-6", "ryzen 5-7", "ryzen 7-5"
        ],
        "negative_keywords": "thinkbook rog-strix alienware legion-pro i9 rtx4070 rtx4080 rtx4090 rtx5070 rtx5080 rtx5090"
    },
    "40000-50000": {
        "include_brands": [
            "HP Victus", "MSI Cyborg", "Acer Nitro", "ASUS TUF",
            "Lenovo LOQ", "Monster Tulpar", "MSI Katana"
        ],
        "include_specs": [
            "rtx 4050", "rtx 4060", "rtx 3060", "rtx 3060 ti",
            "i5-13", "i5-14", "i7-12", "i7-13", 
            "ryzen 5-7", "ryzen 7-7", "ryzen 7-8"
        ],
        "negative_keywords": "thinkbook-i9 rog-strix alienware i9-14900 ultra-9 rtx4080 rtx4090 rtx5070 rtx5080 rtx5090"
    },
    "50000-65000": {
        "include_brands": [
            "HP Victus", "ASUS TUF", "MSI Cyborg", "MSI Katana",
            "Acer Nitro", "Lenovo LOQ", "ASUS ROG Strix G"
        ],
        "include_specs": [
            "rtx 4060", "rtx 4070", "rtx 5060",
            "i7-13", "i7-14", "i9-12", "i9-13",
            "ryzen 7-8", "ryzen 9-7"
        ],
        "negative_keywords": "thinkbook-i9-14900 alienware razer i9-14900hx ultra-9 rtx4090 rtx5080 rtx5090"
    },
    "65000-85000": {
        "include_brands": [
            "ASUS ROG Strix", "MSI GF", "MSI Katana", "Lenovo Legion 5",
            "Acer Predator", "HP Omen", "ASUS TUF i9"
        ],
        "include_specs": [
            "rtx 4070", "rtx 4080", "rtx 5060", "rtx 5070",
            "i7-14", "i9-13", "i9-14",
            "ryzen 9-7", "ryzen 9-8"
        ],
        "negative_keywords": "alienware-x razer-blade-18 rtx4090 rtx5090 128gb dual-gpu"
    },
    "85000+": {
        "include_brands": [
            "ASUS ROG Zephyrus", "MSI GE", "MSI Titan", "Alienware",
            "Razer Blade", "Legion Pro 7", "Legion 9i"
        ],
        "include_specs": [
            "rtx 4080", "rtx 4090", "rtx 5070", "rtx 5080", "rtx 5090",
            "i9-14", "ultra 9", "ryzen 9-8"
        ],
        "negative_keywords": ""
    }
}

# ===== DESKTOP STRATEJILERI =====
DESKTOP_STRATEGIES = {
    "25000-35000": {
        "include_brands": [
            "hazır sistem", "gaming pc", "sistem tavsiyesi", "oyuncu bilgisayar"
        ],
        "include_specs": [
            "hazır sistem rtx 3050", "gaming pc rtx 4060", "sistem tavsiyesi rtx 3060",
            "hazır sistem ryzen 5 5600", "gaming pc i5-12400"
        ],
        "negative_keywords": "ekran kartı graphics card sadece kart gpu only rtx4080 rtx4090 workstation"
    },
    "35000-50000": {
        "include_brands": [
            "hazır sistem", "gaming pc", "sistem tavsiyesi", "oyuncu bilgisayar", "oem paket"
        ],
        "include_specs": [
            "hazır sistem rtx 5060", "gaming pc rtx 4060", "sistem tavsiyesi rtx 5060 ti",
            "hazır sistem ryzen 5 7600", "gaming pc i5-13400", "oem paket rtx 5060"
        ],
        "negative_keywords": "ekran kartı graphics card gpu only rtx4090 rtx5080 workstation"
    },
    "50000-70000": {
        "include_brands": [
            "hazır sistem", "gaming pc", "sistem tavsiyesi", "oyuncu bilgisayar", "oem paket"
        ],
        "include_specs": [
            "hazır sistem rtx 5060 ti", "gaming pc rtx 4070", "sistem tavsiyesi rtx 5070",
            "hazır sistem ryzen 7 7700", "gaming pc i7-13700", "oem paket rtx 5070"
        ],
        "negative_keywords": "ekran kartı graphics card gpu only rtx4090 rtx5090 workstation render"
    },
    "70000-100000": {
        "include_brands": [
            "hazır sistem", "gaming pc", "sistem tavsiyesi", "oyuncu bilgisayar", "oem paket"
        ],
        "include_specs": [
            "hazır sistem rtx 5070", "gaming pc rtx 4080", "sistem tavsiyesi rtx 5080",
            "hazır sistem ryzen 9 7900", "gaming pc i9-13900", "oem paket rtx 5080"
        ],
        "negative_keywords": "ekran kartı graphics card gpu only"
    },
    "100000+": {
        "include_brands": [
            "hazır sistem", "gaming pc", "sistem tavsiyesi", "workstation", "oem paket"
        ],
        "include_specs": [
            "hazır sistem rtx 5090", "gaming pc rtx 4090", "sistem tavsiyesi rtx 5090",
            "hazır sistem ryzen 9 7950x3d", "gaming pc i9-14900k", "oem paket rtx 5090"
        ],
        "negative_keywords": ""
    }
}

# ===== TELEFON STRATEJILERI =====
PHONE_STRATEGIES = {
    "10000-20000": {
        "include_brands": [
            "Xiaomi Redmi", "Samsung Galaxy A", "Realme", "Poco",
            "Oppo", "Motorola Moto"
        ],
        "include_specs": [
            "128gb 6gb ram", "128gb 8gb ram", "256gb 8gb ram",
            "5000mah", "90hz", "amoled"
        ],
        "negative_keywords": "iphone galaxy-s ultra pro-max flagship"
    },
    "20000-30000": {
        "include_brands": [
            "Samsung Galaxy A", "Xiaomi Redmi", "Xiaomi", "Poco",
            "Realme", "Oppo Reno", "Motorola Edge"
        ],
        "include_specs": [
            "256gb 8gb ram", "256gb 12gb ram", "120hz amoled",
            "5000mah hızlı şarj", "50mp kamera"
        ],
        "negative_keywords": "iphone galaxy-s24 ultra pro-max flagship"
    },
    "30000-45000": {
        "include_brands": [
            "Samsung Galaxy A", "Xiaomi", "OnePlus Nord", "Google Pixel",
            "Motorola Edge", "Oppo Reno", "Nothing Phone"
        ],
        "include_specs": [
            "256gb 12gb ram", "512gb 12gb ram", "120hz oled",
            "snapdragon 7", "dimensity 9000"
        ],
        "negative_keywords": "iphone-pro s24-ultra ultra"
    },
    "45000-60000": {
        "include_brands": [
            "Samsung Galaxy S", "OnePlus", "Google Pixel", "Xiaomi",
            "iPhone", "Nothing Phone"
        ],
        "include_specs": [
            "256gb", "512gb", "snapdragon 8 gen 2", "google tensor"
        ],
        "negative_keywords": "pro-max ultra 1tb"
    },
    "60000-85000": {
        "include_brands": [
            "iPhone", "Samsung Galaxy S", "Google Pixel Pro", "OnePlus"
        ],
        "include_specs": [
            "256gb", "512gb", "titanium", "snapdragon 8 gen 3"
        ],
        "negative_keywords": "1tb"
    },
    "85000+": {
        "include_brands": [
            "iPhone Pro Max", "Samsung Galaxy S Ultra", "Google Pixel Pro"
        ],
        "include_specs": [
            "512gb", "1tb", "titanium", "8k video"
        ],
        "negative_keywords": ""
    }
}


# ============================================================
# USER INTENT DETECTION (v5.0'dan)
# ============================================================

def detect_tech_intent(query: str) -> List[str]:
    """Sorgudaki teknik özellikleri (GPU, CPU) tespit eder"""
    query_lower = query.lower()
    found_specs = []
    
    gpu_patterns = [
        r"rtx\s*\d{4}(?:\s*ti|\s*super)?",
        r"gtx\s*\d{4}(?:\s*ti)?",
        r"rx\s*\d{4}\s*(?:xt)?",
    ]
    
    cpu_patterns = [
        r"i\d[-\s]?\d{4,5}[hkf]?",
        r"ryzen\s*\d\s*\d{4}[x]?"
    ]
    
    for pattern in gpu_patterns + cpu_patterns:
        match = re.search(pattern, query_lower)
        if match:
            found_specs.append(match.group(0).replace(" ", ""))
            
    return found_specs


def has_price_in_query(query: str) -> bool:
    """Sorguda fiyat ifadesi var mı kontrol eder"""
    return bool(re.search(r"\d{4,6}\s*(?:tl|try|lira)", query.lower()))


def generate_budget_strategies(
    query: str,
    budget: float,
    category: str,
    num_strategies: int = 7
) -> List[Tuple[str, str]]:
    """
    Final Budget Strategies v6.1
    
    Strateji Öncelik Sırası:
    1. Fiyat aralığı (kullanıcı yazmadıysa)
    2. Negative keywords (spec conflict temizlenmiş)
    3. 5 MARKA stratejisi
    4. 1 Spec stratejisi (kullanıcı spec belirtmediyse)
    """
    original_query_lower = query.lower()
    budget_range = get_budget_range(budget, category)
    
    # Teknolojik özellikleri ayır
    tech_spec = ""
    tech_patterns = [
        r'\brtx\s*\d{4}(?:\s*ti)?\b',
        r'\bgtx\s*\d{4}(?:\s*ti)?\b',
        r'\bi\d-\d{4,5}[a-z]*\b',
        r'\bryzen\s*\d+\s*\d{4}[a-z]*\b'
    ]
    
    for pattern in tech_patterns:
        match = re.search(pattern, original_query_lower)
        if match:
            tech_spec = match.group(0)
            break
    
    query_processed = tech_spec if tech_spec else query.lower()
    
    # Kategori stratejilerini al
    if category == "laptop":
        strategies_map = LAPTOP_STRATEGIES
    elif category == "phone":
        strategies_map = PHONE_STRATEGIES
    elif category == "desktop":
        strategies_map = DESKTOP_STRATEGIES
    else:
        return []
    
    mapping = strategies_map.get(budget_range, {})
    if not mapping:
        return []
    
    strategies = []
    
    # User intent tespiti
    detected_specs = detect_tech_intent(original_query_lower)
    user_has_price = has_price_in_query(original_query_lower)
    
    # ============================================================
    # 1. FİYAT STRATEJİLERİ (3 ADET - DİNAMİK!)
    # ============================================================
    if not user_has_price:
        min_price = int(budget * 0.85)
        max_price = int(budget * 1.15)
        # 3 ayrı fiyat sorgusu (alt, orta, üst)
        strategies.append((f"{min_price} tl {query_processed}", "high"))
        strategies.append((f"{int(budget)} tl {query_processed}", "high"))
        strategies.append((f"{max_price} tl {query_processed}", "high"))
    
    # ============================================================
    # 2. NEGATIVE KEYWORDS (SPEC CONFLICT TEMİZLENMİŞ!)
    # ============================================================
    raw_negatives = mapping.get("negative_keywords", "").split()
    cleaned_negatives = []
    
    for neg in raw_negatives:
        neg_clean = neg.replace("-", "").lower()
        
        # SPEC CONFLICT: Kullanıcı "rtx 4050" arıyorsa "-rtx4050" ekleme!
        skip_negative = False
        for user_spec in detected_specs:
            user_spec_clean = user_spec.replace(" ", "").lower()
            if user_spec_clean in neg_clean or neg_clean in user_spec_clean:
                skip_negative = True
                break
        
        if skip_negative:
            continue
            
        cleaned_negatives.append(neg if neg.startswith("-") else f"-{neg}")
    
    negative_str = " ".join(cleaned_negatives)
    if negative_str:
        strategies.append((f"{query_processed} {negative_str}", "high"))
    
    # ============================================================
    # 3. MARKA STRATEJİLERİ (5 ADET!)
    # ============================================================
    include_brands = mapping.get("include_brands", [])[:5]
    
    for brand in include_brands:
        strategies.append((f"{brand} {query_processed}", "high"))
    
    # ============================================================
    # 4. SPEC STRATEJİSİ (1 ADET)
    # ============================================================
    if not detected_specs:
        for spec in mapping.get("include_specs", [])[:1]:
            strategies.append((f"{spec} {query_processed}", "high"))
    
    return strategies[:num_strategies]

# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("🧪 BUDGET STRATEGIES v6.1 FINAL TEST\n")
    print("="*80 + "\n")
    
    # Test 1: 35000TL RTX 4050 Laptop
    print("💻 Test 1: '35000tl rtx 4050 laptop'")
    strategies = generate_budget_strategies("35000tl rtx 4050 laptop", 35000, "laptop", 7)
    for i, (strat, priority) in enumerate(strategies, 1):
        print(f"  {i}. [{priority}] {strat}")
    
    print("\n" + "="*80 + "\n")
    
    # Test 2: 45000 RTX 4060 Laptop
    print("💻 Test 2: '45000 tl rtx 4060 laptop'")
    strategies = generate_budget_strategies("45000 tl rtx 4060 laptop", 45000, "laptop", 7)
    for i, (strat, priority) in enumerate(strategies, 1):
        print(f"  {i}. [{priority}] {strat}")
    
    print("\n" + "="*80 + "\n")
    
    # Test 3: Genel Laptop Arama
    print("💻 Test 3: 'gaming laptop' (45000 TL)")
    strategies = generate_budget_strategies("gaming laptop", 45000, "laptop", 7)
    for i, (strat, priority) in enumerate(strategies, 1):
        print(f"  {i}. [{priority}] {strat}")
    
    print("\n" + "="*80 + "\n")
    
    # Test 4: iPhone
    print("📱 Test 4: 'iphone 15 pro' (70000 TL)")
    strategies = generate_budget_strategies("iphone 15 pro", 70000, "phone", 7)
    for i, (strat, priority) in enumerate(strategies, 1):
        print(f"  {i}. [{priority}] {strat}")
    
    print("\n" + "="*80)