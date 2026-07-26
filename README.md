# EduGen: ผู้ช่วยการเรียนรู้อัจฉริยะด้วย AI (AI-Powered Education Assistant)

EduGen คือระบบผู้ช่วยอัจฉริยะสำหรับการเรียนรู้ พัฒนาด้วย **FastAPI** (ฝั่ง Backend) และ **Next.js** (ฝั่ง Frontend) ช่วยให้ผู้เรียนสามารถประมวลผลข้อความหรือเอกสาร PDF, สร้างสรุปเนื้อหาอัจฉริยะ, สร้างชุดข้อสอบแบบอินเทอร์แอกทีฟ และถาม-ตอบจากบริบทของเอกสารได้โดยใช้ความสามารถของ OpenAI

## ✨ ฟีเจอร์หลัก (Key Features)

- **📄 ประมวลผลเอกสาร:** อัปโหลดไฟล์ PDF หรือวางข้อความลงไปตรงๆ เพื่อสกัดและวิเคราะห์เนื้อหา
- **🧠 สรุปเนื้อหาด้วย AI:** สร้างสรุปที่มีโครงสร้างชัดเจนอัตโนมัติ (ภาพรวม, ประเด็นสำคัญ, สรุปตามหัวข้อ และข้อมูลตัวเลขสถิติ)
- **📝 สร้างข้อสอบอัจฉริยะ:** สร้างข้อสอบแบบปรนัย (MCQ) และถูก/ผิด (TF) จากบริบทของเอกสาร พร้อมระบบป้องกันการสร้างคำถามซ้ำ
- **💬 ถาม-ตอบจากบริบท:** สอบถามข้อมูลต่างๆ จากเอกสารที่อัปโหลด โดยระบบจะหาคำตอบที่แม่นยำจากเนื้อหาที่กำหนดให้เท่านั้น
- **📚 คลังเก็บข้อมูลบน Cloud:** ประวัติการใช้งาน, โน้ตย่อ และคลังข้อสอบส่วนตัว จะถูกเก็บรักษาไว้อย่างปลอดภัยบน **Firestore** ทำให้ซิงค์ข้อมูลข้ามอุปกรณ์และพร้อมรองรับสถาปัตยกรรมระดับ PaaS
- **🖨️ Export เป็น PDF:** นำออกชุดข้อสอบที่สร้างขึ้นมาเป็นไฟล์ PDF ที่จัดหน้าไว้อย่างสวยงาม

## 🛠️ เทคโนโลยีที่ใช้ (Tech Stack)

- **Backend:** Python 3, FastAPI, Pydantic, OpenAI API, Firebase Admin SDK, PDFPlumber, ReportLab
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Firebase Auth, React Query, Zod
- **Database:** Google Cloud Firestore (NoSQL)

## 🚀 เริ่มต้นการใช้งาน (Getting Started)

### สิ่งที่ต้องมีเบื้องต้น (Prerequisites)

- Python 3.10+
- Node.js 18+
- [OpenAI API Key](https://platform.openai.com/api-keys)
- โปรเจกต์ Firebase (เปิดใช้งาน Authentication และ Firestore)
- ไฟล์ Service Account JSON ของ Firebase Admin SDK

### 1. ตั้งค่า Environment

สร้างไฟล์ `.env` ที่ root ของโปรเจกต์ โดยคัดลอกรูปแบบจาก `.env.example`:

```bash
cp .env.example .env
```

ตรวจสอบให้แน่ใจว่าได้ระบุตัวแปรเหล่านี้ในไฟล์ `.env` เรียบร้อยแล้ว:
```env
OPENAI_API_KEY=your-openai-api-key
FIREBASE_PROJECT_ID=your-firebase-project-id
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
ALLOW_DEMO_AUTH=true # ตั้งเป็น false เมื่อขึ้น production
```

### 2. รัน Backend (FastAPI)

```bash
# ติดตั้ง dependencies ที่จำเป็น
pip install -r requirements.txt

# (ทางเลือก) ติดตั้ง dependencies สำหรับการทดสอบและ development
pip install -r requirements-dev.txt

# สตาร์ท FastAPI server
uvicorn app.main:app --reload
```
คุณสามารถดู API documentation ได้ที่ `http://127.0.0.1:8000/docs`

### 3. รัน Frontend (Next.js)

```bash
cd frontend

# ติดตั้ง Node modules
npm install

# สตาร์ท development server
npm run dev
```
เว็บแอปพลิเคชันจะเปิดให้ใช้งานได้ที่ `http://localhost:3000`

## 📚 สถาปัตยกรรมและคู่มือการพัฒนาระบบ

หากต้องการเจาะลึกรายละเอียดเกี่ยวกับสถาปัตยกรรมของระบบ, API endpoints, Data Models หรือวิธีการจัดเก็บข้อมูล อ่านเพิ่มเติมได้ที่คู่มือนี้:
- 📖 **[System Architecture & API Docs (lean.md)](lean.md)**

## ☁️ การนำขึ้นระบบจริง (Azure App Service)

โปรเจกต์นี้ได้รับการปรับแต่งและพร้อมสำหรับการ Deploy ลงบน **Azure App Service** ภายใต้สถาปัตยกรรมแบบสองชั้น (Two-tier Web App architecture):
- Node.js App Service สำหรับ Next.js frontend
- Python App Service สำหรับ FastAPI backend

สำหรับขั้นตอนการนำขึ้นระบบอย่างละเอียด, การตั้งค่า GitHub secrets ที่จำเป็น และคำสั่ง Startup ของ App Service สามารถดูได้จากคู่มือการใช้งาน Azure:
- 📘 **[Azure App Service Deployment Guide (docs/azure/app-service.md)](docs/azure/app-service.md)**
