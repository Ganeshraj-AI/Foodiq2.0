import sqlite3
conn = sqlite3.connect("canteen.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS canteen (
    canteen_id INTEGER PRIMARY KEY AUTOINCREMENT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS meals (
    meal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_name TEXT NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS dishes (
    dish_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dish_name TEXT NOT NULL,
    price_per_unit REAL NOT NULL
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    canteen_id INTEGER,
    meal_id INTEGER,
    dish_id INTEGER,
    quantity_prepared INTEGER,
    quantity_consumed INTEGER,
    order_id TEXT,
    special_event TEXT,

    FOREIGN KEY (canteen_id) REFERENCES canteen(canteen_id),
    FOREIGN KEY (meal_id) REFERENCES meals(meal_id),
    FOREIGN KEY (dish_id) REFERENCES dishes(dish_id)
)
""")

print("Database and tables created successfully!")
conn.commit()
conn.close()
