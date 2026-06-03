"""
Elyanivery — Configuration
SQL Server connection settings.
Supports both local development and Railway (cloud) deployment.
Environment variables take precedence over hardcoded values.
"""

import os


class Config:
    # ── SQL Server Connection ──
    # For LOCAL development (SQL Server 2025 with Windows Authentication):
    #   - DB_SERVER: 'localhost' for default instance
    #   - DB_UID: '' (empty) for Windows Authentication
    #   - DB_PWD: '' (empty) for Windows Authentication
    #
    # For RAILWAY / CLOUD deployment:
    #   - Set environment variables: DB_SERVER, DB_DATABASE, DB_UID, DB_PWD, DB_DRIVER
    #   - Railway will auto-provide DATABASE_URL if you add a SQL Server addon
    #
    # Environment variables OVERRIDE the defaults below.

    DB_SERVER = os.environ.get('DB_SERVER', 'localhost')
    DB_DATABASE = os.environ.get('DB_DATABASE', 'Elyanivery')
    DB_UID = os.environ.get('DB_UID', '')           # Empty = Windows Auth (local)
    DB_PWD = os.environ.get('DB_PWD', '')           # Empty = Windows Auth (local)
    DB_DRIVER = os.environ.get('DB_DRIVER', '{ODBC Driver 18 for SQL Server}')  # Driver 18 is what Dockerfile installs
    DB_TRUST_CERT = os.environ.get('DB_TRUST_CERT', 'yes')
    DB_ENCRYPT = os.environ.get('DB_ENCRYPT', 'no')
    DB_TIMEOUT = int(os.environ.get('DB_TIMEOUT', '10'))

    # ── Server Settings ──
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', '8080'))       # Railway sets PORT automatically

    # ── JWT Settings ──
    JWT_SECRET = os.environ.get('JWT_SECRET', 'elyanivery-secret-key-change-in-production-2024')
    JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', '72'))

    @classmethod
    def conn_string(cls, database=None):
        """Build connection string for the app database."""
        db = database or cls.DB_DATABASE
        timeout_str = f"Connection Timeout={cls.DB_TIMEOUT};"
        if cls.DB_UID:
            # SQL Server Authentication (used on Railway/cloud)
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
            # Windows Authentication (used locally)
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
