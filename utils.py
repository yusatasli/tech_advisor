# utils.py
from typing import Optional

def normalize_category(text: str) -> Optional[str]:
    t = (text or "").lower()
    if any(w in t for w in ["telefon", "iphone", "android", "smartphone", "cep telefonu", "cep"]):
        return "Telefon"
    if any(w in t for w in ["laptop", "notebook", "ultrabook", "macbook", "dizüstü"]):
        return "Laptop"
    if any(w in t for w in ["masaüstü", "desktop", "oyun bilgisayarı", "gaming pc", "toplama", "pc"]):
        return "Masaüstü"
    return None
