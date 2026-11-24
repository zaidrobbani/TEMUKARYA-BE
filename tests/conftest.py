import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-yang-panjangnya-minimal-32-karakter")
# Test tidak boleh mengirim push FCM sungguhan walau .env berisi kredensial Firebase.
os.environ["FIREBASE_CREDENTIALS_FILE"] = ""
