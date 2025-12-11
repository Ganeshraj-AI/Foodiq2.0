from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import hashlib
import secrets
import os

app = Flask(__name__)
CORS(app)

# Database file
DB_FILE = 'foodiq.db'

# Secret key for sessions (you can change this)
SECRET_KEY = 'foodiq-secret-2025'

# ==================== DATABASE SETUP ====================

def init_db():
    """Initialize database with tables"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('canteen', 'ngo')) NOT NULL,
        name TEXT NOT NULL,
        location TEXT,
        phone TEXT,
        token TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Menu items
    c.execute('''CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category TEXT CHECK(category IN ('breakfast', 'lunch', 'dinner')) NOT NULL,
        canteen_id INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1
    )''')
    
    # Daily production
    c.execute('''CREATE TABLE IF NOT EXISTS daily_production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        item_name TEXT NOT NULL,
        quantity_prepared INTEGER NOT NULL,
        quantity_consumed INTEGER NOT NULL,
        quantity_surplus INTEGER NOT NULL,
        canteen_id INTEGER DEFAULT 1,
        shift TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Orders
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        canteen_id INTEGER DEFAULT 1,
        total_amount REAL NOT NULL,
        payment_mode TEXT,
        is_complimentary INTEGER DEFAULT 0,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Surplus broadcasts
    c.execute('''CREATE TABLE IF NOT EXISTS surplus_broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canteen_id INTEGER DEFAULT 1,
        item_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity TEXT NOT NULL,
        pickup_window TEXT,
        status TEXT DEFAULT 'active',
        claimed_by INTEGER,
        broadcast_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")
    seed_data()

def seed_data():
    """Add sample menu items"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if menu already has items
    c.execute('SELECT COUNT(*) FROM menu_items')
    count = c.fetchone()[0]
    
    if count == 0:
        print("🌱 Seeding menu items...")
        menu_items = [
            ('Vada Pav', 20, 'breakfast'),
            ('Samosa Pav', 22, 'breakfast'),
            ('Idli Sambar', 40, 'breakfast'),
            ('Masala Dosa', 70, 'breakfast'),
            ('Upma', 25, 'breakfast'),
            ('Veg Thali', 100, 'lunch'),
            ('Chicken Thali', 150, 'lunch'),
            ('Chicken Biryani', 160, 'lunch'),
            ('Veg Biryani', 120, 'lunch'),
            ('Dal Khichdi', 90, 'lunch'),
            ('Pav Bhaji', 100, 'dinner'),
            ('Veg Frankie', 60, 'dinner'),
            ('Chicken Frankie', 90, 'dinner'),
            ('Veg Pizza', 120, 'dinner'),
            ('Cold Coffee', 60, 'dinner')
        ]
        
        c.executemany('INSERT INTO menu_items (name, price, category) VALUES (?, ?, ?)', menu_items)
        conn.commit()
        print("✅ Menu items seeded!")
    
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== AUTHENTICATION ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'canteen')
    name = data.get('name')
    
    if not all([email, password, name]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    try:
        token = secrets.token_hex(16)
        c.execute('''INSERT INTO users (email, password, role, name, token) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (email, hash_password(password), role, name, token))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'User registered',
            'token': token,
            'userId': user_id,
            'role': role
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    
    if not user or user['password'] != hash_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate new token
    token = secrets.token_hex(16)
    c.execute('UPDATE users SET token = ? WHERE id = ?', (token, user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({
        'token': token,
        'userId': user['id'],
        'role': user['role'],
        'name': user['name']
    })

# ==================== MENU ROUTES ====================

@app.route('/api/menu', methods=['GET'])
def get_menu():
    category = request.args.get('category')
    
    conn = get_db()
    c = conn.cursor()
    
    if category:
        c.execute('SELECT * FROM menu_items WHERE category = ? AND is_active = 1', (category,))
    else:
        c.execute('SELECT * FROM menu_items WHERE is_active = 1')
    
    items = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(items)

@app.route('/api/menu', methods=['POST'])
def add_menu_item():
    data = request.json
    name = data.get('name')
    price = data.get('price')
    category = data.get('category')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO menu_items (name, price, category) VALUES (?, ?, ?)',
              (name, price, category))
    conn.commit()
    item_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': item_id, 'message': 'Menu item added'}), 201

# ==================== ORDER ROUTES ====================

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    total_amount = data.get('total_amount')
    payment_mode = data.get('payment_mode', 'cash')
    is_complimentary = data.get('is_complimentary', 0)
    
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO orders (order_number, total_amount, payment_mode, is_complimentary) 
                 VALUES (?, ?, ?, ?)''',
              (order_number, total_amount, payment_mode, is_complimentary))
    conn.commit()
    order_id = c.lastrowid
    conn.close()
    
    return jsonify({
        'orderId': order_id,
        'order_number': order_number,
        'message': 'Order created'
    }), 201

@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM orders ORDER BY order_date DESC LIMIT 50')
    orders = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(orders)

# ==================== PRODUCTION/WASTAGE ROUTES ====================

@app.route('/api/production', methods=['POST'])
def log_production():
    data = request.json
    date = data.get('date')
    item_name = data.get('item_name')
    quantity_prepared = data.get('quantity_prepared')
    quantity_consumed = data.get('quantity_consumed')
    shift = data.get('shift')
    
    quantity_surplus = quantity_prepared - quantity_consumed
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO daily_production 
                 (date, item_name, quantity_prepared, quantity_consumed, quantity_surplus, shift) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (date, item_name, quantity_prepared, quantity_consumed, quantity_surplus, shift))
    conn.commit()
    prod_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': prod_id, 'message': 'Production logged'}), 201

@app.route('/api/stats/overall', methods=['GET'])
def get_overall_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT 
                    SUM(quantity_prepared) as total_prepared,
                    SUM(quantity_consumed) as total_consumed,
                    SUM(quantity_surplus) as total_surplus,
                    AVG(quantity_surplus) as avg_surplus_per_day,
                    (SUM(quantity_consumed) * 100.0 / SUM(quantity_prepared)) as avg_consumption_rate_percent
                 FROM daily_production''')
    stats = dict(c.fetchone())
    conn.close()
    
    # Handle None values
    for key in stats:
        if stats[key] is None:
            stats[key] = 0
    
    return jsonify(stats)

@app.route('/api/stats/production', methods=['GET'])
def get_production_stats():
    days = request.args.get('days', 30)
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT 
                    date,
                    SUM(quantity_prepared) as total_prepared,
                    SUM(quantity_consumed) as total_consumed,
                    SUM(quantity_surplus) as total_surplus
                 FROM daily_production 
                 WHERE date >= DATE('now', '-' || ? || ' days')
                 GROUP BY date
                 ORDER BY date DESC''', (days,))
    stats = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(stats)

@app.route('/api/stats/wastage-by-item', methods=['GET'])
def get_wastage_by_item():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT 
                    item_name as dish_name,
                    SUM(quantity_prepared) as total_prepared,
                    SUM(quantity_consumed) as total_consumed,
                    SUM(quantity_surplus) as total_surplus,
                    ROUND(SUM(quantity_surplus) * 100.0 / SUM(quantity_prepared), 2) as waste_rate_percent
                 FROM daily_production
                 GROUP BY item_name
                 ORDER BY total_surplus DESC
                 LIMIT 10''')
    items = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(items)

# ==================== SURPLUS ROUTES ====================

@app.route('/api/surplus/broadcast', methods=['POST'])
def broadcast_surplus():
    data = request.json
    item_name = data.get('item_name')
    category = data.get('category')
    quantity = data.get('quantity')
    pickup_window = data.get('pickup_window')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO surplus_broadcasts 
                 (item_name, category, quantity, pickup_window) 
                 VALUES (?, ?, ?, ?)''',
              (item_name, category, quantity, pickup_window))
    conn.commit()
    broadcast_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': broadcast_id, 'message': 'Broadcast created'}), 201

@app.route('/api/surplus/active', methods=['GET'])
def get_active_surplus():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT * FROM surplus_broadcasts 
                 WHERE status = 'active'
                 ORDER BY broadcast_date DESC''')
    broadcasts = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(broadcasts)

@app.route('/api/surplus/<int:id>/claim', methods=['POST'])
def claim_surplus(id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE surplus_broadcasts 
                 SET status = 'claimed', claimed_by = 1 
                 WHERE id = ? AND status = 'active' ''', (id,))
    conn.commit()
    
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Broadcast not available'}), 400
    
    conn.close()
    return jsonify({'message': 'Surplus claimed successfully'})

# ==================== BUSINESS STATS ====================

@app.route('/api/stats/revenue', methods=['GET'])
def get_revenue_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT 
                    SUM(total_amount) as total_revenue,
                    COUNT(*) as total_orders,
                    AVG(total_amount) as avg_order_value
                 FROM orders
                 WHERE DATE(order_date) >= DATE('now', '-30 days')''')
    stats = dict(c.fetchone())
    conn.close()
    
    # Handle None values
    for key in stats:
        if stats[key] is None:
            stats[key] = 0
    
    return jsonify(stats)

# ==================== SERVE HTML FILES ====================

@app.route('/')
def index():
    return send_from_directory('.', 'login.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('.', path)

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    print("🚀 Starting FoodIQ Backend Server...")
    print("=" * 50)
    
    # Initialize database
    init_db()
    
    print("=" * 50)
    print("✅ Server is ready!")
    print("📍 Open: http://localhost:5000")
    print("=" * 50)
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)