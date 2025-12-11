// server.js - FoodIQ Backend Server
const express = require('express');
const cors = require('cors');
const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const JWT_SECRET = process.env.JWT_SECRET || 'foodiq-secret-key-2025';

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Initialize Database
const db = new sqlite3.Database('./foodiq.db', (err) => {
  if (err) {
    console.error('Database connection error:', err);
  } else {
    console.log('Connected to SQLite database');
    initDatabase();
  }
});

// Database Schema
function initDatabase() {
  db.serialize(() => {
    // Users Table
    db.run(`CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      role TEXT CHECK(role IN ('canteen', 'ngo')) NOT NULL,
      name TEXT NOT NULL,
      location TEXT,
      phone TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    // Menu Items Table
    db.run(`CREATE TABLE IF NOT EXISTS menu_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      price REAL NOT NULL,
      category TEXT CHECK(category IN ('breakfast', 'lunch', 'dinner')) NOT NULL,
      canteen_id INTEGER,
      is_active BOOLEAN DEFAULT 1,
      FOREIGN KEY (canteen_id) REFERENCES users(id)
    )`);

    // Daily Production Table
    db.run(`CREATE TABLE IF NOT EXISTS daily_production (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date DATE NOT NULL,
      item_id INTEGER NOT NULL,
      quantity_prepared INTEGER NOT NULL,
      quantity_consumed INTEGER NOT NULL,
      quantity_surplus INTEGER NOT NULL,
      canteen_id INTEGER NOT NULL,
      shift TEXT CHECK(shift IN ('breakfast', 'lunch', 'dinner')),
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (item_id) REFERENCES menu_items(id),
      FOREIGN KEY (canteen_id) REFERENCES users(id)
    )`);

    // Orders Table
    db.run(`CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_number TEXT UNIQUE NOT NULL,
      canteen_id INTEGER NOT NULL,
      total_amount REAL NOT NULL,
      payment_mode TEXT CHECK(payment_mode IN ('cash', 'upi', 'card')),
      is_complimentary BOOLEAN DEFAULT 0,
      order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (canteen_id) REFERENCES users(id)
    )`);

    // Order Items Table
    db.run(`CREATE TABLE IF NOT EXISTS order_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL,
      item_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL,
      price REAL NOT NULL,
      FOREIGN KEY (order_id) REFERENCES orders(id),
      FOREIGN KEY (item_id) REFERENCES menu_items(id)
    )`);

    // Surplus Broadcasts Table
    db.run(`CREATE TABLE IF NOT EXISTS surplus_broadcasts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      canteen_id INTEGER NOT NULL,
      item_name TEXT NOT NULL,
      category TEXT NOT NULL,
      quantity TEXT NOT NULL,
      pickup_window TEXT,
      status TEXT CHECK(status IN ('active', 'claimed', 'expired')) DEFAULT 'active',
      claimed_by INTEGER,
      broadcast_date DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (canteen_id) REFERENCES users(id),
      FOREIGN KEY (claimed_by) REFERENCES users(id)
    )`);

    // NGO Partners Table
    db.run(`CREATE TABLE IF NOT EXISTS ngo_partners (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ngo_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      location TEXT NOT NULL,
      latitude REAL,
      longitude REAL,
      needs TEXT,
      FOREIGN KEY (ngo_id) REFERENCES users(id)
    )`);

    console.log('Database schema initialized');
    seedDefaultData();
  });
}

// Seed Default Data
function seedDefaultData() {
  // Check if data exists
  db.get('SELECT COUNT(*) as count FROM menu_items', [], (err, row) => {
    if (row && row.count === 0) {
      console.log('Seeding default menu items...');
      
      const menuItems = [
        // Breakfast
        { name: 'Vada Pav', price: 20, category: 'breakfast' },
        { name: 'Samosa Pav', price: 22, category: 'breakfast' },
        { name: 'Idli Sambar', price: 40, category: 'breakfast' },
        { name: 'Masala Dosa', price: 70, category: 'breakfast' },
        { name: 'Upma', price: 25, category: 'breakfast' },
        
        // Lunch
        { name: 'Veg Thali', price: 100, category: 'lunch' },
        { name: 'Chicken Thali', price: 150, category: 'lunch' },
        { name: 'Chicken Biryani', price: 160, category: 'lunch' },
        { name: 'Veg Biryani', price: 120, category: 'lunch' },
        { name: 'Dal Khichdi', price: 90, category: 'lunch' },
        
        // Dinner
        { name: 'Pav Bhaji', price: 100, category: 'dinner' },
        { name: 'Veg Frankie', price: 60, category: 'dinner' },
        { name: 'Chicken Frankie', price: 90, category: 'dinner' },
        { name: 'Veg Pizza', price: 120, category: 'dinner' },
        { name: 'Cold Coffee', price: 60, category: 'dinner' }
      ];

      const stmt = db.prepare('INSERT INTO menu_items (name, price, category, canteen_id) VALUES (?, ?, ?, 1)');
      menuItems.forEach(item => {
        stmt.run(item.name, item.price, item.category);
      });
      stmt.finalize();
      
      console.log('Default menu items seeded');
    }
  });
}

// Middleware: Verify JWT Token
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ error: 'Invalid or expired token' });
    }
    req.user = user;
    next();
  });
}

// ==================== AUTHENTICATION ROUTES ====================

// Register
app.post('/api/auth/register', async (req, res) => {
  const { email, password, role, name, location, phone } = req.body;

  if (!email || !password || !role || !name) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const hashedPassword = await bcrypt.hash(password, 10);
    
    db.run(
      'INSERT INTO users (email, password, role, name, location, phone) VALUES (?, ?, ?, ?, ?, ?)',
      [email, hashedPassword, role, name, location, phone],
      function(err) {
        if (err) {
          if (err.message.includes('UNIQUE')) {
            return res.status(400).json({ error: 'Email already exists' });
          }
          return res.status(500).json({ error: err.message });
        }

        const token = jwt.sign({ id: this.lastID, email, role }, JWT_SECRET, { expiresIn: '7d' });
        res.status(201).json({ message: 'User registered', token, userId: this.lastID, role });
      }
    );
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Login
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;

  db.get('SELECT * FROM users WHERE email = ?', [email], async (err, user) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign({ id: user.id, email: user.email, role: user.role }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ token, userId: user.id, role: user.role, name: user.name });
  });
});

// ==================== MENU ROUTES ====================

// Get All Menu Items
app.get('/api/menu', (req, res) => {
  const { category } = req.query;
  let query = 'SELECT * FROM menu_items WHERE is_active = 1';
  const params = [];

  if (category) {
    query += ' AND category = ?';
    params.push(category);
  }

  db.all(query, params, (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

// Add Menu Item
app.post('/api/menu', authenticateToken, (req, res) => {
  const { name, price, category } = req.body;
  const canteen_id = req.user.id;

  db.run(
    'INSERT INTO menu_items (name, price, category, canteen_id) VALUES (?, ?, ?, ?)',
    [name, price, category, canteen_id],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({ id: this.lastID, message: 'Menu item added' });
    }
  );
});

// ==================== ORDER ROUTES ====================

// Create Order
app.post('/api/orders', authenticateToken, (req, res) => {
  const { items, total_amount, payment_mode, is_complimentary } = req.body;
  const canteen_id = req.user.id;
  const order_number = `ORD-${Date.now()}`;

  db.run(
    'INSERT INTO orders (order_number, canteen_id, total_amount, payment_mode, is_complimentary) VALUES (?, ?, ?, ?, ?)',
    [order_number, canteen_id, total_amount, payment_mode, is_complimentary ? 1 : 0],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }

      const orderId = this.lastID;
      const stmt = db.prepare('INSERT INTO order_items (order_id, item_id, quantity, price) VALUES (?, ?, ?, ?)');
      
      items.forEach(item => {
        stmt.run(orderId, item.id, item.quantity, item.price);
      });
      stmt.finalize();

      res.status(201).json({ orderId, order_number, message: 'Order created' });
    }
  );
});

// Get Orders
app.get('/api/orders', authenticateToken, (req, res) => {
  const canteen_id = req.user.id;

  db.all(
    'SELECT * FROM orders WHERE canteen_id = ? ORDER BY order_date DESC LIMIT 50',
    [canteen_id],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// ==================== PRODUCTION/WASTAGE ROUTES ====================

// Log Daily Production
app.post('/api/production', authenticateToken, (req, res) => {
  const { date, item_id, quantity_prepared, quantity_consumed, shift } = req.body;
  const canteen_id = req.user.id;
  const quantity_surplus = quantity_prepared - quantity_consumed;

  db.run(
    `INSERT INTO daily_production 
    (date, item_id, quantity_prepared, quantity_consumed, quantity_surplus, canteen_id, shift) 
    VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [date, item_id, quantity_prepared, quantity_consumed, quantity_surplus, canteen_id, shift],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({ id: this.lastID, message: 'Production logged' });
    }
  );
});

// Get Production Stats
app.get('/api/stats/production', authenticateToken, (req, res) => {
  const canteen_id = req.user.id;
  const { days = 30 } = req.query;

  db.all(
    `SELECT 
      DATE(date) as date,
      SUM(quantity_prepared) as total_prepared,
      SUM(quantity_consumed) as total_consumed,
      SUM(quantity_surplus) as total_surplus
    FROM daily_production 
    WHERE canteen_id = ? AND date >= DATE('now', '-${days} days')
    GROUP BY DATE(date)
    ORDER BY date DESC`,
    [canteen_id],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// Get Wastage by Item
app.get('/api/stats/wastage-by-item', authenticateToken, (req, res) => {
  const canteen_id = req.user.id;

  db.all(
    `SELECT 
      m.name as dish_name,
      SUM(dp.quantity_prepared) as total_prepared,
      SUM(dp.quantity_consumed) as total_consumed,
      SUM(dp.quantity_surplus) as total_surplus,
      ROUND(SUM(dp.quantity_surplus) * 100.0 / SUM(dp.quantity_prepared), 2) as waste_rate_percent
    FROM daily_production dp
    JOIN menu_items m ON dp.item_id = m.id
    WHERE dp.canteen_id = ?
    GROUP BY m.id
    ORDER BY total_surplus DESC
    LIMIT 10`,
    [canteen_id],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// Get Overall Summary
app.get('/api/stats/overall', authenticateToken, (req, res) => {
  const canteen_id = req.user.id;

  db.get(
    `SELECT 
      SUM(quantity_prepared) as total_prepared,
      SUM(quantity_consumed) as total_consumed,
      SUM(quantity_surplus) as total_surplus,
      ROUND(AVG(quantity_surplus), 2) as avg_surplus_per_day,
      ROUND(SUM(quantity_consumed) * 100.0 / SUM(quantity_prepared), 2) as avg_consumption_rate_percent
    FROM daily_production
    WHERE canteen_id = ?`,
    [canteen_id],
    (err, row) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(row || {});
    }
  );
});

// ==================== SURPLUS BROADCAST ROUTES ====================

// Create Surplus Broadcast
app.post('/api/surplus/broadcast', authenticateToken, (req, res) => {
  const { item_name, category, quantity, pickup_window } = req.body;
  const canteen_id = req.user.id;

  db.run(
    `INSERT INTO surplus_broadcasts 
    (canteen_id, item_name, category, quantity, pickup_window) 
    VALUES (?, ?, ?, ?, ?)`,
    [canteen_id, item_name, category, quantity, pickup_window],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({ id: this.lastID, message: 'Broadcast created' });
    }
  );
});

// Get Active Surplus Broadcasts
app.get('/api/surplus/active', (req, res) => {
  db.all(
    `SELECT sb.*, u.name as canteen_name, u.location
    FROM surplus_broadcasts sb
    JOIN users u ON sb.canteen_id = u.id
    WHERE sb.status = 'active'
    ORDER BY sb.broadcast_date DESC`,
    [],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// Claim Surplus
app.post('/api/surplus/:id/claim', authenticateToken, (req, res) => {
  const { id } = req.params;
  const ngo_id = req.user.id;

  db.run(
    `UPDATE surplus_broadcasts 
    SET status = 'claimed', claimed_by = ? 
    WHERE id = ? AND status = 'active'`,
    [ngo_id, id],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(400).json({ error: 'Broadcast not available' });
      }
      res.json({ message: 'Surplus claimed successfully' });
    }
  );
});

// ==================== NGO ROUTES ====================

// Get NGO Partners
app.get('/api/ngos', (req, res) => {
  db.all(
    `SELECT * FROM ngo_partners ORDER BY name`,
    [],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// ==================== BUSINESS STATS ROUTES ====================

// Revenue Stats
app.get('/api/stats/revenue', authenticateToken, (req, res) => {
  const canteen_id = req.user.id;

  db.get(
    `SELECT 
      SUM(total_amount) as total_revenue,
      COUNT(*) as total_orders,
      AVG(total_amount) as avg_order_value
    FROM orders
    WHERE canteen_id = ? AND DATE(order_date) >= DATE('now', '-30 days')`,
    [canteen_id],
    (err, row) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(row || {});
    }
  );
});

// Error Handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// Start Server
app.listen(PORT, () => {
  console.log(`🚀 FoodIQ Backend running on http://localhost:${PORT}`);
  console.log(`📊 Database: SQLite (foodiq.db)`);
  console.log(`🔐 JWT Secret: ${JWT_SECRET.substring(0, 10)}...`);
});