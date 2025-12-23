import os
import re
import time
import json
from dotenv import load_dotenv

from normalize import parse_query
load_dotenv()
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import math

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn
from fastapi.middleware.cors import CORSMiddleware  # ← Ekle
from candidates import gather_candidates, gather_candidates_async, CATEGORY_SITES
from db import get_db_connection, get_final_score_by_name

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from auth import (
    UserRegister, UserLogin, UserResponse,
    hash_password, verify_password, create_access_token,
    get_current_user
)
from db import (
    create_user, get_user_by_email, get_user_by_id,
    increment_user_search,
    add_search_history, get_search_history
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

app = FastAPI(
    title="Tech Advisor API", 
    description="Akıllı ürün tavsiye motoru için streaming destekli API.",
    version="4.1"
) 
# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL'i
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------- Yardımcılar -----------------------
def parse_budget_tl(text: str) -> Optional[float]:
    t = (text or "").lower().replace(".", "").replace(",", "")
    m_k = re.search(r"(\d+)\s*k\b", t)
    if m_k:
        return float(int(m_k.group(1)) * 1000)
    m_bin = re.search(r"(\d+)\s*bin\b", t)
    if m_bin:
        return float(int(m_bin.group(1)) * 1000)
    digits = re.findall(r"\d+", t)
    if digits:
        val = int("".join(digits)) # Birden fazla sayı grubunu birleştir (örn: "40 000")
        return float(val) if val >= 1000 else None
    return None

# ---  Kategori ve Özellikler için Eş Anlamlılar ---
CATEGORY_SYNONYMS: Dict[str, List[str]] = {
    "Laptop": ["laptop", "dizüstü", "notebook", "taşınabilir bilgisayar", "macbook", "ultrabook"],
    "Telefon": ["telefon", "cep telefonu", "smartphone", "akıllı telefon", "phone", "iphone", "android"],
    "Masaüstü": ["masaüstü", "desktop", "pc", "bilgisayar kasası",
    "oyuncu kasası", "masaüstü pc", "hazır sistemler", "tavsiye sistemler", "hazır sistem", "sistem tavsiyesi", "gaming pc"],
}

FEATURE_SYNONYMS: Dict[str, List[str]] = {
    "kamera": ["kamera", "camera", "mp", "megapiksel", "megapixel"],
    "ekran": ["ekran", "screen", "display", "amoled", "oled", "ips", "hz", "inç", "inch"],
    "batarya": ["batarya", "pil", "battery", "mah"],
    "depolama": ["depolama", "disk", "ssd", "hdd", "gb", "tb"],
    "ram": ["ram", "bellek"],
    "işlemci": ["işlemci", "cpu", "processor", "chip", "intel", "amd", "ryzen", "core", "m1", "m2", "m3"],
    "gpu": ["gpu", "ekran kartı", "graphic card", "rtx", "gtx", "radeon"],
}

def _normalize_category_with_synonyms(text: str) -> Optional[str]:
    """Verilen metindeki anahtar kelimelere göre kategoriyi normalize eder."""
    if not text:
        return None
    lower_text = text.lower()
    for category, synonyms in CATEGORY_SYNONYMS.items():
        if any(synonym in lower_text for synonym in synonyms):
            return category
    return None

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

def _score_product(product: Dict[str, Any], query_price: Optional[float], query_features: List[str]) -> float:
    """
    Ürün puanlama fonksiyonu - GÜNCELLENMİŞ (v5.3)
    - Yerel veritabanı puanının (final_score) baskınlığı azaltıldı.
    - Web kaynaklı ürünlere 'Tazelik Bonusu' eklendi.
    """
    score = 0.0
    
    # 1. Fiyat Uyumu Puanı
    if query_price and product.get("price"):
        try:
            product_price = float(product["price"])
            # Genişletilmiş Tolerans: %25 alt, %15 üst
            lower_bound = query_price * 0.75
            upper_bound = query_price * 1.15

            if lower_bound <= product_price <= upper_bound:
                # Fiyat hedefe ne kadar yakınsa o kadar iyi
                pdiff = abs(product_price - query_price) / float(query_price)
                # Maksimum 15 puan
                score += (1 - (pdiff / 0.25)) * 15.0
        except (ValueError, TypeError):
            pass # Fiyat parse edilemezse puan verme
    
    if query_price and not product.get("price"):
        score -= 5.0  # Fiyatı olmayan ürüne ceza

    # 2. Özellik Eşleşme Puanı
    matched = _get_product_features(product, query_features)
    score += 5.0 * len(matched)  # Her eşleşen özellik için 5 puan

    # 3. Veritabanı Performans Puanı (Yerel Ürünler İçin)
    try:
        pname = product.get("name")
        if pname:
            fs = get_final_score_by_name(pname)
            if fs is not None:
                # ESKİ: score += fs * 100 (Aşırı baskındı)
                # YENİ: Daha makul bir etki
                score += fs * 0.2 
    except Exception as e:
        print(f"[score] final_score lookup error for {product.get('name')}: {e}")

    # 4. 🔥 KAYNAK BONUSU (WEB-FIRST MANTIĞI)
    # Web'den gelen taze verilere öncelik ver
    source = str(product.get("source", "")).lower()
    if "scraped" in source or "web" in source:
        score += 50.0  # Web ürünlerine büyük avantaj (Yerel ürünlerin önüne geçmesi için)
    elif "local" in source:
        score += 10.0  # Yerel ürünlere küçük bir güvenilirlik bonusu

    return score
    
# ----------------------- Modeller (GÜNCELLENDİ) -----------------------
class Query(BaseModel):
    query: str
    budget: Optional[float] = None # int -> float

class StructuredQuery(BaseModel):
    category: str
    features: Optional[str] = None
    price_text: Optional[str] = None

# Streaming endpoint için model
class StreamingQuery(BaseModel):
    query: str
    count: int = 10

class Candidate(BaseModel):
    source: Optional[str] = None
    id: Optional[Any] = None # int -> Any (Web ID'leri string hash olduğu için)
    name: str
    brand: Optional[str] = None
    price: Optional[float] = None # int -> float (Kuruşlu fiyatlar için)
    category: Optional[str] = None
    specs: Dict[str, str]
    url: Optional[str] = None

class Answer(BaseModel):
    answer: str
    explanation: str
    products: List[Candidate]

class AIRecommendation(Candidate):
    """
    Candidate modelindeki tüm alanlara ek olarak,
    yapay zeka tarafından üretilen yorumu da içerir.
    """
    ai_commentary: str

class StructuredAnswer(BaseModel):
    """
    AI analizinin nihai, birleşik yanıt formatı.
    """
    introductory_text: str 
    recommendations: List[AIRecommendation]
    
class StreamSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    count: int = Field(default=8, ge=1, le=30)
    budget: Optional[float] = Field(default=None, description="Explicit budget in TL")

# ----------------------- Mantık ve Uç Noktalar -----------------------

async def process_query_logic(query: str, count: int, explicit_budget: Optional[float] = None) -> List[Dict[str, Any]]:
    """
    Sorguyu işleyen, adayları toplayan ve sıralayan ana mantık.
    GÜNCELLENMİŞ (v5.3): Web öncelikli sıralama mantığı ile uyumlu.
    """
    final_products = []
    
    # 1. Adayları Topla (gather_candidates_async zaten Web-First çalışıyor)
    async for chunk in gather_candidates_async(query, count=count + 5, explicit_budget=explicit_budget):
        if chunk.get("status") == "complete" or chunk.get("status") == "cache_hit":
            final_products = chunk.get("products", [])
            break 
        elif chunk.get("status") == "fatal_error" or chunk.get("status") == "error":
            print(f"Arama sırasında hata: {chunk.get('message')}")
            return []

    if not final_products:
        return []

    # 2. Sorgu Analizi (Filtreleme için)
    parsed_query = parse_query(query)
    category = parsed_query.category
    
    # Eğer API'den açık bütçe gelmediyse, parsed_query'den al
    budget = explicit_budget if explicit_budget is not None else parsed_query.budget

    # 3. Kategori Filtreleme (Sadece yanlış kategorileri temizle)
    if category:
        # Web sonuçlarında kategori bazen boş gelebilir, onları hemen eleme
        final_products = [
            p for p in final_products 
            if p.get("category") is None or p.get("category").lower() == category.lower()
        ]

    # 4. Özellikleri Çıkar
    query_features = _extract_features_from_query(query)

    # 5. Puanlama ve Sıralama
    for prod in final_products:
        prod["_score"] = _score_product(prod, budget, query_features)

    # Puana göre azalan sırala
    final_products.sort(key=lambda x: x.get("_score", 0), reverse=True)
    
    # İstenen sayı kadarını al
    return final_products[:count]

@app.post("/ask", response_model=Answer, tags=["Product Search"])
async def ask(query: Query):
    start_time = time.time()
    query_text = query.query
    explicit_budget = query.budget

    best_products = await process_query_logic(query_text, count=5, explicit_budget=explicit_budget)

    elapsed = time.time() - start_time

    final_answer_text = "İstediğiniz ürünleri bulamadık." if not best_products else "İşte önerilerimiz!"
    return Answer(
        answer=final_answer_text,
        explanation=f"Toplam {len(best_products)} aday bulundu. ({elapsed:.2f}s)",
        products=[Candidate(**p) for p in best_products]
    )

@app.post("/structured_ask_stream", tags=["Product Search"])
async def structured_ask_stream(request: StreamingQuery):
    query = request.query
    count = request.count

    async def stream_generator():
        try:
            async for chunk in gather_candidates_async(query, count):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"
        except Exception as e:
            error_data = {
                "status": "fatal_error",
                "message": f"Sunucuda hata oluştu: {str(e)}"
            }
            yield json.dumps(error_data, ensure_ascii=False) + "\n"

    # Jeneratörü, StreamingResponse ile döndür.
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@app.post("/structured_ask_stream_with_ai", tags=["Product Search"])
async def structured_ask_stream_with_ai(
    request: StreamSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Hibrit endpoint: Stream hızı + AI yorumu
    
    Akış:
    1. Stream ile tüm ürünleri döndür (hızlı) ✅
    2. En iyi 3 ürün için AI yorumu oluştur 🤖
    3. AI yorumlarını ekstra event olarak gönder 📤
    """
    # Kullanıcı bilgilerini getir
    user = get_user_by_id(current_user["user_id"])
    
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    # Günlük limit kontrolü
    from datetime import date
    today = date.today()
    searches_used = user["daily_searches_used"]
    last_date = user["last_search_date"]
    
    # Gece yarısı reset
    if last_date != today:
        searches_used = 0
    
    # Limit dolmuş mu?
    if searches_used >= user["daily_searches_limit"]:
        raise HTTPException(
            status_code=429, 
            detail=f"Günlük arama limitiniz doldu. Limit: {user['daily_searches_limit']} arama/gün"
        )
        
    # Arama sayısını artır
    increment_result = increment_user_search(current_user["user_id"])
    if increment_result is None:
        raise HTTPException(status_code=500, detail="Arama kaydedilemedi")
    if not increment_result:
        raise HTTPException(
            status_code=429, 
            detail="Günlük arama hakkınız dolmuştur. Lütfen yarın tekrar deneyin."
        )
        
    # Query'yi parse et ve kategoriyi al
    parsed = parse_query(request.query)
    category_for_history = parsed.category if parsed.category else None
    
    # Arama geçmişine kaydet (kategori ile)
    add_search_history(current_user["user_id"], request.query, category_for_history)
    
    query = request.query
    count = request.count
    explicit_budget = request.budget
    
    async def stream_generator():
        try:
            # Adım 1: Stream ile ürünleri gönder (hızlı)
            final_products = []
            async for chunk in gather_candidates_async(query, count, explicit_budget=explicit_budget):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"
                
                # Tüm ürünler geldiğinde kaydet
            if chunk.get("status") in ["complete", "cache_hit", "filtering_complete"]:
                    final_products = chunk.get("products", [])
            
            # Adım 2: AI yorumlarını oluştur (sadece en iyi 3 ürün için)
            if final_products and client:
                try:
                    # En iyi 3 ürünü seç
                    top_3_products = final_products[:3]
                    
                    # AI için veri hazırla
                    product_data_for_ai = []
                    for p in top_3_products:
                        product_data_for_ai.append({
                            "name": p.get("name"),
                            "price": p.get("price"),
                            "brand": p.get("brand"),
                            "source": (p.get("source") or "").replace("_scraped", ""),
                            "specs": p.get("specs", {})
                        })
                    
                    # Kullanıcının query'sini özetle
                    user_request_summary = f"Kullanıcı şunu arıyor: '{query}'"
                    
                    # AI prompt
                    prompt = f"""
                    Sen deneyimli, samimi ve teknik detaylara hakim bir teknoloji danışmanısın.
                    {user_request_summary}
                    
                    Aşağıdaki ürünlerin HER BİRİ için kısa (2-3 cümle), özgün ve doğal bir yorum yaz.
                    
                    KURALLAR:
                    1. Her yorum farklı bir açıdan yaklaşmalı (performans, fiyat, taşınabilirlik, vs.)
                    2. Klişe başlangıçlar kullanma ("Bu ürün...", "Güçlü işlemcisi ile...")
                    3. Doğrudan özelliklerden bahset
                    4. Samimi ve ikna edici ol
                    
                    JSON formatında yanıt ver:
                    {{
                      "commentaries": [
                        {{"name": "Ürün Adı", "commentary": "Yorum metni"}},
                        ...
                      ]
                    }}
                    
                    Ürün Listesi:
                    {json.dumps(product_data_for_ai, ensure_ascii=False, indent=2)}
                    """
                    
                    # OpenAI API çağrısı
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "Sen piyasayı iyi bilen, samimi bir teknoloji uzmanısın."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        response_format={"type": "json_object"}
                    )
                    
                    ai_response = json.loads(response.choices[0].message.content)
                    commentaries = ai_response.get("commentaries", [])
                    
                    # AI yorumlarını ürünlerle eşleştir
                    products_with_ai = []
                    for product in top_3_products:
                        commentary = next(
                            (c["commentary"] for c in commentaries if c["name"] == product.get("name")),
                            None
                        )
                        if commentary:
                            product_copy = product.copy()
                            product_copy["ai_commentary"] = commentary
                            products_with_ai.append(product_copy)
                    
                    # AI yorumlarını stream olarak gönder
                    yield json.dumps({
                        "status": "ai_commentary_added",
                        "products_with_ai": products_with_ai
                    }, ensure_ascii=False) + "\n"
                    
                except Exception as e:
                    print(f"AI Commentary Error: {e}")
                    yield json.dumps({
                        "status": "ai_commentary_failed",
                        "message": f"AI yorumu oluşturulamadı: {str(e)}"
                    }, ensure_ascii=False) + "\n"
            
        except Exception as e:
            error_data = {"status": "fatal_error", "message": f"Hata: {str(e)}"}
            yield json.dumps(error_data, ensure_ascii=False) + "\n"
    
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


@app.post("/structured_ask", response_model=StructuredAnswer, tags=["Product Search"])
async def structured_ask(query: StructuredQuery):
    start = time.time()
    
    # Adım 1: Aday ürünleri bul
    combined_query_for_search = query.features.strip()
    best_products = await process_query_logic(combined_query_for_search, count=6)

    if not best_products:
        return StructuredAnswer(
            introductory_text="Üzgünüm, aradığınız kriterlere uygun bir ürün bulamadım.",
            recommendations=[]
        )
    
    # Adım 2: OpenAI için veri hazırla
    product_data_for_ai = []
    for p in best_products:
        product_data_for_ai.append({
            "name": p.get("name"),
            "price": p.get("price"),
            "brand": p.get("brand"),
            "source": (p.get("source") or "").replace("_scraped", ""),
            "specs": p.get("specs", {})
        })

    user_request_summary = f"Kullanıcının isteği: '{query.features}', Bütçe: '{query.price_text}'."

    # --- GÜNCELLENMİŞ VE GELİŞMİŞ PROMPT ---
    prompt = f"""
    Sen deneyimli, dobra ve teknik detaylara hakim bir **Teknoloji Editörüsün.**
    Kullanıcı şu kriterlerde ürün arıyor: {user_request_summary}

    Aşağıdaki ürün listesinden EN İYİ 3 tanesini seç ve JSON formatında yanıtla.

    HEDEF: Her ürün için "robotik" olmayan, sanki bir arkadaşına tavsiye veriyormuşsun gibi doğal ve spesifik yorumlar yazmak.

    JSON Şablonu:
    {{
      "introductory_text": "Kullanıcıyı karşılayan, samimi ve kısa bir giriş cümlesi (Örn: 'Bütçene göre piyasadaki en mantıklı cihazları senin için seçtim...').",
      "recommendations": [
        {{
          "name": "Ürünün Tam Adı",
          "price": Fiyatı (sayı),
          "brand": "Marka",
          "source": "Kaynak",
          "url": "Link (Boş bırak, sistem dolduracak)",
          "specs": {{ "İşlemci": "...", "Ekran Kartı": "...", "RAM": "...", "SSD": "..." }},
          "ai_commentary": "BURAYA DİKKAT: Yorum alanı."
        }}
      ]
    }}

    'ai_commentary' YAZIM KURALLARI (ÇOK ÖNEMLİ):
    1. **KLİŞELERİ YASAKLA:** Asla "Bu ürün...", "Bu laptop...", "Güçlü işlemcisi ile..." gibi sıkıcı girişler yapma. Doğrudan o ürünün fark yaratan özelliğinden bahset.
    2. **ÇEŞİTLİLİK SAĞLA:** - Bir üründe Fiyat/Performans dengesini övüyorsan, diğerinde Ekran Kalitesine (Hz, Panel) odaklan.
       - Bir diğerinde ise Malzeme Kalitesi veya Marka Güvenilirliğine değin.
    3. **TEKNİK KIYASLAMA YAP:** Sadece "iyi işlemci" deme. "İçindeki i7-12700H, i5 modellere göre render işlerinde %20 daha hızlıdır" gibi spesifik konuş.
    4. **GERÇEKÇİ OL:** Ürün ucuzsa "Malzeme kalitesi plastik olabilir ama bu fiyata donanımı rakipsiz" gibi dürüst yorumlar yap.
    5. **TON:** Samimi, bilgili ve ikna edici ol.

    Ürün Listesi:
    {json.dumps(product_data_for_ai, ensure_ascii=False, indent=2)}
    """

    # Adım 3: OpenAI API Çağrısı
    if not client:
        return StructuredAnswer(introductory_text="OpenAI API anahtarı yapılandırılmamış.", recommendations=[])

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "Sen piyasayı çok iyi bilen, teknik terimlere hakim bir donanım uzmanısın. Asla sıkıcı ve tekrar eden cümleler kurmazsın."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, # Yaratıcılığı artırmak için biraz yükselttik
            response_format={"type": "json_object"}
        )
        
        ai_response_json = json.loads(response.choices[0].message.content)
        
        # AI, URL'leri ve ID'leri bilmediği için onları orijinal listeden eşleştiriyoruz
        final_recommendations = []
        for rec in ai_response_json.get("recommendations", []):
            # İsme göre orijinal ürünü bul
            original_product = next((p for p in best_products if p.get("name") == rec.get("name")), None)
            if original_product:
                # AI'ın ürettiği yorumu ve spec'leri al, geri kalan kritik verileri (URL, ID) orijinalden çek
                rec["url"] = original_product.get("url")
                rec["id"] = original_product.get("id")
                rec["source"] = original_product.get("source") # Source'u düzelt
                final_recommendations.append(rec)
        
        return StructuredAnswer(
            introductory_text=ai_response_json.get("introductory_text", ""),
            recommendations=final_recommendations
        )

    except Exception as e:
        print(f"AI Error: {e}")
        # Hata durumunda fallback (AI yorumu olmadan dön)
        return StructuredAnswer(
            introductory_text="Yapay zeka bağlantısında sorun oldu, ancak bulduğum ürünler şunlar:",
            recommendations=[AIRecommendation(**p, ai_commentary="Yorum yüklenemedi.") for p in best_products[:3]]
        )
        # ==================== AUTH ENDPOINTS ====================

@app.post("/auth/register", response_model=UserResponse, tags=["Authentication"])
async def register(user: UserRegister):
    """Yeni kullanıcı kaydı"""
    # Email kontrolü
    existing_user = get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    
    # Şifre hash'le
    password_hash = hash_password(user.password)
    
    # Kullanıcı oluştur
    new_user = create_user(user.email, password_hash, user.name)
    
    if not new_user:
        raise HTTPException(status_code=500, detail="Kullanıcı oluşturulamadı")
    
    return UserResponse(
        id=new_user["id"],
        email=new_user["email"],
        name=new_user["name"],
        daily_searches_used=new_user["daily_searches_used"],
        daily_searches_limit=new_user["daily_searches_limit"],
        last_search_date=None
    )

@app.post("/auth/login", tags=["Authentication"])
async def login(credentials: UserLogin):
    """Kullanıcı girişi"""
    # Kullanıcıyı bul
    user = get_user_by_email(credentials.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")
    
    # Şifre kontrolü
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")
    
    # Token oluştur
    token = create_access_token({"user_id": user["id"], "email": user["email"]})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "daily_searches_used": user["daily_searches_used"],
            "daily_searches_limit": user["daily_searches_limit"]
        }
    }

@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Mevcut kullanıcı bilgilerini getir"""
    from datetime import date
    
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    # Gün değişmişse arama hakkını sıfırla
    today = date.today()
    last_date = user["last_search_date"]
    
    if last_date != today:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET daily_searches_used = 0, last_search_date = CURRENT_DATE WHERE id = %s",
            (user["id"],)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        # User objesini güncelle
        user["daily_searches_used"] = 0
        user["last_search_date"] = today
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        daily_searches_used=user["daily_searches_used"],
        daily_searches_limit=user["daily_searches_limit"],
        last_search_date=str(user["last_search_date"]) if user["last_search_date"] else None
    )
@app.get("/search_history")
async def get_user_search_history(current_user: dict = Depends(get_current_user)):
    """Kullanıcının arama geçmişini getir"""
    try:
        history = get_search_history(current_user["user_id"], limit=10)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)