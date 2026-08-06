from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import HTTPException, Request, Security
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.db.firebase import fb_auth, save_user_profile

security = HTTPBearer(auto_error=False)


def _verify_bearer_token(token: str) -> str:
    if not token:
        raise HTTPException(401, "Empty auth token")
    if fb_auth is None:
        raise HTTPException(500, "Firebase auth not configured on server")
    try:
        decoded = fb_auth.verify_id_token(token)
        uid = (decoded.get("uid") or "").strip()
        if not uid:
            raise HTTPException(401, "Invalid auth token (no uid)")

        # บันทึกอีเมล/ชื่อลงเอกสารผู้ใช้ เพื่อให้ดูใน Firestore ได้ว่า UID นี้คือใคร
        # (ไม่ให้ล้มถ้าบันทึกไม่สำเร็จ เพราะ auth สำคัญกว่า)
        save_user_profile(
            uid,
            email=(decoded.get("email") or "").strip(),
            name=(decoded.get("name") or "").strip(),
        )
        return uid
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid or expired auth token")


def get_current_user(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Verify Firebase Bearer token, or fall back to X-User-Id when ALLOW_DEMO_AUTH=true."""
    if cred and cred.credentials:
        return _verify_bearer_token(cred.credentials)

    if settings.ALLOW_DEMO_AUTH:
        demo_uid = (request.headers.get("X-User-Id") or "demo-user").strip()
        if demo_uid:
            return demo_uid

    raise HTTPException(401, "Missing or invalid authentication")