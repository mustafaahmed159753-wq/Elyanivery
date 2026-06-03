"""
Elyanivery — Database Module
SQL Server helpers using pyodbc with thread-local connections.
"""

import pyodbc
import threading
from config import Config

# Thread-local storage for DB connections
_local = threading.local()


def _get_conn():
    """Get or create a connection for the current thread."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        try:
            _local.conn = pyodbc.connect(Config.conn_string(), autocommit=True)
        except Exception as e:
            print(f"  DB connection error: {e}")
            raise
    return _local.conn


def close_conn():
    """Close the connection for the current thread."""
    if hasattr(_local, 'conn') and _local.conn is not None:
        try:
            _local.conn.close()
        except:
            pass
        _local.conn = None


def query(sql, params=(), fetch_one=False, fetch=False):
    """
    Execute a SELECT query and return results.
    - fetch_one=True -> returns a single dict or None
    - fetch=True     -> returns a list of dicts
    - otherwise      -> returns cursor (for UPDATE/DELETE that don't need results)
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)

        # For non-SELECT statements
        if cursor.description is None:
            return None

        columns = [desc[0] for desc in cursor.description]

        if fetch_one:
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(zip(columns, row))

        if fetch:
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

        # Default: return nothing useful for non-fetch queries
        return None
    except Exception as e:
        # Try to reconnect once on connection error
        if '08S01' in str(e) or 'HY000' in str(e) or 'closed' in str(e).lower():
            try:
                close_conn()
                conn = _get_conn()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                if cursor.description is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                if fetch_one:
                    row = cursor.fetchone()
                    return dict(zip(columns, row)) if row else None
                if fetch:
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
            except Exception as e2:
                print(f"  DB query retry failed: {e2}")
                raise
        else:
            print(f"  DB query error: {e}")
            raise


def insert(sql, params=()):
    """
    Execute an INSERT and return the newly generated identity ID.
    Uses SCOPE_IDENTITY() to retrieve the new ID.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        # Get the identity value
        cursor.execute("SELECT SCOPE_IDENTITY()")
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return None
    except Exception as e:
        # Try to reconnect once
        if '08S01' in str(e) or 'HY000' in str(e) or 'closed' in str(e).lower():
            try:
                close_conn()
                conn = _get_conn()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                cursor.execute("SELECT SCOPE_IDENTITY()")
                row = cursor.fetchone()
                if row and row[0] is not None:
                    return int(row[0])
                return None
            except Exception as e2:
                print(f"  DB insert retry failed: {e2}")
                raise
        else:
            print(f"  DB insert error: {e}")
            raise


def init_db():
    """Create the Elyanivery database and all required tables if they don't exist."""
    # Create database if it doesn't exist
    try:
        conn = pyodbc.connect(Config.master_conn_string(), autocommit=True)
        cursor = conn.cursor()
        # Check if database exists
        cursor.execute("SELECT database_id FROM sys.databases WHERE name=?", (Config.DB_DATABASE,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(f"CREATE DATABASE [{Config.DB_DATABASE}]")
            print(f"  Created database: {Config.DB_DATABASE}")
        else:
            print(f"  Database exists: {Config.DB_DATABASE}")
        conn.close()
    except Exception as e:
        print(f"  DB init (create database) note: {e}")

    # Create tables
    tables = [
        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Users' AND xtype='U')
        CREATE TABLE Users (
            id INT PRIMARY KEY IDENTITY(1,1),
            username NVARCHAR(100) NOT NULL UNIQUE,
            password_hash NVARCHAR(500) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'customer',
            display_name NVARCHAR(200),
            avatar_url NVARCHAR(500) NULL,
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Restaurants' AND xtype='U')
        CREATE TABLE Restaurants (
            id INT PRIMARY KEY IDENTITY(1,1),
            name NVARCHAR(200) NOT NULL,
            description NVARCHAR(1000),
            address NVARCHAR(500),
            latitude FLOAT DEFAULT 41.3874,
            longitude FLOAT DEFAULT 2.1686,
            is_open BIT DEFAULT 1,
            image_url NVARCHAR(500) NULL,
            created_by INT NULL,
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Items' AND xtype='U')
        CREATE TABLE Items (
            id INT PRIMARY KEY IDENTITY(1,1),
            restaurant_id INT NOT NULL,
            name NVARCHAR(200) NOT NULL,
            description NVARCHAR(500),
            price DECIMAL(10,2) NOT NULL,
            is_available BIT DEFAULT 1,
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Orders' AND xtype='U')
        CREATE TABLE Orders (
            id INT PRIMARY KEY IDENTITY(1,1),
            order_number NVARCHAR(50) UNIQUE,
            customer_id INT NOT NULL,
            restaurant_id INT NOT NULL,
            courier_id INT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            subtotal DECIMAL(10,2) DEFAULT 0,
            delivery_fee DECIMAL(10,2) DEFAULT 2.50,
            total DECIMAL(10,2) DEFAULT 0,
            delivery_address NVARCHAR(500),
            delivery_lat FLOAT NULL,
            delivery_lng FLOAT NULL,
            landmark NVARCHAR(500) NULL,
            created_at DATETIME DEFAULT GETUTCDATE(),
            updated_at DATETIME NULL,
            courier_arrived_restaurant_at DATETIME NULL,
            order_picked_up_at DATETIME NULL,
            courier_arrived_customer_at DATETIME NULL,
            delivered_at DATETIME NULL,
            cancelled_at DATETIME NULL
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='OrderItems' AND xtype='U')
        CREATE TABLE OrderItems (
            id INT PRIMARY KEY IDENTITY(1,1),
            order_id INT NOT NULL,
            item_id INT NOT NULL,
            item_name NVARCHAR(200),
            item_price DECIMAL(10,2),
            quantity INT DEFAULT 1
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='OrderLog' AND xtype='U')
        CREATE TABLE OrderLog (
            id INT PRIMARY KEY IDENTITY(1,1),
            order_id INT NOT NULL,
            status VARCHAR(50),
            note NVARCHAR(500),
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CourierLocations' AND xtype='U')
        CREATE TABLE CourierLocations (
            id INT PRIMARY KEY IDENTITY(1,1),
            courier_id INT NOT NULL,
            latitude FLOAT DEFAULT 0,
            longitude FLOAT DEFAULT 0,
            is_online BIT DEFAULT 0,
            updated_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Ratings' AND xtype='U')
        CREATE TABLE Ratings (
            id INT PRIMARY KEY IDENTITY(1,1),
            order_id INT NOT NULL,
            user_id INT NOT NULL,
            courier_rating INT DEFAULT 5,
            service_rating INT DEFAULT 5,
            comment NVARCHAR(500),
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Favorites' AND xtype='U')
        CREATE TABLE Favorites (
            id INT PRIMARY KEY IDENTITY(1,1),
            user_id INT NOT NULL,
            restaurant_id INT NOT NULL,
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",

        """IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PromoCodes' AND xtype='U')
        CREATE TABLE PromoCodes (
            id INT PRIMARY KEY IDENTITY(1,1),
            code NVARCHAR(50) NOT NULL UNIQUE,
            description NVARCHAR(500),
            discount_type VARCHAR(20) DEFAULT 'percentage',
            discount_value DECIMAL(10,2) DEFAULT 0,
            max_discount_amount DECIMAL(10,2) NULL,
            min_order_amount DECIMAL(10,2) DEFAULT 0,
            usage_limit INT NULL,
            used_count INT DEFAULT 0,
            is_active BIT DEFAULT 1,
            valid_from DATETIME DEFAULT GETUTCDATE(),
            valid_until DATETIME DEFAULT DATEADD(YEAR, 1, GETUTCDATE()),
            created_at DATETIME DEFAULT GETUTCDATE()
        )""",
    ]

    for sql in tables:
        try:
            query(sql)
        except Exception as e:
            print(f"  Table init note: {e}")


def seed_data():
    """Seed the database with sample restaurants, items, and promo codes if empty."""
    # Seed restaurants if none exist
    rest_count = query("SELECT COUNT(*) as cnt FROM Restaurants", fetch_one=True)
    if rest_count and rest_count['cnt'] == 0:
        restaurants = [
            ('Pizza Palace', 'Authentic Italian pizza and pasta', 'Carrer de Balmes 15, Barcelona', 41.3920, 2.1530),
            ('Burger Barn', 'Gourmet burgers and craft beers', 'Carrer de Provenca 88, Barcelona', 41.3950, 2.1620),
            ('Sushi World', 'Fresh Japanese cuisine', 'Rambla de Catalunya 42, Barcelona', 41.3880, 2.1680),
            ('Taco Fiesta', 'Mexican street food', 'Carrer de Muntaner 200, Barcelona', 41.3935, 2.1570),
            ('Green Bowl', 'Healthy salads and smoothies', 'Passeig de Gracia 55, Barcelona', 41.3905, 2.1650),
        ]
        for name, desc, addr, lat, lng in restaurants:
            try:
                insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open) VALUES (?,?,?,?,?,1)",
                       (name, desc, addr, lat, lng))
            except Exception as e:
                print(f"  Seed restaurant note: {e}")
        print("  Seeded 5 sample restaurants")

        # Seed items for each restaurant
        items_data = {
            1: [  # Pizza Palace
                ('Margherita Pizza', 'Classic tomato, mozzarella, basil', 9.99),
                ('Pepperoni Pizza', 'Pepperoni, mozzarella, tomato sauce', 11.99),
                ('Carbonara Pasta', 'Spaghetti with creamy carbonara sauce', 12.50),
                ('Caesar Salad', 'Romaine, croutons, parmesan, caesar dressing', 8.50),
                ('Tiramisu', 'Classic Italian dessert', 6.50),
            ],
            2: [  # Burger Barn
                ('Classic Burger', 'Beef patty, lettuce, tomato, cheese', 10.99),
                ('BBQ Burger', 'Beef patty, BBQ sauce, bacon, onion rings', 13.50),
                ('Chicken Wings', 'Spicy buffalo wings (8 pcs)', 9.99),
                ('Loaded Fries', 'Cheese, bacon, jalapenos', 7.50),
                ('Milkshake', 'Vanilla, chocolate, or strawberry', 5.50),
            ],
            3: [  # Sushi World
                ('Salmon Nigiri (4 pcs)', 'Fresh Atlantic salmon', 8.99),
                ('California Roll (8 pcs)', 'Crab, avocado, cucumber', 10.50),
                ('Dragon Roll (8 pcs)', 'Eel, avocado, tobiko', 14.99),
                ('Miso Soup', 'Traditional Japanese miso soup', 4.50),
                ('Edamame', 'Steamed soybeans with sea salt', 5.00),
            ],
            4: [  # Taco Fiesta
                ('Beef Tacos (3 pcs)', 'Seasoned beef, salsa, guacamole', 9.50),
                ('Chicken Burrito', 'Grilled chicken, rice, beans, cheese', 11.99),
                ('Nachos Supreme', 'Loaded nachos with all toppings', 8.99),
                ('Churros', 'Cinnamon sugar churros with chocolate dip', 5.50),
                ('Horchata', 'Traditional rice drink', 3.50),
            ],
            5: [  # Green Bowl
                ('Power Bowl', 'Quinoa, avocado, chickpeas, tahini', 12.99),
                ('Greek Salad', 'Feta, olives, cucumber, tomato', 9.50),
                ('Acai Bowl', 'Acai, granola, banana, berries', 10.99),
                ('Green Smoothie', 'Spinach, banana, mango, almond milk', 6.50),
                ('Hummus Wrap', 'Hummus, veggies, whole wheat wrap', 8.99),
            ],
        }
        for rid, items in items_data.items():
            for name, desc, price in items:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price) VALUES (?,?,?,?)",
                           (rid, name, desc, price))
                except Exception as e:
                    print(f"  Seed item note: {e}")
        print("  Seeded menu items for all restaurants")

    # Seed promo codes if none exist
    promo_count = query("SELECT COUNT(*) as cnt FROM PromoCodes", fetch_one=True)
    if promo_count and promo_count['cnt'] == 0:
        promos = [
            ('WELCOME10', '10% off your first order', 'percentage', 10.00, 5.00, 15.00, 100),
            ('FREEDELIVERY', 'Free delivery on orders over 20eur', 'fixed', 2.50, None, 20.00, 200),
            ('SAVE5', '5 euros off', 'fixed', 5.00, None, 25.00, 50),
        ]
        for code, desc, dtype, val, maxdisc, minorder, limit in promos:
            try:
                insert("INSERT INTO PromoCodes (code,description,discount_type,discount_value,max_discount_amount,min_order_amount,usage_limit) VALUES (?,?,?,?,?,?,?)",
                       (code, desc, dtype, val, maxdisc, minorder, limit))
            except Exception as e:
                print(f"  Seed promo note: {e}")
        print("  Seeded 3 promo codes")
