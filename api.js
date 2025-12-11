// api.js - Frontend API Client
// Add this file to your project and include it in your HTML files

const API_BASE_URL = 'http://localhost:5000/api';

// Store token in localStorage
const AuthService = {
  setToken(token) {
    localStorage.setItem('foodiq_token', token);
  },
  
  getToken() {
    return localStorage.getItem('foodiq_token');
  },
  
  removeToken() {
    localStorage.removeItem('foodiq_token');
  },
  
  isAuthenticated() {
    return !!this.getToken();
  },
  
  getUserData() {
    const data = localStorage.getItem('foodiq_user');
    return data ? JSON.parse(data) : null;
  },
  
  setUserData(userData) {
    localStorage.setItem('foodiq_user', JSON.stringify(userData));
  }
};

// API Helper Function
async function apiRequest(endpoint, options = {}) {
  const token = AuthService.getToken();
  
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` })
    },
    ...options
  };

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Request failed');
    }
    
    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

// Authentication APIs
const AuthAPI = {
  async login(email, password) {
    const data = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    
    AuthService.setToken(data.token);
    AuthService.setUserData({ userId: data.userId, role: data.role, name: data.name });
    return data;
  },
  
  async register(userData) {
    const data = await apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData)
    });
    
    AuthService.setToken(data.token);
    AuthService.setUserData({ userId: data.userId, role: data.role });
    return data;
  },
  
  logout() {
    AuthService.removeToken();
    localStorage.removeItem('foodiq_user');
    window.location.href = 'login.html';
  }
};

// Menu APIs
const MenuAPI = {
  async getAll(category = null) {
    const query = category ? `?category=${category}` : '';
    return await apiRequest(`/menu${query}`);
  },
  
  async add(menuItem) {
    return await apiRequest('/menu', {
      method: 'POST',
      body: JSON.stringify(menuItem)
    });
  }
};

// Order APIs
const OrderAPI = {
  async create(orderData) {
    return await apiRequest('/orders', {
      method: 'POST',
      body: JSON.stringify(orderData)
    });
  },
  
  async getAll() {
    return await apiRequest('/orders');
  }
};

// Production/Wastage APIs
const ProductionAPI = {
  async log(productionData) {
    return await apiRequest('/production', {
      method: 'POST',
      body: JSON.stringify(productionData)
    });
  },
  
  async getStats(days = 30) {
    return await apiRequest(`/stats/production?days=${days}`);
  },
  
  async getWastageByItem() {
    return await apiRequest('/stats/wastage-by-item');
  },
  
  async getOverall() {
    return await apiRequest('/stats/overall');
  }
};

// Surplus APIs
const SurplusAPI = {
  async broadcast(broadcastData) {
    return await apiRequest('/surplus/broadcast', {
      method: 'POST',
      body: JSON.stringify(broadcastData)
    });
  },
  
  async getActive() {
    return await apiRequest('/surplus/active');
  },
  
  async claim(broadcastId) {
    return await apiRequest(`/surplus/${broadcastId}/claim`, {
      method: 'POST'
    });
  }
};

// Business Stats APIs
const StatsAPI = {
  async getRevenue() {
    return await apiRequest('/stats/revenue');
  }
};

// NGO APIs
const NGOAPI = {
  async getAll() {
    return await apiRequest('/ngos');
  }
};

// Export for use in HTML files
if (typeof window !== 'undefined') {
  window.FoodIQAPI = {
    Auth: AuthAPI,
    Menu: MenuAPI,
    Order: OrderAPI,
    Production: ProductionAPI,
    Surplus: SurplusAPI,
    Stats: StatsAPI,
    NGO: NGOAPI,
    AuthService
  };
}