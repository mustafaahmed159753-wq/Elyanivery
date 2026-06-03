---
Task ID: 1
Agent: Main Agent
Task: Fix SQL Server connection for Elyanivery server (SQL Server 2025 + Windows Authentication)

Work Log:
- Diagnosed root cause: config.py was using `localhost\SQLEXPRESS` instance and SQL Authentication (`sa`/`your_password`)
- SQL Server 2025 default instance is just `localhost`, not `SQLEXPRESS`
- User confirmed Windows Authentication (no username/password)
- Updated config.py: DB_SERVER='localhost', DB_UID='', DB_PWD='' for Windows Auth
- Updated config.py: Added DB_TIMEOUT=10, simplified conn_string() method with database parameter
- Updated db.py: Added _detect_sql_server() auto-detection that tries 8 common server configs
- Updated db.py: Auto-selects best ODBC driver from available ones
- Fixed server.py startup: Removed early DB connection test that blocked auto-detection
- init_db() now runs auto-detection FIRST, then creates database and tables
- Created static/uploads directory for avatar storage

Stage Summary:
- Key fix: DB connection was failing because of wrong instance name and auth method
- Auto-detection will try: localhost, localhost\SQLEXPRESS, ., .\SQLEXPRESS, (local), etc.
- Server version bumped to v2.1
- Login and registration handlers verified correct - the issue was purely DB connectivity
- Files modified: config.py, db.py, server.py
