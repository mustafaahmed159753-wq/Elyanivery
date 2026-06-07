"""
Elyanivery — Database Module (PostgreSQL)
Uses psycopg2 with thread-local connections.
All SQL Server-specific syntax has been converted to PostgreSQL.
v6.0 — Version-based auto-reseed, Admin approval, broadcasts, phone numbers, Moldova seed data, Deliver Anything addresses
"""

# ── Current seed version — bump this to force a database reseed on Railway ──
CURRENT_SEED_VERSION = '9'

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
            phone VARCHAR(30) NULL,
            approval_status VARCHAR(20) DEFAULT 'approved',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Restaurants (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description VARCHAR(1000),
            address VARCHAR(500),
            latitude FLOAT DEFAULT 47.0105,
            longitude FLOAT DEFAULT 28.8638,
            is_open BOOLEAN DEFAULT TRUE,
            image_url VARCHAR(500) NULL,
            category VARCHAR(50) DEFAULT 'restaurant',
            phone VARCHAR(30) NULL,
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
            estimated_prep_minutes INT NULL,
            courier_earnings NUMERIC(10,2) DEFAULT 0,
            waiting_minutes INT DEFAULT 0,
            is_deliver_anything BOOLEAN DEFAULT FALSE,
            delivery_type VARCHAR(20) NULL,
            pickup_address VARCHAR(500) NULL,
            pickup_lat FLOAT NULL,
            pickup_lng FLOAT NULL,
            pickup_contact_name VARCHAR(200) NULL,
            pickup_contact_phone VARCHAR(30) NULL,
            delivery_contact_name VARCHAR(200) NULL,
            delivery_contact_phone VARCHAR(30) NULL,
            item_description VARCHAR(500) NULL,
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
            vehicle_type VARCHAR(20) DEFAULT 'bicycle',
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

        """CREATE TABLE IF NOT EXISTS CourierEarnings (
            id SERIAL PRIMARY KEY,
            courier_id INT NOT NULL,
            order_id INT NULL,
            amount NUMERIC(10,2) NOT NULL DEFAULT 0,
            earning_type VARCHAR(30) DEFAULT 'delivery_fee',
            description VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS SupportTickets (
            id SERIAL PRIMARY KEY,
            order_id INT NOT NULL,
            user_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL
        )""",

        """CREATE TABLE IF NOT EXISTS SupportMessages (
            id SERIAL PRIMARY KEY,
            ticket_id INT NOT NULL,
            sender_id INT NOT NULL,
            message VARCHAR(2000),
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS Broadcasts (
            id SERIAL PRIMARY KEY,
            admin_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            message VARCHAR(2000) NOT NULL,
            target_roles VARCHAR(200) DEFAULT 'all',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL
        )""",

        """CREATE TABLE IF NOT EXISTS AppSettings (
            key VARCHAR(100) PRIMARY KEY,
            value VARCHAR(500) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    for sql in tables:
        try:
            query(sql)
        except Exception as e:
            print(f"  Table init note: {e}")

    # ── Add new columns to existing tables if they don't exist ──
    _migrate_columns()


def _migrate_columns():
    """Add new columns to existing tables if they don't exist yet.
    Uses PostgreSQL ALTER TABLE ... ADD COLUMN IF NOT EXISTS (PG 9.6+)."""
    migrations = [
        ("CourierLocations", "vehicle_type", "VARCHAR(20) DEFAULT 'bicycle'"),
        ("Orders", "estimated_prep_minutes", "INT NULL"),
        ("Orders", "courier_earnings", "NUMERIC(10,2) DEFAULT 0"),
        ("Orders", "waiting_minutes", "INT DEFAULT 0"),
        ("Restaurants", "category", "VARCHAR(50) DEFAULT 'restaurant'"),
        ("Restaurants", "phone", "VARCHAR(30) NULL"),
        ("Users", "phone", "VARCHAR(30) NULL"),
        ("Users", "approval_status", "VARCHAR(20) DEFAULT 'approved'"),
        ("Orders", "is_deliver_anything", "BOOLEAN DEFAULT FALSE"),
        ("Orders", "delivery_type", "VARCHAR(20) NULL"),
        ("Orders", "pickup_address", "VARCHAR(500) NULL"),
        ("Orders", "pickup_lat", "FLOAT NULL"),
        ("Orders", "pickup_lng", "FLOAT NULL"),
        ("Orders", "pickup_contact_name", "VARCHAR(200) NULL"),
        ("Orders", "pickup_contact_phone", "VARCHAR(30) NULL"),
        ("Orders", "delivery_contact_name", "VARCHAR(200) NULL"),
        ("Orders", "delivery_contact_phone", "VARCHAR(30) NULL"),
        ("Orders", "item_description", "VARCHAR(500) NULL"),
        ("Items", "image_url", "VARCHAR(500) NULL"),
        ("Items", "sub_category", "VARCHAR(100) NULL"),
        ("Orders", "payment_method", "VARCHAR(50) NULL"),
    ]
    for table, column, definition in migrations:
        try:
            query(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        except Exception as e:
            # Some PG versions don't support IF NOT EXISTS on ALTER TABLE
            # Try without it and ignore "already exists" errors
            try:
                query(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except Exception as e2:
                if 'already exists' not in str(e2).lower():
                    print(f"  Migration note ({table}.{column}): {e2}")


def check_seed_version():
    """Check if the database seed version matches CURRENT_SEED_VERSION.
    Returns True if reseed is needed, False if version matches."""
    try:
        row = query("SELECT value FROM AppSettings WHERE key=%s", ('db_seed_version',), fetch_one=True)
        db_version = row['value'] if row else '0'
        if db_version != CURRENT_SEED_VERSION:
            print(f"  Seed version mismatch: DB={db_version}, Code={CURRENT_SEED_VERSION} → Reseeding...")
            return True
        print(f"  Seed version OK: {db_version}")
        return False
    except Exception as e:
        print(f"  Seed version check note: {e} → Will reseed")
        return True


def update_seed_version():
    """Update the db_seed_version in AppSettings to CURRENT_SEED_VERSION."""
    try:
        existing = query("SELECT key FROM AppSettings WHERE key=%s", ('db_seed_version',), fetch_one=True)
        if existing:
            query("UPDATE AppSettings SET value=%s, updated_at=CURRENT_TIMESTAMP WHERE key=%s",
                  (CURRENT_SEED_VERSION, 'db_seed_version'))
        else:
            insert("INSERT INTO AppSettings (key, value) VALUES (%s, %s)",
                   ('db_seed_version', CURRENT_SEED_VERSION))
        print(f"  Seed version updated to {CURRENT_SEED_VERSION}")
    except Exception as e:
        print(f"  Seed version update note: {e}")


def seed_data(force=False):
    """Seed the database with sample restaurants, items, and promo codes.
    v6.0 — Version-based auto-reseed. If force=True or version mismatch, clears and reseeds.
    All addresses in Chisinau, Moldova. Categories: restaurant, fast_food, pharmacy, supermarket."""
    # Check if we need to force reseed
    needs_reseed = force or check_seed_version()

    if needs_reseed:
        # Clear existing seed data for a clean reseed
        try:
            query("DELETE FROM OrderItems")
            query("DELETE FROM OrderLog")
            query("DELETE FROM Orders")
            query("DELETE FROM Items")
            query("DELETE FROM Restaurants")
            query("DELETE FROM PromoCodes")
            query("DELETE FROM Favorites")
            query("DELETE FROM Ratings")
            query("DELETE FROM CourierEarnings")
            query("DELETE FROM SupportTickets")
            query("DELETE FROM SupportMessages")
            query("DELETE FROM ChatMessages")
            query("DELETE FROM Notifications")
            query("DELETE FROM Addresses")
            query("DELETE FROM PointTransactions")
            query("DELETE FROM LoyaltyPoints")
            query("DELETE FROM CourierLocations")
            query("DELETE FROM Users")
            query("DELETE FROM CallSessions")
            query("DELETE FROM IceCandidates")
            query("DELETE FROM Broadcasts")
            print("  Cleared all existing data for reseed")
        except Exception as e:
            print(f"  Clear data note: {e}")

    # Seed restaurants if none exist (or after clearing)
    rest_count = query("SELECT COUNT(*) as cnt FROM Restaurants", fetch_one=True)
    if rest_count and rest_count['cnt'] == 0:
        # All coordinates centered on Chisinau, Moldova (47.0105, 28.8638)
        # Unsplash images for each business
        restaurants = [
            # ── RESTAURANTS ──
            ('La Placinte', 'Traditional Moldovan cuisine with modern twist', 'Str. Stefan cel Mare 67, Chisinau', 47.0258, 28.8328, 'restaurant', '+373 22 123 456', 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&h=400&fit=crop'),
            ('Carpe Diem', 'Fine dining & wine bar in the heart of Chisinau', 'Str. V. Pircalab 52, Chisinau', 47.0189, 28.8451, 'restaurant', '+373 22 234 567', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            ('Andys Pizza', 'Popular Italian-style pizza restaurant', 'Bulevardul Stefan cel Mare 32, Chisinau', 47.0312, 28.8407, 'restaurant', '+373 22 345 678', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&h=400&fit=crop'),
            ('Propaganda', 'Modern European cuisine with local ingredients', 'Str. M. Eminescu 24, Chisinau', 47.0156, 28.8503, 'restaurant', '+373 22 456 789', 'https://images.unsplash.com/photo-1559339352-11d035aa65de?w=600&h=400&fit=crop'),
            ('Beef by Victor', 'Premium steakhouse and grill', 'Str. A. Mateevici 15, Chisinau', 47.0273, 28.8516, 'restaurant', '+373 22 567 890', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=600&h=400&fit=crop'),
            ('Osha Restaurant', 'Authentic Middle Eastern and Lebanese cuisine', 'Str. Bucuresti 68, Chisinau', 47.0201, 28.8385, 'restaurant', '+373 22 678 902', 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&h=400&fit=crop'),
            ('Casa Daca', 'Romantic wine bar with artisan cheese plates', 'Str. Columna 103, Chisinau', 47.0267, 28.8440, 'restaurant', '+373 22 678 903', 'https://images.unsplash.com/photo-1550966871-3ed3cdb51f3a?w=600&h=400&fit=crop'),
            # ── FAST FOOD ──
            ('McDonalds Chisinau', 'Classic fast food burgers and fries', 'Bulevardul Dacia 39, Chisinau', 47.0356, 28.8297, 'fast_food', '+373 22 678 901', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600&h=400&fit=crop'),
            ('KFC Mall Dova', 'Fried chicken and sides', 'Str. Arborilor 21, Chisinau', 47.0125, 28.8612, 'fast_food', '+373 22 789 012', 'https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=600&h=400&fit=crop'),
            ('Shawarma King', 'Best shawarma and falafel in town', 'Str. Ismail 49, Chisinau', 47.0198, 28.8379, 'fast_food', '+373 22 890 123', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600&h=400&fit=crop'),
            ('Burger Box', 'Gourmet burgers and craft shakes', 'Str. M. Eminescu 79, Chisinau', 47.0234, 28.8412, 'fast_food', '+373 22 890 124', 'https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=600&h=400&fit=crop'),
            # ── PHARMACIES ──
            ('Farmacia Familia', 'Full-service pharmacy delivery', 'Str. Alexandru cel Bun 80, Chisinau', 47.0241, 28.8562, 'pharmacy', '+373 22 901 234', 'https://images.unsplash.com/photo-1576602976047-174e57a47881?w=600&h=400&fit=crop'),
            ('Farmacie Noapte', '24/7 pharmacy open all night', 'Bulevardul Decebal 23, Chisinau', 47.0089, 28.8445, 'pharmacy', '+373 22 012 345', 'https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=600&h=400&fit=crop'),
            ('Sensiblu Chisinau', 'Health and wellness pharmacy', 'Str. Tighina 34, Chisinau', 47.0172, 28.8689, 'pharmacy', '+373 22 123 457', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=600&h=400&fit=crop'),
            # ── SUPERMARKETS ──
            ('Nr1 Supermarket', 'Everything you need, delivered fast', 'Str. Moscovei 5, Chisinau', 47.0301, 28.8234, 'supermarket', '+373 22 234 568', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=600&h=400&fit=crop'),
            ('Fidesco Market', 'Premium grocery and household items', 'Str. Calea Orheiului 16, Chisinau', 47.0412, 28.8578, 'supermarket', '+373 22 345 679', 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=600&h=400&fit=crop'),
            ('Linella Supermarket', 'Affordable groceries for every family', 'Bulevardul Mircea cel Batran 8, Chisinau', 47.0067, 28.8534, 'supermarket', '+373 22 456 780', 'https://images.unsplash.com/photo-1534723454574-44b0d39e4a2c?w=600&h=400&fit=crop'),
            # ── DELIVERY SERVICE (virtual) ──
            ('Elyanivery Delivery Service', 'Virtual restaurant for Deliver Anything orders', '', 47.0105, 28.8638, 'delivery_service', '', ''),
        ]
        for name, desc, addr, lat, lng, cat, phone, img in restaurants:
            try:
                insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,category,phone,image_url) VALUES (?,?,?,?,?,TRUE,?,?,?)",
                       (name, desc, addr, lat, lng, cat, phone, img))
            except Exception as e:
                print(f"  Seed restaurant note: {e}")
        print("  Seeded 18 Moldova-based restaurants with Unsplash images")

        # Seed items for each restaurant
        # Format: (name, description, price, sub_category, image_url)
        items_data = {
            1: [  # La Placinte - Moldovan
                ('Placinta cu Branza', 'Traditional cheese-filled pastry', 4.50, 'Pastries', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Placinta cu Varza', 'Cabbage-filled pastry', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Mamaliga cu Branza', 'Polenta with cheese and sour cream', 6.99, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Zeama de Pui', 'Traditional chicken soup', 5.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Sarmale', 'Stuffed cabbage rolls', 7.99, 'Main Course', 'https://images.unsplash.com/photo-1625944525533-473f1a3d54e7?w=300&h=300&fit=crop'),
                ('Placinta cu Mere', 'Apple-filled sweet pastry', 3.50, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Compot de Visine', 'Cherry compote drink', 2.50, 'Drinks', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?w=300&h=300&fit=crop'),
                ('Salata de Vinete', 'Eggplant salad spread', 4.99, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
            ],
            2: [  # Carpe Diem - Fine dining
                ('Duck Confit', 'Slow-cooked duck leg with cherry sauce', 18.50, 'Main Course', 'https://images.unsplash.com/photo-1432139555190-58524dae6a55?w=300&h=300&fit=crop'),
                ('Risotto ai Funghi', 'Wild mushroom risotto', 14.99, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Beef Carpaccio', 'Thin sliced raw beef with arugula', 12.50, 'Starters', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Wine Selection', 'Local Moldovan wine pairing', 9.99, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Creme Brulee', 'Classic vanilla custard dessert', 7.50, 'Desserts', 'https://images.unsplash.com/photo-1470124182917-cc6e71b22ecc?w=300&h=300&fit=crop'),
                ('Foie Gras', 'Seared foie gras with fig jam', 22.50, 'Starters', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Grilled Sea Bass', 'Mediterranean sea bass with herbs', 19.99, 'Main Course', 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=300&h=300&fit=crop'),
                ('Cheese Plate', 'Artisan cheese selection with honey', 14.50, 'Starters', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
            ],
            3: [  # Andys Pizza
                ('Margherita Pizza', 'Tomato, mozzarella, basil', 8.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
                ('Pepperoni Pizza', 'Pepperoni, mozzarella, tomato sauce', 10.99, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=300&h=300&fit=crop'),
                ('Quattro Formaggi', 'Four cheese pizza', 12.50, 'Pizza', 'https://images.unsplash.com/photo-1513104890138-7967b7f0d212?w=300&h=300&fit=crop'),
                ('Caesar Salad', 'Romaine, croutons, parmesan', 7.50, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('Tiramisu', 'Classic Italian dessert', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=300&h=300&fit=crop'),
                ('Hawaiian Pizza', 'Ham and pineapple', 11.99, 'Pizza', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=300&h=300&fit=crop'),
                ('Garlic Bread', 'Toasted with garlic butter', 3.99, 'Sides', 'https://images.unsplash.com/photo-1619535860434-ba1d8fa12536?w=300&h=300&fit=crop'),
                ('Coca Cola 0.5L', 'Cold refreshing drink', 1.99, 'Drinks', 'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=300&h=300&fit=crop'),
                ('Panna Cotta', 'Vanilla cream dessert with berry sauce', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
            ],
            4: [  # Propaganda
                ('Salmon Steak', 'Grilled salmon with dill sauce', 16.99, 'Main Course', 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=300&h=300&fit=crop'),
                ('Pasta Carbonara', 'Creamy spaghetti with bacon', 11.50, 'Pasta', 'https://images.unsplash.com/photo-1612874742237-6526221588e3?w=300&h=300&fit=crop'),
                ('Burrata Salad', 'Fresh burrata with tomatoes and pesto', 13.50, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Aperol Spritz', 'Refreshing cocktail', 6.50, 'Drinks', 'https://images.unsplash.com/photo-1551538827-9c037cb4f32a?w=300&h=300&fit=crop'),
                ('Chocolate Fondant', 'Warm chocolate cake with ice cream', 8.99, 'Desserts', 'https://images.unsplash.com/photo-1424847651672-bf20a4b0982b?w=300&h=300&fit=crop'),
                ('Lobster Ravioli', 'Handmade ravioli with lobster filling', 19.99, 'Pasta', 'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?w=300&h=300&fit=crop'),
                ('Bruschetta', 'Toasted bread with tomato and basil', 6.99, 'Starters', 'https://images.unsplash.com/photo-1572695157366-5e585ab2b69f?w=300&h=300&fit=crop'),
            ],
            5: [  # Beef by Victor
                ('Ribeye Steak 300g', 'Premium aged ribeye', 24.99, 'Steaks', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Burger Classic', 'House-ground beef patty with toppings', 12.50, 'Burgers', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=300&h=300&fit=crop'),
                ('Tomahawk Steak', 'Show-stopping bone-in steak', 34.99, 'Steaks', 'https://images.unsplash.com/photo-1558030006-450675393462?w=300&h=300&fit=crop'),
                ('Loaded Baked Potato', 'Sour cream, bacon, chives', 5.99, 'Sides', 'https://images.unsplash.com/photo-1518977676601-b53f82ber635?w=300&h=300&fit=crop'),
                ('Craft Beer', 'Local brewery selection', 4.50, 'Drinks', 'https://images.unsplash.com/photo-1535958636474-b021ee887b13?w=300&h=300&fit=crop'),
                ('Wagyu Steak 200g', 'Japanese A5 wagyu beef', 49.99, 'Steaks', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Caesar Salad', 'Classic with parmesan and croutons', 8.99, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('Sweet Potato Fries', 'Crispy sweet potato fries with dip', 4.99, 'Sides', 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=300&h=300&fit=crop'),
            ],
            6: [  # Osha Restaurant (was McDonalds - renumbered)
                ('Hummus Plate', 'Creamy hummus with pita bread', 5.99, 'Starters', 'https://images.unsplash.com/photo-1577805947697-89e18249d767?w=300&h=300&fit=crop'),
                ('Lamb Kebab', 'Grilled lamb with spices', 12.99, 'Main Course', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Falafel Plate', 'Crispy falafel with tahini', 8.99, 'Main Course', 'https://images.unsplash.com/photo-1593001874117-c99c800e3eb7?w=300&h=300&fit=crop'),
                ('Tabbouleh', 'Fresh parsley and bulgur salad', 5.50, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Baklava', 'Sweet phyllo pastry with nuts', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Mint Tea', 'Traditional Moroccan mint tea', 2.50, 'Drinks', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300&h=300&fit=crop'),
            ],
            7: [  # Casa Daca (was Carpe Diem duplicate)
                ('Cheese Plate', 'Artisan Moldovan cheese selection', 12.99, 'Starters', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
                ('Wine Tasting Flight', '3 local wines tasting set', 14.99, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Charcuterie Board', 'Premium meats and accompaniments', 16.99, 'Starters', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Chocolate Fondue', 'Melted chocolate with fruits', 9.99, 'Desserts', 'https://images.unsplash.com/photo-1424847651672-bf20a4b0982b?w=300&h=300&fit=crop'),
                ('Prosecco', 'Italian sparkling wine', 7.50, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
            ],
            8: [  # McDonalds Chisinau
                ('Big Mac', 'Double patty with special sauce', 5.99, 'Burgers', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=300&h=300&fit=crop'),
                ('McChicken', 'Crispy chicken sandwich', 4.99, 'Burgers', 'https://images.unsplash.com/photo-1606755962773-d324e0a13086?w=300&h=300&fit=crop'),
                ('Large Fries', 'Golden crispy fries', 2.99, 'Sides', 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=300&h=300&fit=crop'),
                ('McFlurry', 'Ice cream with toppings', 3.50, 'Desserts', 'https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=300&h=300&fit=crop'),
                ('Happy Meal', 'Kids meal with toy', 4.50, 'Combos', 'https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=300&h=300&fit=crop'),
                ('Nuggets 9pc', 'Crispy chicken nuggets', 4.99, 'Burgers', 'https://images.unsplash.com/photo-1562967914-608f82629710?w=300&h=300&fit=crop'),
                ('Sprite 0.5L', 'Lemon-lime soda', 1.50, 'Drinks', 'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=300&h=300&fit=crop'),
            ],
            9: [  # KFC Mall Dova
                ('Bucket 8pc', 'Original recipe chicken', 12.99, 'Chicken', 'https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=300&h=300&fit=crop'),
                ('Zinger Burger', 'Spicy crispy chicken sandwich', 5.99, 'Burgers', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=300&h=300&fit=crop'),
                ('Coleslaw', 'Creamy coleslaw side', 2.50, 'Sides', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('Popcorn Chicken', 'Bite-sized chicken pieces', 4.99, 'Chicken', 'https://images.unsplash.com/photo-1562967914-608f82629710?w=300&h=300&fit=crop'),
                ('Corn on the Cob', 'Buttered sweet corn', 2.99, 'Sides', 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=300&h=300&fit=crop'),
                ('Hot Wings 6pc', 'Spicy buffalo wings', 5.99, 'Chicken', 'https://images.unsplash.com/photo-1527477396000-e27163b4bbed?w=300&h=300&fit=crop'),
            ],
            10: [  # Shawarma King
                ('Chicken Shawarma', 'Large chicken shawarma wrap', 4.99, 'Shawarma', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Beef Shawarma', 'Juicy beef shawarma wrap', 5.99, 'Shawarma', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Falafel Wrap', 'Crispy falafel with hummus', 4.50, 'Wraps', 'https://images.unsplash.com/photo-1593001874117-c99c800e3eb7?w=300&h=300&fit=crop'),
                ('Hummus Plate', 'Creamy hummus with pita bread', 3.99, 'Sides', 'https://images.unsplash.com/photo-1577805947697-89e18249d767?w=300&h=300&fit=crop'),
                ('Ayran Drink', 'Refreshing yogurt drink', 1.99, 'Drinks', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?w=300&h=300&fit=crop'),
                ('Mixed Grill Plate', 'Assorted grilled meats', 9.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
            ],
            11: [  # Burger Box
                ('Classic Smash Burger', 'Double smashed patty with cheese', 8.99, 'Burgers', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=300&h=300&fit=crop'),
                ('BBQ Bacon Burger', 'Smoky BBQ sauce with crispy bacon', 10.99, 'Burgers', 'https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=300&h=300&fit=crop'),
                ('Mushroom Swiss', 'Sautéed mushrooms with Swiss cheese', 9.99, 'Burgers', 'https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=300&h=300&fit=crop'),
                ('Onion Rings', 'Crispy battered onion rings', 3.99, 'Sides', 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=300&h=300&fit=crop'),
                ('Milkshake Vanilla', 'Thick vanilla milkshake', 4.50, 'Drinks', 'https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=300&h=300&fit=crop'),
                ('Milkshake Chocolate', 'Rich chocolate milkshake', 4.50, 'Drinks', 'https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=300&h=300&fit=crop'),
            ],
            12: [  # Farmacia Familia
                ('Paracetamol 500mg', 'Pain relief tablets (20 pcs)', 3.50, 'Pain Relief', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Ibuprofen 400mg', 'Anti-inflammatory tablets (20 pcs)', 4.99, 'Pain Relief', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Vitamin D3', 'Immune support (30 capsules)', 6.50, 'Vitamins', 'https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=300&h=300&fit=crop'),
                ('Nasal Spray', 'Decongestant spray 15ml', 4.20, 'Cold & Flu', 'https://images.unsplash.com/photo-1576602976047-174e57a47881?w=300&h=300&fit=crop'),
                ('Thermometer Digital', 'Fast-read digital thermometer', 12.99, 'Devices', 'https://images.unsplash.com/photo-1584820927498-cfe5211fd8bf?w=300&h=300&fit=crop'),
                ('Vitamin C 1000mg', 'Immune booster (30 tablets)', 5.99, 'Vitamins', 'https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=300&h=300&fit=crop'),
                ('Cough Syrup 200ml', 'Honey-based cough remedy', 4.50, 'Cold & Flu', 'https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=300&h=300&fit=crop'),
                ('Blood Pressure Monitor', 'Digital BP monitor', 29.99, 'Devices', 'https://images.unsplash.com/photo-1584820927498-cfe5211fd8bf?w=300&h=300&fit=crop'),
            ],
            13: [  # Farmacie Noapte
                ('Cold & Flu Pack', 'Complete cold remedy kit', 8.99, 'Cold & Flu', 'https://images.unsplash.com/photo-1576602976047-174e57a47881?w=300&h=300&fit=crop'),
                ('Cough Syrup', 'Honey-based cough syrup 200ml', 5.50, 'Cold & Flu', 'https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=300&h=300&fit=crop'),
                ('Allergy Tablets', 'Antihistamine (10 pcs)', 4.80, 'Allergy', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Hand Sanitizer', 'Antibacterial gel 250ml', 2.99, 'Hygiene', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('First Aid Kit', 'Basic first aid supplies', 15.99, 'First Aid', 'https://images.unsplash.com/photo-1603398938378-e54eab446dde?w=300&h=300&fit=crop'),
                ('Antiseptic Cream', 'Wound care cream 30g', 3.99, 'First Aid', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
            ],
            14: [  # Sensiblu
                ('Probiotics', 'Digestive health (30 capsules)', 9.50, 'Vitamins', 'https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=300&h=300&fit=crop'),
                ('Omega 3 Fish Oil', 'Heart health supplement', 7.99, 'Vitamins', 'https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=300&h=300&fit=crop'),
                ('Eye Drops', 'Moisturizing eye drops 10ml', 3.99, 'Eye Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Bandages Assorted', 'Self-adhesive bandages (20 pcs)', 2.50, 'First Aid', 'https://images.unsplash.com/photo-1603398938378-e54eab446dde?w=300&h=300&fit=crop'),
                ('Sunscreen SPF50', 'Sun protection 200ml', 8.99, 'Skin Care', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Magnesium 400mg', 'Muscle and nerve support', 6.99, 'Vitamins', 'https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=300&h=300&fit=crop'),
            ],
            15: [  # Nr1 Supermarket
                ('Bread Loaf', 'Fresh white bread', 1.20, 'Bakery', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Milk 1L', 'Fresh whole milk', 1.49, 'Dairy', 'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=300&h=300&fit=crop'),
                ('Eggs (10)', 'Farm fresh eggs', 2.99, 'Dairy', 'https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=300&h=300&fit=crop'),
                ('Potatoes (1kg)', 'Fresh potatoes', 0.99, 'Vegetables', 'https://images.unsplash.com/photo-1518977676601-b53f82be635?w=300&h=300&fit=crop'),
                ('Chicken Breast (1kg)', 'Fresh chicken breast', 5.99, 'Meat', 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=300&h=300&fit=crop'),
                ('Apples (1kg)', 'Fresh red apples', 1.99, 'Fruits', 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=300&h=300&fit=crop'),
                ('Butter 200g', 'Premium butter', 2.49, 'Dairy', 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=300&h=300&fit=crop'),
                ('Mineral Water 1.5L', 'Sparkling mineral water', 0.79, 'Drinks', 'https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=300&h=300&fit=crop'),
                ('Sugar 1kg', 'White granulated sugar', 1.29, 'Pantry', 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=300&h=300&fit=crop'),
                ('Yogurt 400g', 'Natural yogurt', 1.49, 'Dairy', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
            ],
            16: [  # Fidesco Market
                ('Imported Cheese 200g', 'Premium Dutch cheese', 4.50, 'Dairy', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
                ('Olive Oil 500ml', 'Extra virgin olive oil', 6.99, 'Pantry', 'https://images.unsplash.com/photo-1474979266404-7f28db8034e9?w=300&h=300&fit=crop'),
                ('Pasta Barilla 500g', 'Italian spaghetti', 2.50, 'Pantry', 'https://images.unsplash.com/photo-1551462147-ff29053bfc14?w=300&h=300&fit=crop'),
                ('Orange Juice 1L', 'Fresh squeezed juice', 3.20, 'Drinks', 'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=300&h=300&fit=crop'),
                ('Coffee Beans 250g', 'Arabica coffee beans', 5.99, 'Drinks', 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=300&h=300&fit=crop'),
                ('Salmon Fillet 300g', 'Fresh Atlantic salmon', 8.99, 'Meat', 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=300&h=300&fit=crop'),
                ('Avocado (2pc)', 'Ripe Hass avocados', 3.49, 'Fruits', 'https://images.unsplash.com/photo-1523049673857-eb18f1d7b578?w=300&h=300&fit=crop'),
                ('Red Wine 750ml', 'Moldovan Cabernet Sauvignon', 6.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
            ],
            17: [  # Linella Supermarket
                ('Rice 1kg', 'Long grain white rice', 1.80, 'Pantry', 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=300&h=300&fit=crop'),
                ('Tomatoes (1kg)', 'Fresh tomatoes', 2.20, 'Vegetables', 'https://images.unsplash.com/photo-1518977676601-b53f82be635?w=300&h=300&fit=crop'),
                ('Bananas (1kg)', 'Ripe bananas', 1.50, 'Fruits', 'https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=300&h=300&fit=crop'),
                ('Sour Cream 400g', 'Traditional sour cream', 1.29, 'Dairy', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
                ('Minced Meat 500g', 'Pork and beef mix', 3.99, 'Meat', 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=300&h=300&fit=crop'),
                ('Cucumber (1kg)', 'Fresh cucumbers', 1.49, 'Vegetables', 'https://images.unsplash.com/photo-1518977676601-b53f82be635?w=300&h=300&fit=crop'),
                ('Chocolate Bar', 'Local Moldovan chocolate', 1.79, 'Snacks', 'https://images.unsplash.com/photo-1549007994-cb92caebd54b?w=300&h=300&fit=crop'),
                ('Tea Bags (25pc)', 'Black tea assortment', 2.29, 'Drinks', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300&h=300&fit=crop'),
            ],
        }
        for rid, items in items_data.items():
            for name, desc, price, sub_cat, img in items:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price,sub_category,image_url) VALUES (?,?,?,?,?,?)",
                           (rid, name, desc, price, sub_cat, img))
                except Exception as e:
                    print(f"  Seed item note: {e}")
        print("  Seeded menu items with sub-categories and images for all Moldova businesses")

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

    # Update the seed version after successful seeding
    if needs_reseed:
        update_seed_version()
        print("  ✅ Database reseed complete!")
