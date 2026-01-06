// Backend API URL'i
const API_URL = 'http://localhost:8000';

// 1. GİRİŞSİZ ARAMA (Public)
// Bu fonksiyon artık Auth istemeyen "structured_ask_stream" endpointine gidecek.
export async function searchProducts(query: string) {
  // NOT: Backend'de bu endpoint şifre istemez.
  const response = await fetch(`${API_URL}/structured_ask_stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error('Arama başlatılamadı (Public API Hatası)');
  }

  return response.body;
}

// 2. GİRİŞLİ ARAMA (Private - AI Destekli)
export async function searchProductsWithAuth(query: string) {
  const token = localStorage.getItem('token');
  
  if (!token) {
    throw new Error('Lütfen giriş yapın');
  }

  // NOT: Burası auth isteyen "_with_ai" endpointine gider.
  const response = await fetch(`${API_URL}/structured_ask_stream_with_ai`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`, // Token şart
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error('Günlük arama hakkınız dolmuştur. Lütfen yarın tekrar deneyin.');
    }
    if (response.status === 401) {
      // Token geçersizse temizleyelim ki kullanıcı login ekranına dönsün
      localStorage.removeItem('token');
      throw new Error('Oturum süreniz dolmuş. Lütfen tekrar giriş yapın.');
    }
    throw new Error('Arama başlatılamadı (Private API Hatası)');
  }

  return response.body;
}

// ==================== AUTH FONKSİYONLARI ====================

export async function register(email: string, password: string, name: string) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password, name }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Kayıt başarısız');
  }

  return response.json();
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Giriş başarısız');
  }

  return response.json();
}

export async function getSearchHistory() {
  const token = localStorage.getItem('token');
  
  if (!token) {
    throw new Error('Lütfen giriş yapın');
  }

  const response = await fetch(`${API_URL}/search_history`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Arama geçmişi alınamadı');
  }

  return response.json();
}