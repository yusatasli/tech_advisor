import React, { useState } from 'react';
import ReactDOM from 'react-dom';  
import './App.css';
import { searchProductsWithAuth, getSearchHistory } from './api';
import AuthModal from './AuthModal';  

function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<any[]>([]);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [theme, setTheme] = useState('dark');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchHistory, setSearchHistory] = useState<any[]>([]); 
  const [showHistory, setShowHistory] = useState(false);
  const handleCategoryClick = (category: string) => {
    // Toggle: Aynı kategoriye basarsa iptal et
    if (selectedCategory === category) {
      setSelectedCategory('');
    } else {
      setSelectedCategory(category);
    }
  };
  // ← BURAYA EKLE
  // LocalStorage'dan kullanıcıyı yükle
  React.useEffect(() => {
  const savedUser = localStorage.getItem('user');
  if (savedUser) {
    setUser(JSON.parse(savedUser));
    // Arama geçmişini yükle
    loadSearchHistory();
  }
}, []);

// Arama geçmişini yükle
const loadSearchHistory = async () => {
  try {
    const data = await getSearchHistory();
    setSearchHistory(data.history || []);
  } catch (err) {
    console.error('Geçmiş yüklenemedi:', err);
  }
};

  // Auth başarılı olduğunda
  const handleAuthSuccess = (userData: any, token: string) => {
    setUser(userData);
    setShowAuthModal(false);
  };

  // Çıkış yap
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };
  const formatDate = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Az önce';
    if (diffMins < 60) return `${diffMins} dakika önce`;
    if (diffHours < 24) return `${diffHours} saat önce`;
    if (diffDays === 1) return 'Dün';
    if (diffDays < 7) return `${diffDays} gün önce`;
    return date.toLocaleDateString('tr-TR');
  };

    const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };
  
  const handleSearch = async (searchQuery?: string, searchCategory?: string) => {
  // Parametre gelmediyse state'ten al
  const queryToSearch = searchQuery || query;
  const categoryToSearch = searchCategory !== undefined ? searchCategory : selectedCategory;
  
  if (!queryToSearch.trim()) return;
  
  if (!user) {
    setShowAuthModal(true);
    return;
  }
  
  // Akıllı kategori ekleme: Query'de yoksa ekle
  let finalQuery = queryToSearch.trim();
  if (categoryToSearch) {
    const queryLower = queryToSearch.toLowerCase();
    const categoryLower = categoryToSearch.toLowerCase();
    // Eğer query'de kategori adı yoksa ekle
    if (!queryLower.includes(categoryLower)) {
      finalQuery = `${queryToSearch} ${categoryToSearch}`.trim();
    }
  }
  
  setLoading(true);
  setProducts([]);
  setHasSearched(true);
    
  try {
    const stream = await searchProductsWithAuth(finalQuery);
    const reader = stream?.getReader();
    const decoder = new TextDecoder();
    
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.trim());
        
        for (const line of lines) {
          try {
            const data = JSON.parse(line);

            // Dinamik loading mesajları
            if (data.status === 'query_parsed') {
              setLoadingMessage('🔍 İnternette size en uygun ürünler aranıyor...');
            } else if (data.status === 'searching_web') {
              setLoadingMessage('🌐 Web siteleri taranıyor...');
            } else if (data.status === 'scraping_urls') {
              setLoadingMessage('📦 Ürünler filtreleniyor...');
            } else if (data.status === 'filtering_complete') {
              setLoadingMessage('✨ En iyi seçenekler belirleniyor...');
            } else if (data.status === 'generating_ai_commentary') {
              setLoadingMessage('🤖 Sizin için AI yorumları hazırlanıyor...');
            } else if (data.status === 'ai_commentary_added' && data.products_with_ai) {
              // Sadece AI yorumlu ürünleri al
              setProducts(data.products_with_ai);
              setLoadingMessage('');
            }
          } catch (e) {
            // JSON parse hatası - devam et
          }
        }
      }
    }
  } catch (error: any) {
    console.error('Hata:', error);
    
    // Özel hata mesajlarını kontrol et
    if (error.message && error.message.includes('Günlük arama hakkınız')) {
      alert('⚠️ Günlük arama hakkınız dolmuştur.\nLütfen yarın tekrar deneyin.');
    } else if (error.message && error.message.includes('429')) {
      alert('⚠️ Günlük arama hakkınız dolmuştur.\nLütfen yarın tekrar deneyin.');
    } else {
      alert('❌ Arama sırasında hata oluştu!');
    }
  } finally {
    setLoading(false);
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const response = await fetch('http://localhost:8000/auth/me', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
          localStorage.setItem('user', JSON.stringify(userData));
          
          // YENİ EKLE: Arama geçmişini de güncelle
          loadSearchHistory();
        }
      }
    } catch (err) {
      console.error('Kullanıcı bilgisi güncellenemedi:', err);
    }
  }
};

  return (
  <>
    {/* YENİ EKLE: Giriş Yapmamışsa Giriş Butonu */}
    {!user && ReactDOM.createPortal(
      <button 
        className="login-btn"
        data-theme={theme}
        onClick={() => setShowAuthModal(true)}
      >
        🔐 Giriş Yap / Kayıt Ol
      </button>,
      document.body
    )}
    
    {/* User Info - Portal ile body'ye direkt render */}
    {user && ReactDOM.createPortal(
      <div className="user-info" data-theme={theme}>
        <span>👤 {user.name}</span>
        <span className="search-count">{user.daily_searches_used}/{user.daily_searches_limit} arama</span>
        <button className="logout-btn" onClick={handleLogout}>Çıkış</button>
      </div>,
      document.body
    )}
    {user && searchHistory.length > 0 && ReactDOM.createPortal(
      <button 
        className="history-toggle-left"
        onClick={() => setShowHistory(!showHistory)}
      >
        📜 Geçmiş ({searchHistory.length})
      </button>,
      document.body
    )}
    {showHistory && searchHistory.length > 0 && ReactDOM.createPortal(
  <div className="search-history-left">
    <h3>Son Aramalar</h3>
    {searchHistory.map((item, index) => (
      <div 
        key={index} 
        className="history-item"
        onClick={() => {
            setQuery(item.query);
            setSelectedCategory(item.category || '');
            setShowHistory(false);
            // Otomatik arama yap - direkt parametre gönder
            handleSearch(item.query, item.category || '');
        }}
        >
        <div className="history-content">
          <span className="history-query">{item.query}</span>
          {/* YENİ EKLE: Tarih */}
          {item.created_at && (
            <span className="history-date">{formatDate(item.created_at)}</span>
          )}
        </div>
        {item.category && (
          <span className="history-category">{item.category}</span>
        )}
      </div>
    ))}
  </div>,
  document.body
)}
      <div className="App" data-theme={theme}>
        <header className="App-header">
          {/* Theme Toggle Butonu */}
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          
          <h1 className="logo">BİLGE</h1>
          <p className="tagline">Akıllı alışverişin yeni adresi</p>

          <div className="search-box">
            <input
              type="text"
              placeholder="Örnek: 35.000 TL bütçem var, mühendislik için laptop arıyorum"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyPress}
            />
            <button onClick={() => handleSearch()}>🔍 Ara</button>
          </div>
          <div className="categories">
            <button 
              className={selectedCategory === 'Telefon' ? 'active' : ''}
              onClick={() => handleCategoryClick('Telefon')}
            >
              📱 Telefon
            </button>
            <button 
              className={selectedCategory === 'Masaüstü' ? 'active' : ''}
              onClick={() => handleCategoryClick('Masaüstü')}
            >
              💻 Masaüstü
            </button>
            <button 
              className={selectedCategory === 'Laptop' ? 'active' : ''}
              onClick={() => handleCategoryClick('Laptop')}
            >
              💼 Laptop
            </button>
          </div>
          
          <p className="disclaimer">
            ⚠️ Bilge hata yapabilir. Lütfen önerileri kontrol ediniz.
          </p>
          
          {/* Loading Durumu */}
          {loading && (
            <div className="loading">
              <p>{loadingMessage || '🔍 Aranıyor...'}</p>
            </div>
          )}
          
          {/* Ürün Bulunamadı */}
              {!loading && hasSearched && products.length === 0 && (
            <div className="no-results">
              <h3>😔 Ürün Bulunamadı</h3>
              <p>Belirttiğiniz kriterlere uygun ürün bulunamadı.</p>
              <p>💡 Öneriler:</p>
              <ul>
                <li>Bütçenizi artırmayı deneyin</li>
                <li>Farklı bir model veya marka arayın</li>
                <li>Daha genel bir arama yapın</li>
              </ul>
            </div>
          )}
          
          {/* Ürünler */}
          {products.length > 0 && (
            <div className="results">
              <h2>Bulunan Ürünler ({products.length})</h2>
              {products.map((product, index) => (
                <div key={index} className="product-card">
                  <h3>{product.name}</h3>
                  <p className="price">{product.price} TL</p>
                  
                  {/* AI Yorumu */}
                  {product.ai_commentary && (
                    <div className="ai-comment">
                      <span className="ai-badge">🤖 AI Yorumu</span>
                      <p>{product.ai_commentary}</p>
                    </div>
                  )}

                  {product.specs && Object.keys(product.specs).length > 0 && (
                    <div className="specs">
                      <h4>Öne Çıkan Özellikler:</h4>
                      <ul>
                        {Object.entries(product.specs).slice(0, 5).map(([key, value], i) => (
                          <li key={i}>
                            <strong>{key}:</strong> {String(value)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  <a href={product.url} target="_blank" rel="noopener noreferrer">
                    Ürüne Git →
                  </a>
                </div>
              ))}
            </div>
          )}
        </header>
      </div>
      
      {/* Auth Modal */}
      {showAuthModal && ReactDOM.createPortal(
  <div data-theme={theme}>
    <AuthModal 
      onClose={() => setShowAuthModal(false)}
      onSuccess={handleAuthSuccess}
    />
  </div>,
  document.body
)}
    </>
  );
}

export default App;