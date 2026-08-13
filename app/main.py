from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.firebase import init_firebase
from app.api.routes import health, pdf, summary, quiz, qa, notes, bank, export, history

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

if settings.FRONTEND_ORIGINS:
    allow_origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
else:
    allow_origins = ["http://127.0.0.1:3000"]

allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

init_firebase(settings.FIREBASE_PROJECT_ID, settings.GOOGLE_APPLICATION_CREDENTIALS)

# เตือนเมื่อเปิดโหมด demo — โหมดนี้ยอมให้ระบุตัวตนผ่าน header X-User-Id โดยไม่ตรวจสอบ
# เหมาะกับการพัฒนาเท่านั้น ห้ามเปิดบนเครื่องที่เข้าถึงได้จากภายนอก
if settings.ALLOW_DEMO_AUTH:
    print("=" * 70)
    print("[คำเตือน] ALLOW_DEMO_AUTH=true : ใครก็ตามที่ส่ง header X-User-Id")
    print("          จะเข้าถึงข้อมูลของผู้ใช้รายนั้นได้โดยไม่ต้องยืนยันตัวตน")
    print("          ก่อนนำขึ้นใช้งานจริง ให้ตั้ง ALLOW_DEMO_AUTH=false ใน .env")
    print("=" * 70)

app.include_router(health.router)
app.include_router(pdf.router, prefix="/pdf", tags=["pdf"])
app.include_router(summary.router, prefix="/summarize", tags=["summary"])
app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
app.include_router(qa.router, prefix="/qa", tags=["qa"])
app.include_router(notes.router, prefix="/notes", tags=["notes"])
app.include_router(bank.router, prefix="/bank", tags=["bank"])
app.include_router(export.router, prefix="/export", tags=["export"])
app.include_router(history.router, prefix="/history", tags=["history"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)