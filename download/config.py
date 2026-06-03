"""
Elyanivery — Configuration
SQL Server connection settings.
Edit the values below to match your SQL Server setup.
"""

class Config:
    # ── SQL Server Connection ──
    # For SQL Server 2025 with Windows Authentication:
    #   - DB_SERVER: 'localhost' for default instance, or r'localhost\INSTANCE_NAME' for named instances
    #   - DB_UID: '' (empty) for Windows Authentication
    #   - DB_PWD: '' (empty) for Windows Authentication
    #
    # For SQL Server Authentication:
    #   - DB_UID: your SQL username (e.g. 'sa')
    #   - DB_PWD: your SQL password
    #
    # The server will AUTO-DETECT the correct instance name on startup
    # if the default connection fails. You can also set it manually below.

    DB_SERVER = 'localhost'                  # Default instance (most common for SQL Server 2025)
    DB_DATABASE = 'Elyanivery'               # Database name
    DB_UID = ''                              # Empty = Windows Authentication
    DB_PWD = ''                              # Empty = Windows Authentication
    DB_DRIVER = '{ODBC Driver 17 for SQL Server}'  # ODBC driver name
    DB_TRUST_CERT = 'yes'                    # Trust server certificate
    DB_ENCRYPT = 'no'                        # Encrypt connection
    DB_TIMEOUT = 10                          # Connection timeout in seconds

    # ── Server Settings ──
    HOST = '0.0.0.0'                         # Listen on all interfaces
    PORT = 8080                              # HTTP port

    # ── JWT Settings ──
    JWT_SECRET = 'elyanivery-secret-key-change-in-production-2024'
    JWT_EXPIRY_HOURS = 72

    @classmethod
    def conn_string(cls, database=None):
        """Build connection string for the app database."""
        db = database or cls.DB_DATABASE
        timeout_str = f"Connection Timeout={cls.DB_TIMEOUT};"
        if cls.DB_UID:
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={db};"
                f"UID={cls.DB_UID};"
                f"PWD={cls.DB_PWD};"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
                f"{timeout_str}"
            )
        else:
            # Windows Authentication
            return (
                f"DRIVER={cls.DB_DRIVER};"
                f"SERVER={cls.DB_SERVER};"
                f"DATABASE={db};"
                f"Trusted_Connection=yes;"
                f"TrustServerCertificate={cls.DB_TRUST_CERT};"
                f"Encrypt={cls.DB_ENCRYPT};"
                f"{timeout_str}"
            )

    @classmethod
    def master_conn_string(cls):
        """Connection string to the master database (for creating the app DB if needed)."""
        return cls.conn_string(database='master')
