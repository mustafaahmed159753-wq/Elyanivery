"""
Elyanivery — Database Module (PostgreSQL)
Uses psycopg2 with thread-local connections.
All SQL Server-specific syntax has been converted to PostgreSQL.
v6.0 — Version-based auto-reseed, Admin approval, broadcasts, phone numbers, Moldova seed data, Deliver Anything addresses
"""

# ── Current seed version — bump this to force a database reseed on Railway ──
CURRENT_SEED_VERSION = '8'

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
        restaurants = [
            # ── RESTAURANTS ──
            ('La Placinte', 'Traditional Moldovan cuisine with modern twist', 'Str. Stefan cel Mare 67, Chisinau', 47.0258, 28.8328, 'restaurant', '+373 22 123 456'),
            ('Carpe Diem', 'Fine dining & wine bar in the heart of Chisinau', 'Str. V. Pircalab 52, Chisinau', 47.0189, 28.8451, 'restaurant', '+373 22 234 567'),
            ('Andys Pizza', 'Popular Italian-style pizza restaurant', 'Bulevardul Stefan cel Mare 32, Chisinau', 47.0312, 28.8407, 'restaurant', '+373 22 345 678'),
            ('Propaganda', 'Modern European cuisine with local ingredients', 'Str. M. Eminescu 24, Chisinau', 47.0156, 28.8503, 'restaurant', '+373 22 456 789'),
            ('Beef by Victor', 'Premium steakhouse and grill', 'Str. A. Mateevici 15, Chisinau', 47.0273, 28.8516, 'restaurant', '+373 22 567 890'),
            # ── FAST FOOD ──
            ('McDonalds Chisinau', 'Classic fast food burgers and fries', 'Bulevardul Dacia 39, Chisinau', 47.0356, 28.8297, 'fast_food', '+373 22 678 901'),
            ('KFC Mall Dova', 'Fried chicken and sides', 'Str. Arborilor 21, Chisinau', 47.0125, 28.8612, 'fast_food', '+373 22 789 012'),
            ('Shawarma King', 'Best shawarma and falafel in town', 'Str. Ismail 49, Chisinau', 47.0198, 28.8379, 'fast_food', '+373 22 890 123'),
            # ── PHARMACIES ──
            ('Farmacia Familia', 'Full-service pharmacy delivery', 'Str. Alexandru cel Bun 80, Chisinau', 47.0241, 28.8562, 'pharmacy', '+373 22 901 234'),
            ('Farmacie Noapte', '24/7 pharmacy open all night', 'Bulevardul Decebal 23, Chisinau', 47.0089, 28.8445, 'pharmacy', '+373 22 012 345'),
            ('Sensiblu Chisinau', 'Health and wellness pharmacy', 'Str. Tighina 34, Chisinau', 47.0172, 28.8689, 'pharmacy', '+373 22 123 457'),
            # ── SUPERMARKETS ──
            ('Nr1 Supermarket', 'Everything you need, delivered fast', 'Str. Moscovei 5, Chisinau', 47.0301, 28.8234, 'supermarket', '+373 22 234 568'),
            ('Fidesco Market', 'Premium grocery and household items', 'Str. Calea Orheiului 16, Chisinau', 47.0412, 28.8578, 'supermarket', '+373 22 345 679'),
            ('Linella Supermarket', 'Affordable groceries for every family', 'Bulevardul Mircea cel Batran 8, Chisinau', 47.0067, 28.8534, 'supermarket', '+373 22 456 780'),
            # ── DELIVERY SERVICE (virtual) ──
            ('Elyanivery Delivery Service', 'Virtual restaurant for Deliver Anything orders', '', 47.0105, 28.8638, 'delivery_service', ''),
        ]
        for name, desc, addr, lat, lng, cat, phone in restaurants:
            try:
                insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,category,phone) VALUES (?,?,?,?,?,TRUE,?,?)",
                       (name, desc, addr, lat, lng, cat, phone))
            except Exception as e:
                print(f"  Seed restaurant note: {e}")
        print("  Seeded 15 Moldova-based restaurants (restaurants, fast_food, pharmacies, supermarkets)")

        # Seed items for each restaurant
        items_data = {
            1: [  # La Placinte - Moldovan
                ('Placinta cu Branza', 'Traditional cheese-filled pastry', 4.50),
                ('Placinta cu Varza', 'Cabbage-filled pastry', 3.99),
                ('Mamaliga cu Branza', 'Polenta with cheese and sour cream', 6.99),
                ('Zeama de Pui', 'Traditional chicken soup', 5.50),
                ('Sarmale', 'Stuffed cabbage rolls', 7.99),
            ],
            2: [  # Carpe Diem - Fine dining
                ('Duck Confit', 'Slow-cooked duck leg with cherry sauce', 18.50),
                ('Risotto ai Funghi', 'Wild mushroom risotto', 14.99),
                ('Beef Carpaccio', 'Thin sliced raw beef with arugula', 12.50),
                ('Wine Selection', 'Local Moldovan wine pairing', 9.99),
                ('Creme Brulee', 'Classic vanilla custard dessert', 7.50),
            ],
            3: [  # Andys Pizza
                ('Margherita Pizza', 'Tomato, mozzarella, basil', 8.99),
                ('Pepperoni Pizza', 'Pepperoni, mozzarella, tomato sauce', 10.99),
                ('Quattro Formaggi', 'Four cheese pizza', 12.50),
                ('Caesar Salad', 'Romaine, croutons, parmesan', 7.50),
                ('Tiramisu', 'Classic Italian dessert', 5.99),
            ],
            4: [  # Propaganda
                ('Salmon Steak', 'Grilled salmon with dill sauce', 16.99),
                ('Pasta Carbonara', 'Creamy spaghetti with bacon', 11.50),
                ('Burrata Salad', 'Fresh burrata with tomatoes and pesto', 13.50),
                ('Aperol Spritz', 'Refreshing cocktail', 6.50),
                ('Chocolate Fondant', 'Warm chocolate cake with ice cream', 8.99),
            ],
            5: [  # Beef by Victor
                ('Ribeye Steak 300g', 'Premium aged ribeye', 24.99),
                ('Burger Classic', 'House-ground beef patty with toppings', 12.50),
                ('Tomahawk Steak', 'Show-stopping bone-in steak', 34.99),
                ('Loaded Baked Potato', 'Sour cream, bacon, chives', 5.99),
                ('Craft Beer', 'Local brewery selection', 4.50),
            ],
            6: [  # McDonalds
                ('Big Mac', 'Double patty with special sauce', 5.99),
                ('McChicken', 'Crispy chicken sandwich', 4.99),
                ('Large Fries', 'Golden crispy fries', 2.99),
                ('McFlurry', 'Ice cream with toppings', 3.50),
                ('Happy Meal', 'Kids meal with toy', 4.50),
            ],
            7: [  # KFC
                ('Bucket 8pc', 'Original recipe chicken', 12.99),
                ('Zinger Burger', 'Spicy crispy chicken sandwich', 5.99),
                ('Coleslaw', 'Creamy coleslaw side', 2.50),
                ('Popcorn Chicken', 'Bite-sized chicken pieces', 4.99),
                ('Corn on the Cob', 'Buttered sweet corn', 2.99),
            ],
            8: [  # Shawarma King
                ('Chicken Shawarma', 'Large chicken shawarma wrap', 4.99),
                ('Beef Shawarma', 'Juicy beef shawarma wrap', 5.99),
                ('Falafel Wrap', 'Crispy falafel with hummus', 4.50),
                ('Hummus Plate', 'Creamy hummus with pita bread', 3.99),
                ('Ayran Drink', 'Refreshing yogurt drink', 1.99),
            ],
            9: [  # Farmacia Familia
                ('Paracetamol 500mg', 'Pain relief tablets (20 pcs)', 3.50),
                ('Ibuprofen 400mg', 'Anti-inflammatory tablets (20 pcs)', 4.99),
                ('Vitamin D3', 'Immune support (30 capsules)', 6.50),
                ('Nasal Spray', 'Decongestant spray 15ml', 4.20),
                ('Thermometer Digital', 'Fast-read digital thermometer', 12.99),
            ],
            10: [  # Farmacie Noapte
                ('Cold & Flu Pack', 'Complete cold remedy kit', 8.99),
                ('Cough Syrup', 'Honey-based cough syrup 200ml', 5.50),
                ('Allergy Tablets', 'Antihistamine (10 pcs)', 4.80),
                ('Hand Sanitizer', 'Antibacterial gel 250ml', 2.99),
                ('First Aid Kit', 'Basic first aid supplies', 15.99),
            ],
            11: [  # Sensiblu
                ('Probiotics', 'Digestive health (30 capsules)', 9.50),
                ('Omega 3 Fish Oil', 'Heart health supplement', 7.99),
                ('Eye Drops', 'Moisturizing eye drops 10ml', 3.99),
                ('Bandages Assorted', 'Self-adhesive bandages (20 pcs)', 2.50),
                ('Sunscreen SPF50', 'Sun protection 200ml', 8.99),
            ],
            12: [  # Nr1 Supermarket
                ('Bread Loaf', 'Fresh white bread', 1.20),
                ('Milk 1L', 'Fresh whole milk', 1.49),
                ('Eggs (10)', 'Farm fresh eggs', 2.99),
                ('Potatoes (1kg)', 'Fresh potatoes', 0.99),
                ('Chicken Breast (1kg)', 'Fresh chicken breast', 5.99),
            ],
            13: [  # Fidesco Market
                ('Imported Cheese 200g', 'Premium Dutch cheese', 4.50),
                ('Olive Oil 500ml', 'Extra virgin olive oil', 6.99),
                ('Pasta Barilla 500g', 'Italian spaghetti', 2.50),
                ('Orange Juice 1L', 'Fresh squeezed juice', 3.20),
                ('Coffee Beans 250g', 'Arabica coffee beans', 5.99),
            ],
            14: [  # Linella Supermarket
                ('Rice 1kg', 'Long grain white rice', 1.80),
                ('Tomatoes (1kg)', 'Fresh tomatoes', 2.20),
                ('Bananas (1kg)', 'Ripe bananas', 1.50),
                ('Sour Cream 400g', 'Traditional sour cream', 1.29),
                ('Minced Meat 500g', 'Pork and beef mix', 3.99),
            ],
        }
        for rid, items in items_data.items():
            for name, desc, price in items:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price) VALUES (?,?,?,?)",
                           (rid, name, desc, price))
                except Exception as e:
                    print(f"  Seed item note: {e}")
        print("  Seeded menu items for all Moldova restaurants")

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
