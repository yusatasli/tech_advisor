import psycopg2
import psycopg2.extras
from typing import Dict, List, Any, Optional, Tuple
import json

from db import get_db_connection, create_tables, health_check
from data import products
from fetch_data import (
    fetch_cpu_benchmark_score,
    fetch_gpu_benchmark_score,
    fetch_antutu_benchmark_score,  # YENİ: AnTuTu fonksiyonu import edildi
    FALLBACK_CPU_BENCHMARKS,
    FALLBACK_GPU_BENCHMARKS
)
from logger import (
    get_logger,
    monitor_performance,
    handle_errors,
    DatabaseError,
    BenchmarkError
)

logger = get_logger("load_data")

@monitor_performance
@handle_errors(reraise=True)
def load_products() -> int:
    """Lokal ürünleri doğrulayıp, AnTuTu puanı çekip products tablosuna UPSERT eder."""
    logger.info("Ürün verileri yükleniyor...")
    success_count = 0
    error_count = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for p in products:
                try:
                    if not p.get('name') or not p.get('category'):
                        logger.warning("Ürün adı veya kategori eksik, atlanıyor", product_data=p)
                        error_count += 1
                        continue

                    specs = p.get('specs', {}) or {}
                    cpu_name = specs.get('CPU')
                    gpu_name = specs.get('GPU')

                    # YENİ: Kategori "Telefon" ise AnTuTu puanını çek
                    antutu_puanı = None
                    if p['category'].lower() == 'telefon':
                        antutu_puanı = fetch_antutu_benchmark_score(p['name'])

                    if cpu_name and len(cpu_name.strip()) < 3:
                        cpu_name = None
                    if gpu_name and len(gpu_name.strip()) < 3:
                        gpu_name = None

                    price = p.get('price')
                    if price is not None and (not isinstance(price, (int, float)) or price < 0):
                        logger.warning("Geçersiz fiyat, sıfırlanıyor", product_name=p['name'], price=price)
                        price = None

                    # YENİ: SQL sorgusuna antutu_score eklendi
                    cur.execute("""
                        INSERT INTO products (category, name, brand, price, cpu_name, gpu_name, antutu_score, specs, url, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (name)
                        DO UPDATE SET
                            category = EXCLUDED.category,
                            brand = EXCLUDED.brand,
                            price = EXCLUDED.price,
                            cpu_name = EXCLUDED.cpu_name,
                            gpu_name = EXCLUDED.gpu_name,
                            antutu_score = EXCLUDED.antutu_score,
                            specs = EXCLUDED.specs,
                            url = EXCLUDED.url,
                            source = EXCLUDED.source,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (
                        p['category'],
                        p['name'],
                        p.get('brand'),
                        price,
                        cpu_name,
                        gpu_name,
                        antutu_puanı,  # YENİ: AnTuTu puanı eklendi
                        json.dumps(specs),
                        p.get('url'),
                        "local_seed"
                    ))

                    success_count += 1

                except psycopg2.Error as e:
                    logger.error("Ürün yükleme hatası", product_name=p.get('name', 'unknown'), error=str(e))
                    conn.rollback()
                    error_count += 1
                except Exception as e:
                    logger.error("Beklenmeyen ürün yükleme hatası", product_name=p.get('name', 'unknown'), error=str(e))
                    error_count += 1

            conn.commit()

    logger.info(f"✅ Ürün yükleme tamamlandı. Başarılı: {success_count}, Hatalı: {error_count}, Toplam: {len(products)}")
    return success_count

def extract_components_from_products() -> Tuple[List[str], List[str]]:
    """Products tablosundan benzersiz CPU/GPU isimlerini çeker."""
    cpus = set()
    gpus = set()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT cpu_name FROM products
                WHERE cpu_name IS NOT NULL AND cpu_name <> '' AND LENGTH(cpu_name) > 3
            """)
            for row in cur.fetchall():
                if row['cpu_name']:
                    cpus.add(row['cpu_name'].strip())

            cur.execute("""
                SELECT DISTINCT gpu_name FROM products
                WHERE gpu_name IS NOT NULL AND gpu_name <> '' AND LENGTH(gpu_name) > 3
            """)
            for row in cur.fetchall():
                if row['gpu_name']:
                    gpus.add(row['gpu_name'].strip())

    logger.info("Bileşenler çıkarıldı", cpu_count=len(cpus), gpu_count=len(gpus))
    return list(cpus), list(gpus)

@monitor_performance
@handle_errors(reraise=True)
def load_cpu_benchmarks(source: str = "fetch_data") -> int:
    """CPU benchmark verilerini yükler (web+fallback)."""
    logger.info(f"cpu_benchmarks verileri yükleniyor... (Kaynak: {source})")
    success_count = 0
    cpus, _ = extract_components_from_products()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for cpu_name in cpus:
                try:
                    score = fetch_cpu_benchmark_score(cpu_name) if source == "fetch_data" else FALLBACK_CPU_BENCHMARKS.get(cpu_name)
                    if score is None or not isinstance(score, int) or score <= 0:
                        logger.warning("Geçersiz CPU puanı atlandı", cpu=cpu_name, score=score)
                        continue

                    cur.execute("""
                        INSERT INTO cpu_benchmarks (cpu_name, score, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cpu_name) DO UPDATE
                        SET score = EXCLUDED.score,
                            source = EXCLUDED.source,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE EXCLUDED.score IS NOT NULL;
                    """, (cpu_name, score, source))
                    success_count += 1

                except Exception as e:
                    logger.error("CPU benchmark yükleme hatası", cpu=cpu_name, error=str(e))
                    conn.rollback() # Sadece bu işlem için rollback

            conn.commit()

    # HATA DÜZELTİLDİ
    logger.info(f"✅ {success_count} adet CPU benchmark kaydı yüklendi/güncellendi.")
    return success_count

@monitor_performance
@handle_errors(reraise=True)
def load_gpu_benchmarks(source: str = "fetch_data") -> int:
    """GPU benchmark verilerini yükler (web+fallback)."""
    logger.info(f"gpu_benchmarks verileri yükleniyor... (Kaynak: {source})")
    success_count = 0
    _, gpus = extract_components_from_products()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for gpu_name in gpus:
                try:
                    score = fetch_gpu_benchmark_score(gpu_name) if source == "fetch_data" else FALLBACK_GPU_BENCHMARKS.get(gpu_name)
                    if score is None or not isinstance(score, int) or score <= 0:
                        logger.warning("Geçersiz GPU puanı atlandı", gpu=gpu_name, score=score)
                        continue

                    cur.execute("""
                        INSERT INTO gpu_benchmarks (gpu_name, score, source)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (gpu_name) DO UPDATE
                        SET score = EXCLUDED.score,
                            source = EXCLUDED.source,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE EXCLUDED.score IS NOT NULL;
                    """, (gpu_name, score, source))
                    success_count += 1

                except Exception as e:
                    logger.error("GPU benchmark yükleme hatası", gpu=gpu_name, error=str(e))
                    conn.rollback() # Sadece bu işlem için rollback

            conn.commit()

    # HATA DÜZELTİLDİ
    logger.info(f"✅ {success_count} adet GPU benchmark kaydı yüklendi/güncellendi.")
    return success_count

@monitor_performance
def load_benchmarks_with_fallback() -> Dict[str, Any]:
    """
    Web kaynakları engellenirse fallback ile devam eder.
    """
    result = {"cpu": 0, "gpu": 0, "mode": "fetch_data"}
    try:
        result["cpu"] = load_cpu_benchmarks(source="fetch_data")
        result["gpu"] = load_gpu_benchmarks(source="fetch_data")
    except Exception as e:
        logger.error("Benchmark 'fetch_data' başarısız, 'fallback' moduna geçiliyor", error=str(e))
        result["mode"] = "fallback"
        result["cpu"] = load_cpu_benchmarks(source="fallback")
        result["gpu"] = load_gpu_benchmarks(source="fallback")
    return result

if __name__ == "__main__":
    # 1) Veritabanı şemasını hazırla/güncelle
    create_tables()

    # 2) Ürünleri ve (varsa) AnTuTu puanlarını yükle
    load_products()

    # 3) Ürünlerdeki CPU/GPU'lar için benchmarkları çek
    bench_res = load_benchmarks_with_fallback()
    logger.info("Benchmark yükleme özeti", summary=bench_res)

    # 4) Veritabanının son durumunu kontrol et
    health = health_check()
    logger.info("Veri yükleme sonrası DB durumu", product_count=health.get("product_count"))

