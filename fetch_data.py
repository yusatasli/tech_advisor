import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import re
import time
import json
import random
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

from logger import (  # type: ignore
    get_logger,
    retry_on_failure,
    handle_errors,
    monitor_performance,
    BenchmarkError
)

logger = get_logger("fetch_data")

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
]

# Fallback benchmark data - yaklaşık değerler
FALLBACK_CPU_BENCHMARKS = {
    # Mevcut PC İşlemcileri (İyi)
    "Intel Core i9-13980HX": 35000, "Intel Core i9-13900K": 42000, "Intel Core i9-13900KF": 42500,
    "Intel Core i7-13700K": 32000, "Intel Core i7-13700": 30000, "Intel Core i5-12400F": 18500,
    "Intel Core i5-13400F": 21000, "Intel Core i5-13600K": 28000, "AMD Ryzen 9 7950X": 45000,
    "AMD Ryzen 9 7900X": 38000, "AMD Ryzen 7 7700X": 32000, "AMD Ryzen 7 7745HX": 31000,
    "AMD Ryzen 5 7600X": 25000, "AMD Ryzen 5 5600": 17000, "AMD Ryzen 5 5600X": 18000,
    "Intel i7-12700H": 26000, "Intel i5-12500H": 21000, "Ryzen 7 6800H": 23000,

    # YENİ EKLENEN MOBİL İŞLEMCİLER
    "Apple A17 Pro": 15500,
    "Apple A16 Bionic": 14000,
    "Snapdragon 8 Gen 3": 17000,
    "Snapdragon 8 Gen 2": 14500,
    "Snapdragon 8+ Gen 1": 12500,
    "Google Tensor G3": 11000,
    "Google Tensor G2": 9500,
    "Google Tensor": 8000,
    "MediaTek Dimensity 9200": 13000,
    "MediaTek Dimensity 8100": 10500,
    "MediaTek Dimensity 1080": 7000,
    "Exynos 1380": 7200,
    "Exynos 1280": 6500,
    "Snapdragon 695 5G": 6000,
    "Kirin 9000S": 9800,
    "Snapdragon 480 5G": 4500,
    "Dimensity 900": 6800
}

# Yaklaşık G3D Mark puanları
FALLBACK_GPU_BENCHMARKS = {
    # Bu liste şimdilik yeterli görünüyor, gerekirse genişletilebilir
    "NVIDIA GeForce RTX 4090": 28000, "NVIDIA GeForce RTX 4080": 23000, "NVIDIA GeForce RTX 4070 Ti": 19000,
    "NVIDIA GeForce RTX 4070": 16000, "NVIDIA GeForce RTX 4060 Ti": 14000, "NVIDIA GeForce RTX 4060": 12000,
    "GeForce RTX 4090": 28000, "GeForce RTX 4080": 23000, "GeForce RTX 4070": 16000,
    "GeForce RTX 4060": 12000, "RTX 4090": 28000, "RTX 4080": 23000,
    "RTX 4070": 16000, "RTX 4060": 12000, "NVIDIA GeForce RTX 3090": 24000,
    "NVIDIA GeForce RTX 3080": 20000, "NVIDIA GeForce RTX 3070": 17000, "NVIDIA GeForce RTX 3060": 13000,
    "GeForce RTX 3090": 24000, "GeForce RTX 3080": 20000, "GeForce RTX 3070": 17000,
    "GeForce RTX 3060": 13000, "RTX 3090": 24000, "RTX 3080": 20000,
    "RTX 3070": 17000, "RTX 3060": 13000, "AMD Radeon RX 7900 XTX": 25000,
    "AMD Radeon RX 7900 XT": 22000, "AMD Radeon RX 7800 XT": 19000, "AMD Radeon RX 6900 XT": 21000,
    "AMD Radeon RX 6800 XT": 19000, "AMD Radeon RX 6700 XT": 16000, "Intel Iris Xe": 3000,
    "Intel UHD Graphics": 1200, "AMD Radeon Graphics": 2500,
}

# Yaklaşık AnTuTu (v10) Puanları
FALLBACK_ANTUTU_BENCHMARKS = {
    # Mevcut Olanlar
    "Apple iPhone 15 Pro Max": 1580000,
    "Samsung Galaxy S24 Ultra": 1850000,
    "Xiaomi 14 Pro": 2050000,
    "OnePlus 12": 2100000,
    "Google Pixel 8 Pro": 1150000,
    "Samsung Galaxy A54": 630000,
    "Xiaomi Redmi Note 12 Pro": 540000,

    # YENİ EKLENEN TELEFONLAR (data.py listesinden)
    "Google Pixel 6a": 710000,
    "OnePlus Nord CE 3 Lite": 410000,
    "Oppo Reno 8 Pro": 850000,
    "Honor Magic 5 Lite": 460000,
    "Realme GT Neo 3": 820000,
    "Nokia G400": 380000,
    "Vivo V25": 580000,
    "Samsung Galaxy M34": 480000,
    "iPhone 14 Pro": 1450000,
    "Samsung Galaxy S23 Ultra": 1550000,
    "Xiaomi 13 Pro": 1560000,
    "Google Pixel 7 Pro": 1050000,
    "Nothing Phone (2)": 1100000,
    "OnePlus 11": 1570000,
    "Huawei P60 Pro": 1200000,
    "Asus Zenfone 10": 1580000,
    "Samsung Galaxy Z Flip5": 1520000,
    "Xiaomi 14": 1980000,
    "iPhone 15 Pro": 1560000,
    "Samsung Galaxy Z Fold5": 1540000,
    "Huawei Mate 60 Pro+": 1100000
}

def get_random_headers() -> Dict[str, str]:
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

def normalize_component_name(name: str) -> str:
    if not name:
        return ""
    normalized = ' '.join(name.split()).strip()
    normalized = re.sub(r'\bNVIDIA\s+GeForce\s+', 'NVIDIA GeForce ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bGeForce\s+', 'GeForce ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bIntel\s+Core\s+', 'Intel Core ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bAMD\s+Ryzen\s+', 'AMD Ryzen ', normalized, flags=re.IGNORECASE)
    return normalized

def find_fallback_score(component_name: str, component_type: str) -> Optional[int]:
    if not component_name:
        return None
    normalized_name = normalize_component_name(component_name)
    
    # YENİ: antutu tipi eklendi
    if component_type == 'cpu':
        fallback_data = FALLBACK_CPU_BENCHMARKS
    elif component_type == 'gpu':
        fallback_data = FALLBACK_GPU_BENCHMARKS
    elif component_type == 'antutu':
        fallback_data = FALLBACK_ANTUTU_BENCHMARKS
    else:
        return None

    if normalized_name in fallback_data:
        logger.info(f"Exact fallback match found for {component_type}", component=normalized_name, score=fallback_data[normalized_name])
        return fallback_data[normalized_name]
    for key, score in fallback_data.items():
        if normalized_name.lower() in key.lower() or key.lower() in normalized_name.lower():
            logger.info(f"Partial fallback match found for {component_type}", component=normalized_name, matched_key=key, score=score)
            return score
    model_pattern = r'(\w+\s+\w+\s+\w*\d+\w*)'
    model_match = re.search(model_pattern, normalized_name, re.IGNORECASE)
    if model_match:
        model_name = model_match.group(1).strip()
        for key, score in fallback_data.items():
            if model_name.lower() in key.lower():
                logger.info(f"Model-based fallback match found for {component_type}", component=normalized_name, model=model_name, matched_key=key, score=score)
                return score
    logger.warning(f"No fallback benchmark found for {component_type}", component=normalized_name)
    return None

@retry_on_failure(max_attempts=2, delay=2.0, exceptions=(requests.RequestException, BenchmarkError))
@handle_errors(default_return=None, reraise=False)
def _fetch_page_content(url: str, timeout: int = 15) -> Optional[str]:
    headers = get_random_headers()
    try:
        logger.debug("Fetching page", url=url)
        time.sleep(random.uniform(1.0, 3.0))
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        logger.debug("Response received", url=url, status_code=resp.status_code, content_length=len(resp.text) if hasattr(resp, 'text') else 0)
        if resp.status_code == 403:
            raise BenchmarkError("Web sayfası erişimi engellendi (403 Forbidden)", context={"url": url, "status_code": 403})
        elif resp.status_code == 429:
            raise BenchmarkError("Rate limit aşıldı (429 Too Many Requests)", context={"url": url, "status_code": 429})
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.Timeout:
        raise BenchmarkError(f"Request timeout after {timeout}s", context={"url": url, "timeout": timeout})
    except requests.exceptions.ConnectionError as e:
        raise BenchmarkError(f"Connection error: {str(e)}", context={"url": url})
    except requests.exceptions.RequestException as e:
        raise BenchmarkError(f"Request failed: {str(e)}", context={"url": url})
    except Exception as e:
        logger.error("Web sayfası çekme hatası", url=url, error=str(e))
        raise BenchmarkError("Web sayfası çekme hatası", context={"url": url, "error": str(e)})

# YENİ FONKSİYON
@monitor_performance
def fetch_antutu_benchmark_score(phone_name: str) -> Optional[int]:
    """Telefonlar için kimovil.com'dan AnTuTu puanı çeker."""
    if not phone_name or not phone_name.strip():
        return None
    
    phone_name = phone_name.strip()
    logger.info(f"AnTuTu benchmark puanı aranıyor: {phone_name}")

    try:
        # kimovil URL'leri genellikle model adının '-' ile birleştirilmiş halidir
        encoded_name = quote_plus(phone_name).replace('+', '-')
        search_url = f"https://www.kimovil.com/tr/nerede-satin-alinir-{encoded_name}"
        
        logger.info(f"Kimovil'den AnTuTu puanı aranıyor", extra={"phone": phone_name, "url": search_url})
        content = _fetch_page_content(search_url)

        if content:
            soup = BeautifulSoup(content, 'html.parser')
            antutu_heading = soup.find('div', class_='name', text=re.compile(r'AnTuTu'))
            if antutu_heading:
                score_value_div = antutu_heading.find_next_sibling('div', class_='value')
                if score_value_div:
                    score_match = re.search(r'([\d\.]+)', score_value_div.text)
                    if score_match:
                        score = int(score_match.group(1).replace('.', ''))
                        logger.info(f"AnTuTu puanı bulundu: {score}", extra={"phone": phone_name})
                        return score
    except Exception as e:
        logger.warning(f"AnTuTu puanı web'den çekilemedi: {e}", extra={"phone": phone_name})

    fallback = find_fallback_score(phone_name, 'antutu')
    if fallback:
        return fallback

    logger.error(f"AnTuTu puanı bulunamadı.", extra={"phone": phone_name})
    return None

def create_benchmark_query(component_name: str) -> str:
    if not component_name:
        return ""
    clean_name = normalize_component_name(component_name)
    return f"{clean_name} benchmark"

@monitor_performance
def fetch_cpu_benchmark_score(cpu_name: str) -> Optional[int]:
    if not cpu_name or not cpu_name.strip():
        return None
    cpu_name = cpu_name.strip()
    normalized_name = normalize_component_name(cpu_name)
    logger.info(f"CPU benchmark puanı aranıyor: {cpu_name}")
    try:
        encoded_name = quote_plus(normalized_name)
        passmark_url = f"https://www.cpubenchmark.net/cpu.php?cpu={encoded_name}"
        logger.info("PassMark CPU puanı aranıyor.", cpu=normalized_name, url=passmark_url)
        content = _fetch_page_content(passmark_url)
        if content:
            score_patterns = [r'CPU Mark:\s*(\d+)', r'PassMark.*?(\d{4,6})', r'score.*?(\d{4,6})']
            for pattern in score_patterns:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    score = int(m.group(1))
                    if 1000 <= score <= 100000:
                        logger.info("PassMark CPU puanı bulundu", cpu=normalized_name, score=score)
                        return score
    except Exception as e:
        logger.warning("PassMark CPU puanı çekilemedi", cpu=normalized_name, error=str(e))
    fallback = find_fallback_score(normalized_name, 'cpu')
    if fallback:
        logger.info("CPU fallback puanı kullanılıyor", cpu=normalized_name, score=fallback)
        return fallback
    est = estimate_cpu_score(normalized_name)
    if est:
        logger.info("CPU puanı tahmin edildi", cpu=normalized_name, score=est)
        return est
    logger.error("CPU puanı çekme veya ayrıştırma hatası.", cpu=normalized_name)
    return None

@monitor_performance
def fetch_gpu_benchmark_score(gpu_name: str) -> Optional[int]:
    if not gpu_name or not gpu_name.strip():
        return None
    gpu_name = gpu_name.strip()
    normalized_name = normalize_component_name(gpu_name)
    logger.info(f"GPU benchmark puanı aranıyor: {gpu_name}")
    try:
        encoded_name = quote_plus(normalized_name)
        geekbench_url = f"https://browser.geekbench.com/search?q={encoded_name}"
        logger.info("Geekbench GPU puanı aranıyor.", gpu=normalized_name, url=geekbench_url)
        content = _fetch_page_content(geekbench_url)
        if content:
            m = re.search(r'Compute.*?(\d{4,6})', content, re.IGNORECASE)
            if m:
                score = int(m.group(1))
                if 1000 <= score <= 50000:
                    logger.info("Geekbench GPU puanı bulundu", gpu=normalized_name, score=score)
                    return score
    except Exception as e:
        logger.warning("Geekbench GPU puanı çekilemedi", gpu=normalized_name, error=str(e))
    fallback = find_fallback_score(normalized_name, 'gpu')
    if fallback:
        logger.info("GPU fallback puanı kullanılıyor", gpu=normalized_name, score=fallback)
        return fallback
    est = estimate_gpu_score(normalized_name)
    if est:
        logger.info("GPU puanı tahmin edildi", gpu=normalized_name, score=est)
        return est
    logger.error("GPU puanı çekme veya ayrıştırma hatası.", gpu=normalized_name)
    return None

def estimate_cpu_score(cpu_name: str) -> Optional[int]:
    if not cpu_name:
        return None
    name_lower = cpu_name.lower()
    if 'intel' in name_lower:
        if 'i9' in name_lower:
            if '13' in name_lower: return random.randint(35000, 45000)
            elif '12' in name_lower: return random.randint(30000, 40000)
            else: return random.randint(25000, 35000)
        elif 'i7' in name_lower:
            if '13' in name_lower: return random.randint(28000, 35000)
            elif '12' in name_lower: return random.randint(23000, 30000)
            else: return random.randint(18000, 25000)
        elif 'i5' in name_lower:
            if '13' in name_lower: return random.randint(18000, 25000)
            elif '12' in name_lower: return random.randint(15000, 22000)
            else: return random.randint(12000, 18000)
    elif 'ryzen' in name_lower:
        if 'ryzen 9' in name_lower:
            if '7' in name_lower: return random.randint(40000, 50000)
            else: return random.randint(30000, 40000)
        elif 'ryzen 7' in name_lower:
            if '7' in name_lower: return random.randint(28000, 35000)
            else: return random.randint(22000, 30000)
        elif 'ryzen 5' in name_lower:
            if '7' in name_lower: return random.randint(20000, 28000)
            else: return random.randint(15000, 22000)
    return None

def estimate_gpu_score(gpu_name: str) -> Optional[int]:
    if not gpu_name:
        return None
    name_lower = gpu_name.lower()
    if 'rtx' in name_lower:
        if '4090' in name_lower: return random.randint(26000, 30000)
        elif '4080' in name_lower: return random.randint(21000, 25000)
        elif '4070' in name_lower: return random.randint(14000, 18000)
        elif '4060' in name_lower: return random.randint(11000, 13000)
        elif '3090' in name_lower: return random.randint(22000, 26000)
        elif '3080' in name_lower: return random.randint(18000, 22000)
        elif '3070' in name_lower: return random.randint(15000, 19000)
        elif '3060' in name_lower: return random.randint(11000, 15000)
    elif 'radeon' in name_lower:
        if '7900' in name_lower: return random.randint(22000, 26000)
        elif '7800' in name_lower: return random.randint(17000, 21000)
        elif '6900' in name_lower: return random.randint(19000, 23000)
        elif '6800' in name_lower: return random.randint(17000, 21000)
    return None

@monitor_performance
def fetch_multiple_benchmarks(components: List[Dict[str, str]]) -> Dict[str, Optional[int]]:
    results = {}
    for component in components:
        comp_type = component.get('type')
        comp_name = component.get('name')
        if not comp_type or not comp_name:
            continue
        try:
            if comp_type == 'cpu':
                score = fetch_cpu_benchmark_score(comp_name)
            elif comp_type == 'gpu':
                score = fetch_gpu_benchmark_score(comp_name)
            else:
                score = None
            results[comp_name] = score
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            logger.error("Component benchmark failed", component=comp_name, type=comp_type, error=str(e))
            results[comp_name] = None
    return results

def health_check() -> Dict[str, Any]:
    # YENİ: antutu_count eklendi
    return {
        "fallback_cpu_count": len(FALLBACK_CPU_BENCHMARKS),
        "fallback_gpu_count": len(FALLBACK_GPU_BENCHMARKS),
        "fallback_antutu_count": len(FALLBACK_ANTUTU_BENCHMARKS),
        "user_agents_count": len(USER_AGENTS),
        "status": "ok"
    }

if __name__ == "__main__":
    logger.info("Starting benchmark fetch test")
    
    cpu_score = fetch_cpu_benchmark_score("Intel Core i5-12400F")
    print(f"Intel i5-12400F score: {cpu_score}")
    
    gpu_score = fetch_gpu_benchmark_score("NVIDIA GeForce RTX 4060")
    print(f"RTX 4060 score: {gpu_score}")

    # YENİ TEST EKLENDİ
    antutu_score = fetch_antutu_benchmark_score("Samsung Galaxy S24 Ultra")
    print(f"Samsung Galaxy S24 Ultra AnTuTu score: {antutu_score}")

    components = [
        {"type": "cpu", "name": "AMD Ryzen 5 5600"},
        {"type": "gpu", "name": "GeForce RTX 3070"},
    ]
    batch_results = fetch_multiple_benchmarks(components)
    print("Batch results:", batch_results)
    
    print("Health check:", health_check())

