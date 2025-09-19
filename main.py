import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import math

from fastapi import FastAPI  # type: ignore
from pydantic import BaseModel  # type: ignore
from dotenv import load_dotenv  # type: ignore
load_dotenv()

from candidates import gather_candidates, CATEGORY_SITES
from utils import normalize_category
from db import get_final_score_by_name

# OpenAI opsiyonel
try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

app = FastAPI(title="Tech Advisor API", version="2.6")

# ----------------------- Yardımcılar -----------------------
def parse_budget_tl(text: str):  # type: (str) -> Optional[int]
    """
    40.000, 40000, 40k, 40 bin gibi bütçeleri sayıya çevirir.
    """
    t = (text or "").lower().replace(".", "").replace(",", "")
    m_k = re.search(r"(\d+)\s*k\b", t)
    if m_k:
        return int(m_k.group(1)) * 1000
    m_bin = re.search(r"(\d+)\s*bin\b", t)
    if m_bin:
        return int(m_bin.group(1)) * 1000
    digits = re.findall(r"\d+", t)
    if digits:
        val = int(digits[0])
        return val if val >= 1000 else None
    return None

FEATURE_SYNONYMS: Dict[str, List[str]] = {
    "kamera": ["kamera", "camera", "mp", "megapiksel", "megapixel"],
    "ekran": ["ekran", "screen", "display", "amoled", "oled", "ips", "hz", "inç", "inch"],
    "batarya": ["batarya", "pil", "battery", "mah"],
    "depolama": ["depolama", "disk", "ssd", "hdd", "gb", "tb"],
    "ram": ["ram", "bellek"],
    "işlemci": ["işlemci", "cpu", "processor", "chip"],
    "gpu": ["gpu", "ekran kartı", "graphic card"],
}

def _extract_features_from_query(q: str) -> List[str]:
    ql = (q or "").lower()
    feats: List[str] = []
    for key, syns in FEATURE_SYNONYMS.items():
        if any(s in ql for s in syns):
            feats.append(key)
    return feats

def _get_product_features(product: Dict[str, Any], feature_keys: List[str]) -> List[str]:
    found: List[str] = []
    specs = product.get("specs") or {}
    specs_text = " ".join([f"{k} {v}" for k, v in specs.items()]).lower()
    for f_key in feature_keys:
        syns = FEATURE_SYNONYMS.get(f_key, [])
        if any(s in specs_text for s in syns):
            found.append(f_key)
    return found

def _score_product(product: Dict[str, Any], query_price: Optional[int], query_features: List[str]) -> float:
    """
    Basit toplam skor:
      - Bütçe yakınlığı
      - Özellik eşleşmesi
      - DB.final_score katkısı (0.5 * (final_score/1000))
    """
    score = 0.0
    
    # 1) Bütçe yakınlığı (±%10 → 5 puandan lineer düşüş)
    if query_price and product.get("price"):
        pdiff = abs(product["price"] - query_price) / float(query_price)
        if pdiff <= 0.10:
            score += 5.0 - (pdiff * 50.0)
            # Fiyat yoksa ve bütçe verilmişse hafif ceza (listeden komple düşürmeden, sırada geri kalsın)
        if query_price and not product.get("price"):
            score -= 0.5

    # 2) Özellik eşleşmesi
    matched = _get_product_features(product, query_features)
    score += 1.5 * len(matched)
    
    # 3) DB final_score katkısı
    try:
        pname = product.get("name")
        if pname:
            fs = get_final_score_by_name(pname)
            if fs is not None:
                # final_score değeri bir f/p oranı, doğrudan ana puana ekleyelim
                # Daha yüksek final_score, daha iyi ürün anlamına gelir
                score += fs * 100 # Katsayıyı artırarak daha belirgin bir etki sağlayalım
    except Exception as e:
        print(f"[score] final_score lookup error for {product.get('name')}: {e}")

    return score
    
# ----------------------- Modeller -----------------------
class Query(BaseModel):
    query: str
    budget: Optional[int] = None

class Candidate(BaseModel):
    source: str
    id: int
    name: str
    brand: str
    price: int
    category: str
    specs: Dict[str, str]

class Answer(BaseModel):
    answer: str
    explanation: str
    products: List[Candidate]

# ----------------------- Uç Noktalar -----------------------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(timespec="seconds"),
        "env": {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "GOOGLE_CSE_KEY": bool(os.getenv("GOOGLE_CSE_KEY")),
            "GOOGLE_CSE_CX": bool(os.getenv("GOOGLE_CSE_CX")),
        },
        "version": "health-2"
    }

@app.get("/debug/cse")
def debug_cse(q: str = "kamerası iyi telefon", n: int = 5):
    try:
        from web_search import search_products_on_web, _get_keys
        key, cx = _get_keys()
    except Exception as e:
        return {"ok": False, "error": f"import error: {e}"}

    category = normalize_category(q) or ""
    restrict = CATEGORY_SITES.get(category, None)

    hits: List[Dict[str, Any]] = []
    err = None
    try:
        hits = search_products_on_web(q, count=n, restrict_sites=restrict)
    except Exception as e:
        err = str(e)

    return {
        "ok": True,
        "have_key": bool(key),
        "have_cx": bool(cx),
        "query": q,
        "category": category,
        "restrict_domains": [d for (d, _) in restrict] if restrict else [],
        "returned": len(hits),
        "sample": hits[:3],
        "error": err,
    }

@app.get("/debug/candidates")
def debug_candidates(q: str = "30.000 TL hafif laptop", n: int = 12, top: int = 6):
    cands = gather_candidates(q, count=n)
    cat = (normalize_category(q) or "").lower()
    if cat:
        cands = [c for c in cands if (c.get("category") or "").lower() == cat]

    # Fiyata göre kaba sıralama
    cands.sort(key=lambda p: p.get("price") or 999999)
    top_cands = cands[:top]

    return {
        "ok": True,
        "query": q,
        "normalized_category": normalize_category(q),
        "count": len(cands),
        "candidates": top_cands,
    }

# --- Klasik öneri: GET /products/recommend ---
@app.get("/products/recommend")
def recommend_engine(query: str):
    """
    Ör: /products/recommend?query=40.000+TL+hafif+laptop
    - Bütçeyi ve kategoriyi sorgudan çıkarır
    - Adayları toplar (web+local)
    - Bütçe/kategori filtreler
    - _score_product ile puanlar (DB.final_score katkısı)
    - En iyi 3 ürünü döndürür
    """
    q = (query or "").strip()
    if not q:
        return {
            "query": query,
            "recommendations": [],
            "note": "Boş sorgu.",
            "message": "Lütfen bir sorgu verin."
        }

    budget = parse_budget_tl(q)
    category = normalize_category(q) or ""
    features = _extract_features_from_query(q)

    candidates = gather_candidates(q, count=12)

    pre_filtered: List[Dict[str, Any]] = []
    for p in candidates:
        pcat = (p.get("category") or "")
        ok_cat = (not category) or (pcat.lower() == category.lower())
        ok_budget = (not budget) or (p.get("price") is None) or (p["price"] <= budget * 1.25)
        if ok_cat and ok_budget:
            pre_filtered.append(p)

    if not pre_filtered:
        return {
            "query": query,
            "recommendations": [],
            "note": "Aradığınız kriterlere uygun ürün bulunamadı.",
            "message": "Hiç aday kalmadı (bütçe/kategori filtresi sonrası)."
        }

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for p in pre_filtered:
        s = _score_product(p, budget, features)
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    best3 = [p for (s, p) in scored[:3]]

    note = (
        "Aradığınız kriterlere uygun ürünler listelenmiştir."
        if len(best3) == 3 else
        "Sadece sınırlı sayıda öneri bulunabildi."
    )

    return {
        "query": query,
        "recommendations": best3,
        "note": note,
        "message": "Ürün önerileriniz başarıyla oluşturuldu."
    }

# --- LLM destekli açıklama: POST /ask ---
@app.post("/ask", response_model=Answer)
def ask(query: Query):
    start = time.time()
    user_query = query.query.strip()
    if not user_query:
        return Answer(
            answer="Lütfen bir soru girin.",
            explanation="Boş sorgu gönderdiniz.",
            products=[]
        )

    budget = query.budget or parse_budget_tl(user_query)
    category = normalize_category(user_query) or ""
    features = _extract_features_from_query(user_query)

    # 1) adaylar
    candidates = gather_candidates(user_query, count=12)

    # 2) bütçe+kategori ön filtre
    pre_filtered = [
        p for p in candidates
        if (not budget or (p.get("price") is None) or (p["price"] <= budget * 1.25))
        and (not category or (p.get("category") or "").lower() == category.lower())
    ]
    if not pre_filtered:
        return Answer(
            answer="Bütçenize veya kategorinize uygun bir ürün bulamadım.",
            explanation="Lütfen bütçe ve/veya kategori bilginizi gözden geçirin.",
            products=[]
        )

    # 3) puanla ve sırala
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for p in pre_filtered:
        s = _score_product(p, budget, features)
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = [p for (s, p) in scored[:6]]  # ilk 6

    # 4) LLM açıklaması için ürün metinleri
    product_texts: List[str] = []
    for p in best:
        specs = p.get("specs") or {}
        specs_str = ", ".join(f"{k}: {v}" for k, v in specs.items()) if specs else "belirtilmemiş"
        product_texts.append(
            f"Ad: {p.get('name','?')}, Marka: {p.get('brand','?')}, Fiyat: {p.get('price','?')} TL, "
            f"Kategori: {p.get('category','?')}, Özellikler: {specs_str}, Kaynak: {p.get('source','?')}, URL: {p.get('url','-')}"
        )

    prompt = (
        f"Kullanıcının sorgusu: '{user_query}'.\n\n"
        f"Aşağıdaki listedeki ürünler arasından kullanıcının sorusuna en uygun olanları, nedenleriyle birlikte, "
        f"özetle ve maddeler halinde açıkla. Yanıt Türkçe olsun. "
        f"Ürünlerin fiyatı, markası ve temel özelliklerini belirt. Sadece listelenen ürünleri kullan. "
        f"URL varsa ekle.\n\n"
        f"Ürün listesi:\n- " + "\n- ".join(product_texts)
    )

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Sen bir teknoloji ürünleri danışmanısın. Kullanıcının sorusuna, elindeki ürün verilerine göre yanıt ver."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=False
            )
            explanation = response.choices[0].message.content
        except Exception as e:
            explanation = f"OpenAI API çağrısı sırasında bir hata oluştu: {e}"
    else:
        explanation = "OpenAI API anahtarı bulunamadı veya istemci başlatılamadı."

    # 5) pydantic modele uygun çıktı
    response_products: List[Dict[str, Any]] = []
    seen_ids = set()
    for p in best:
        pid = p.get("id", 0)
        try:
            pid_int = int(pid) if isinstance(pid, (int, str)) and str(pid).isdigit() else 0
        except Exception:
            pid_int = 0
        clean_p = {
            "source": p.get("source", "bilinmiyor"),
            "id": pid_int,
            "name": p.get("name", "bilinmiyor"),
            "brand": p.get("brand", "bilinmiyor"),
            "price": p.get("price", 0),
            "category": p.get("category", "bilinmiyor"),
            "specs": p.get("specs", {})
        }
        if clean_p['id'] not in seen_ids:
            response_products.append(clean_p)
            seen_ids.add(clean_p['id'])

    return Answer(
        answer=f"{user_query} için en uygun ürünleri listeliyorum:",
        explanation=explanation,
        products=response_products
    )
