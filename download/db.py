"""
Elyanivery — Database Module
SQL Server helpers using pyodbc with thread-local connections.
Includes auto-detection of SQL Server instance on startup.
"""

import pyodbc
import re
import threading
from config import Config

# Thread-local storage for DB connections
_local = threading.local()

# Track the working server name once discovered
_working_server = None


def _build_conn_str(server, database, uid='', pwd='', driver=None, timeout=10):
    """Build a connection string with the given parameters."""
    drv = driver or Config.DB_DRIVER
    if uid:
        return (
            f"DRIVER={drv};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={uid};"
            f"PWD={pwd};"
            f"TrustServerCertificate=yes;"
            f"Encrypt=no;"
            f"Connection Timeout={timeout};"
        )
    else:
        return (
            f"DRIVER={drv};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
            f"Encrypt=no;"
            f"Connection Timeout={timeout};"
        )


def _detect_sql_server():
    """
    Auto-detect the SQL Server instance by trying common configurations.
    Returns the working server string, or None if nothing works.
    """
    global _working_server

    # If we already found it, use it
    if _working_server:
        return _working_server

    # Get available drivers
    available_drivers = [d for d in pyodbc.drivers() if 'sql server' in d.lower()]
    print(f"  Available ODBC drivers: {available_drivers}")

    # Pick the best available driver
    driver = None
    for preferred in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server',
                      'SQL Server Native Client 11.0', 'SQL Server']:
        if preferred in available_drivers:
            driver = f'{{{preferred}}}'
            break
    if not driver and available_drivers:
        driver = f'{{{available_drivers[0]}}}'

    if not driver:
        print("  ERROR: No SQL Server ODBC driver found!")
        return None

    print(f"  Using driver: {driver}")

    # Common server name patterns to try
    server_attempts = [
        'localhost',                    # Default instance
        r'localhost\SQLEXPRESS',        # SQL Express named instance
        r'localhost\MSSQLSERVER',       # Named instance variant
        '.',                            # Dot = default instance (local)
        r'.\SQLEXPRESS',                # Dot with Express
        '(local)',                      # (local) = default instance
        r'(local)\SQLEXPRESS',          # (local) with Express
        '127.0.0.1',                    # IP default instance
    ]

    uid = Config.DB_UID
    pwd = Config.DB_PWD

    for server in server_attempts:
        try:
            conn_str = _build_conn_str(server, 'master', uid, pwd, driver, timeout=5)
            conn = pyodbc.connect(conn_str, autocommit=True)
            conn.close()
            print(f"  SUCCESS: Connected to SQL Server at '{server}'")
            _working_server = server
            # Update Config so all future connections use the working server
            Config.DB_SERVER = server
            Config.DB_DRIVER = driver
            return server
        except Exception as e:
            err_str = str(e)
            # Shorten error for display
            short_err = err_str[:80] + '...' if len(err_str) > 80 else err_str
            print(f"  Tried '{server}' ... failed ({short_err})")

    print("  WARNING: Could not auto-detect SQL Server instance!")
    print("  Please check that SQL Server is running and edit config.py manually.")
    return None


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
    Uses OUTPUT INSERTED.id clause for reliable identity retrieval.
    
    NOTE: With autocommit=True, each cursor.execute() is a separate SQL batch.
    SCOPE_IDENTITY() returns NULL in a new batch because the INSERT scope is gone.
    The OUTPUT clause returns the identity value directly from the INSERT statement,
    so it works reliably regardless of autocommit settings.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        
        # Check if the SQL already contains OUTPUT clause (caller managed identity)
        if 'OUTPUT' in sql.upper() and 'INSERTED' in sql.upper():
            cursor.execute(sql, params)
            if cursor.description is not None:
                row = cursor.fetchone()
                if row and row[0] is not None:
                    return int(row[0])
            return None
        
        # Transform: INSERT INTO Table (cols) VALUES (...) 
        #      → INSERT INTO Table (cols) OUTPUT INSERTED.id VALUES (...)
        # This lets SQL Server return the new identity in the same statement
        transformed = re.sub(
            r'(INSERT\s+INTO\s+\w+\s*\([^)]+\))\s*(VALUES)',
            r'\1 OUTPUT INSERTED.id \2',
            sql,
            flags=re.IGNORECASE
        )
        
        cursor.execute(transformed, params)
        
        # The OUTPUT clause produces a result set with the inserted id
        if cursor.description is not None:
            row = cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
        
        # Fallback: try @@IDENTITY (session-scoped, works with autocommit)
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        
        return None
    except Exception as e:
        # If the OUTPUT clause fails (e.g. complex SQL), fall back to @@IDENTITY
        try:
            cursor2 = conn.cursor()
            cursor2.execute("SELECT @@IDENTITY")
            row = cursor2.fetchone()
            if row and row[0] is not None:
                return int(row[0])
        except:
            pass
        
        # Try to reconnect once on connection error
        if '08S01' in str(e) or 'HY000' in str(e) or 'closed' in str(e).lower():
            try:
                close_conn()
                conn = _get_conn()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                cursor.execute("SELECT @@IDENTITY")
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

    # ── Auto-detect SQL Server instance ──
    print("  Detecting SQL Server instance...")
    detected = _detect_sql_server()
    if not detected:
        print("  Proceeding with configured server: " + Config.DB_SERVER)

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
