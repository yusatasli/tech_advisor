# scoring.py (Python 3.9 uyumlu)
import os
import math
from typing import Optional

import psycopg2 # type: ignore
import psycopg2.extras # type: ignore

# .env içinden DB bağlantısı
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Aa3453Aa@tech_advisor_db:5432/tech_advisor"
)

# Ağırlıklar (istersen .env ile override edebilirsin)
CPU_WEIGHT = float(os.getenv("CPU_WEIGHT", "0.4"))
GPU_WEIGHT = float(os.getenv("GPU_WEIGHT", "0.6"))

def _connect():
    """Veritabanına bağlantı kurar."""
    return psycopg2.connect(
        DB_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def _get_cpu_score(cur, name: Optional[str]) -> Optional[int]:
    """Verilen CPU adı için benchmark skorunu döndürür."""
    if not name:
        return None
    cur.execute(
        "SELECT score FROM cpu_benchmarks WHERE cpu_name=%s LIMIT 1;",
        (name,)
    )
    row = cur.fetchone()
    return row["score"] if row else None

def _get_gpu_score(cur, name: Optional[str]) -> Optional[int]:
    """Verilen GPU adı için benchmark skorunu döndürür."""
    if not name:
        return None
    cur.execute(
        "SELECT score FROM gpu_benchmarks WHERE gpu_name=%s LIMIT 1;",
        (name,)
    )
    row = cur.fetchone()
    return row["score"] if row else None


def run():
    """Veritabanındaki tüm ürünler için final_score'u hesaplar ve günceller."""
    conn = _connect()
    cur = conn.cursor()
    print("[scoring] Veritabanı bağlantısı kuruldu.")
    
    try:
        # --- 1. Laptop ve Masaüstü Bilgisayarları Puanla ---
        cur.execute("""
          SELECT id, name, cpu_name, gpu_name, price
          FROM products
          WHERE category IN ('Laptop','Masaüstü');
        """)
        pc_rows = cur.fetchall()
        print(f"[scoring] Puanlanacak PC/Laptop sayısı: {len(pc_rows)}")

        pc_updated = 0
        for r in pc_rows:
            cpu_score = _get_cpu_score(cur, r["cpu_name"]) or 0
            gpu_score = _get_gpu_score(cur, r["gpu_name"]) or 0
            price = r["price"]
            
            final_score = 0
            # Sadece CPU veya GPU puanı varsa puanlama yap
            if (cpu_score > 0 or gpu_score > 0) and price and price > 1000:
                # Ağırlıklı bileşen skoru
                component_score = (CPU_WEIGHT * cpu_score) + (GPU_WEIGHT * gpu_score)
                # Logaritmik F/P puanı
                final_score = (component_score / math.log10(price)) * 10
            
            if final_score > 0:
                cur.execute(
                    "UPDATE products SET final_score=%s WHERE id=%s AND (final_score IS DISTINCT FROM %s);",
                    (int(final_score), r["id"], int(final_score))
                )
                if cur.rowcount > 0:
                    pc_updated += 1
        
        print(f"[scoring] {pc_updated} adet PC/Laptop güncellendi.")

        # --- 2. Telefonları Puanla ---
        cur.execute("""
          SELECT id, name, antutu_score, price
          FROM products
          WHERE category = 'Telefon';
        """)
        phone_rows = cur.fetchall()
        print(f"[scoring] Puanlanacak Telefon sayısı: {len(phone_rows)}")
        
        phone_updated = 0
        for r in phone_rows:
            antutu_score = r["antutu_score"]
            price = r["price"]
            
            final_score = 0
            if antutu_score and price and price > 1000:
                # Logaritmik F/P puanı
                final_score = (antutu_score / math.log10(price)) / 10 # PC'lerle benzer bir aralığa getirmek için
            
            if final_score > 0:
                cur.execute(
                    "UPDATE products SET final_score=%s WHERE id=%s AND (final_score IS DISTINCT FROM %s);",
                    (int(final_score), r["id"], int(final_score))
                )
                if cur.rowcount > 0:
                    phone_updated += 1
                    
        print(f"[scoring] {phone_updated} adet Telefon güncellendi.")
        
        conn.commit()
        print("[scoring] Tüm değişiklikler veritabanına kaydedildi.")

    except Exception as e:
        print(f"[scoring] HATA: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        print("[scoring] Veritabanı bağlantısı kapatıldı.")


if __name__ == "__main__":
    print("[scoring] Fiyat/Performans puanlama script'i başlatılıyor...")
    run()
    print("[scoring] İşlem tamamlandı.")
