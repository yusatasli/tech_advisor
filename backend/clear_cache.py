# Bu script, sadece ürün aramalarıyla ilgili cache'i temizler.
from cache import ProductCache

print("🧹 Cache temizleniyor...")

try:
    # Doğrudan ProductCache sınıfından bir örnek oluşturuyoruz.
    cache = ProductCache()
    
    # Artık var olan `clear_all_product_searches` fonksiyonunu çağırıyoruz.
    result = cache.clear_all_product_searches()
    
    print(f"✅ {result} adet ürün araması cache'den başarıyla temizlendi.")

except Exception as e:
    print(f"❌ Cache temizlenirken bir hata oluştu: {e}")
