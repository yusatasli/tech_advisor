import React, { useState } from 'react';
import { login, register } from './api';
import './AuthModal.css';

interface AuthModalProps {
  onClose: () => void;
  onSuccess: (user: any, token: string) => void;
}

function AuthModal({ onClose, onSuccess }: AuthModalProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        // Login
        const response = await login(email, password);
        localStorage.setItem('token', response.access_token);
        localStorage.setItem('user', JSON.stringify(response.user));
        onSuccess(response.user, response.access_token);
      } else {
        // Register
        await register(email, password, name);
        // Kayıttan sonra otomatik login
        const loginResponse = await login(email, password);
        localStorage.setItem('token', loginResponse.access_token);
        localStorage.setItem('user', JSON.stringify(loginResponse.user));
        onSuccess(loginResponse.user, loginResponse.access_token);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        
        <h2>{isLogin ? 'Giriş Yap' : 'Kayıt Ol'}</h2>
        
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <input
              type="text"
              placeholder="Adınız Soyadınız"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          )}
          
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          
          <input
            type="password"
            placeholder="Şifre"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          
          {error && <div className="error-message">{error}</div>}
          
          <button type="submit" disabled={loading}>
            {loading ? 'Yükleniyor...' : isLogin ? 'Giriş Yap' : 'Kayıt Ol'}
          </button>
        </form>
        
        <p className="auth-switch">
          {isLogin ? 'Hesabınız yok mu?' : 'Zaten hesabınız var mı?'}
          <button onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Kayıt Ol' : 'Giriş Yap'}
          </button>
        </p>
      </div>
    </div>
  );
}

export default AuthModal;