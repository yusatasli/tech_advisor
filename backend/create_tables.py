import psycopg2
import os

def create_tables():
    # DATABASE_URL'den connection bilgilerini al
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL bulunamadı!")
        return
    
    try:
        # PostgreSQL'e bağlan
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("✅ Database'e bağlandı!")
        
        # Users tablosu
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ users tablosu oluşturuldu!")
        
        # Search history tablosu
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                query TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ search_history tablosu oluşturuldu!")
        
        # Index'ler
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id);
        """)
        print("✅ Index'ler oluşturuldu!")
        
        # Commit
        conn.commit()
        cur.close()
        conn.close()
        
        print("🎉 Tüm tablolar başarıyla oluşturuldu!")
        
    except Exception as e:
        print(f"❌ Hata: {e}")

if __name__ == "__main__":
    create_tables()
