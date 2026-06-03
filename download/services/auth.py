"""
Elyanivery — Authentication Service
Password hashing and JWT token management.
"""

import hashlib
import hmac
import time
import json
import base64
from config import Config


class AuthService:
    """Handles password hashing/verification and JWT token creation/verification."""

    @staticmethod
    def hash_pw(password: str) -> str:
        """Hash a password using SHA-256 with a random salt."""
        import os
        salt = os.urandom(32).hex()
        pw_hash = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
        return f"{salt}:{pw_hash}"

    @staticmethod
    def verify_pw(password: str, stored_hash: str) -> bool:
        """Verify a password against the stored hash."""
        try:
            if not stored_hash or ':' not in stored_hash:
                return False
            salt, pw_hash = stored_hash.split(':', 1)
            check_hash = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
            return hmac.compare_digest(check_hash, pw_hash)
        except Exception:
            return False

    @staticmethod
    def make_token(user_id: int, role: str) -> str:
        """Create a simple JWT-like token."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).decode().rstrip('=')

        payload = base64.urlsafe_b64encode(
            json.dumps({
                "uid": user_id,
                "role": role,
                "exp": int(time.time()) + Config.JWT_EXPIRY_HOURS * 3600
            }).encode()
        ).decode().rstrip('=')

        signature = base64.urlsafe_b64encode(
            hmac.new(
                Config.JWT_SECRET.encode(),
                f"{header}.{payload}".encode(),
                hashlib.sha256
            ).digest()
        ).decode().rstrip('=')

        return f"{header}.{payload}.{signature}"

    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify a JWT-like token and return the payload dict.
        Returns {'uid': int, 'role': str} on success, None on failure.
        """
        try:
            if not token or '.' not in token:
                return None

            parts = token.split('.')
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature_b64 = parts

            # Verify signature
            expected_sig = base64.urlsafe_b64encode(
                hmac.new(
                    Config.JWT_SECRET.encode(),
                    f"{header_b64}.{payload_b64}".encode(),
                    hashlib.sha256
                ).digest()
            ).decode().rstrip('=')

            if not hmac.compare_digest(signature_b64, expected_sig):
                return None

            # Decode payload
            # Add padding back
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding

            payload = json.loads(
                base64.urlsafe_b64decode(payload_b64)
            )

            # Check expiration
            if payload.get('exp', 0) < int(time.time()):
                return None

            return {
                'uid': payload['uid'],
                'role': payload['role']
            }
        except Exception:
            return None
