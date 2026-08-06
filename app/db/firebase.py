try:
    import firebase_admin
    from firebase_admin import credentials, auth as fb_auth
    from google.cloud import firestore
except ImportError:
    firebase_admin = None
    fb_auth = None
    firestore = None

_db = None

def init_firebase(project_id: str, cred_path: str = "./service-account.json"):
    global _db
    if firebase_admin is not None and firestore is not None:
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(
                    cred,
                    {"projectId": project_id} if project_id else None,
                )
            _db = firestore.Client(project=project_id) if project_id else firestore.Client()
            print("Firebase Admin / Firestore initialized")
        except Exception as e:
            print(f"Firebase init failed: {e}")
            _db = None
    else:
        print("Firebase Admin / Firestore not available (libraries not installed?)")

def get_firestore_db():
    return _db

def log_user_event(user_id: str, collection: str, data: dict) -> None:
    db = get_firestore_db()
    if db is None or firestore is None:
        return
    try:
        db.collection("users").document(user_id).collection(collection).add(
            {
                **data,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
    except Exception as e:
        print(f"[history-log error] {e}")


# เก็บ uid ที่บันทึก profile ไปแล้วในรอบนี้ กันเขียนซ้ำทุก request
_profile_cache: set = set()


def save_user_profile(user_id: str, email: str = "", name: str = "") -> None:
    """บันทึกอีเมล/ชื่อลงเอกสารผู้ใช้ เพื่อให้ดูใน Firestore Console ได้ว่า UID นี้คือใคร
    เขียนครั้งเดียวต่อการรันเซิร์ฟเวอร์ 1 รอบ (ไม่เขียนซ้ำทุก request)
    """
    if not user_id or user_id in _profile_cache:
        return
    db = get_firestore_db()
    if db is None or firestore is None:
        return
    try:
        payload = {"lastSeenAt": firestore.SERVER_TIMESTAMP}
        if email:
            payload["email"] = email
        if name:
            payload["displayName"] = name
        db.collection("users").document(user_id).set(payload, merge=True)
        _profile_cache.add(user_id)
    except Exception as e:
        print(f"[user-profile error] {e}")