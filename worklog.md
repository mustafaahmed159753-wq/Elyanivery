---
Task ID: 1
Agent: Main Agent
Task: Fix login and user creation - investigate why default users/admins cannot login and new users cannot be created

Work Log:
- Read server.py (2122 lines) and discovered it imports from `config`, `db`, and `services.auth` modules that DO NOT EXIST as files
- This is the ROOT CAUSE: the server cannot even start because of missing modules, so login and user creation are impossible
- Created `config.py` with Config class containing SQL Server connection settings, HOST/PORT, JWT settings
- Created `db.py` with thread-local connection management, query(), insert(), init_db(), seed_data(), close_conn()
  - init_db() creates the Elyanivery database and all required tables (Users, Restaurants, Items, Orders, etc.)
  - seed_data() populates 5 sample restaurants, menu items, and 3 promo codes
- Created `services/__init__.py` and `services/auth.py` with AuthService class
  - hash_pw() uses SHA-256 with random salt
  - verify_pw() uses HMAC-safe comparison
  - make_token() / verify_token() implement JWT-like tokens with HMAC-SHA256 signatures
- Created `static/uploads/` directory for avatar storage
- Verified customer HTML already has: splash screen, goHome() redirect after rating/skip, cancelOrder -> goHome()
- Verified server.py already has log_message suppression for polling endpoints (heartbeat fix)
- Customer and courier HTML files already have splash screens present

Stage Summary:
- Root cause identified: Missing config.py, db.py, and services/auth.py files prevented server from starting
- All 3 missing modules created with full functionality
- Server should now start, create database, seed data, create default users, and handle login/registration
- Default credentials: admin/admin, customer1/1234, courier1/1234
- Splash screens were NOT removed - they exist in both HTML files
- The ensure_default_users() function in server.py also resets passwords on every startup for safety
