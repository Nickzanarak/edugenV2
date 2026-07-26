import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "EduGen API"
    VERSION: str = "3.8.5"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FRONTEND_ORIGINS: str = os.getenv("FRONTEND_ORIGINS", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./service-account.json")
    ALLOW_DEMO_AUTH: bool = os.getenv("ALLOW_DEMO_AUTH", "false").lower() in ("1", "true", "yes")

    NEAR_DUP_THRESHOLD: float = 0.78
    CTX_CHAR_LIMIT: int = 15000
    EXCLUDE_LIST_LIMIT: int = 30

settings = Settings()

if not settings.OPENAI_API_KEY:
    raise RuntimeError("ไม่มี Key ของ Openai กรุณาตรวจที่ไฟล์ .env")
