import os
import psycopg2
import psycopg2.extras
import psycopg2.pool
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager

from logger import (
    get_logger,
    retry_on_failure,
    handle_errors,
    monitor_performance,
    DatabaseError,
    with_db_connection
)

logger = get_logger("database")

DB_NAME = os.getenv("POSTGRES_DB", "tech_advisor")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Aa3453Aa")
DB_HOST = os.getenv("POSTGRES_HOST", "tech_advisor_db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "1"))
MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))

_connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

def initialize_connection_pool():
    global _connection_pool
    if _connection_pool is not None:
        logger.info("Connection pool already initialized")
        return
    try:
        logger.info(
            "Initializing database connection pool",
            min_conn=MIN_CONNECTIONS,
            max_conn=MAX_CONNECTIONS,
            host=DB_HOST,
            database=DB_NAME
        )
        
        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=MIN_CONNECTIONS,
            maxconn=MAX_CONNECTIONS,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=psycopg2.extras.RealDictCursor,
            connect_timeout=CONNECTION_TIMEOUT
        )
        
        logger.info("Database connection pool initialized successfully")
    except psycopg2.OperationalError as e:
        logger.error(
            "Failed to initialize connection pool",
            error=str(e),
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER
        )
        raise DatabaseError(
            f"Could not initialize connection pool: {str(e)}",
            context={
                "host": DB_HOST,
                "database": DB_NAME,
                "user": DB_USER,
                "error_type": "OperationalError"
            }
        ) from e
    except Exception as e:
        logger.error("Unexpected error initializing connection pool", error=str(e))
        raise DatabaseError(f"Unexpected error: {str(e)}") from e

def close_connection_pool():
    global _connection_pool
    if _connection_pool is not None:
        try:
            _connection_pool.closeall()
            _connection_pool = None
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error("Error closing connection pool", error=str(e))

@contextmanager
def get_db_connection():
    if _connection_pool is None:
        initialize_connection_pool()
    
    assert _connection_pool is not None, "Connection pool must be initialized"
    
    conn = None
    try:
        conn = _connection_pool.getconn()
        yield conn
    finally:
        if conn:
            _connection_pool.putconn(conn)

def get_db_connection_legacy():
    logger.warning("Using legacy get_db_connection - consider using context manager version")
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error("Legacy connection failed", error=str(e))
        return None
get_connection = get_db_connection_legacy

@monitor_performance
@handle_errors(reraise=True)
def create_tables():
    logger.info("Creating or updating database tables")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                # Products table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50),
                    name VARCHAR(255) UNIQUE,
                    brand VARCHAR(50),
                    price INTEGER,
                    cpu_name VARCHAR(255),
                    gpu_name VARCHAR(255),
                    antutu_score INTEGER,  -- YENİ: AnTuTu puanı için sütun
                    final_score INTEGER,
                    specs JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    url TEXT,
                    source VARCHAR(100)
                );
                """)
                # Add new columns if they don't exist
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='url') THEN
                            ALTER TABLE products ADD COLUMN url TEXT;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='source') THEN
                            ALTER TABLE products ADD COLUMN source VARCHAR(100);
                        END IF;
                        -- YENİ: antutu_score sütununu, tablo zaten varsa ekler
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='antutu_score') THEN
                            ALTER TABLE products ADD COLUMN antutu_score INTEGER;
                        END IF;
                    END
                    $$;
                """)
                
                # Create indexes for performance
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_final_score ON products(final_score);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_cpu_name ON products(cpu_name);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_gpu_name ON products(gpu_name);")
                # YENİ: antutu_score için index eklendi
                cur.execute("CREATE INDEX IF NOT EXISTS idx_products_antutu_score ON products(antutu_score);")

                
                # CPU benchmarks table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS cpu_benchmarks (
                    cpu_name VARCHAR(255) PRIMARY KEY,
                    score INTEGER NOT NULL,
                    source VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # GPU benchmarks table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS gpu_benchmarks (
                    gpu_name VARCHAR(255) PRIMARY KEY,
                    score INTEGER NOT NULL,
                    source VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # CPU aliases table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS cpu_aliases (
                    alias VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # GPU aliases table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS gpu_aliases (
                    alias VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Benchmark sources tables
                cur.execute("""
                CREATE TABLE IF NOT EXISTS cpu_benchmark_sources (
                    source_id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    url VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                cur.execute("""
                CREATE TABLE IF NOT EXISTS gpu_benchmark_sources (
                    source_id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    url VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Create trigger for updated_at
                cur.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
                """)
                
                # Add triggers to tables that have updated_at
                for table in ['products', 'cpu_benchmarks', 'gpu_benchmarks']:
                    cur.execute(f"""
                    DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                    CREATE TRIGGER update_{table}_updated_at
                        BEFORE UPDATE ON {table}
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                    """)
                
                conn.commit()
                logger.info("Database tables created successfully")
                
            except psycopg2.Error as e:
                conn.rollback()
                logger.error("Failed to create tables", error=str(e))
                raise DatabaseError(f"Table creation failed: {str(e)}") from e

@monitor_performance
@handle_errors(default_return=None, reraise=False)
def get_final_score_by_name(name: str) -> Optional[int]:
    if not name or not name.strip():
        logger.warning("Empty product name provided")
        return None
    name = name.strip()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT final_score FROM products WHERE name=%s LIMIT 1;",
                    (name,)
                )
                row = cur.fetchone()
                if row and row.get("final_score") is not None:
                    score = int(row["final_score"])
                    logger.debug("Final score retrieved", product=name, score=score)
                    return score
                else:
                    logger.debug("No final score found", product=name)
                    return None
            except psycopg2.Error as e:
                logger.error("Database error getting final score", product=name, error=str(e))
                return None
            except (ValueError, TypeError) as e:
                logger.error("Invalid score value", product=name, error=str(e))
                return None

@monitor_performance
@handle_errors(reraise=True)
def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    if not isinstance(product_id, int) or product_id <= 0:
        raise DatabaseError(f"Invalid product ID: {product_id}")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM products WHERE id=%s LIMIT 1;",
                (product_id,)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return None

@monitor_performance
@handle_errors(reraise=True)
def get_products_by_category(category: str, limit: int = 50) -> list:
    if not category or not category.strip():
        raise DatabaseError("Category cannot be empty")
    if limit <= 0 or limit > 1000:
        raise DatabaseError(f"Invalid limit: {limit}")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM products 
                   WHERE category=%s 
                   ORDER BY final_score DESC NULLS LAST, price ASC 
                   LIMIT %s;""",
                (category.strip(), limit)
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

@monitor_performance
def health_check() -> Dict[str, Any]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user;")
                row = cur.fetchone()
                cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public' 
                AND table_name IN ('products', 'cpu_benchmarks', 'gpu_benchmarks')
                ORDER BY table_name;
                """)
                tables = [r['table_name'] for r in cur.fetchall()]
                cur.execute("SELECT COUNT(*) as count FROM products;")
                product_count = cur.fetchone()['count']
                return {
                    "status": "healthy",
                    "database": row['current_database'],
                    "user": row['current_user'],
                    "version": row['version'].split()[0:2],
                    "tables": tables,
                    "product_count": product_count,
                    "pool_status": {
                        "min_connections": MIN_CONNECTIONS,
                        "max_connections": MAX_CONNECTIONS,
                        "initialized": _connection_pool is not None
                    }
                }
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__
        }

if __name__ == "__main__":
    logger.info("Starting database test")
    try:
        initialize_connection_pool()
        create_tables()
        health = health_check()
        print("Database health:", health)
        score = get_final_score_by_name("Test Product")
        print(f"Test score lookup (should be None): {score}")
        logger.info("Database test completed successfully")
    except Exception as e:
        logger.error("Database test failed", error=str(e))
        print(f"Database test failed: {e}")
    finally:
        close_connection_pool()
# ==================== USER YÖNETİMİ ====================
# Bu kodu db.py dosyasının EN SONUNA ekle

def create_users_table():
    """Kullanıcı tablosu oluştur"""
    conn = get_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                daily_searches_used INTEGER DEFAULT 0,
                daily_searches_limit INTEGER DEFAULT 10,
                last_search_date DATE,
                is_guest BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("✅ Users tablosu oluşturuldu")
    except Exception as e:
        print(f"❌ Users tablosu hatası: {e}")
    finally:
        cur.close()
        conn.close()

def create_user(email: str, password_hash: str, name: str):
    """Yeni kullanıcı oluştur"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (email, password_hash, name, daily_searches_limit)
            VALUES (%s, %s, %s, 10)
            RETURNING id, email, name, daily_searches_used, daily_searches_limit
        """, (email, password_hash, name))
        
        user = cur.fetchone()
        conn.commit()
        
        if user:
            return {
                "id": user["id"],  # ← DİCTİONARY KEY!
                "email": user["email"],
                "name": user["name"],
                "daily_searches_used": user["daily_searches_used"],
                "daily_searches_limit": user["daily_searches_limit"]
            }
        return None
    except Exception as e:
        print(f"❌ Kullanıcı oluşturma hatası: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_email(email: str):
    """Email ile kullanıcı getir"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, password_hash, name, daily_searches_used, 
                   daily_searches_limit, last_search_date
            FROM users WHERE email = %s
        """, (email,))
        
        user = cur.fetchone()
        if user:
            return {
                "id": user["id"],
                "email": user["email"],
                "password_hash": user["password_hash"],
                "name": user["name"],
                "daily_searches_used": user["daily_searches_used"],
                "daily_searches_limit": user["daily_searches_limit"],
                "last_search_date": user["last_search_date"]
            }
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_id(user_id: int):
    """ID ile kullanıcı getir"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, name, daily_searches_used, 
                   daily_searches_limit, last_search_date
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cur.fetchone()
        if user:
            return {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "daily_searches_used": user["daily_searches_used"],
                "daily_searches_limit": user["daily_searches_limit"],
                "last_search_date": user["last_search_date"]
            }
        return None
    finally:
        cur.close()
        conn.close()

def increment_user_search(user_id: int):
    """Kullanıcının günlük arama sayısını artır (v2.0: Otomatik reset)"""
    conn = get_connection()
    if not conn:
        return None  # Bağlantı hatası
    
    try:
        cur = conn.cursor()
        
        # Kullanıcı bilgilerini al
        cur.execute("""
            SELECT daily_searches_used, daily_searches_limit, last_search_date
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cur.fetchone()
        if not user:
            return None
        
        from datetime import date
        today = date.today()
        last_date = user["last_search_date"]
        
        # 🔥 GÜN DEĞİŞTİYSE ARAMA SAYISINI SIFIRLA!
        if last_date != today:
            logger.info(f"📅 Yeni gün! Kullanıcı {user_id} arama sayısı sıfırlandı (Son: {last_date})")
            cur.execute("""
                UPDATE users
                SET daily_searches_used = 1,
                    last_search_date = CURRENT_DATE
                WHERE id = %s
                RETURNING daily_searches_used, last_search_date
            """, (user_id,))
        else:
            # Aynı gün - limit kontrolü
            if user["daily_searches_used"] >= user["daily_searches_limit"]:
                return False  # Limit doldu
            
            # Arama sayısını artır
            cur.execute("""
                UPDATE users 
                SET daily_searches_used = daily_searches_used + 1,
                    last_search_date = CURRENT_DATE
                WHERE id = %s
                RETURNING daily_searches_used, last_search_date
            """, (user_id,))
        
        result = cur.fetchone()
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Arama sayısı artırma hatası: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def create_search_history_table():
    """Search history tablosunu oluştur"""
    conn = get_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                query TEXT NOT NULL,
                category VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("✅ Search history tablosu oluşturuldu")
    except Exception as e:
        print(f"❌ Search history tablo hatası: {e}")
    finally:
        cur.close()
        conn.close()
def add_search_history(user_id: int, query: str, category: str = None):
    """Arama geçmişine kayıt ekle"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO search_history (user_id, query, category)
            VALUES (%s, %s, %s)
        """, (user_id, query, category))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Arama geçmişi kaydetme hatası: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_search_history(user_id: int, limit: int = 10):
    """Kullanıcının arama geçmişini getir"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT query, category, created_at
            FROM search_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        
        results = cur.fetchall()
        return [{
            "query": row["query"],
            "category": row["category"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        } for row in results]
    except Exception as e:
        print(f"❌ Arama geçmişi okuma hatası: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def add_search_history(user_id: int, query: str, category: str = None):
    """Arama geçmişine kayıt ekle"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO search_history (user_id, query, category)
            VALUES (%s, %s, %s)
        """, (user_id, query, category))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Arama geçmişi kaydetme hatası: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_search_history(user_id: int, limit: int = 10):
    """Kullanıcının arama geçmişini getir"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT query, category, created_at
            FROM search_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        
        results = cur.fetchall()
        return [{
            "query": row["query"],
            "category": row["category"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        } for row in results]
    except Exception as e:
        print(f"❌ Arama geçmişi okuma hatası: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# Uygulama başlatıldığında tabloları oluştur
create_users_table()
create_search_history_table()  # ← YENİ EKLE
