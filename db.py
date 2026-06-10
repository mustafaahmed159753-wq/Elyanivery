"""
Elyanivery — Database Module (PostgreSQL)
Uses psycopg2 with thread-local connections.
All SQL Server-specific syntax has been converted to PostgreSQL.
v6.0 — Version-based auto-reseed, Admin approval, broadcasts, phone numbers, Moldova seed data, Deliver Anything addresses
"""

# ── Current seed version — bump this to force a database reseed on Railway ──
CURRENT_SEED_VERSION = '15'

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

        """CREATE TABLE IF NOT EXISTS DeliveryZones (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            center_lat FLOAT NOT NULL DEFAULT 47.0105,
            center_lng FLOAT NOT NULL DEFAULT 28.8638,
            radius_km FLOAT NOT NULL DEFAULT 5.0,
            is_active BOOLEAN DEFAULT TRUE,
            polygon_points TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",

        """CREATE TABLE IF NOT EXISTS ActivityLog (
            id SERIAL PRIMARY KEY,
            admin_id INT NOT NULL,
            action VARCHAR(100) NOT NULL,
            target_type VARCHAR(50),
            target_id INT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        ("Restaurants", "is_active", "BOOLEAN DEFAULT TRUE"),
        ("DeliveryZones", "is_active", "BOOLEAN DEFAULT TRUE"),
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
        # Use TRUNCATE with RESTART IDENTITY CASCADE to reset SERIAL sequences
        # This ensures new rows get IDs starting from 1 again
        try:
            tables_to_truncate = [
                'OrderItems', 'OrderLog', 'Orders', 'Items', 'Restaurants',
                'PromoCodes', 'Favorites', 'Ratings', 'CourierEarnings',
                'SupportTickets', 'SupportMessages', 'Broadcasts',
                'CourierLocations', 'DeliveryZones',
            ]
            # These may or may not exist, so try individually
            for tbl in tables_to_truncate:
                try:
                    query(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE")
                except Exception:
                    try:
                        query(f"DELETE FROM {tbl}")
                    except Exception:
                        pass
            # Tables that may not exist in all deployments
            for tbl in ['ChatMessages', 'Notifications', 'Addresses', 'PointTransactions', 'LoyaltyPoints', 'CallSessions', 'IceCandidates']:
                try:
                    query(f"DELETE FROM {tbl}")
                except Exception:
                    pass
            # Users last (referenced by other tables)
            try:
                query("TRUNCATE TABLE Users RESTART IDENTITY CASCADE")
            except Exception:
                try:
                    query("DELETE FROM Users")
                except Exception:
                    pass
            print("  Cleared all existing data for reseed (with sequence reset)")
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
            # ── CAFES ──
            ('Tucano Coffee', 'Specialty coffee and fresh pastries', 'Str. Alexandru cel Bun 56, Chisinau', 47.0225, 28.8521, 'cafe', '+373 22 345 100', 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600&h=400&fit=crop'),
            ('Bonito Cafe', 'Cozy brunch spot with artisan coffee', 'Str. Bucuresti 31, Chisinau', 47.0190, 28.8405, 'cafe', '+373 22 456 200', 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=600&h=400&fit=crop'),
            ('Dianas Cafe', 'Family-friendly cafe with homemade desserts', 'Bulevardul Stefan cel Mare 75, Chisinau', 47.0325, 28.8390, 'cafe', '+373 22 567 300', 'https://images.unsplash.com/photo-1559305616-3f99cd43e353?w=600&h=400&fit=crop'),
            # ── MORE RESTAURANTS ──
            ('Pirogovo', 'Traditional Russian and Ukrainian cuisine', 'Str. M. Eminescu 42, Chisinau', 47.0178, 28.8478, 'restaurant', '+373 22 678 400', 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&h=400&fit=crop'),
            ('Goiu Restaurant', 'Moldovan and Romanian traditional dishes', 'Str. Ismail 12, Chisinau', 47.0208, 28.8360, 'restaurant', '+373 22 789 500', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            # ── BAKERY ──
            ('Franzeluta Bakery', 'Fresh bread, cakes and pastries since 1964', 'Str. Alba Iulia 43, Chisinau', 47.0280, 28.8460, 'bakery', '+373 22 890 600', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            # ── JUICE BAR ──
            ('Fresh Bar', 'Cold-pressed juices and healthy smoothies', 'Str. V. Alecsandri 23, Chisinau', 47.0160, 28.8420, 'cafe', '+373 22 901 700', 'https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=600&h=400&fit=crop'),
            # ── SUSHI ──
            ('Sushi Master', 'Premium Japanese sushi and rolls', 'Bulevardul Decebal 8, Chisinau', 47.0100, 28.8450, 'restaurant', '+373 22 012 800', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=600&h=400&fit=crop'),
            # ── MORE CAFES ──
            ('Mona Cafe', 'Artisan coffee and European pastries', 'Str. 31 August 78, Chisinau', 47.0180, 28.8350, 'cafe', '+373 22 111 001', 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600&h=400&fit=crop'),
            ('Art Coffee', 'Specialty brews in an artistic setting', 'Str. Bucuresti 15, Chisinau', 47.0210, 28.8395, 'cafe', '+373 22 111 002', 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=600&h=400&fit=crop'),
            ('Smilecafe', 'Friendly neighborhood coffee shop', 'Bulevardul Stefan cel Mare 90, Chisinau', 47.0330, 28.8380, 'cafe', '+373 22 111 003', 'https://images.unsplash.com/photo-1559305616-3f99cd43e353?w=600&h=400&fit=crop'),
            ('Coffee-Mol', 'Moldova\'s favorite coffee chain', 'Str. V. Pircalab 30, Chisinau', 47.0175, 28.8460, 'cafe', '+373 22 111 004', 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600&h=400&fit=crop'),
            ('Pani Pitca', 'Traditional Moldovan pitca and baked goods', 'Str. Tighina 47, Chisinau', 47.0155, 28.8700, 'cafe', '+373 22 111 005', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            ('Forno Rosso', 'Italian wood-fired oven specialties', 'Str. M. Eminescu 63, Chisinau', 47.0190, 28.8490, 'restaurant', '+373 22 111 006', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&h=400&fit=crop'),
            ('Galantom', 'Elegant cafe-restaurant with live music', 'Str. Columna 45, Chisinau', 47.0245, 28.8435, 'cafe', '+373 22 111 007', 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=600&h=400&fit=crop'),
            # ── MORE RESTAURANTS ──
            ('Mono', 'Modern minimalist dining experience', 'Str. A. Mateevici 25, Chisinau', 47.0280, 28.8520, 'restaurant', '+373 22 111 008', 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&h=400&fit=crop'),
            ('La Scufita', 'Cozy Romanian and Moldovan comfort food', 'Str. Ismail 30, Chisinau', 47.0200, 28.8365, 'restaurant', '+373 22 111 009', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            ('Crocodile', 'Legendary Chisinau restaurant since 1998', 'Str. Stefan cel Mare 102, Chisinau', 47.0340, 28.8310, 'restaurant', '+373 22 111 010', 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&h=400&fit=crop'),
            ('Supa', 'Dedicated soup restaurant with global recipes', 'Str. V. Alecsandri 12, Chisinau', 47.0155, 28.8415, 'restaurant', '+373 22 111 011', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600&h=400&fit=crop'),
            ('Merenilor', 'Fine dining in a charming orchard setting', 'Str. Ghioceilor 8, Chisinau', 47.0070, 28.8500, 'restaurant', '+373 22 111 012', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            ('Vila Codru', 'Elegant restaurant in a historic villa', 'Str. Codrilor 22, Chisinau', 47.0350, 28.8550, 'restaurant', '+373 22 111 013', 'https://images.unsplash.com/photo-1559339352-11d035aa65de?w=600&h=400&fit=crop'),
            ('Restaurant Nobil', 'Noble dining with premium ingredients', 'Bulevardul Negruzzi 7, Chisinau', 47.0220, 28.8340, 'restaurant', '+373 22 111 014', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            # ── MORE FAST FOOD ──
            ('Doner Kebab', 'Authentic Turkish doner kebab', 'Str. Alexandru cel Bun 15, Chisinau', 47.0230, 28.8540, 'fast_food', '+373 22 111 015', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600&h=400&fit=crop'),
            ('Strudel Haus', 'Austrian strudels and savory pastries', 'Str. Bucuresti 50, Chisinau', 47.0195, 28.8410, 'fast_food', '+373 22 111 016', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            ('Perfect Pizza', 'Fast delivery pizza and calzones', 'Bulevardul Dacia 55, Chisinau', 47.0360, 28.8300, 'fast_food', '+373 22 111 017', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&h=400&fit=crop'),
            # ── MORE BAKERIES ──
            ('Pekarnya', 'Slavic-style bakery with fresh daily bakes', 'Str. Alba Iulia 20, Chisinau', 47.0275, 28.8455, 'bakery', '+373 22 111 018', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            ('Casuta Cu Bunatati', 'Cozy house of homemade baked treats', 'Str. Moscovei 18, Chisinau', 47.0295, 28.8240, 'bakery', '+373 22 111 019', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=600&h=400&fit=crop'),
            # ── MORE PHARMACIES ──
            ('Farmacia Vita', 'Your health, our priority', 'Str. Stefan cel Mare 88, Chisinau', 47.0310, 28.8365, 'pharmacy', '+373 22 111 020', 'https://images.unsplash.com/photo-1576602976047-174e57a47881?w=600&h=400&fit=crop'),
            ('Help Net Farmacie', 'Modern pharmacy with online ordering', 'Str. Tighina 55, Chisinau', 47.0160, 28.8695, 'pharmacy', '+373 22 111 021', 'https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=600&h=400&fit=crop'),
            # ── MORE SUPERMARKETS ──
            ('Metro Cash & Carry', 'Bulk wholesale for businesses and families', 'Str. Uzinelor 17, Chisinau', 47.0380, 28.8600, 'supermarket', '+373 22 111 022', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=600&h=400&fit=crop'),
            ('Kaufland Chisinau', 'Large-format grocery and household store', 'Str. Calea Orheiului 35, Chisinau', 47.0420, 28.8580, 'supermarket', '+373 22 111 023', 'https://images.unsplash.com/photo-1534723454574-44b0d39e4a2c?w=600&h=400&fit=crop'),
            # ── V2 EXPANDED BUSINESSES ──
            ('Mona Cafe', 'Stylish cafe with specialty coffee and brunch', 'Str. Alexandru cel Bun 12, Chisinau', 47.0215, 28.8501, 'cafe', '+373 22 112 001', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&h=400&fit=crop'),
            ('Art Coffee', 'Artisan coffee roasters with cozy atmosphere', 'Str. Bucuresti 78, Chisinau', 47.0182, 28.8395, 'cafe', '+373 22 112 002', 'https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=600&h=400&fit=crop'),
            ('Doner Kebab House', 'Authentic Turkish doner and kebabs', 'Str. Ismail 66, Chisinau', 47.0220, 28.8360, 'fast_food', '+373 22 112 003', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600&h=400&fit=crop'),
            ('La Scufita', 'Romanian and Moldovan traditional cuisine', 'Str. V. Pircalab 15, Chisinau', 47.0175, 28.8475, 'restaurant', '+373 22 112 004', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            ('Supa Restaurant', 'Gourmet soups and healthy bowls', 'Str. M. Eminescu 56, Chisinau', 47.0165, 28.8485, 'restaurant', '+373 22 112 005', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600&h=400&fit=crop'),
            ('Pani Pitca', 'Traditional Moldovan pies and placinte', 'Str. Calea Orheiului 34, Chisinau', 47.0390, 28.8550, 'bakery', '+373 22 112 006', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            ('Forno Rosso', 'Italian wood-fired pizza and pasta', 'Bulevardul Stefan cel Mare 101, Chisinau', 47.0340, 28.8385, 'restaurant', '+373 22 112 007', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&h=400&fit=crop'),
            ('Farmacia Vita', 'Health products and prescription delivery', 'Str. Tighina 78, Chisinau', 47.0150, 28.8650, 'pharmacy', '+373 22 112 008', 'https://images.unsplash.com/photo-1576602976047-174e57a47881?w=600&h=400&fit=crop'),
            ('Metro Cash&Carry', 'Bulk groceries and household items', 'Str. Uzinelor 21, Chisinau', 47.0450, 28.8700, 'supermarket', '+373 22 112 009', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=600&h=400&fit=crop'),
            ('Strudel Haus', 'Austrian pastries and strudels', 'Str. Columna 45, Chisinau', 47.0240, 28.8435, 'bakery', '+373 22 112 010', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&h=400&fit=crop'),
            ('Perfect Pizza', 'Fast pizza delivery with creative toppings', 'Str. Moscovei 23, Chisinau', 47.0290, 28.8230, 'fast_food', '+373 22 112 011', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&h=400&fit=crop'),
            ('Vila Codru', 'Elegant dining in a historic villa setting', 'Str. Codrilor 12, Chisinau', 47.0350, 28.8620, 'restaurant', '+373 22 112 012', 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&h=400&fit=crop'),
            ('Smilecafe', 'Happy vibes and great coffee', 'Bulevardul Decebal 45, Chisinau', 47.0095, 28.8430, 'cafe', '+373 22 112 013', 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=600&h=400&fit=crop'),
            ('Galantom', 'Fine dining with Moldovan wine pairing', 'Str. 31 August 78, Chisinau', 47.0200, 28.8350, 'restaurant', '+373 22 112 014', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&h=400&fit=crop'),
            ('Help Net Farmacie', 'Modern pharmacy with home delivery', 'Bulevardul Mircea cel Batran 34, Chisinau', 47.0075, 28.8520, 'pharmacy', '+373 22 112 015', 'https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=600&h=400&fit=crop'),
        ]
        for name, desc, addr, lat, lng, cat, phone, img in restaurants:
            try:
                insert("INSERT INTO Restaurants (name,description,address,latitude,longitude,is_open,category,phone,image_url) VALUES (?,?,?,?,?,TRUE,?,?,?)",
                       (name, desc, addr, lat, lng, cat, phone, img))
            except Exception as e:
                print(f"  Seed restaurant note: {e}")
        print("  Seeded 64 Moldova-based businesses with Unsplash images")

        # Build a name->id mapping for robust item seeding
        # (This ensures items link to correct restaurant IDs even if sequence doesn't start from 1)
        rest_rows = query("SELECT id, name FROM Restaurants ORDER BY id", fetch=True) or []
        rest_name_to_id = {r['name']: r['id'] for r in rest_rows}
        # Also build an index-based mapping (1st restaurant = index 1, etc.)
        rest_index_to_id = {i+1: r['id'] for i, r in enumerate(rest_rows)}

        # Seed items for each restaurant
        # Format: (name, description, price, sub_category, image_url)
        # Keys use index positions matching the restaurant list order (1=La Placinte, 2=Carpe Diem, etc.)
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
            19: [  # Tucano Coffee
                ('Cappuccino', 'Rich espresso with steamed milk foam', 3.50, 'Coffee', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Latte', 'Smooth espresso with steamed milk', 3.99, 'Coffee', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
                ('Espresso', 'Strong concentrated coffee shot', 2.50, 'Coffee', 'https://images.unsplash.com/photo-1510707577719-ae7c14805e3a?w=300&h=300&fit=crop'),
                ('Croissant Butter', 'Flaky French-style butter croissant', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Chocolate Muffin', 'Double chocolate muffin', 2.50, 'Pastries', 'https://images.unsplash.com/photo-1607958996333-41aef7caefaa?w=300&h=300&fit=crop'),
                ('Iced Latte', 'Cold espresso with milk over ice', 4.50, 'Cold Drinks', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
                ('Cheesecake Slice', 'New York style cheesecake', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
            ],
            20: [  # Bonito Cafe
                ('Avocado Toast', 'Smashed avocado on sourdough', 6.99, 'Brunch', 'https://images.unsplash.com/photo-1541519227354-08fa5d50c44d?w=300&h=300&fit=crop'),
                ('Eggs Benedict', 'Poached eggs with hollandaise', 8.99, 'Brunch', 'https://images.unsplash.com/photo-1608039829572-9b0189fd5a67?w=300&h=300&fit=crop'),
                ('Pancake Stack', 'Fluffy pancakes with maple syrup', 5.99, 'Brunch', 'https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=300&h=300&fit=crop'),
                ('Flat White', 'Velvety microfoam coffee', 3.99, 'Coffee', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Acai Bowl', 'Acai blend with granola and fruit', 7.50, 'Brunch', 'https://images.unsplash.com/photo-1590301157890-4810ed352733?w=300&h=300&fit=crop'),
                ('Matcha Latte', 'Japanese matcha with oat milk', 4.50, 'Coffee', 'https://images.unsplash.com/photo-1515823064-d6e0c04616a7?w=300&h=300&fit=crop'),
            ],
            21: [  # Dianas Cafe
                ('Homemade Cheesecake', 'Creamy baked cheesecake', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Apple Strudel', 'Warm apple strudel with vanilla sauce', 5.50, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Hot Chocolate', 'Rich dark hot chocolate', 3.50, 'Drinks', 'https://images.unsplash.com/photo-1542990253-0d0f5be5f0ed?w=300&h=300&fit=crop'),
                ('Club Sandwich', 'Triple-decker chicken sandwich', 6.99, 'Main Course', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Caesar Salad', 'Crispy romaine with caesar dressing', 5.99, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('Lemonade Fresh', 'Freshly squeezed lemonade', 2.99, 'Drinks', 'https://images.unsplash.com/photo-1621263764928-df1444c5e859?w=300&h=300&fit=crop'),
            ],
            22: [  # Pirogovo
                ('Borscht', 'Traditional beetroot soup with sour cream', 5.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Pelmeni', 'Russian meat dumplings', 7.50, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Beef Stroganoff', 'Creamy beef with mushrooms', 9.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Blini with Caviar', 'Thin pancakes with red caviar', 12.50, 'Starters', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Vodka Shot', 'Premium Russian vodka 50ml', 3.99, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
                ('Olivier Salad', 'Traditional Russian potato salad', 4.99, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
            ],
            23: [  # Goiu Restaurant
                ('Mititei', 'Grilled skinless sausages with mustard', 7.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Ciorba de Burta', 'Tripe soup with sour cream', 6.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Dovlecei Pane', 'Breaded fried zucchini', 4.99, 'Starters', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Papanași', 'Romanian donuts with cream and jam', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Tochitura Moldoveneasca', 'Pork stew with polenta', 9.50, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Tuica', 'Traditional plum brandy 50ml', 3.50, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
            ],
            24: [  # Franzeluta Bakery
                ('White Bread Loaf', 'Fresh baked white bread', 1.50, 'Bread', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Black Bread', 'Traditional dark rye bread', 1.99, 'Bread', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Birthday Cake 1kg', 'Custom decorated birthday cake', 15.99, 'Cakes', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=300&h=300&fit=crop'),
                ('Napoleon Cake Slice', 'Layered cream cake slice', 3.99, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Eclairs 3pc', 'Chocolate cream eclairs', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Croissants 4pc', 'Butter croissants pack', 4.50, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Baguette', 'French-style baguette', 1.20, 'Bread', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Honey Cake Slice', 'Medovik honey layer cake', 4.50, 'Cakes', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=300&h=300&fit=crop'),
            ],
            25: [  # Fresh Bar
                ('Green Detox Juice', 'Kale, apple, ginger, lemon', 4.99, 'Juices', 'https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=300&h=300&fit=crop'),
                ('Orange Fresh', 'Freshly squeezed orange juice', 3.99, 'Juices', 'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=300&h=300&fit=crop'),
                ('Berry Smoothie', 'Mixed berries with yogurt', 5.50, 'Smoothies', 'https://images.unsplash.com/photo-1553530666-ba11a7da3888?w=300&h=300&fit=crop'),
                ('Tropical Paradise', 'Mango, pineapple, coconut milk', 5.99, 'Smoothies', 'https://images.unsplash.com/photo-1553530666-ba11a7da3888?w=300&h=300&fit=crop'),
                ('Protein Shake', 'Banana, peanut butter, whey', 6.50, 'Smoothies', 'https://images.unsplash.com/photo-1553530666-ba11a7da3888?w=300&h=300&fit=crop'),
                ('Carrot Ginger Shot', 'Immune boosting wellness shot', 3.50, 'Shots', 'https://images.unsplash.com/photo-1622597467836-f3285f2131b8?w=300&h=300&fit=crop'),
            ],
            26: [  # Sushi Master
                ('Salmon Nigiri 2pc', 'Fresh salmon over rice', 5.99, 'Nigiri', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
                ('California Roll 8pc', 'Crab, avocado, cucumber roll', 8.99, 'Rolls', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
                ('Philadelphia Roll 8pc', 'Salmon, cream cheese roll', 9.99, 'Rolls', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
                ('Miso Soup', 'Traditional Japanese miso soup', 3.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Edamame', 'Steamed soybeans with salt', 3.99, 'Starters', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
                ('Sashimi Set 12pc', 'Assorted fresh fish sashimi', 14.99, 'Sashimi', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
                ('Tempura Shrimp 4pc', 'Lightly battered fried shrimp', 7.50, 'Starters', 'https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=300&h=300&fit=crop'),
            ],
            27: [  # Mona Cafe
                ('Espresso', 'Double shot Italian espresso', 2.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
                ('Cappuccino', 'Espresso with steamed milk foam', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Latte Art', 'Creamy latte with artistic foam', 4.00, 'Hot Drinks', 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=300&h=300&fit=crop'),
                ('Croissant Butter', 'Flaky French butter croissant', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Eggs Benedict', 'Poached eggs with hollandaise on muffin', 8.99, 'Breakfast', 'https://images.unsplash.com/photo-1608039829572-9b0189d2e7ae?w=300&h=300&fit=crop'),
                ('Avocado Toast', 'Smashed avocado on sourdough', 7.50, 'Breakfast', 'https://images.unsplash.com/photo-1541519227354-08fa5d50c44d?w=300&h=300&fit=crop'),
                ('Iced Mocha', 'Cold coffee with chocolate and cream', 4.50, 'Cold Drinks', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
                ('Pancake Stack', 'Fluffy pancakes with maple syrup and berries', 6.99, 'Breakfast', 'https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=300&h=300&fit=crop'),
                ('Cheesecake Slice', 'New York style cheesecake', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Fresh Orange Juice', 'Freshly squeezed orange juice', 3.50, 'Cold Drinks', 'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=300&h=300&fit=crop'),
            ],
            28: [  # Art Coffee
                ('Pour Over Coffee', 'Hand-poured single origin coffee', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=300&h=300&fit=crop'),
                ('Flat White', 'Velvety microfoam with espresso', 3.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Matcha Latte', 'Japanese matcha with steamed milk', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1515823064-d6e0c04616a7?w=300&h=300&fit=crop'),
                ('Almond Croissant', 'Croissant filled with almond cream', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Acai Bowl', 'Acai blended with granola and fruits', 8.50, 'Breakfast', 'https://images.unsplash.com/photo-1590301157890-4810ed352733?w=300&h=300&fit=crop'),
                ('Chai Latte', 'Spiced tea with steamed milk', 3.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1557006021-b85faa2bc5e2?w=300&h=300&fit=crop'),
                ('Cold Brew', 'Slow-steeped cold coffee', 3.99, 'Cold Drinks', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
                ('Banana Bread', 'Homemade banana bread slice', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Granola Parfait', 'Yogurt with granola and honey', 5.50, 'Breakfast', 'https://images.unsplash.com/photo-1541519227354-08fa5d50c44d?w=300&h=300&fit=crop'),
                ('Tiramisu', 'Classic Italian tiramisu', 5.50, 'Desserts', 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=300&h=300&fit=crop'),
            ],
            29: [  # Smilecafe
                ('Hot Chocolate', 'Rich cocoa with marshmallows', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1542990253-0d0f5be5f0ed?w=300&h=300&fit=crop'),
                ('Fruit Smoothie', 'Mixed berry and banana smoothie', 4.50, 'Cold Drinks', 'https://images.unsplash.com/photo-1505252585461-04db1eb84625?w=300&h=300&fit=crop'),
                ('Chocolate Muffin', 'Double chocolate muffin', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1607958996333-41aef7caefaa?w=300&h=300&fit=crop'),
                ('Club Sandwich', 'Triple decker with chicken and bacon', 7.99, 'Sandwiches', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Caesar Wrap', 'Grilled chicken caesar in a wrap', 6.50, 'Sandwiches', 'https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=300&h=300&fit=crop'),
                ('Brownie', 'Fudgy chocolate brownie', 3.50, 'Desserts', 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=300&h=300&fit=crop'),
                ('Americano', 'Long black coffee', 2.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
                ('Iced Latte', 'Cold latte over ice', 3.99, 'Cold Drinks', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
            ],
            30: [  # Coffee-Mol
                ('Moldovan Coffee', 'Locally roasted Moldovan beans', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=300&h=300&fit=crop'),
                ('Turkish Coffee', 'Traditional Turkish style coffee', 2.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefda?w=300&h=300&fit=crop'),
                ('Viennese Coffee', 'Coffee with whipped cream', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Chocolate Eclair', 'Choux pastry with chocolate cream', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Cheese Danish', 'Flaky danish with cheese filling', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Ham & Cheese Toast', 'Grilled ham and cheese on toast', 4.50, 'Sandwiches', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Lemonade', 'Fresh squeezed lemonade', 3.00, 'Cold Drinks', 'https://images.unsplash.com/photo-1621263764928-df1444c5e859?w=300&h=300&fit=crop'),
                ('Apple Strudel', 'Traditional apple strudel', 4.50, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
            ],
            31: [  # Pani Pitca (cafe version)
                ('Placinta cu Branza', 'Traditional cheese pitca', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Placinta cu Carne', 'Meat-filled pitca', 4.99, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Placinta cu Dovleac', 'Pumpkin-filled sweet pitca', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Tea with Honey', 'Herbal tea with local honey', 2.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300&h=300&fit=crop'),
                ('Coffee Latte', 'Latte with Moldovan coffee', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Kompot', 'Traditional fruit kompot', 2.00, 'Cold Drinks', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?w=300&h=300&fit=crop'),
            ],
            32: [  # Forno Rosso (restaurant version)
                ('Margherita DOC', 'San Marzano, buffalo mozzarella, basil', 11.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
                ('Diavola Pizza', 'Spicy salami, mozzarella, chili', 13.50, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=300&h=300&fit=crop'),
                ('Pasta Truffle', 'Tagliatelle with black truffle cream', 16.99, 'Pasta', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Burrata Caprese', 'Fresh burrata with heirloom tomatoes', 12.50, 'Starters', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Osso Buco', 'Braised veal shank with risotto', 19.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Tiramisu Classico', 'Mascarpone tiramisu', 6.50, 'Desserts', 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=300&h=300&fit=crop'),
                ('Bruschetta Trio', 'Three artisan bruschetta', 7.99, 'Starters', 'https://images.unsplash.com/photo-1572695157366-5e585ab2b69f?w=300&h=300&fit=crop'),
                ('Chianti Wine Glass', 'Italian red wine by the glass', 5.99, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Panna Cotta', 'Vanilla bean panna cotta with berries', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
                ('Seafood Risotto', 'Arborio rice with mixed seafood', 15.50, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
            ],
            33: [  # Galantom (cafe version)
                ('Espresso Martini', 'Coffee cocktail with vodka', 7.50, 'Drinks', 'https://images.unsplash.com/photo-1551538827-9c037cb4f32a?w=300&h=300&fit=crop'),
                ('Wine by Glass', 'Local Moldovan wine selection', 4.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Cheese Board', 'Artisan cheese and crackers', 12.99, 'Starters', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
                ('Creme Brulee', 'Vanilla custard with caramelized top', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1470124182917-cc6e71b22ecc?w=300&h=300&fit=crop'),
                ('Live Music Night Special', 'Charcuterie + 2 wines combo', 18.99, 'Combos', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=300&h=300&fit=crop'),
                ('Coffee Liqueur', 'Moldovan coffee liqueur shot', 3.50, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
                ('Dark Chocolate Fondant', 'Warm chocolate cake with ice cream', 7.99, 'Desserts', 'https://images.unsplash.com/photo-1424847651672-bf20a4b0982b?w=300&h=300&fit=crop'),
            ],
            34: [  # Mono
                ('Tasting Menu 5-Course', 'Chef selection seasonal dishes', 35.00, 'Main Course', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=300&h=300&fit=crop'),
                ('Wagyu Tartare', 'Hand-cut wagyu with quail egg', 22.50, 'Starters', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Deconstructed Salad', 'Artistic vegetable composition', 12.99, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Sous Vide Salmon', '48-hour cooked salmon with citrus', 24.99, 'Main Course', 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=300&h=300&fit=crop'),
                ('Molecular Dessert', 'Sphere dessert with surprise center', 9.99, 'Desserts', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Craft Cocktail', 'Bartender special creation', 8.50, 'Drinks', 'https://images.unsplash.com/photo-1551538827-9c037cb4f32a?w=300&h=300&fit=crop'),
                ('Artisan Bread Basket', 'Selection of house-baked breads', 5.99, 'Starters', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Truffle Oil Pasta', 'Fresh pasta with truffle oil', 18.50, 'Pasta', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
            ],
            35: [  # La Scufita (restaurant version)
                ('Tochitura Moldoveneasca', 'Traditional pork stew with mamaliga', 9.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Zeama de Pui', 'Traditional chicken soup with noodles', 5.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Placinta cu Branza', 'Homemade cheese placinta', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Racituri', 'Pork aspic with garlic', 7.50, 'Starters', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Friptura de Porc', 'Grilled pork chop with vegetables', 11.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Salata de Vinete', 'Roasted eggplant salad', 4.99, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Mamaliga cu Rindunica', 'Polenta with sour cream and cheese', 6.50, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Vin Rosu', 'Local red wine glass', 3.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Papanași', 'Fried donuts with jam and sour cream', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
            ],
            36: [  # Crocodile
                ('Crocodile Special Platter', 'Mixed grill for two with sides', 29.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Beef Stroganoff', 'Creamy beef with mushrooms', 12.50, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Fish & Chips', 'Beer-battered fish with fries', 9.99, 'Main Course', 'https://images.unsplash.com/photo-1579208030886-b1f5b734f9ac?w=300&h=300&fit=crop'),
                ('Caesar Salad', 'Romaine, croutons, parmesan dressing', 7.50, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('French Onion Soup', 'Caramelized onion soup with cheese crouton', 6.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('BBQ Ribs', 'Slow-cooked pork ribs with BBQ sauce', 14.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Beer Draft 0.5L', 'Local draft beer', 3.00, 'Drinks', 'https://images.unsplash.com/photo-1535958636474-b021ee887b13?w=300&h=300&fit=crop'),
                ('Chocolate Lava Cake', 'Warm chocolate cake with ice cream', 6.99, 'Desserts', 'https://images.unsplash.com/photo-1424847651672-bf20a4b0982b?w=300&h=300&fit=crop'),
            ],
            37: [  # Supa
                ('Tom Yum', 'Thai spicy shrimp soup', 7.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Minestrone', 'Italian vegetable soup', 5.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Borscht', 'Traditional beet soup', 5.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('French Onion Soup', 'Gratineed onion soup', 6.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Chicken Noodle', 'Homestyle chicken noodle soup', 5.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Lentil Soup', 'Hearty red lentil soup', 4.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Bread Basket', 'Fresh bread for dipping', 2.99, 'Sides', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Croutons', 'Crunchy bread croutons', 1.50, 'Sides', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
            ],
            38: [  # Merenilor
                ('Duck Breast', 'Pan-seared duck with cherry sauce', 18.99, 'Main Course', 'https://images.unsplash.com/photo-1432139555190-58524dae6a55?w=300&h=300&fit=crop'),
                ('Lamb Chops', 'Grilled lamb with rosemary jus', 22.50, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Wild Mushroom Risotto', 'Seasonal forest mushroom risotto', 14.99, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Garden Salad', 'Fresh orchard vegetables', 6.50, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Apple Strudel', 'Orchard-fresh apple strudel', 6.99, 'Desserts', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Wine Pairing Flight', '3 local wines matched to your meal', 12.99, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Cheese Fondue', 'Melted cheese with bread and apples', 14.50, 'Main Course', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
            ],
            39: [  # Vila Codru (restaurant version)
                ('Grilled Sea Bass', 'Mediterranean sea bass with vegetables', 19.99, 'Main Course', 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=300&h=300&fit=crop'),
                ('Beef Wellington', 'Puff pastry wrapped beef tenderloin', 24.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Caesar Salad', 'Classic caesar with anchovy dressing', 8.50, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=300&h=300&fit=crop'),
                ('Lobster Bisque', 'Creamy lobster soup', 10.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Creme Brulee', 'Tahitian vanilla creme brulee', 6.99, 'Desserts', 'https://images.unsplash.com/photo-1470124182917-cc6e71b22ecc?w=300&h=300&fit=crop'),
                ('Vintage Wine', 'Selected vintage Moldovan wine', 8.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Escargot', 'Burgundy snails in garlic butter', 9.99, 'Starters', 'https://images.unsplash.com/photo-1572695157366-5e585ab2b69f?w=300&h=300&fit=crop'),
                ('Filet Mignon', 'Premium beef filet with truffle sauce', 28.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
            ],
            40: [  # Restaurant Nobil
                ('Nobil Tasting Menu', '7-course chef degustation', 45.00, 'Main Course', 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=300&h=300&fit=crop'),
                ('Foie Gras Torchon', 'Sauternes-poached foie gras', 24.99, 'Starters', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Black Truffle Risotto', 'Alba truffle with carnaroli rice', 28.50, 'Main Course', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Caviar Service', 'Osetra caviar with blinis', 35.00, 'Starters', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Champagne Glass', 'French champagne by the glass', 12.00, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
                ('Wagyu A5 Steak', 'Japanese wagyu with gold leaf', 59.99, 'Steaks', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Petit Fours', 'Assorted miniature desserts', 8.50, 'Desserts', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
            ],
            41: [  # Doner Kebab
                ('Chicken Doner', 'Chicken doner in pita bread', 4.50, 'Doner', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Beef Doner', 'Spiced beef doner wrap', 5.50, 'Doner', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Mixed Doner Plate', 'Chicken and beef doner with rice', 8.99, 'Main Course', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Lamb Kofta', 'Spiced lamb kofta kebab', 6.50, 'Kebabs', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Falafel Plate', 'Crispy falafel with tahini sauce', 5.99, 'Main Course', 'https://images.unsplash.com/photo-1593001874117-c99c800e3eb7?w=300&h=300&fit=crop'),
                ('Turkish Tea', 'Traditional black tea in glass', 1.99, 'Drinks', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300&h=300&fit=crop'),
                ('Ayran', 'Cold yogurt drink', 1.99, 'Drinks', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?w=300&h=300&fit=crop'),
                ('Baklava', 'Sweet phyllo pastry with pistachio', 3.50, 'Desserts', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
            ],
            42: [  # Strudel Haus (fast_food version)
                ('Apple Strudel', 'Classic Austrian apple strudel', 4.99, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Cherry Strudel', 'Sweet cherry strudel', 4.50, 'Pastries', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Cheese Strudel', 'Cream cheese strudel with raisins', 4.99, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Spinach Strudel', 'Savory spinach and feta strudel', 5.50, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Sausage Roll', 'Puff pastry sausage roll', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Coffee mit Schlag', 'Coffee with whipped cream', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Hot Chocolate', 'Austrian hot chocolate', 3.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1542990253-0d0f5be5f0ed?w=300&h=300&fit=crop'),
            ],
            43: [  # Perfect Pizza
                ('Pepperoni Lovers', 'Double pepperoni with extra cheese', 11.99, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=300&h=300&fit=crop'),
                ('BBQ Chicken Pizza', 'BBQ sauce, chicken, red onion', 12.50, 'Pizza', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=300&h=300&fit=crop'),
                ('Veggie Supreme', 'Bell peppers, mushrooms, olives, onion', 10.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
                ('Meat Feast', 'Pepperoni, sausage, bacon, ham', 13.99, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=300&h=300&fit=crop'),
                ('Garlic Bread', 'Toasted with garlic butter and cheese', 3.99, 'Sides', 'https://images.unsplash.com/photo-1619535860434-ba1d8fa12536?w=300&h=300&fit=crop'),
                ('Chicken Wings 8pc', 'Buffalo or BBQ wings', 6.99, 'Chicken', 'https://images.unsplash.com/photo-1527477396000-e27163b4bbed?w=300&h=300&fit=crop'),
                ('Coca Cola 0.5L', 'Cold soda', 1.99, 'Drinks', 'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=300&h=300&fit=crop'),
                ('Calzone Classico', 'Folded pizza with ham and cheese', 10.50, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
            ],
            44: [  # Pekarnya
                ('Rye Bread', 'Traditional dark rye bread loaf', 1.99, 'Breads', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('White Bread', 'Fresh white bread loaf', 1.50, 'Breads', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Brioche', 'Sweet butter brioche', 2.99, 'Breads', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Honey Cake', 'Medovik layered honey cake', 4.50, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Napoleon Cake', 'Flaky cream napoleon slice', 3.99, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Pirozhki Meat', 'Fried meat pirozhki', 2.50, 'Pastries', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Pirozhki Cabbage', 'Fried cabbage pirozhki', 2.00, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Smetannik', 'Sour cream cake', 3.50, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
            ],
            45: [  # Casuta Cu Bunatati
                ('Sour Cherry Pie', 'Traditional visinata pie', 3.99, 'Pies', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Apple Pie', 'Homemade apple pie slice', 3.50, 'Pies', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Plum Cake', 'Seasonal plum cake', 3.50, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Chocolate Cookie', 'Big chocolate chip cookie', 1.99, 'Cookies', 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=300&h=300&fit=crop'),
                ('Oat Cookie', 'Healthy oat and raisin cookie', 1.50, 'Cookies', 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=300&h=300&fit=crop'),
                ('Cozonac', 'Traditional sweet bread with walnut', 4.50, 'Breads', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Milk', 'Fresh farm milk', 1.50, 'Drinks', 'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=300&h=300&fit=crop'),
            ],
            46: [  # Farmacia Vita
                ('Ibuprofen 400mg', 'Anti-inflammatory pain relief (20 pcs)', 4.50, 'Pain Relief', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Vitamin C 1000mg', 'Immune support effervescent (20 pcs)', 5.50, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Nasal Spray', 'Decongestant nasal spray', 3.99, 'Cold & Flu', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Hand Sanitizer 500ml', 'Antibacterial hand gel', 2.99, 'Personal Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Omega-3 Capsules', 'Fish oil omega-3 (60 pcs)', 8.50, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Plaster Pack', 'Adhesive bandages assorted (30 pcs)', 2.50, 'First Aid', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Baby Diaper Pack', 'Disposable diapers size 3 (30 pcs)', 9.99, 'Baby Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Cough Syrup', 'Dry and wet cough relief 200ml', 4.99, 'Cold & Flu', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
            ],
            47: [  # Help Net Farmacie
                ('Allergy Tablets', 'Cetirizine 10mg (30 pcs)', 5.50, 'Cold & Flu', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Probiotics', 'Gut health probiotics (30 caps)', 7.99, 'Digestive', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Sunscreen SPF50', 'Sun protection cream 100ml', 6.50, 'Skin Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Digital Thermometer', 'Fast-read digital thermometer', 4.99, 'First Aid', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Vitamin D3', 'Vitamin D supplement (60 caps)', 5.99, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Antiseptic Cream', 'Wound healing cream 30g', 3.50, 'First Aid', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Magnesium 400mg', 'Magnesium supplement (60 pcs)', 6.50, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
            ],
            48: [  # Metro Cash & Carry
                ('Rice 5kg', 'Long grain white rice', 4.99, 'Pantry', 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=300&h=300&fit=crop'),
                ('Olive Oil 1L', 'Extra virgin olive oil', 6.99, 'Pantry', 'https://images.unsplash.com/photo-1474979266404-7f28db2e3792?w=300&h=300&fit=crop'),
                ('Chicken Breast 1kg', 'Fresh chicken breast', 5.50, 'Meat', 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=300&h=300&fit=crop'),
                ('Pasta 1kg', 'Italian spaghetti', 1.99, 'Pantry', 'https://images.unsplash.com/photo-1551462147-ff29053bfc14?w=300&h=300&fit=crop'),
                ('Toilet Paper 12pk', 'Soft toilet tissue rolls', 4.50, 'Household', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=300&h=300&fit=crop'),
                ('Milk 1L', 'Fresh whole milk', 1.20, 'Dairy', 'https://images.unsplash.com/photo-1563636619-e9143da7973b?w=300&h=300&fit=crop'),
                ('Eggs 30pk', 'Farm fresh eggs', 3.50, 'Dairy', 'https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=300&h=300&fit=crop'),
                ('Detergent 2L', 'Laundry detergent', 4.99, 'Household', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=300&h=300&fit=crop'),
                ('Bananas 1kg', 'Fresh bananas', 1.50, 'Fruits', 'https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=300&h=300&fit=crop'),
                ('Potatoes 5kg', 'Fresh potatoes', 2.50, 'Vegetables', 'https://images.unsplash.com/photo-1518977676601-b53f82ber635?w=300&h=300&fit=crop'),
            ],
            49: [  # Kaufland Chisinau
                ('Bread Loaf', 'Fresh baked bread', 0.99, 'Bakery', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Yogurt 500g', 'Natural yogurt', 1.50, 'Dairy', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
                ('Mineral Water 2L', 'Sparkling mineral water', 0.80, 'Beverages', 'https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=300&h=300&fit=crop'),
                ('Cheese 300g', 'Local Moldovan cheese', 3.50, 'Dairy', 'https://images.unsplash.com/photo-1452195100486-9cc805987862?w=300&h=300&fit=crop'),
                ('Sausages 500g', 'Pork sausages', 3.99, 'Meat', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Apples 1kg', 'Fresh apples', 1.20, 'Fruits', 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=300&h=300&fit=crop'),
                ('Tomatoes 1kg', 'Fresh tomatoes', 1.50, 'Vegetables', 'https://images.unsplash.com/photo-1518977676601-b53f82ber635?w=300&h=300&fit=crop'),
                ('Chocolate Bar', 'Local chocolate', 1.20, 'Snacks', 'https://images.unsplash.com/photo-1549007994-cb92caebd54b?w=300&h=300&fit=crop'),
                ('Beer 6-pack', 'Local beer cans', 3.50, 'Beverages', 'https://images.unsplash.com/photo-1535958636474-b021ee887b13?w=300&h=300&fit=crop'),
                ('Frozen Pizza', 'Ready to bake frozen pizza', 2.99, 'Frozen', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
            ],
            50: [  # Mona Cafe (v2)
                ('Espresso Double', 'Bold double espresso shot', 2.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
                ('Caramel Latte', 'Espresso with caramel and steamed milk', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Berry Smoothie Bowl', 'Mixed berry smoothie with toppings', 7.99, 'Breakfast', 'https://images.unsplash.com/photo-1590301157890-4810ed352733?w=300&h=300&fit=crop'),
                ('Pain au Chocolat', 'Chocolate-filled French pastry', 2.99, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Mediterranean Toast', 'Tomato, feta, olive oil on sourdough', 6.50, 'Sandwiches', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Affogato', 'Espresso poured over gelato', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
            ],
            51: [  # Art Coffee (v2)
                ('Cold Brew Tonic', 'Cold brew with tonic water', 4.99, 'Cold Drinks', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300&h=300&fit=crop'),
                ('Oat Milk Latte', 'Espresso with oat milk', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Cinnamon Roll', 'Warm cinnamon glazed roll', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Quiche Lorraine', 'French quiche with bacon', 5.99, 'Breakfast', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Hot Apple Cider', 'Spiced warm apple drink', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?w=300&h=300&fit=crop'),
                ('Macaron Box 6pc', 'Assorted French macarons', 5.99, 'Desserts', 'https://images.unsplash.com/photo-1569864358642-9d1684040f43?w=300&h=300&fit=crop'),
            ],
            52: [  # Doner Kebab House
                ('Adana Kebab', 'Spicy minced lamb kebab', 6.99, 'Kebabs', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Iskender Doner', 'Doner over bread with yogurt sauce', 7.99, 'Doner', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Shish Tawook', 'Marinated chicken skewers', 6.50, 'Kebabs', 'https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=300&h=300&fit=crop'),
                ('Pide with Cheese', 'Turkish boat-shaped bread with cheese', 5.50, 'Main Course', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Lentil Soup', 'Red lentil soup with lemon', 3.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Turkish Coffee', 'Traditional fine-ground coffee', 2.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefda?w=300&h=300&fit=crop'),
            ],
            53: [  # La Scufita (v2)
                ('Ciorba de Burta', 'Traditional tripe soup', 5.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Mititei', 'Grilled skinless sausages', 7.50, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Salata Boeuf', 'Romanian beef and potato salad', 5.50, 'Salads', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop'),
                ('Drob de Miel', 'Traditional lamb haggis', 8.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Zacusca', 'Eggplant and pepper spread', 4.50, 'Starters', 'https://images.unsplash.com/photo-1577805947697-89e18249d767?w=300&h=300&fit=crop'),
                ('Tuica', 'Traditional plum brandy shot', 2.50, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
            ],
            54: [  # Supa Restaurant
                ('Pho Bo', 'Vietnamese beef pho', 8.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Cream of Mushroom', 'Velvety mushroom cream soup', 5.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Gazpacho', 'Cold Spanish tomato soup', 4.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Ramen Tonkotsu', 'Japanese pork bone ramen', 9.50, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Lobster Bisque', 'Creamy lobster soup', 11.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Bread Bowl', 'Sourdough bread bowl for soup', 2.50, 'Sides', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
            ],
            55: [  # Pani Pitca (bakery v2)
                ('Placinta cu Cartofi', 'Potato-filled pastry', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1519676867240-f03562e64571?w=300&h=300&fit=crop'),
                ('Placinta cu Visine', 'Sour cherry pastry', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Placinta cu Urda', 'Sweet ricotta pastry', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Cozonac cu Nuca', 'Walnut sweet bread', 4.50, 'Breads', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Pasca', 'Traditional Easter sweet bread', 5.50, 'Breads', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Mucenici', 'Traditional figure-eight pastry', 3.99, 'Pastries', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
            ],
            56: [  # Forno Rosso (v2)
                ('Quattro Stagioni', 'Four seasons pizza', 13.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
                ('Prosciutto e Rucola', 'Parma ham and arugula pizza', 14.50, 'Pizza', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=300&h=300&fit=crop'),
                ('Carbonara Pasta', 'Classic carbonara with guanciale', 12.99, 'Pasta', 'https://images.unsplash.com/photo-1612874742237-6526221588e3?w=300&h=300&fit=crop'),
                ('Gnocchi Sorrentina', 'Potato gnocchi with tomato and mozzarella', 11.50, 'Pasta', 'https://images.unsplash.com/photo-1476124369491-e7addf5db371?w=300&h=300&fit=crop'),
                ('Affogato al Caffe', 'Espresso over vanilla gelato', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
                ('Limoncello', 'Italian lemon liqueur shot', 3.50, 'Drinks', 'https://images.unsplash.com/photo-1553361371-9b22f78e8b1d?w=300&h=300&fit=crop'),
            ],
            57: [  # Farmacia Vita (v2)
                ('Aspirin 500mg', 'Pain relief aspirin (20 pcs)', 2.99, 'Pain Relief', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Vitamin B Complex', 'B-vitamin supplement (60 pcs)', 6.99, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Cough Lozenges', 'Throat soothing lozenges (24 pcs)', 2.50, 'Cold & Flu', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Eye Drops', 'Moisturizing eye drops 10ml', 3.99, 'Personal Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Antacid Tablets', 'Heartburn relief (30 pcs)', 3.50, 'Digestive', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Diabetic Test Strips', 'Blood glucose test strips (50 pcs)', 12.99, 'First Aid', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
            ],
            58: [  # Metro Cash&Carry (v2)
                ('Flour 5kg', 'All-purpose wheat flour', 2.99, 'Pantry', 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=300&h=300&fit=crop'),
                ('Sugar 5kg', 'White granulated sugar', 2.50, 'Pantry', 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=300&h=300&fit=crop'),
                ('Butter 500g', 'Premium butter', 3.50, 'Dairy', 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9e?w=300&h=300&fit=crop'),
                ('Sour Cream 500g', 'Fresh sour cream', 1.50, 'Dairy', 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=300&h=300&fit=crop'),
                ('Pork 1kg', 'Fresh pork meat', 4.99, 'Meat', 'https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=300&h=300&fit=crop'),
                ('Dish Soap 1L', 'Dishwashing liquid', 1.99, 'Household', 'https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=300&h=300&fit=crop'),
            ],
            59: [  # Strudel Haus (bakery v2)
                ('Viennese Apple Strudel', 'Classic Austrian apple strudel', 5.99, 'Pies', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Topfenstrudel', 'Austrian quark cheese strudel', 5.50, 'Pastries', 'https://images.unsplash.com/photo-1555507036-ab1f4038024a?w=300&h=300&fit=crop'),
                ('Kaiserschmarrn', 'Shredded pancake with raisins', 6.50, 'Desserts', 'https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=300&h=300&fit=crop'),
                ('Sachertorte Slice', 'Austrian chocolate cake with apricot', 4.99, 'Cakes', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
                ('Apfelkuchen', 'German apple cake slice', 3.99, 'Cakes', 'https://images.unsplash.com/photo-1562007908-17c67e878c88?w=300&h=300&fit=crop'),
                ('Viennese Coffee', 'Coffee with whipped cream', 3.99, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
            ],
            60: [  # Perfect Pizza (v2)
                ('Margherita DOP', 'San Marzano and buffalo mozzarella', 10.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=300&h=300&fit=crop'),
                ('Truffle Pizza', 'Black truffle cream and mushroom pizza', 16.50, 'Pizza', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=300&h=300&fit=crop'),
                ('Bianca Pizza', 'White pizza with ricotta and garlic', 12.50, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=300&h=300&fit=crop'),
                ('Garlic Knots 6pc', 'Buttery garlic knots', 3.50, 'Sides', 'https://images.unsplash.com/photo-1619535860434-ba1d8fa12536?w=300&h=300&fit=crop'),
                ('Tiramisu', 'Classic Italian tiramisu', 5.50, 'Desserts', 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=300&h=300&fit=crop'),
                ('Italian Soda', 'Blood orange Italian soda', 2.50, 'Drinks', 'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=300&h=300&fit=crop'),
            ],
            61: [  # Vila Codru (v2)
                ('Grilled Octopus', 'Tender grilled octopus with potatoes', 16.99, 'Starters', 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=300&h=300&fit=crop'),
                ('Venison Medallion', 'Deer medallion with berry sauce', 22.99, 'Main Course', 'https://images.unsplash.com/photo-1544025162-d76694265947?w=300&h=300&fit=crop'),
                ('Forest Mushroom Soup', 'Wild mushroom cream soup', 6.99, 'Soups', 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=300&h=300&fit=crop'),
                ('Trout Amandine', 'Pan-fried trout with almonds', 15.50, 'Main Course', 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=300&h=300&fit=crop'),
                ('Wine Pairing', 'Somelier selected wine for your dish', 8.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Pavlova', 'Meringue dessert with fresh berries', 7.50, 'Desserts', 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=300&h=300&fit=crop'),
            ],
            62: [  # Smilecafe (v2)
                ('Lavender Latte', 'Espresso with lavender syrup', 4.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=300&h=300&fit=crop'),
                ('Mango Smoothie', 'Fresh mango and banana smoothie', 4.99, 'Cold Drinks', 'https://images.unsplash.com/photo-1505252585461-04db1eb84625?w=300&h=300&fit=crop'),
                ('Cinnamon Bun', 'Warm glazed cinnamon roll', 3.50, 'Pastries', 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=300&h=300&fit=crop'),
                ('Grilled Cheese', 'Classic grilled cheese sandwich', 5.50, 'Sandwiches', 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=300&h=300&fit=crop'),
                ('Macchiato', 'Espresso with a dollop of foam', 3.50, 'Hot Drinks', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=300&h=300&fit=crop'),
                ('Ice Cream Sundae', 'Vanilla ice cream with toppings', 4.99, 'Desserts', 'https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=300&h=300&fit=crop'),
            ],
            63: [  # Galantom (v2)
                ('Cabernet Sauvignon Glass', 'Premium red wine by the glass', 5.50, 'Drinks', 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=300&h=300&fit=crop'),
                ('Beef Carpaccio', 'Thinly sliced raw beef with truffle oil', 13.99, 'Starters', 'https://images.unsplash.com/photo-1588168333986-5078d3ae3976?w=300&h=300&fit=crop'),
                ('Lobster Thermidor', 'Classic lobster in creamy sauce', 29.99, 'Main Course', 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=300&h=300&fit=crop'),
                ('Crème Catalan', 'Citrus custard with caramelized sugar', 6.99, 'Desserts', 'https://images.unsplash.com/photo-1470124182917-cc6e71b22ecc?w=300&h=300&fit=crop'),
                ('Negroni Cocktail', 'Classic Italian bitter cocktail', 7.50, 'Drinks', 'https://images.unsplash.com/photo-1551538827-9c037cb4f32a?w=300&h=300&fit=crop'),
            ],
            64: [  # Help Net Farmacie (v2)
                ('Melatonin 5mg', 'Sleep aid supplement (30 pcs)', 4.99, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Electrolyte Pack', 'Hydration electrolyte sachets (10 pcs)', 5.50, 'First Aid', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Lip Balm', 'Moisturizing lip balm with SPF', 2.50, 'Skin Care', 'https://images.unsplash.com/photo-1585435557343-3b092031a831?w=300&h=300&fit=crop'),
                ('Iron Supplement', 'Iron 65mg tablets (60 pcs)', 5.99, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
                ('Thermometer Infrared', 'Contactless infrared thermometer', 12.99, 'First Aid', 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&h=300&fit=crop'),
                ('Zinc 50mg', 'Immune support zinc (60 pcs)', 4.50, 'Vitamins', 'https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=300&h=300&fit=crop'),
            ],
        }
        for rid, items in items_data.items():
            # Use the actual restaurant ID from the database, not the hardcoded index
            actual_rid = rest_index_to_id.get(rid, rid)
            for name, desc, price, sub_cat, img in items:
                try:
                    insert("INSERT INTO Items (restaurant_id,name,description,price,sub_category,image_url) VALUES (?,?,?,?,?,?)",
                           (actual_rid, name, desc, price, sub_cat, img))
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

    # Seed delivery zones
    zone_count = query("SELECT COUNT(*) as cnt FROM DeliveryZones", fetch_one=True)
    if zone_count and zone_count['cnt'] == 0:
        zones = [
            ('Chisinau Center', 47.0105, 28.8638, 5.0),
            ('Chisinau Suburbs', 47.0205, 28.8600, 10.0),
            ('Balti', 47.7540, 27.9270, 5.0),
            ('Cahul', 45.9040, 28.1950, 5.0),
            ('Ungheni', 47.2060, 27.7930, 5.0),
            ('Orhei', 47.3830, 28.8230, 5.0),
            ('Soroca', 48.1570, 28.2970, 5.0),
        ]
        for name, lat, lng, radius in zones:
            try:
                insert("INSERT INTO DeliveryZones (name,center_lat,center_lng,radius_km,is_active) VALUES (?,?,?,?,TRUE)",
                       (name, lat, lng, radius))
            except Exception as e:
                print(f"  Seed zone note: {e}")
        print("  Seeded 7 Moldova delivery zones")

    # Update the seed version after successful seeding
    if needs_reseed:
        update_seed_version()
        print("  ✅ Database reseed complete!")
