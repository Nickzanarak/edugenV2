# Azure App Service — PaaS Readiness Audit

> ตรวจสอบเมื่อ 12 มิ.ย. 2569 — โปรเจค **EduGen** (FastAPI backend + Next.js frontend)

---

## สรุปภาพรวม

| ด้าน | สถานะ | หมายเหตุ |
|------|--------|----------|
| Next.js `output: "standalone"` | ✅ พร้อม | ตั้งค่าแล้วใน `next.config.ts` |
| GitHub Actions — Frontend | ✅ พร้อม | Build → standalone artifact → deploy |
| GitHub Actions — Backend | ✅ พร้อม | Test → artifact → deploy |
| Health Check Endpoint | ✅ พร้อม | `GET /health` → `{"ok": true}` |
| `gunicorn` ใน requirements | ✅ พร้อม | มีอยู่แล้ว |
| CORS config | ✅ พร้อม | อ่านจาก `FRONTEND_ORIGINS` env var |
| Firebase Auth / Security | ✅ พร้อม | `ALLOW_DEMO_AUTH` ปิดได้ผ่าน App Settings |
| `.gitignore` — secrets | ✅ พร้อม | `.env`, `service-account.json` ถูก ignore |
| Docs — deployment guide | ✅ พร้อม | `docs/azure/app-service.md` ครบถ้วน |
| **Local filesystem persistence** | ⚠️ ต้องตัดสินใจ | `data/notes`, `data/qb` เขียนลง disk |
| **`os.getcwd()` path resolution** | ⚠️ ควรแก้ | App Service อาจ cwd ไม่ตรงกับที่คาด |
| **Frontend standalone copy path** | ⚠️ ตรวจสอบ | monorepo root กับ standalone path |
| **pytest in production deps** | 💡 ปรับปรุงได้ | `pytest` อยู่ใน `requirements.txt` หลัก |

---

## ✅ สิ่งที่พร้อมแล้ว

### 1. Next.js Standalone Build
```ts
// frontend/next.config.ts
output: "standalone"
```
ถูกต้อง — Azure App Service ต้องการ standalone output เพื่อรัน `node server.js` ได้โดยตรง

### 2. GitHub Actions Workflows
ทั้งสอง workflow พร้อมใช้:
- [deploy-frontend-azure-app-service.yml](file:///d:/project/Edu/.github/workflows/deploy-frontend-azure-app-service.yml) — build → copy standalone + static + public → deploy
- [deploy-backend-azure-app-service.yml](file:///d:/project/Edu/.github/workflows/deploy-backend-azure-app-service.yml) — test → copy app + fonts + requirements → deploy

### 3. Backend Entrypoint
[app/main.py](file:///d:/project/Edu/app/main.py) — `app.main:app` ตรงกับ startup command ที่ระบุไว้ใน docs:
```bash
gunicorn --bind=0.0.0.0:8000 --timeout 600 -k uvicorn.workers.UvicornWorker app.main:app
```

### 4. Health Check
[health.py](file:///d:/project/Edu/app/api/routes/health.py) — `GET /health` → พร้อมตั้ง Health Check Path บน Azure

### 5. Security & Env Config
- [config.py](file:///d:/project/Edu/app/core/config.py) — อ่าน env vars ผ่าน `os.getenv()`
- [security.py](file:///d:/project/Edu/app/core/security.py) — `ALLOW_DEMO_AUTH` ปิดง่ายผ่าน App Settings

---

## ⚠️ สิ่งที่ต้องแก้ / ตัดสินใจ

### Issue 1: Local Filesystem Persistence (สำคัญที่สุด)

> [!WARNING]
> Azure App Service **ไม่รับประกัน persistent local storage** — ไฟล์ใน `/home/site/wwwroot` จะถูกลบเมื่อ redeploy หรือ scale out

**ไฟล์ที่ได้รับผลกระทบ:**

| ไฟล์ | ใช้งานที่ | เขียนอะไร |
|------|----------|----------|
| [config.py:19](file:///d:/project/Edu/app/core/config.py#L19) | `NOTES_ROOT` | `data/notes/{user_id}/{file_id}.json` |
| [file_helper.py:16](file:///d:/project/Edu/app/utils/file_helper.py#L16) | `get_qb_paths()` | `data/qb/{user_id}/questions.json`, `quizzes.json` |
| [notes.py:44](file:///d:/project/Edu/app/api/routes/notes.py#L44) | `put_note()` | เขียน notes ลง local JSON |

**ทางเลือกแก้ไข:**

1. **Azure Blob Storage** — ย้าย read/write JSON ไปเก็บที่ Blob container (แนะนำ)
2. **Firestore** — ย้ายข้อมูล notes/quiz bank ไปเก็บใน Firestore ที่ใช้อยู่แล้ว (เหมาะสมที่สุด เพราะมี Firebase อยู่แล้ว)
3. **Azure Files Mount** — mount `/home/data` เป็น Azure File Share (ง่ายที่สุด แต่ช้ากว่า)

> [!TIP]
> **แนะนำ Option 2** — ย้ายไป Firestore เพราะโปรเจคมี Firebase อยู่แล้ว ไม่ต้องเพิ่ม dependency ใหม่

---

### Issue 2: `os.getcwd()` Path Resolution

> [!IMPORTANT]
> App Service อาจจะ `cwd` ต่างจาก deploy path — ใช้ `__file__` หรือ env var แทน

**จุดที่ใช้ `os.getcwd()`:**

| ไฟล์ | บรรทัด | ใช้ทำอะไร |
|------|--------|----------|
| [config.py:19](file:///d:/project/Edu/app/core/config.py#L19) | `NOTES_ROOT` | กำหนด root path ของ notes |
| [file_helper.py:16](file:///d:/project/Edu/app/utils/file_helper.py#L16) | `get_qb_paths()` | กำหนด root path ของ quiz bank |
| [export.py:25](file:///d:/project/Edu/app/api/routes/export.py#L25) | `_load_th_font()` | หา fonts directory |

**แก้ไขแนะนำ:**

```python
# แทนที่ os.getcwd() ด้วย path สัมพัทธ์กับตัวไฟล์
import pathlib
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent  # ปรับตาม structure

# หรือใช้ env var
DATA_DIR = os.getenv("DATA_DIR", "/home/site/wwwroot/data")
```

> [!NOTE]
> ถ้าเลือก Issue 1 Option 2 (ย้ายไป Firestore) ปัญหานี้จะหายไปเองสำหรับ notes/qb แต่ **fonts path ใน export.py ยังต้องแก้**

---

### Issue 3: Frontend Standalone Copy Path

> [!IMPORTANT]
> ต้องตรวจสอบว่า standalone build path ตรงกับ monorepo structure

ใน workflow:
```yaml
cp -R .next/standalone/frontend/. deploy/
```

เนื่องจาก `next.config.ts` มี `turbopack.root: path.join(__dirname, "..")` อาจทำให้ standalone output path เปลี่ยน ควร **ทดลอง build บน CI ก่อน deploy จริง** เพื่อยืนยันว่าไฟล์อยู่ที่ `.next/standalone/frontend/`

**ตรวจสอบ:**
```bash
cd frontend && npm run build
ls -la .next/standalone/
```

---

### Issue 4: pytest in Production Requirements

> [!NOTE]
> ไม่ blocking แต่ควรแยก

`pytest>=8.0` อยู่ใน [requirements.txt](file:///d:/project/Edu/requirements.txt#L25) หลัก ทำให้ App Service ติดตั้ง test dependency โดยไม่จำเป็น

**แก้ไขแนะนำ:**

```diff
# requirements.txt — ลบ pytest ออก
-pytest>=8.0
```

สร้างไฟล์แยก:
```
# requirements-dev.txt
-r requirements.txt
pytest>=8.0
```

แล้วแก้ workflow:
```yaml
- name: Install dependencies
  run: pip install -r requirements-dev.txt
```

---

## 📋 Checklist ก่อน Deploy

- [ ] **ตัดสินใจเรื่อง data persistence** — เลือก Firestore / Blob / Azure Files
- [ ] **แก้ `os.getcwd()`** ใน `config.py`, `file_helper.py`, `export.py`
- [ ] **ทดลอง frontend build** เพื่อยืนยัน standalone path
- [ ] **แยก pytest** ออกจาก `requirements.txt` หลัก
- [ ] **สร้าง Azure Resources** — 2 Web Apps (Node 20 + Python 3.12)
- [ ] **ตั้งค่า App Settings** ตามที่ระบุใน `docs/azure/app-service.md`
- [ ] **อัปโหลด `service-account.json`** หรือแก้โค้ดให้อ่าน credentials จาก env var
- [ ] **เพิ่ม GitHub Secrets** — `AZURE_FRONTEND_PUBLISH_PROFILE`, `AZURE_BACKEND_PUBLISH_PROFILE`
- [ ] **เพิ่ม GitHub Variables** — app names + `NEXT_PUBLIC_*` values
- [ ] **ตั้ง Startup Command** บน Azure Portal สำหรับทั้ง backend และ frontend
- [ ] **เปิด Health Check** path = `/health` บน backend App Service
- [ ] **ตรวจสอบ `ALLOW_DEMO_AUTH=false`** ทั้ง backend และ frontend

---

## สรุป

โปรเจค **พร้อมเป็นส่วนใหญ่แล้ว** — architecture, CI/CD, config, security ถูกเตรียมไว้หมด ปัญหาหลักที่ต้องจัดการก่อน deploy จริงคือ **local filesystem persistence** สำหรับ notes/quiz bank ซึ่งแนะนำให้ย้ายไป Firestore ที่มีอยู่แล้ว
