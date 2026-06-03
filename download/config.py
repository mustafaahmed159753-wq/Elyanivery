"""
Elyanivery — Configuration
SQL Server connection settings.
Edit the values below to match your SQL Server setup.
"""

class Config:
    # ── SQL Server Connection ──
    # Change these to match your SQL Server instance
    DB_SERVER = r'localhost\SQLEXPRESS'   # e.g. 'localhost', r'localhost\SQLEXPRESS', '192.168.1.100'
    DB_DATABASE = 'Elyanivery'            # Database name
    DB_UID = 'sa'                         # SQL Server username (leave '' for Windows Auth)
    DB_PWD = 'your_password'              # SQL Server password (leave '' for Windows Auth)
    DB_DRIVER = '{ODBC Driver 17 for SQL Server}'  # ODBC driver name
    DB_TRUST_CERT = 'yes'                 # Trust server certificate
    DB_ENCRYPT = 'no'                     # Encrypt connection

    # ── Server Settings ──
    HOST = '0.0.0.0'                      # Listen on all interfaces
    PORT = 8080                            # HTTP port

    # ── JWT Settings ──
    JWT_SECRET = 'elyanivery-secret-key-change-in-production-2024'
    JWT_EXPIRY_HOURS = 72

    @classmethod
    def conn_string(cls):
        """Build connection string for the app database."""
        if cls.DB_UID:
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={cls.DB_DATABASE};"
                f"UID={cls.DB_UID};"
                f"PWD={cls.DB_PWD};"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
            )
        else:
            # Windows Authentication
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={cls.DB_DATABASE};"
                f"Trusted_Connection=yes;"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
            )

    @classmethod
    def master_conn_string(cls):
        """Connection string to the master database (for creating the app DB if needed)."""
        if cls.DB_UID:
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE=master;"
                f"UID={cls.DB_UID};"
                f"PWD={cls.DB_PWD};"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
            )
        else:
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE=master;"
                f"Trusted_Connection=yes;"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
            )
