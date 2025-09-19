# -*- coding: utf-8 -*-
"""
Hepsiburada, Trendyol, Vatan, İncehesap, Amazon.com.tr, MediaMarkt, N11, Itopya, Gaming.gen.tr ve Gamegaraj destekli scraper.
- Akıllı bekleme: çoklu seçici + görünürlük
- HB: 'Tüm Özellikler' sekmesini açmayı dener; detay tablo → özet tablo fallback
- TY: HTML attributes + JSON-LD (additionalProperty) fallback
- Vatan: Alternatif seçiciler + JSON-LD offers.name/price fallback
- İncehesap: 'Tüm Özellikler' butonunu açar, JSON-LD ve DOM fallback ile veri toplar
- Amazon: Güvenilir ID ve sınıf bazlı seçicilerle veri toplar
- MediaMarkt: Pop-up'ları yönetir, özellikleri genişletir ve modern HTML yapısından veri toplar
- N11: Pop-up'ları yönetir, 'Daha Fazla Özellik' butonuna tıklar ve esnek spec ayrıştırma yapar
- Itopya: Ürün adından specleri ayırır ve güvenilir fiyat seçicilerini kullanır
- Gaming.gen.tr: 'Model Bilgileri' ve 'Tavsiye Sistem' tablolarından özellikleri toplar
- Gamegaraj: Liste ve iconlu yapılarından özellikleri çıkarır, esnek seçicilerle çalışır
"""

from __future__ import annotations
import re
import json
import time
import random
from typing import Dict, Any, Optional, List

from bs4 import BeautifulSoup

# --- Selenium ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# Genel ayarlar
# =========================

COMMON_BRANDS = [
    "MSI", "Apple", "Samsung", "Xiaomi", "Asus", "Acer", "Lenovo", "HP", "Dell", "Huawei", "Gigabyte", "Monster", "AMD", "Intel", "CASPER",
    "ASUS ROG", "ASRock", "Inno3D", "Palit", "Zotac", "Sapphire", "PowerColor", "XFX", "PNY", "NVIDIA", "AIGO", "Corsair", "Kingston", "Crucial",
    "WD", "Seagate", "GAMING", "GAMEGARAGE", "INCEHESAP"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]

def _pick_ua() -> str:
    return random.choice(USER_AGENTS)

# =========================
# Selenium yardımcıları
# =========================

def _build_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(f"user-agent={_pick_ua()}")
    opts.add_argument("--lang=tr-TR,tr")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=opts,
    )
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(60)
    return driver

def _scroll_soft(driver: webdriver.Chrome, steps: int = 4, pause: float = 0.6):
    for _ in range(steps):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight/4);")
        time.sleep(pause)

def wait_any_selector(driver: webdriver.Chrome, selectors: List[str], timeout: int = 60, visible: bool = True) -> str:
    end = time.time() + timeout
    last_err = None
    while time.time() < end:
        for sel in selectors:
            try:
                if visible:
                    WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
                else:
                    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                print(f"[Scraper] Seçici bulundu: {sel}")
                return sel
            except Exception as e:
                last_err = e
        time.sleep(0.5)
    if last_err:
        raise last_err
    raise TimeoutException(f"Seçicilerden hiçbiri bulunamadı: {selectors}")

def click_if_exists(driver: webdriver.Chrome, selectors: List[str], by: By = By.CSS_SELECTOR) -> bool:
    for sel in selectors:
        try:
            wait = WebDriverWait(driver, 3)
            element = wait.until(EC.element_to_be_clickable((by, sel)))
            driver.execute_script("arguments[0].click();", element)
            time.sleep(0.8)
            print(f"[Scraper] Tıklama başarılı: {sel}")
            return True
        except Exception:
            continue
    return False

# =========================
# Ortak yardımcılar
# =========================

def _parse_price(price_text: Optional[str]) -> Optional[float]:
    """Türkçe formatlı fiyatları güvenilir şekilde ayrıştıran yenilenmiş fonksiyon."""
    if not price_text:
        return None
    try:
        cleaned_text = re.sub(r"[.TL₺\s]", "", str(price_text)).strip()
        cleaned_text = cleaned_text.replace(",", ".")
        if cleaned_text.endswith(','):
            cleaned_text = cleaned_text[:-1]
        val = float(cleaned_text)
        return val if val > 10 else None
    except (ValueError, TypeError):
        price_re = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)")
        m = price_re.search(price_text)
        if m:
            v = m.group(1).replace(".", "").replace(" ", "").replace(",", ".")
            try:
                val = float(v)
                return val if val > 10 else None
            except:
                return None
    return None

def _find_text(soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
    results = []
    for s in selectors:
        try:
            el = soup.select_one(s)
            if el:
                txt = el.get_text(strip=True)
                print(f"[Scraper] _find_text: Seçici '{s}' bulundu, metin: '{txt}'")
                results.append((s, txt))
                if txt:
                    return txt
                else:
                    print(f"[Scraper] _find_text: Seçici '{s}' bulundu ama metin boş")
            else:
                print(f"[Scraper] _find_text: Seçici '{s}' bulunamadı")
        except Exception as e:
            print(f"[Scraper] _find_text: Seçici '{s}' için hata: {e}")
    if results:
        print(f"[Scraper] _find_text: Tüm fiyat sonuçları: {results}")
    return None

def _meta(soup: BeautifulSoup, sel: str, attr: str = "content") -> Optional[str]:
    el = soup.select_one(sel)
    if el and el.has_attr(attr):
        val = (el.get(attr) or "").strip()
        print(f"[Scraper] _meta: Seçici '{sel}' bulundu, {attr}: '{val}'")
        return val or None
    print(f"[Scraper] _meta: Seçici '{sel}' bulunamadı")
    return None

def _guess_brand(title: Optional[str], specs: Optional[Dict[str, str]] = None, url: str = "") -> Optional[str]:
    if specs and isinstance(specs, dict) and "Marka" in specs and specs["Marka"]:
        return specs["Marka"]
    if not title:
        return None
    for b in COMMON_BRANDS:
        if b.lower() in title.lower():
            if "incehesap.com" in url and "Tavsiye Sistem" in title:
                return "INCEHESAP"
            return b
    if "gaming.gen.tr" in url:
        return "GAMING"
    if "gamegaraj.com" in url:
        return "GAMEGARAGE"
    if "itopya.com" in url:
        return "ITOPYA"
    return None

# =========================
# Hepsiburada
# =========================

def hb_before_capture(driver: webdriver.Chrome):
    _scroll_soft(driver, steps=3, pause=0.5)
    click_if_exists(driver, [
        '#specifications button',
        'a[data-test-id="product-tech-specs"]',
        'a[href="#productTechSpecContainer"]',
    ])
    _scroll_soft(driver, steps=2, pause=0.4)

def _hb_specs_table(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    table_container = soup.select_one('div#specifications, #productTechSpecContainer')
    if not table_container:
        return specs
    for row in table_container.select('tr'):
        key_el = row.select_one('th, .spec-key, th > a')
        val_el = row.select_one('td, .spec-value, td > a')
        if key_el and val_el:
            key = key_el.get_text(strip=True)
            val = val_el.get_text(strip=True)
            if key and val:
                specs[key] = val
    return specs

def _hb_specs_summary(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    container = soup.select_one('#techSpecs')
    if not container:
        return specs
    for row in container.select('div'):
        k = row.select_one('.OXP5AzPvafgN_i3y6wGp')
        v = row.select_one('.AxM3TmSghcDRH1F871Vh')
        if k and v:
            key = k.get_text(strip=True)
            val = v.get_text(strip=True)
            if key and val:
                specs[key] = val
    return specs

def _scrape_hepsiburada(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "hepsiburada", "url": url}
    data["name"] = _find_text(soup, ['h1[data-test-id="title"]', 'h1[itemprop="name"]'])
    price_text = _find_text(soup, ['span[data-test-id="price-current-price"]', '[data-test-id="price-current-price"]'])
    data["brand"] = _guess_brand(data["name"], url=url) or _meta(soup, 'meta[itemprop="brand"]')
    data["price"] = _parse_price(price_text)

    specs = _hb_specs_table(soup)
    if not specs:
        print("[Scraper] Hepsiburada: Detaylı tablo bulunamadı, özet tablo deneniyor.")
        specs = _hb_specs_summary(soup)
    data["specs"] = specs

    if not data.get("name") or not data.get("price"):
        return None
    return data

# =========================
# Trendyol
# =========================

def _ty_specs_html(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    container = soup.select_one('div.attributes, ul.detail-attr-container')
    if not container:
        return specs
    items = container.select('.attribute-item, li.detail-attr-item')
    for it in items:
        spans = it.find_all('span')
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True)
            val = spans[1].get_text(strip=True)
            if key and val:
                specs[key] = val
    return specs

def _ty_specs_jsonld(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(script.string or "{}")
        except Exception:
            continue
        objs = obj if isinstance(obj, list) else [obj]
        for o in objs:
            if not isinstance(o, dict): continue
            addp = o.get("additionalProperty")
            if isinstance(addp, list):
                for ap in addp:
                    n, v = (ap or {}).get("name"), (ap or {}).get("value") or (ap or {}).get("unitText")
                    if n and v: specs[str(n).strip()] = str(v).strip()
    return specs

def _scrape_trendyol(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "trendyol", "url": url}
    title_el = soup.select_one('h1[data-testid="product-title"], h1.pr-new-br')
    data["name"] = (title_el.get_text(strip=True) if title_el else None) or _meta(soup, 'meta[property="og:title"]')
    brand_el = soup.select_one('h1[data-testid="product-title"] a, h1.pr-new-br a, h1.pr-new-br strong')
    data["brand"] = (brand_el.get_text(strip=True) if brand_el else _guess_brand(data["name"], url=url)) or _meta(soup, 'meta[itemprop="brand"]')
    price_text = _find_text(soup, ['.price-container .discounted', 'span.prc-dsc', 'span.price__current', 'span.pr-bx-w']) or \
                 _meta(soup, 'meta[itemprop="price"]') or _meta(soup, 'meta[property="product:price:amount"]')
    data["price"] = _parse_price(price_text)
    data["specs"] = _ty_specs_html(soup) or _ty_specs_jsonld(soup)
    if not data.get("name") or not data.get("price"): return None
    return data

# =========================
# Vatan Bilgisayar
# =========================

def _vatan_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    for box in soup.select('div.row.highlights div.highlights-box'):
        k, v = box.find('span'), box.find('h3')
        if k and v:
            key, val = k.get_text(strip=True), v.get_text(strip=True)
            if key and val: specs[key] = val
    for row in soup.select('div.product-feature tr'):
        tds = row.find_all('td')
        if len(tds) == 2:
            key, val = tds[0].get_text(strip=True), tds[1].get_text(strip=True)
            if key and val: specs[key] = val
    return specs

def _vatan_from_jsonld(soup: BeautifulSoup) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(script.string or "{}")
        except Exception:
            continue
        for o in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(o, dict) or o.get("@type") != "Product": continue
            if not out.get("name"): out["name"] = (o.get("name") or "").strip() or None
            brand = o.get("brand")
            if isinstance(brand, dict) and brand.get("name") and not out.get("brand"):
                out["brand"] = (brand.get("name") or "").strip()
            elif isinstance(brand, str) and not out.get("brand"):
                out["brand"] = brand.strip()
            offers = o.get("offers")
            price_val = None
            if isinstance(offers, dict):
                price_val = offers.get("price") or offers.get("lowPrice")
            elif isinstance(offers, list) and offers and isinstance(offers[0], dict):
                price_val = offers[0].get("price") or offers[0].get("lowPrice")
            if price_val and not out.get("price"): out["price"] = _parse_price(str(price_val))
    return out

def _scrape_vatan(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "vatan", "url": url}
    title = _find_text(soup, ['h1.product-detail__title', 'h1.product-list__product-name', 'h1#product-name']) \
            or _meta(soup, 'meta[property="og:title"]')
    if title:
        title = title.split('fiyatı')[0].split(' özellikleri')[0].strip()
    price_text = _find_text(soup, ['span.product-list__price', '.product-detail__price', 'span#offering-price']) \
                 or _meta(soup, 'meta[itemprop="price"]') or _meta(soup, 'meta[property="product:price:amount"]')

    j_data = _vatan_from_jsonld(soup)
    data["name"] = title or j_data.get("name")
    data["price"] = _parse_price(price_text) or j_data.get("price")
    data["brand"] = _guess_brand(data["name"], url=url) or j_data.get("brand")
    data["specs"] = _vatan_specs(soup)

    if not data.get("name") or not data.get("price") or data.get("name") == "Ürün Yorumları": return None
    return data

# =========================
# İncehesap
# =========================

def _incehesap_wait_specs_loaded(wait: WebDriverWait) -> None:
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.prose.prose-neutral table")))
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.prose.prose-neutral table tbody tr")) >= 3)

def incehesap_before_capture(driver: webdriver.Chrome):
    wait = WebDriverWait(driver, 10)
    print("[Scraper] İncehesap: Pop-up'lar yönetiliyor...")
    click_if_exists(driver, ["//button[.//span[contains(., 'Kabul Et')] or contains(., 'Kabul Et')]"]), ("by=By.XPATH")
    
    try:
        all_specs_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(., 'Tüm Özellikler')] or contains(., 'Tüm Özellikler')]"))
        )
        driver.execute_script("arguments[0].click();", all_specs_btn)
        time.sleep(0.3)
        _incehesap_wait_specs_loaded(wait)
        print("[Scraper] İncehesap: 'Tüm Özellikler' tablosu başarıyla açıldı.")
    except Exception:
        print("[Scraper] İncehesap: 'Tüm Özellikler' butonu bulunamadı veya tıklanamadı (sorun olmayabilir).")
    
    print("[Scraper] İncehesap: İsim ve fiyat elementleri için bekleniyor...")
    name_price_selectors = ["h1", ".product-name", ".newPrice > ins", ".price", ".price-new", ".newPrice", "span[itemprop='price']"]
    try:
        wait_any_selector(driver, name_price_selectors, timeout=20, visible=True)
    except TimeoutException:
        print("[Scraper] İncehesap: İsim veya fiyat elementi için zaman aşımı, devam ediliyor...")
    
    print("[Scraper] İncehesap: Fiyat için JS kontrolü yapılıyor...")
    try:
        price_js = driver.execute_script("return document.querySelector('.newPrice > ins')?.innerText || null;")
        if price_js:
            print(f"[Scraper] İncehesap: JS ile fiyat bulundu: {price_js}")
        else:
            print("[Scraper] İncehesap: JS ile fiyat bulunamadı.")
    except Exception:
        print("[Scraper] İncehesap: JS fiyat kontrolü başarısız.")
    
    _scroll_soft(driver, steps=2, pause=0.3)

def _incehesap_collect_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    for table in soup.select("div.prose.prose-neutral table, table"):
        for tr in table.select("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                k, v = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
                if k and v: specs[k] = v
    dts, dds = soup.select("dl dt"), soup.select("dl dd")
    if dts and dds and len(dts) == len(dds):
        for dt, dd in zip(dts, dds):
            k, v = dt.get_text(strip=True), dd.get_text(strip=True)
            if k and v: specs[k] = v
    for li in soup.select("li"):
        txt = li.get_text(" ", strip=True)
        if ":" in txt:
            k, v = [p.strip() for p in txt.split(":", 1)]
            if k and v: specs[k] = v
    return specs

def _scrape_incehesap(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "incehesap", "url": url}
    name_selectors = ["h1", ".product-name", "h1.text-2xl", "h1.font-bold"]
    price_selectors = [".newPrice > ins", ".newPrice", ".price-new", ".price", "span[itemprop='price']", "ins"]
    
    data["name"] = _find_text(soup, name_selectors)
    print(f"[Scraper] İncehesap: Ürün ismi alındı: {data['name']}")
    price_text = _find_text(soup, price_selectors)
    print(f"[Scraper] İncehesap: Fiyat ham metni: {price_text}")
    data["price"] = _parse_price(price_text)
    
    # JSON-LD Fallback for price
    if not data["price"]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                obj = json.loads(script.string or "{}")
                if isinstance(obj, dict) and obj.get("@type") == "Product":
                    offers = obj.get("offers")
                    if offers and isinstance(offers, dict):
                        price_text = offers.get("price")
                        data["price"] = _parse_price(price_text)
                        print(f"[Scraper] İncehesap: JSON-LD ile fiyat alındı: {price_text}")
            except Exception:
                print("[Scraper] İncehesap: JSON-LD ayrıştırmada hata")
    
    print(f"[Scraper] İncehesap: Ayrıştırılmış fiyat: {data['price']}")
    data["brand"] = _guess_brand(data["name"], url=url) or _meta(soup, 'meta[itemprop="brand"]')
    data["specs"] = _incehesap_collect_specs(soup)

    if not data.get("name") or not data.get("price"):
        print(f"[Scraper] İncehesap HATA: İsim veya fiyat alınamadı. İsim: {data.get('name')}, Fiyat: {data.get('price')}")
        return None
    return data

# =========================
# Amazon.com.tr
# =========================

def _scrape_amazon(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "amazon.com.tr", "url": url}
    data["name"] = _find_text(soup, ["#productTitle"])
    price_text = _find_text(soup, ["#corePrice_feature_div .a-price-whole", ".a-price .a-offscreen"])
    data["price"] = _parse_price(price_text)
    data["brand"] = _guess_brand(data["name"], url=url) or _find_text(soup, ["#bylineInfo"])
    specs = {}
    for table in soup.select("#productDetails_techSpec_section_1, #technicalSpecifications_section"):
        for row in table.select("tr"):
            key = row.select_one("th")
            val = row.select_one("td")
            if key and val:
                k, v = key.get_text(strip=True), val.get_text(strip=True)
                if k and v: specs[k] = v
    data["specs"] = specs
    if not data.get("name") or not data.get("price"):
        return None
    return data

# =========================
# MediaMarkt
# =========================

def mediamarkt_handle_popups(driver: webdriver.Chrome) -> bool:
    popup_selectors = [
        'button#onetrust-accept-btn-handler',
        'button[data-test="cookie-accept-all"]',
        'button[id*="cookie"]',
        'button[class*="cookie"]',
    ]
    try:
        accept_button = None
        for selector in popup_selectors:
            try:
                accept_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                break
            except TimeoutException:
                continue

        if accept_button:
            print("[Scraper] MediaMarkt: Çerez kabul butonu bulundu, tıklanıyor...")
            banner_element = None
            for banner_selector in popup_selectors:
                try:
                    banner_element = driver.find_element(By.CSS_SELECTOR, banner_selector)
                    if banner_element:
                        break
                except NoSuchElementException:
                    continue
            
            driver.execute_script("arguments[0].click();", accept_button)
            print("✅ [Scraper] MediaMarkt: Çerez kabul butonu tıklandı")

            if banner_element:
                print("[Scraper] MediaMarkt: Pop-up'ın kaybolması bekleniyor...")
                WebDriverWait(driver, 5).until(EC.invisibility_of_element(banner_element))
                print("✅ [Scraper] MediaMarkt: Pop-up kayboldu.")
            else:
                time.sleep(1)
            return True
        else:
            print("[Scraper] MediaMarkt: Çerez pop-up'ı bulunamadı veya zaten kabul edilmiş.")
            return False
    except Exception as e:
        print(f"[Scraper] MediaMarkt: Pop-up kapatılırken genel bir hata oluştu: {e}")
        return False

def mediamarkt_expand_specs(driver: webdriver.Chrome):
    wait = WebDriverWait(driver, 10)
    spec_button_selectors = [
        'button[aria-controls*="features"]',
        'button#features',
        '//button[contains(text(), "Teknik özellikler")]',
        'button[data-test="show-all-product-features"]',
    ]
    
    for selector in spec_button_selectors:
        try:
            if selector.startswith('//'):
                element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
            else:
                element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", element)
            print(f"✅ [Scraper] MediaMarkt: Teknik özellikler butonu tıklandı.")
            time.sleep(2)
            return True
        except TimeoutException:
            continue
    print("❌ [Scraper] MediaMarkt: Teknik özellikler butonu bulunamadı.")
    return False

def mediamarkt_before_capture(driver: webdriver.Chrome):
    mediamarkt_handle_popups(driver)
    _scroll_soft(driver, steps=2, pause=0.4)
    mediamarkt_expand_specs(driver)
    _scroll_soft(driver, steps=2, pause=0.4)

def mediamarkt_extract_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    
    main_features_container = soup.select_one("div[data-test='mms-pdp-details-mainfeatures']")
    if main_features_container:
        for button in main_features_container.select("button"):
            spans = button.select("span")
            if len(spans) >= 2:
                key, val = spans[0].get_text(strip=True), spans[1].get_text(strip=True)
                if key and val: specs[key] = val

    features_content = soup.select_one("div[id='features-content']")
    if features_content:
        for table in features_content.select("table"):
            for row in table.select("tbody tr, tr"):
                cells = row.select("td, th")
                if len(cells) >= 2:
                    key, val = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
                    if key and val and key not in specs:
                        specs[key] = val
    return specs

def _scrape_mediamarkt(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "mediamarkt", "url": url}
    
    data["name"] = _find_text(soup, ['h1[data-test="product-title"]', 'h1'])
    price_text = _find_text(soup, ['span[data-test="branded-price-whole-value"]'])
    data["price"] = _parse_price(price_text)
    
    brand_text = _find_text(soup, ['a[data-test="manufacturer-link"]'])
    if brand_text:
        data["brand"] = brand_text
    else:
        brand_img = soup.select_one('a[data-test="manufacturer-link"] img, img.manufacturer-logo')
        if brand_img and brand_img.has_attr("alt"):
            data["brand"] = brand_img["alt"]
            print(f"[Scraper] MediaMarkt: Marka logo alt metninden alındı: {data['brand']}")
        else:
            data["brand"] = _guess_brand(data["name"], url=url)
    
    data["specs"] = mediamarkt_extract_specs(soup)

    if not data.get("name") or not data.get("price"):
        return None
        
    return data

# =========================
# N11
# =========================

def n11_before_capture(driver: webdriver.Chrome):
    print("[Scraper] N11: Pop-up'lar ve banner'lar yönetiliyor...")
    click_if_exists(driver, ["#cookieAccept"], by=By.CSS_SELECTOR)
    
    _scroll_soft(driver, steps=2, pause=0.5)
    
    more_specs_selector = 'p.unf-prop-more'
    try:
        element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, more_specs_selector)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        element.click()
        print("[Scraper] N11: 'Daha Fazla Ürün Özelliği' butonu tıklandı.")
        time.sleep(1)
    except TimeoutException:
        print("[Scraper] N11: 'Daha Fazla Ürün Özelliği' butonu bulunamadı veya zaten açık.")
    
    _scroll_soft(driver, steps=2, pause=0.4)

def _n11_extract_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    
    specs_container = soup.select_one('div.unf-prop-context ul.unf-prop-list')
    if specs_container:
        for item in specs_container.select('li.unf-prop-list-item'):
            children = item.find_all(['p', 'strong', 'span'])
            texts = [child.get_text(strip=True) for child in children if child.get_text(strip=True)]
            
            if len(texts) >= 2:
                key, value = texts[0], texts[1]
                if key and value:
                    specs[key] = value
            else:
                full_text = item.get_text(strip=True)
                match = re.match(r'([a-zA-ZğüşıöçĞÜŞİÖÇ\s\(\)/]+)(.+)', full_text)
                if match:
                    key, value = match.group(1).strip(), match.group(2).strip()
                    if key and value:
                        specs[key] = value

    if not specs:
        for table in soup.select("div#unf-prop table, div.product-properties table"):
            for row in table.select("tr"):
                cells = row.select("td")
                if len(cells) == 2:
                    key, value = cells[0].get_text(strip=True), cells[1].get_text(strip=True)
                    if key and value:
                        specs[key] = value

    return specs

def _scrape_n11(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "n11", "url": url}
    
    data["name"] = _find_text(soup, ['h1.proName'])
    
    price_text = _find_text(soup, [
        'div.newPrice ins', 'div.priceContainer ins', 'div.priceDetail ins',
    ])
    data["price"] = _parse_price(price_text)
    
    data["brand"] = _guess_brand(data["name"], url=url)
    
    data["specs"] = _n11_extract_specs(soup)
    
    if not data.get("name") or not data.get("price"):
        return None
        
    return data

# =========================
# Itopya
# =========================

def itopya_before_capture(driver: webdriver.Chrome):
    print("[Scraper] Itopya: Pop-up'lar yönetiliyor...")
    click_if_exists(driver, ["#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"], by=By.CSS_SELECTOR)
    try:
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".price, .newPrice > ins")))
        print("[Scraper] Itopya: Fiyat elementi bulundu.")
    except TimeoutException:
        print("[Scraper] Itopya: Fiyat elementi için zaman aşımı.")
    _scroll_soft(driver, steps=2, pause=0.5)

def _scrape_itopya(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "itopya", "url": url}
    
    full_name = _find_text(soup, [".product-name-title", "h1"])
    
    if full_name and ' / ' in full_name:
        name_and_specs = full_name.split(' / ')
        data["name"] = name_and_specs[0].strip()
        
        specs = {}
        if len(name_and_specs) > 1:
            for spec_item in name_and_specs[1:]:
                spec_parts = spec_item.split(':')
                if len(spec_parts) > 1:
                    key = spec_parts[0].strip()
                    value = ':'.join(spec_parts[1:]).strip()
                    specs[key] = value
                else:
                    specs[f"Özellik {len(specs) + 1}"] = spec_item.strip()
        data["specs"] = specs
    else:
        data["name"] = full_name
        data["specs"] = {}

    price_text = _find_text(soup, [".price", ".newPrice > ins", ".product-new-price", ".newPrice ins", "span.fyatsyt"])
    data["price"] = _parse_price(price_text)
    data["brand"] = _guess_brand(data["name"], url=url)
    
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(script.string or "{}")
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Product":
            if not data.get("name"):
                data["name"] = obj.get("name")
            if not data.get("price") and obj.get("offers"):
                data["price"] = _parse_price(obj["offers"].get("price"))
            if not data.get("brand") and obj.get("brand"):
                if isinstance(obj["brand"], dict):
                    data["brand"] = obj["brand"].get("name")
                else:
                    data["brand"] = obj["brand"]

    if not data.get("name") or not data.get("price"):
        return None
        
    return data

# =========================
# Gaming.gen.tr
# =========================

def extract_gaming_gen_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    all_tables = soup.select("table.woocommerce-product-attributes.shop_attributes, table.shop_attributes")
    print(f"[Scraper] Gaming.gen.tr: {len(all_tables)} adet spec tablosu bulundu.")
    
    for table in all_tables:
        rows = table.select("tr")
        for row in rows:
            key_element = row.select_one("th.woocommerce-product-attributes-item__label")
            value_element = row.select_one("td.woocommerce-product-attributes-item__value")
            if key_element and value_element:
                key = key_element.get_text(strip=True)
                value = value_element.get_text(strip=True)
                if key and value and key not in specs:
                    specs[key] = value
                    print(f"[Scraper] Spec bulundu: {key}: {value}")

    if not specs:
        print("[Scraper] UYARI: Hiçbir spec bilgisi alınamadı.")
    return specs

def _gaming_gen_before_capture(driver: webdriver.Chrome):
    print("[Scraper] Gaming.gen.tr: Pop-up'lar ve özellikler butonu yönetiliyor...")
    click_if_exists(driver, ["button[id*='cookie']", ".cookie-accept"])
    _scroll_soft(driver, steps=4, pause=0.7)
    
    specs_button_selectors = [
        "a[href*='#tab-additional_information']", 
        "li.additional_information_tab a"
    ]
    print("[Scraper] Gaming.gen.tr: Teknik özellikler butonu aranıyor...")
    if click_if_exists(driver, specs_button_selectors):
        print("[Scraper] Teknik özellikler butonu tıklandı.")
    else:
        print("[Scraper] Uyarı: Teknik özellikler butonu bulunamadı, muhtemelen zaten açık.")
    
    time.sleep(2)
    _scroll_soft(driver, steps=2, pause=0.5)

def _scrape_gaming_gen(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "gaming.gen.tr", "url": url}
    name_selectors = ["h1.product_title.entry-title", ".product_title", "h1"]
    data["name"] = _find_text(soup, name_selectors)
    
    price = None
    discount_price_element = soup.select_one("p.price > ins .woocommerce-Price-amount")
    if discount_price_element:
        price_text = discount_price_element.get_text(strip=True)
        price = _parse_price(price_text)
        print(f"[Scraper] Öncelikli (indirimli) fiyat bulundu: '{price_text}', çevrilen değer: {price}")
    
    if not price:
        main_price_element = soup.select_one("p.price .woocommerce-Price-amount")
        if main_price_element:
            price_text = main_price_element.get_text(strip=True)
            price = _parse_price(price_text)
            print(f"[Scraper] Genel fiyat bulundu: '{price_text}', çevrilen değer: {price}")

    data["price"] = price
    data["specs"] = extract_gaming_gen_specs(soup)
    data["brand"] = _guess_brand(data["name"], data["specs"], url)

    if not data.get("name") or not data.get("price"):
        print(f"[Scraper] HATA: Temel bilgiler (isim veya fiyat) alınamadı.")
        return None
    return data

# =========================
# Gamegaraj
# =========================

def extract_gamegaraj_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    specs_list_selectors = [
        "ul.my-4.space-y-1",
        "ul[class*='my-4'][class*='space-y-1']",
        "ul.my-4",
        ".space-y-1",
        "ul"
    ]
    
    for selector in specs_list_selectors:
        ul_element = soup.select_one(selector)
        if ul_element:
            print(f"[Scraper] Specs listesi bulundu: {selector}")
            li_elements = ul_element.select("li")
            print(f"[Scraper] {len(li_elements)} spec elementi bulundu")
            
            for li in li_elements:
                full_text = li.get_text(strip=True)
                print(f"[Scraper] Li text: {full_text[:100]}...")
                if ":" in full_text:
                    parts = full_text.split(":", 1)
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key and value:
                        specs[key] = value
                elif full_text:
                    key = f"Özellik {len(specs) + 1}"
                    specs[key] = full_text
            if specs:
                break
    
    if not specs:
        print("[Scraper] Liste bulunamadı, iconlu yapı deneniyor...")
        icon_containers = soup.select("div[class*='flex'][class*='items-center']")
        for container in icon_containers:
            text_elements = container.select("span, p, div")
            for text_el in text_elements:
                text = text_el.get_text(strip=True)
                if len(text) > 5 and any(keyword in text.lower() for keyword in ['amd', 'intel', 'rtx', 'gtx', 'gb', 'tb', 'ssd', 'hdd']):
                    key = f"Özellik {len(specs) + 1}"
                    specs[key] = text
    
    if not specs:
        print("[Scraper] Hiçbir yapıda spec bulunamadı, genel arama yapılıyor...")
        page_text = soup.get_text()
        patterns = [
            r'İşlemci[:\s]+([^\n]+)',
            r'Ekran Kartı[:\s]+([^\n]+)', 
            r'RAM[:\s]+([^\n]+)',
            r'SSD[:\s]+([^\n]+)',
            r'Soğutucu[:\s]+([^\n]+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                key = pattern.split('[')[0]
                specs[key] = matches[0].strip()
    
    print(f"[Scraper] Gamegaraj: {len(specs)} spec bulundu.")
    return specs

def _gamegaraj_before_capture(driver: webdriver.Chrome):
    print("[Scraper] GameGaraj: Pop-up'lar ve çerezler yönetiliyor...")
    cookie_selectors = [
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "button[id*='cookie']",
        "button[class*='cookie']",
        "button[data-test='accept-cookies']",
        ".cookie-accept",
        ".accept-all",
        "//button[contains(text(), 'Kabul') or contains(text(), 'Accept')]"
    ]
    
    for sel in cookie_selectors:
        if sel.startswith("//"):
            if click_if_exists(driver, [sel], by=By.XPATH):
                print("[Scraper] Çerez butonu tıklandı (XPath)")
                break
        else:
            if click_if_exists(driver, [sel]):
                print("[Scraper] Çerez butonu tıklandı (CSS)")
                break
    
    _scroll_soft(driver, steps=3, pause=0.5)

def _scrape_gamegaraj(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    data: Dict[str, Any] = {"source": "gamegaraj", "url": url}
    name_selectors = [
        "h2.mt-1.text-2xl.font-semibold.text-gray-900",
        "h2[class*='mt-1'][class*='text-2xl'][class*='font-semibold']",
        "h2.mt-1",
        "h2",
        "h1"
    ]
    
    price_selectors = [
        "p.text-3xl.font-extrabold.text-gray-900",
        "p[class*='text-3xl'][class*='font-extrabold'][class*='text-gray-900']",
        "p.text-3xl.font-extrabold",
        "p.text-3xl",
        "p[id='openInstallment']",
        "p[class*='text-3xl']",
    ]
    
    data["name"] = _find_text(soup, name_selectors)
    print(f"[Scraper] Gamegaraj: Ürün ismi alındı: {data['name']}")
    price_text = _find_text(soup, price_selectors)
    print(f"[Scraper] Gamegaraj: Fiyat ham metni: {price_text}")
    data["price"] = _parse_price(price_text)
    print(f"[Scraper] Gamegaraj: Ayrıştırılmış fiyat: {data['price']}")
    data["specs"] = extract_gamegaraj_specs(soup)
    data["brand"] = _guess_brand(data["name"], data["specs"], url)

    if not data.get("name") or not data.get("price"):
        print(f"[Scraper] Gamegaraj HATA: İsim veya fiyat alınamadı. İsim: {data.get('name')}, Fiyat: {data.get('price')}")
        all_paragraphs = soup.find_all('p')
        print(f"[Scraper] Toplam paragraf sayısı: {len(all_paragraphs)}")
        for i, p in enumerate(all_paragraphs[:10]):
            text = p.get_text(strip=True)
            if '₺' in text or 'TL' in text or re.search(r'\d{2,}', text):
                print(f"[Scraper] Paragraf {i}: {text[:50]}...")
        return None
        
    return data

# =========================
# Site konfigürasyonları
# =========================

SITE_CONFIG = {
    "hepsiburada.com": {
        "parser": _scrape_hepsiburada,
        "wait_for_any": ['h1[data-test-id="title"]', 'h1[itemprop="name"]', '[data-test-id="price-current-price"]'],
        "before_capture": hb_before_capture,
    },
    "trendyol.com": {
        "parser": _scrape_trendyol,
        "wait_for_any": ['h1[data-testid="product-title"]', 'h1.pr-new-br', '.price-container .discounted'],
        "before_capture": None,
    },
    "vatanbilgisayar.com": {
        "parser": _scrape_vatan,
        "wait_for_any": ['h1.product-detail__title', 'h1.product-list__product-name', '.product-list__price'],
        "before_capture": None,
    },
    "incehesap.com": {
        "parser": _scrape_incehesap,
        "wait_for_any": ["h1", ".product-name", ".newPrice > ins", ".price", ".price-new", ".newPrice", "span[itemprop='price']"],
        "before_capture": incehesap_before_capture,
    },
    "amazon.com.tr": {
        "parser": _scrape_amazon,
        "wait_for_any": ["#productTitle", "#centerCol", "div#corePrice_feature_div"],
        "before_capture": None,
    },
    "mediamarkt.com.tr": {
        "parser": _scrape_mediamarkt,
        "wait_for_any": ['h1[data-test="product-title"]', 'span[data-test="branded-price-whole-value"]'],
        "before_capture": mediamarkt_before_capture,
    },
    "n11.com": {
        "parser": _scrape_n11,
        "wait_for_any": ['h1.proName', 'div.newPrice ins'],
        "before_capture": n11_before_capture,
    },
    "itopya.com": {
        "parser": _scrape_itopya,
        "wait_for_any": ['.product-name-title', '.price', ".newPrice > ins", "h1"],
        "before_capture": itopya_before_capture,
    },
    "gaming.gen.tr": {
        "parser": _scrape_gaming_gen,
        "wait_for_any": ["h1.product_title.entry-title", ".price", "body"],
        "before_capture": _gaming_gen_before_capture,
    },
    "gamegaraj.com": {
        "parser": _scrape_gamegaraj,
        "wait_for_any": ["h1", "body", ".price", ".product-title", ".container", "main", "#app"],
        "before_capture": _gamegaraj_before_capture,
    },
}

# =========================
# Ana akış
# =========================

def get_page_html_with_selenium(url: str, wait_for_any: Optional[List[str]] = None, before_capture=None) -> Optional[str]:
    driver = None
    try:
        driver = _build_driver()
        print(f"[Scraper] Selenium ile sayfa açılıyor: {url[:80]}...")
        driver.get(url)

        if before_capture:
            try:
                before_capture(driver)
            except Exception as e:
                print(f"[Scraper] 'before_capture' adımında hata: {e}")
                pass

        _scroll_soft(driver, steps=2, pause=0.5)

        if wait_for_any:
            print("[Scraper] bir veya daha fazla seçici bekleniyor...")
            wait_any_selector(driver, wait_for_any, timeout=35, visible=True)

        html = driver.page_source
        if not html or len(html) < 3000:
            print("[Scraper] Uyarı: Kısa/boş HTML (bot koruması olabilir).")
            return None
        print(f"[Scraper] Başarılı: {len(html)} karakter alındı.")
        return html

    except TimeoutException:
        print(f"[Scraper] Zaman aşımı: {url}")
        return None
    except Exception as e:
        print(f"[Scraper] Selenium hatası: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def scrape_product_page(url: str) -> Optional[Dict[str, Any]]:
    domain_key = None
    for d in SITE_CONFIG.keys():
        if d in url:
            domain_key = d
            break
    if not domain_key:
        print(f"[Scraper] Desteklenmeyen site: {url}")
        return None

    cfg = SITE_CONFIG[domain_key]
    html = get_page_html_with_selenium(
        url,
        wait_for_any=cfg.get("wait_for_any"),
        before_capture=cfg.get("before_capture"),
    )
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    return cfg["parser"](soup, url)

if __name__ == "__main__":
    tests = [
        "https://www.hepsiburada.com/msi-cyborg-15-a13vf-892xtr-intel-core-i7-13620h-16gb-512gb-ssd-rtx4060-freedos-15-6-fhd-144hz-tasinabilir-bilgisayar-p-HBCV00005T87HT",
        "https://www.trendyol.com/apple/iphone-air-256gb-uzay-siyahi-p-985256818",
        "https://www.vatanbilgisayar.com/amd-r5-7500f-rtx5070-oc-12g-b650m-r-500gb-ssd-16gb-ram.html",
        "https://www.incehesap.com/apex-fusion-tavsiye-sistem-fiyati-83546",
        "https://www.amazon.com.tr/Samsung-Telefon-Android-Türkiye-Garantili/dp/B0DWXYDS8S",
        "https://www.mediamarkt.com.tr/tr/product/_apple-iphone-15-128-gb-akilli-telefon-mavi-mtp43tua-1232436.html",
        "https://www.n11.com/urun/apple-iphone-16-pro-max-256-gb-apple-turkiye-garantili-59257800",
        "https://www.itopya.com/ali-bicim-kanks-intel-core-i5-14600k-asus-geforce-rtx-5060-8gb-16gb-ddr5-1tb-m2-ssd-gefor_h30618",
        "https://www.gaming.gen.tr/urun/718896/vortex-5060ti-intel-i5-14400f-tray-msi-geforce-rtx-5060-ti-16g-shadow-2x-oc-plus-16gb-16gb-ram-1tb-m-2-ssd/",
        "https://www.gamegaraj.com/tavsiye-sistemler/gravix-5a/",
    ]
    for u in tests:
        print("\n" + "="*80)
        print(f"--- Scraper Test Başlatıldı: {u} ---")
        print("="*80)
        data = scrape_product_page(u)
        if data:
            print("\n✅ BAŞARILI KAZIMA SONUCU:")
            print(f"  Site: {data.get('source')}")
            print(f"  Ürün: {data.get('name')}")
            print(f"  Marka: {data.get('brand')}")
            print(f"  Fiyat: {data.get('price')} TL")
            specs = data.get("specs") or {}
            print(f"  Spec Sayısı: {len(specs)}")
            if specs:
                print("  Örnek Spec'ler:")
                for k, v in list(specs.items())[:5]:
                    print(f"    - {k}: {v}")
        else:
            print("\n❌ KAZIMA BAŞARISIZ")