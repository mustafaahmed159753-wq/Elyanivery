# test_import.py — run this, then delete it
from services.auth import AuthService
print("✅ Import works!")
token = AuthService.make_token(1, "customer")
print(f"✅ Token: {token[:30]}...")
decoded = AuthService.verify_token(token)
print(f"✅ Decoded: {decoded}")
