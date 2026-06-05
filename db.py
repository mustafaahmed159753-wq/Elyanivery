"""
Elyanivery — Database Module (PostgreSQL)
Uses psycopg2 with thread-local connections.
All SQL Server-specific syntax has been converted to PostgreSQL.
"""

import psycopg2
import psycopg2.extras
import threading
from config import Config

# Thread-local storage for DB connections
_local = threading.local()


def _get_conn():
    """Get or create a PostgreSQL connection for the current thread."""
    if not hasattr(_local, 'conn') or _local.conn is None or _local.conn.closed:
        dsn = Config.get_dsn()
        _local.conn = psycopg2.connect(dsn)
        _local.conn.autocommit = True
    return _local.conn


def close_conn():
    """Close the connection for the current thread."""
    if hasattr(_local, 'conn') and _local.conn is not None and not _local.conn.closed:
        try:
            _local.conn.close()
        except:
            pass
        _local.conn = None


def _convert_params(sql, params):
    """Convert ? placeholders to %s for psycopg2 compatibility.
    This allows the rest of the codebase to keep using ? style."""
    if params:
        sql = sql.replace('?', '%s')
    return sql, params


def query(sql, params=(), fetch_one=False, fetch=False):
    """
    Execute a SELECT query and return results.
    - fetch_one=True -> returns a single dict or None
    - fetch=True     -> returns a list of dicts
    - otherwise      -> returns None (for UPDATE/DELETE)
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql, params = _convert_params(sql, params)
        cursor.execute(sql, params)

        # For non-SELECT statements
        if cursor.description is None:
            cursor.close()
            return None

        if fetch_one:
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

        if fetch:
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

        cursor.close()
        return None
    except Exception as e:
        if 'closed' in str(e).lower() or 'connection' in str(e).lower():
            try:
                close_conn()
                conn = _get_conn()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                sql, params = _convert_params(sql, params)
                cursor.execute(sql, params)
                if cursor.description is None:
                    cursor.close()
                    return None
                if fetch_one:
                    row = cursor.fetchone()
                    cursor.close()
                    return dict(row) if row else None
                if fetch:
                    rows = cursor.fetchall()
                    cursor.close()
                    return [dict(r) for r in rows]
                cursor.close()
                return None
            except Exception as e2:
                print(f"  DB query retry failed: {e2}")
                raise
        else:
            print(f"  DB query error: {e}")
            raise


def insert(sql, params=()):
    """
    Execute an INSERT and return the newly generated id.
    Uses PostgreSQL RETURNING id clause for reliable identity retrieval.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        sql, params = _convert_params(sql, params)

        # Add RETURNING id if not already present
        if 'RETURNING' not in sql.upper():
            sql = sql.rstrip()
            if sql.endswith(';'):
                sql = sql[:-1]
            sql += ' RETURNING id'

        cursor.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None
    except Exception as e:
        try:
            close_conn()
            conn = _get_conn()
            cursor = conn.cursor()
            sql, params = _convert_params(sql, params)
            if 'RETURNING' not in sql.upper():
                sql = sql.rstrip() + ' RETURNING id'
            cursor.execute(sql, params)
            row = cursor.fetchone()
            cursor.close()
            if row and row[0] is not None:
                return int(row[0])
            return None
        except Exception as e2:
            print(f"  DB insert error: {e2}")
            raise


def init_db():
    """Create the Elyanivery database and all required tables if they don't exist.
    PostgreSQL uses CREATE TABLE IF NOT EXISTS instead of SQL Server's sysobjects check."""

    # Test connection
    params = Config.get_dsn()
    # Mask password for debug logging
    safe_params = params
    try:
        if 'password=' in params:
            import re
            safe_params = re.sub(r'password=[^ ]+', 'password=****', params)
    except:
        pass
    print(f"  DATABASE_URL set: {bool(Config.DATABASE_URL)}")
    print(f"  Connecting to: {safe_params}")
    try:
        conn = _get_conn()
        print("  PostgreSQL connection OK")
    except Exception as e:
        print(f"  PostgreSQL connection failed: {e}")
        raise

    # Create tables
    tables = [
        """CREATE TABLE IF NOT EXISTS Users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(500) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'customer',
            display_name VARCHAR(200),
            avatar_url VARCHAR(500) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Restaurants (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description VARCHAR(1000),
            address VARCHAR(500),
            latitude FLOAT DEFAULT 41.3874,
            longitude FLOAT DEFAULT 2.1686,
            is_open BOOLEAN DEFAULT TRUE,
            image_url VARCHAR(500) NULL,
            created_by INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Items (
            id SERIAL PRIMARY KEY,
            restaurant_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            description VARCHAR(500),
            price NUMERIC(10,2) NOT NULL,
            is_available BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Orders (
            id SERIAL PRIMARY KEY,
            order_number VARCHAR(50) UNIQUE,
            customer_id INT NOT NULL,
            restaurant_id INT NOT NULL,
            courier_id INT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            subtotal NUMERIC(10,2) DEFAULT 0,
            delivery_fee NUMERIC(10,2) DEFAULT 2.50,
            total NUMERIC(10,2) DEFAULT 0,
            delivery_address VARCHAR(500),
            delivery_lat FLOAT NULL,
            delivery_lng FLOAT NULL,
            landmark VARCHAR(500) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL,
            courier_arrived_restaurant_at TIMESTAMP NULL,
            order_picked_up_at TIMESTAMP NULL,
            courier_arrived_customer_at TIMESTAMP NULL,
            delivered_at TIMESTAMP NULL,
            cancelled_at TIMESTAMP NULL
        )""",

        """CREATE TABLE IF NOT EXISTS OrderItems (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            item_id INT NOT NULL,
            item_name VARCHAR(200),
            item_price NUMERIC(10,2),
            quantity INT DEFAULT 1
        )""",

        """CREATE TABLE IF NOT EXISTS OrderLog (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            status VARCHAR(50),
            note VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS CourierLocations (
            id SERIAL PRIMARY KEY,
            courier_id INT NOT NULL,
            latitude FLOAT DEFAULT 0,
            longitude FLOAT DEFAULT 0,
            is_online BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Ratings (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            user_id INT NOT NULL,
            courier_rating INT DEFAULT 5,
            service_rating INT DEFAULT 5,
            comment VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Favorites (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            restaurant_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS PromoCodes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE,
            description VARCHAR(500),
            discount_type VARCHAR(20) DEFAULT 'percentage',
            discount_value NUMERIC(10,2) DEFAULT 0,
            max_discount_amount NUMERIC(10,2) NULL,
            min_order_amount NUMERIC(10,2) DEFAULT 0,
            usage_limit INT NULL,
            used_count INT DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 year'),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open) VALUES (?,?,?,?,?,TRUE)",
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
