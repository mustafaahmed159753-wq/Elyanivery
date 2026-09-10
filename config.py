"""
Elyanivery — Configuration
PostgreSQL connection settings.
Supports both local development and Railway (cloud) deployment.

Railway provides DATABASE_URL automatically when you add a PostgreSQL service.
For local dev, set individual DB_* environment variables or install PostgreSQL locally.
"""

import os


class Config:
    # ── PostgreSQL Connection ──
    # Railway provides DATABASE_URL automatically when you add a PostgreSQL service
    # Format: postgresql://user:password@host:port/database
    DATABASE_URL = os.environ.get('DATABASE_URL', '')

    # Individual connection params (used if DATABASE_URL is not set)
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'elyanivery')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')

    # ── Server Settings ──
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', '8080'))       # Railway/Render sets PORT automatically

    # ── JWT Settings ──
    JWT_SECRET = os.environ.get('JWT_SECRET', 'elyanivery-secret-key-change-in-production-2024')
    JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', '72'))

    # ── Google Maps API ──
    GOOGLE_MAPS_API_KEY = os.environ.get('NEXT_PUBLIC_GOOGLE_MAPS_API_KEY', os.environ.get('GOOGLE_MAPS_API_KEY', ''))

    # ── Gmail & SMTP Settings for OTP ──
    GMAIL_USER = os.environ.get('GMAIL_USER', os.environ.get('SMTP_USER', os.environ.get('EMAIL_USER', '')))
    GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', os.environ.get('SMTP_PASS', os.environ.get('GMAIL_PASSWORD', '')))
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))

    @classmethod
    def get_dsn(cls):
        """Get PostgreSQL connection DSN string.
        Uses DATABASE_URL if available (Railway), otherwise builds from individual params."""
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        return (
            f"host={cls.DB_HOST} "
            f"port={cls.DB_PORT} "
            f"dbname={cls.DB_NAME} "
            f"user={cls.DB_USER} "
            f"password={cls.DB_PASSWORD}"
        )
