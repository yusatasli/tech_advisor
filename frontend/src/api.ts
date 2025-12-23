// Backend API URL'i
const API_URL = 'http://localhost:8000';

// Arama fonksiyonu
export async function searchProducts(query: string) {
  const response = await fetch(`${API_URL}/structured_ask_stream_with_ai`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error('API hatası');
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

export async function searchProductsWithAuth(query: string) {
  const token = localStorage.getItem('token');
  
  if (!token) {
    throw new Error('Lütfen giriş yapın');
  }

  const response = await fetch(`${API_URL}/structured_ask_stream_with_ai`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error('Günlük arama hakkınız dolmuştur. Lütfen yarın tekrar deneyin.');
    }
    if (response.status === 401) {
      throw new Error('Oturum süreniz dolmuş. Lütfen tekrar giriş yapın.');
    }
    throw new Error('Arama başlatılamadı');
  }

  return response.body;
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