# สรุปภาพรวมโครงสร้างและระบบของ EduGen API

อัปเดตจากโค้ดในโปรเจกต์ ณ วันที่ 12 มิถุนายน 2026  
เวอร์ชัน API: `3.8.5`  
สถาปัตยกรรมหลัก: FastAPI backend แบบ modular layered architecture + Next.js frontend

## ภาพรวมระบบ

EduGen เป็นระบบช่วยเรียนรู้จากเอกสารหรือข้อความ ผู้ใช้สามารถอัปโหลด PDF หรือพิมพ์เนื้อหาเอง แล้วให้ระบบช่วยสรุปเนื้อหา สร้างข้อสอบ ถาม-ตอบจากบริบท จดโน้ต บันทึกประวัติ และจัดการคลังข้อสอบได้

ระบบแบ่งเป็น 2 ส่วนหลัก:

- Backend: FastAPI/Python อยู่ในโฟลเดอร์ `app/` ทำหน้าที่เป็น API, จัดการ auth, เรียก OpenAI, อ่าน PDF, เก็บ note/quiz bank, export PDF และเชื่อม Firestore
- Frontend: Next.js/React/TypeScript อยู่ในโฟลเดอร์ `frontend/` ทำหน้าที่เป็นหน้าใช้งานหลัก เชื่อม Firebase Auth และเรียก API ผ่าน service layer

บริการภายนอกที่ใช้:

- OpenAI `gpt-4o-mini` สำหรับสรุป สร้างหัวข้อ สร้างข้อสอบ และถาม-ตอบ
- Firebase Auth สำหรับยืนยันตัวตนผ่าน ID token
- Firestore สำหรับเก็บประวัติการใช้งาน, log, note และ quiz bank (รองรับ Azure PaaS)

## โครงสร้างโฟลเดอร์

```text
Edu/
├── app/                         # Backend FastAPI package
│   ├── main.py                   # สร้าง FastAPI app, CORS, init Firebase, include routers
│   ├── api/
│   │   └── routes/               # Route แยกตาม feature
│   │       ├── health.py         # GET /health
│   │       ├── pdf.py            # POST /pdf/extract
│   │       ├── summary.py        # POST /summarize
│   │       ├── quiz.py           # POST /quiz/topics, /quiz/mcq, /quiz/tf
│   │       ├── qa.py             # POST /qa
│   │       ├── notes.py          # GET/PUT /notes/{file_id}
│   │       ├── bank.py           # CRUD คลังข้อสอบและชุดข้อสอบ
│   │       ├── export.py         # POST /export/quizzes/{quiz_id}
│   │       └── history.py        # CRUD ประวัติใน Firestore
│   ├── core/
│   │   ├── config.py             # Settings, env vars, constants
│   │   └── security.py           # Firebase Bearer auth + demo auth fallback
│   ├── db/
│   │   └── firebase.py           # Firebase Admin, Firestore, log_user_event
│   ├── models/
│   │   ├── schemas.py            # Pydantic models สำหรับ AI routes
│   │   ├── bank.py               # Pydantic models สำหรับ quiz bank/export
│   │   └── history.py            # Pydantic models สำหรับ history
│   ├── services/
│   │   ├── ai_service.py         # OpenAI client singleton
│   │   ├── summarize_service.py  # สรุปเนื้อหาแบบ 2-step
│   │   ├── quiz_service.py       # สร้าง topics, MCQ, TF, กันคำถามซ้ำ
│   │   ├── qa_service.py         # ตอบคำถามจาก context
│   │   ├── bank_service.py       # CRUD quiz bank ผ่าน Firestore
│   │   └── history_service.py    # CRUD history ผ่าน Firestore
│   └── utils/
│       ├── text.py               # clean/truncate/JSON parse/sentence split
│       ├── nlp.py                # similarity, near-duplicate filtering
│       └── file_helper.py        # JSON file helper สำหรับ offline tooling/tests
├── fonts/
│   └── THSarabunNew.ttf          # ฟอนต์ไทยสำหรับ export PDF
├── frontend/                     # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # หน้าใช้งานหลักแบบ single-page
│   │   └── globals.css
│   └── src/
│       ├── components/           # UI, feature, layout components
│       ├── hooks/                # useQuiz, useBank, useQA, useHistoryQuery
│       ├── services/             # api client และ history helpers
│       ├── schemas/              # Zod runtime validation
│       ├── lib/                  # Firebase client, validate helper
│       ├── constants/            # quiz constants
│       ├── types/                # TypeScript shared types
│       └── utils/                # frontend helper functions
├── tests/                        # pytest backend tests
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Python dev dependencies (เช่น pytest)
├── .env.example                  # ตัวอย่าง environment variables
└── lean.md                       # เอกสารนี้
```

## Tech Stack

Backend:

- `FastAPI` เป็น web API framework
- `uvicorn` สำหรับรัน ASGI server
- `pydantic` สำหรับ request/response validation
- `openai` สำหรับเรียก OpenAI Chat Completions
- `firebase-admin`, `google-cloud-firestore` สำหรับ auth verification และ Firestore
- `pdfplumber` สำหรับอ่านข้อความจาก PDF
- `reportlab` สำหรับสร้าง PDF export
- `python-dotenv` สำหรับโหลด `.env`
- `pytest` สำหรับ unit tests

Frontend:

- `Next.js 16.0.1`
- `React 19.2.0`
- `TypeScript`
- `Tailwind CSS 4`
- `Firebase 12.14.0`
- `TanStack React Query 5`
- `Zod 4`

## Backend Architecture

Backend ใช้รูปแบบ layered architecture:

```text
HTTP Request
  -> FastAPI app / CORS middleware
  -> Route ใน app/api/routes
  -> Security dependency ถ้า endpoint ต้อง auth
  -> Pydantic model validate request
  -> Service layer ทำ business logic
  -> Utils / OpenAI / Firestore / PDF
  -> Response model หรือ raw response
```

ข้อดีของโครงสร้างนี้:

- Route ทำหน้าที่บาง ๆ คือรับ request, validate และส่งต่อให้ service
- Service รวม business logic ของแต่ละ feature ทำให้ทดสอบและแก้ไขง่าย
- Model แยกจาก logic ช่วยให้ schema ชัดเจน
- Utils แยกงานซ้ำ เช่น clean text, parse JSON, similarity, file path
- Auth ถูกบังคับผ่าน FastAPI dependency จึงใส่ใน endpoint ที่ต้องการได้ชัดเจน

## Entry Point และ CORS

ไฟล์หลักคือ `app/main.py`

หน้าที่:

- สร้าง `FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)`
- ตั้งค่า CORS
- เรียก `init_firebase(...)`
- include router ทุก feature
- รองรับการรันตรงผ่าน `python -m app.main` หรือ `uvicorn app.main:app`

CORS:

- อ่าน `FRONTEND_ORIGINS` จาก `.env` ถ้ามี
- ถ้าไม่มี ใช้ fallback เป็น `http://127.0.0.1:3000`
- มี regex อนุญาต `localhost` และ `127.0.0.1` ทุก port
- `allow_credentials=True`
- เปิด method/header ทั้งหมด
- expose header `Content-Disposition` เพื่อให้ frontend อ่านชื่อไฟล์ PDF export ได้

Router prefixes:

```text
/health     -> health.router
/pdf        -> pdf.router
/summarize  -> summary.router
/quiz       -> quiz.router
/qa         -> qa.router
/notes      -> notes.router
/bank       -> bank.router
/export     -> export.router
/history    -> history.router
```

## Configuration

ไฟล์ `app/core/config.py` มี class `Settings` ที่โหลดค่าจาก `.env`

ค่าหลัก:

| ตัวแปร | ความหมาย |
|---|---|
| `PROJECT_NAME` | ชื่อ API: `EduGen API` |
| `VERSION` | เวอร์ชัน: `3.8.5` |
| `OPENAI_API_KEY` | API key สำหรับ OpenAI |
| `FIREBASE_PROJECT_ID` | Firebase project id |
| `FRONTEND_ORIGINS` | origin ของ frontend แบบ comma-separated |
| `GOOGLE_APPLICATION_CREDENTIALS` | path ของ service account, default `./service-account.json` |
| `ALLOW_DEMO_AUTH` | เปิดให้ใช้ `X-User-Id` แทน Bearer token ใน dev |
| `NEAR_DUP_THRESHOLD` | threshold กันคำถามซ้ำ, default `0.78` |
| `CTX_CHAR_LIMIT` | จำนวนตัวอักษรสูงสุดที่ส่งให้ quiz/qa, default `15000` |
| `EXCLUDE_LIST_LIMIT` | จำนวนคำถามเก่าที่ส่งไปให้ AI หลีกเลี่ยง, default `30` |

ข้อควรระวัง:

- ถ้าไม่มี `OPENAI_API_KEY` ระบบจะ raise `RuntimeError` ตั้งแต่ import config
- `ALLOW_DEMO_AUTH=true` เหมาะกับ development เท่านั้น

## Authentication และ Security

ไฟล์ `app/core/security.py`

ฟังก์ชันสำคัญ:

- `_verify_bearer_token(token)` ตรวจ Firebase ID token ผ่าน `fb_auth.verify_id_token`
- `get_current_user(request, cred)` เป็น dependency ที่คืนค่า `uid`

ลำดับการตรวจ:

1. ถ้ามี `Authorization: Bearer <token>` จะ verify token กับ Firebase Admin SDK
2. ถ้า token ถูกต้อง จะดึง `uid` จาก decoded token
3. ถ้าไม่มี token และ `ALLOW_DEMO_AUTH=true` จะใช้ header `X-User-Id`
4. ถ้าไม่มี `X-User-Id` จะ fallback เป็น `demo-user`
5. ถ้าไม่เข้าเงื่อนไขทั้งหมด จะตอบ `401 Missing or invalid authentication`

Endpoint ที่ต้อง auth ใช้รูปแบบ:

```python
uid: str = Depends(get_current_user)
```

Endpoint ที่ต้อง auth ในโค้ดปัจจุบัน:

- `POST /summarize`
- `GET /notes/{file_id}`
- `PUT /notes/{file_id}`
- ทุก endpoint ใน `/bank/*`
- `POST /export/quizzes/{quiz_id}`
- ทุก endpoint ใน `/history/*`

Endpoint ที่ยังไม่บังคับ auth:

- `GET /health`
- `POST /pdf/extract`
- `POST /quiz/topics`
- `POST /quiz/mcq`
- `POST /quiz/tf`
- `POST /qa`

## Firebase และ Firestore

ไฟล์ `app/db/firebase.py`

หน้าที่:

- import Firebase Admin และ Firestore แบบ optional
- `init_firebase(project_id, cred_path)` initialize Firebase Admin app และสร้าง Firestore client
- `get_firestore_db()` คืนค่า Firestore client หรือ `None`
- `log_user_event(user_id, collection, data)` เพิ่ม log ลง path `users/{uid}/{collection}`

พฤติกรรมเมื่อ config ใช้ไม่ได้:

- ถ้าไม่มี library หรือ init ไม่สำเร็จ จะพิมพ์ error และ `_db = None`
- history operations ที่ต้องเขียน DB จะตอบ `500 Database not connected`
- `get_history_list` ถ้า DB ใช้ไม่ได้จะคืน `[]`
- `log_user_event` จะ no-op ถ้า DB ไม่พร้อม

Firestore paths ที่ใช้:

```text
users/{uid}/histories/{history_id}
users/{uid}/summaries/{auto_id}
```

## API Endpoints

### Health

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/health` | ไม่ต้อง | `{ "ok": true, "version": "3.8.5" }` |

### PDF

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `POST` | `/pdf/extract` | ไม่ต้อง | รับไฟล์ `.pdf` แล้วอ่านข้อความ |

รายละเอียด:

- รับ multipart field ชื่อ `pdf`
- ตรวจนามสกุลต้องเป็น `.pdf`
- ใช้ `pdfplumber.open(pdf.file)` อ่านทุกหน้า
- รวมข้อความทุกหน้า แล้ว clean ด้วย `clean_text`
- ถ้าอ่านไม่ได้หรือไม่มี text ตอบ `422`
- ถ้าไม่ได้ติดตั้ง `pdfplumber` ตอบ `500`

Response:

```json
{ "text": "..." }
```

### Summarize

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| `POST` | `/summarize` | ต้อง | `ContextIn` | `SummarizeOut` |

Request:

```json
{ "context": "ข้อความหรือข้อความจาก PDF" }
```

Response:

```json
{
  "overview": "...",
  "key_points": ["..."],
  "sections": [{ "title": "...", "summary": "..." }],
  "data_points": [{ "label": "...", "value": "...", "unit": "..." }]
}
```

ภายใน `SummarizeService.summarize`:

1. ตรวจ context ว่าง ถ้าว่างตอบ `400`
2. truncate context สูงสุด `45000` ตัวอักษร
3. clean text
4. แบ่งเป็น numbered sentences สูงสุด `800` ประโยค
5. เรียก OpenAI รอบแรกเพื่อสรุปเป็น `sections` 5-9 หัวข้อ
6. เรียก OpenAI รอบสองเพื่อสร้าง `overview`, `key_points`, `data_points`
7. normalize fields ให้เป็นชนิดข้อมูลที่คาดไว้
8. log event ลง Firestore collection `summaries`
9. ถ้าเกิด error จะพยายาม log error แล้วตอบ `500 Summarize failed: ...`

OpenAI settings:

- model: `gpt-4o-mini`
- temperature: `0.15`
- response format: JSON object

### Quiz

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `POST` | `/quiz/topics` | ไม่ต้อง | สกัดหัวข้อสำคัญจาก context |
| `POST` | `/quiz/mcq` | ไม่ต้อง | สร้างข้อสอบปรนัย |
| `POST` | `/quiz/tf` | ไม่ต้อง | สร้างข้อสอบถูก/ผิด |

`/quiz/topics`

Request:

```json
{ "context": "..." }
```

Response:

```json
{ "topics": ["หัวข้อ 1", "หัวข้อ 2"] }
```

รายละเอียด:

- context ต้องไม่ว่าง
- ส่ง context สูงสุด `CTX_CHAR_LIMIT` ให้ OpenAI
- ขอ JSON `{ "topics": [...] }`
- ไม่เกินประมาณ 30 หัวข้อจาก prompt

`/quiz/mcq` และ `/quiz/tf`

Request:

```json
{
  "context": "...",
  "n": 5,
  "exclude": ["คำถามเดิมที่ไม่อยากให้ซ้ำ"],
  "topics": ["หัวข้อที่อยากให้ครอบคลุม"]
}
```

Response:

```json
{
  "questions": [
    {
      "type": "mcq",
      "question": "...",
      "choices": ["ก) ...", "ข) ...", "ค) ...", "ง) ..."],
      "answer": "ก",
      "explain": "...",
      "topic": "..."
    }
  ]
}
```

หรือสำหรับ true/false:

```json
{
  "questions": [
    {
      "type": "tf",
      "question": "...",
      "answer": "true",
      "explain": "...",
      "topic": "..."
    }
  ]
}
```

พฤติกรรมภายใน `QuizService`:

- จำกัดจำนวนคำถามต่อ request อยู่ระหว่าง `1` ถึง `10`
- ใช้ `exclude` และคำถามที่เพิ่งสร้างใน batch เพื่อกันคำถามซ้ำ
- ถ้ามี `topics` จะพยายามให้สร้างหัวข้อละ 1 ข้อ
- รอบแรกจะขอ AI มากกว่าที่ต้องการเล็กน้อย (`need + 3`) เพื่อมีตัวเลือกหลังกรองซ้ำ
- retry ได้สูงสุด 2 รอบถ้ายังได้คำถามไม่ครบ
- ใช้ `filter_near_dups` กรองซ้ำจาก AI response
- ใช้ `similar` เทียบกับคำถามใน batch ด้วย threshold `0.78`

OpenAI settings:

- topics: temperature `0.2`, JSON object
- mcq: temperature `0.3`, JSON object
- tf: temperature `0.25`, JSON object

### Q&A

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `POST` | `/qa` | ไม่ต้อง | ตอบคำถามจาก context ที่ให้มาเท่านั้น |

Request:

```json
{
  "context": "...",
  "question": "..."
}
```

Response:

```json
{ "answer": "..." }
```

รายละเอียด:

- context และ question ต้องไม่ว่าง
- ถ้าไม่พบคำตอบใน context prompt สั่งให้ตอบว่าไม่พบในเนื้อหาที่ให้มา
- truncate context สูงสุด `CTX_CHAR_LIMIT`
- ใช้ OpenAI `gpt-4o-mini`, temperature `0.15`

### Notes

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `GET` | `/notes/{file_id}` | ต้อง | อ่าน note ของผู้ใช้ตาม file id |
| `PUT` | `/notes/{file_id}` | ต้อง | เขียนหรืออัปเดต note |

Storage:

```text
Firestore: users/{uid}/notes/{file_id}
```

GET response:

```json
{
  "file_id": "...",
  "content": "...",
  "updated_at": "2026-06-10T..."
}
```

ถ้าไฟล์ไม่มีหรืออ่านไม่ได้ จะคืน content ว่างแทนการ throw error

PUT request:

```json
{ "content": "..." }
```

PUT behavior:

- strip content ก่อนบันทึก
- เขียนลง Firestore document (`users/{uid}/notes/{file_id}`)
- เพิ่ม `updated_at` แบบ UTC ISO string

### Quiz Bank

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `GET` | `/bank/questions` | ต้อง | รายการข้อสอบทั้งหมดของผู้ใช้ |
| `POST` | `/bank/questions` | ต้อง | สร้างข้อสอบเข้าคลัง |
| `PATCH` | `/bank/questions/{qid}` | ต้อง | แก้ไขข้อสอบ |
| `GET` | `/bank/quizzes` | ต้อง | รายการชุดข้อสอบ |
| `POST` | `/bank/quizzes` | ต้อง | สร้างชุดข้อสอบ |
| `PATCH` | `/bank/quizzes/{quiz_id}` | ต้อง | แก้ไขชื่อ/รายการข้อในชุด |
| `POST` | `/bank/quizzes/{quiz_id}/questions` | ต้อง | เพิ่มข้อสอบใหม่เข้า set พร้อมกันซ้ำ |
| `DELETE` | `/bank/quizzes/{quiz_id}` | ต้อง | ลบชุดข้อสอบ |

Storage:

```text
Firestore: users/{uid}/bank/questions
Firestore: users/{uid}/bank/quizzes
```

Question model:

```json
{
  "id": 1,
  "type": "mcq",
  "question": "...",
  "choices": ["...", "...", "...", "..."],
  "answer": "ก",
  "explain": "...",
  "topic": "..."
}
```

Quiz set model:

```json
{
  "id": 1,
  "title": "แบบทดสอบ",
  "question_ids": [1, 2, 3],
  "created_at": "2026-06-10T...",
  "updated_at": "2026-06-10T..."
}
```

Validation สำคัญใน `BankService`:

- `QuestionIn.type` ต้องเป็น `mcq` หรือ `tf`
- MCQ ต้องมี answer เป็น `ก`, `ข`, `ค`, `ง`
- MCQ choices ถูก normalize ให้มี 4 ช่องเสมอ
- TF ต้องมี answer เป็น `true`, `false`, `จริง`, `เท็จ`
- TF ถูกเก็บเป็น `true` หรือ `false`
- ตอนสร้าง/แก้ไข quiz set จะเก็บเฉพาะ `question_ids` ที่มีอยู่จริงใน Firestore `questions` array
- `_next_id` สร้าง id ใหม่จาก max id ปัจจุบัน + 1

การกันข้อสอบซ้ำในชุด:

- endpoint `POST /bank/quizzes/{quiz_id}/questions` จะเรียก `is_duplicate_in_set`
- ดึงข้อความคำถามทั้งหมดในชุดนั้น
- เทียบคำถามใหม่กับคำถามเดิมด้วย `similar`
- ถ้า similarity >= `NEAR_DUP_THRESHOLD` จะตอบ `409`
- ถ้าไม่ซ้ำ จะสร้าง question ใหม่ แล้ว append id เข้า `question_ids` ของ quiz set

### Export PDF

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `POST` | `/export/quizzes/{quiz_id}` | ต้อง | export ชุดข้อสอบเป็น PDF |

Request:

```json
{
  "shuffleChoices": false,
  "showAnswers": false
}
```

รายละเอียด:

- โหลด quiz set และ questions จาก Firestore
- รวมคำถามตาม `question_ids`
- สร้าง PDF ด้วย ReportLab
- พยายามโหลดฟอนต์ไทยจาก `fonts/THSarabunNew.ttf`
- ถ้าไม่มีฟอนต์ จะ fallback เป็น `Helvetica`
- ถ้า `shuffleChoices=true` จะสุ่ม choices ของ MCQ ใน PDF
- ถ้า `showAnswers=true` จะแสดงเฉลยและคำอธิบาย
- ส่งกลับเป็น `StreamingResponse` media type `application/pdf`
- ตั้ง `Content-Disposition` ทั้ง `filename` fallback ASCII และ `filename*` UTF-8

ข้อควรระวัง:

- การ shuffle choices ใน export ตอนนี้สุ่มเฉพาะบรรทัดตัวเลือกใน PDF แต่ไม่ได้ remap เฉลยตามตำแหน่งใหม่ จึงควรใช้ `shuffleChoices=false` ถ้าต้องการแสดงเฉลยที่ตรงกับตัวเลือกเดิม

### History

| Method | Path | Auth | หน้าที่ |
|---|---|---|---|
| `POST` | `/history/save` | ต้อง | บันทึก session ใหม่ |
| `GET` | `/history/list` | ต้อง | ดึงประวัติล่าสุด 30 รายการ |
| `DELETE` | `/history/{item_id}` | ต้อง | ลบประวัติ |
| `PATCH` | `/history/{item_id}` | ต้อง | เปลี่ยนชื่อประวัติ |
| `PATCH` | `/history/update/{item_id}` | ต้อง | อัปเดตข้อมูลประวัติ |

Storage:

```text
users/{uid}/histories/{history_id}
```

ข้อมูลที่บันทึก:

- `fileName`
- `overview`
- `keyPoints`
- `sections`
- `dataPoints`
- `questions`
- `answers`
- `score`
- `content`
- `totalQuestions`
- `timestamp`
- `qa_history`

พฤติกรรม:

- `save_history_item` ใช้ Firestore `.add(data)` และคืน `id`
- `get_history_list` order by `timestamp` descending จำกัด 30 รายการ
- `rename_history_item` update เฉพาะ `fileName`
- `update_history_item` update quiz, answers, score, timestamp และ optional fields ถ้ามีค่า
- ถ้า Firestore ไม่พร้อม การ save/delete/rename/update ตอบ `500`

## Data Models

### `app/models/schemas.py`

| Model | Fields | ใช้กับ |
|---|---|---|
| `ContextIn` | `context: str` | summarize, topics |
| `QuizIn` | `context`, `n=5`, `exclude?`, `topics?` | quiz mcq/tf |
| `QAIn` | `context`, `question` | qa |
| `SummarizeOut` | `overview`, `key_points`, `sections`, `data_points` | summarize response |
| `TopicsOut` | `topics` | topics response |

### `app/models/bank.py`

| Model | Fields |
|---|---|
| `QuestionIn` | `type`, `question`, `choices?`, `answer`, `explain`, `topic` |
| `QuestionOut` | `QuestionIn + id` |
| `QuizCreateIn` | `title`, `question_ids?` |
| `QuizOut` | `id`, `title`, `question_ids`, `created_at`, `updated_at` |
| `ExportOpts` | `shuffleChoices`, `showAnswers` |

### `app/models/history.py`

| Model | Fields |
|---|---|
| `QAPair` | `question`, `answer` |
| `QuizHistoryIn` | `file_name`, `overview`, `key_points`, `sections`, `data_points`, `questions`, `answers`, `score`, `content`, `qa_history` |
| `RenameHistoryIn` | `new_name` |

หมายเหตุ: บาง model ใช้ mutable default เช่น `[]` และ `{}` ใน Pydantic model ปัจจุบัน Pydantic จัดการ copy ให้ได้ในหลายกรณี แต่ในเชิง style อาจพิจารณาใช้ `Field(default_factory=list)` หรือ `Field(default_factory=dict)` เพื่อชัดเจนขึ้น

## Utilities

### Text Utils

ไฟล์ `app/utils/text.py`

| Function | หน้าที่ |
|---|---|
| `sentences(text)` | แยกข้อความเป็นประโยคด้วย regex |
| `clean_text(text)` | ลด newline/space ซ้ำ และ trim |
| `strip_json_fence(s)` | เอา markdown code fence รอบ JSON ออก |
| `safe_json_loads(s, fallback)` | parse JSON แบบมี fallback |
| `numbered_sentences(text, max_sentences)` | คืน list ของ `{id, text}` |
| `truncate_text_chars(text, max_chars)` | ตัดข้อความตามจำนวนตัวอักษร |

### NLP / Similarity Utils

ไฟล์ `app/utils/nlp.py`

| Function | หน้าที่ |
|---|---|
| `tokenize(s)` | lower, ลบ punctuation, split word, ตัด stopword |
| `jaccard(a, b)` | similarity จาก set ของ token |
| `dice_bigram(a, b)` | similarity จาก character bigram |
| `similar(a, b)` | ใช้ค่าสูงสุดระหว่าง Jaccard และ Dice bigram |
| `filter_near_dups(items, exclude, threshold)` | กรองข้อสอบซ้ำจากรายการที่ AI สร้าง |

สูตรกันซ้ำหลัก:

```text
similarity = max(jaccard(question_a, question_b), dice_bigram(question_a, question_b))
duplicate = similarity >= 0.78
```

### File Helpers

ไฟล์ `app/utils/file_helper.py`

| Function | หน้าที่ |
|---|---|
| `read_json(path, default)` | อ่าน JSON ถ้าไม่มี/อ่านพลาดคืน default (ใช้ใน offline tooling/tests) |
| `write_json(path, data)` | เขียน JSON แบบ temp file แล้ว replace (ใช้ใน offline tooling/tests) |

## Frontend Architecture

Frontend เป็น Next.js app router โดยหน้าใช้งานหลักอยู่ที่ `frontend/app/page.tsx`

บทบาทหลักของ frontend:

- จัดการ Firebase Auth client-side
- สร้าง auth headers ให้ backend
- รับข้อความหรือ PDF จากผู้ใช้
- เรียก API เพื่อ extract PDF, summarize, quiz, qa
- เก็บและโหลด history ผ่าน React Query
- autosave note ผ่าน `/notes/{file_id}`
- จัดการ quiz state, answer state, score และ locked state
- จัดการ quiz bank และ export PDF

โครงสร้างสำคัญ:

```text
frontend/src/
├── components/
│   ├── features/        # AuthModal, PdfUploader, SummarySection, QASection, QuizSection, QuizToolbar, BankPanel
│   ├── layout/          # HistorySidebar
│   ├── providers/       # QueryProvider
│   └── ui/              # Card, Label, Modal, PrimaryBtn, LoadingOverlay
├── hooks/
│   ├── useQuiz.ts       # quiz state, generate, submit, restore
│   ├── useBank.ts       # quiz bank query/mutations/export
│   ├── useQA.ts         # Q&A state
│   ├── useHistoryQuery.ts
│   └── useTypewriter.ts
├── services/
│   ├── api.ts           # API base, auth headers, apiFetch, ApiError
│   ├── api-helpers.ts   # normalize/shuffle quiz helpers
│   └── history.ts       # build/save/update history payload
├── schemas/
│   └── api.ts           # Zod schemas
├── lib/
│   ├── firebase.ts      # Firebase client
│   └── validate.ts      # parseApi helper
├── constants/
│   └── quiz.ts          # MAX_QUESTIONS, BATCH_SIZE
└── types/
    └── index.ts
```

## Frontend API Client

ไฟล์ `frontend/src/services/api.ts`

ค่าหลัก:

- `getAPIBase()` อ่าน `NEXT_PUBLIC_API`, fallback `http://localhost:8000`
- `isDemoAuthEnabled()` อ่าน `NEXT_PUBLIC_ALLOW_DEMO_AUTH`
- `canUseProtectedApi(hasUser)` คืน true ถ้ามี user หรือ demo auth เปิดอยู่
- `buildAuthHeaders(token, demoUid)` สร้าง header:
  - ถ้ามี token: `{ Authorization: "Bearer <token>" }`
  - ถ้าไม่มี token แต่ demo auth เปิด: `{ "X-User-Id": demoUid }`
  - ไม่เข้าเงื่อนไข: `{}`
- `apiFetch` เป็น wrapper fetch สำหรับ JSON response และ error handling
- `apiFetchBlob` ใช้กับ response ที่เป็น blob เช่น PDF export

Runtime validation:

- frontend ใช้ `Zod` schemas ใน `src/schemas/api.ts`
- ใช้ `parseApi` ใน `src/lib/validate.ts` ตรวจ response จาก backend ก่อนใช้จริง

## Frontend State และ Flow หลัก

### Auth flow

1. `onAuthStateChanged(auth, ...)` ตรวจสถานะ Firebase user
2. ถ้ามี user จะเรียก `user.getIdToken()` และเก็บ `authToken`
3. `buildAuthHeaders` สร้าง Bearer header
4. ถ้าไม่มี user และ demo auth เปิด จะใช้ uid จาก `localStorage.uid` หรือ `demo-user`
5. protected action เช่น summarize/history/notes/bank ใช้ `canUseProtectedApi`

### PDF/manual input flow

```text
ผู้ใช้พิมพ์ข้อความหรืออัปโหลด PDF
  -> ถ้า PDF: POST /pdf/extract
  -> ได้ pdfText
  -> context = text + pdfText หรือ hiddenContext จาก history
  -> POST /summarize พร้อม auth
  -> แสดง summary + บันทึก history
```

### Summary flow

```text
page.tsx summarize()
  -> ตรวจ context
  -> ตรวจ auth/demo auth
  -> POST /summarize
  -> validate ด้วย SummarizeResponseSchema
  -> set overview/keyPoints/sections/dataPoints
  -> ensureTopics()
  -> save/update history
```

### Quiz flow

ไฟล์ `frontend/src/hooks/useQuiz.ts`

State หลัก:

- `questions`
- `answers`
- `score`
- `lockedCount`
- `topicsRef`

Flow สร้างข้อสอบ:

```text
กดเพิ่ม MCQ หรือ TF
  -> ensureTopics() เรียก /quiz/topics ถ้ายังไม่มี topics
  -> คำนวณจำนวนที่ยังเพิ่มได้
  -> ส่ง exclude เป็นคำถามเดิมประเภทเดียวกัน
  -> POST /quiz/mcq หรือ /quiz/tf
  -> validate response
  -> normalize + shuffle/remap batch ฝั่ง frontend
  -> append เข้า questions
  -> save/update history
```

Flow submit:

```text
ผู้ใช้ตอบครบ
  -> submitQuiz()
  -> เทียบ answer ของผู้ใช้กับ answer จริง
  -> set score
  -> lock จำนวนคำถามทั้งหมด
  -> save/update history
```

### Q&A flow

ไฟล์ `frontend/src/hooks/useQA.ts`

โดยรวม:

```text
ผู้ใช้ถาม
  -> POST /qa พร้อม context/question
  -> เพิ่ม QAPair เข้า qaHistory
  -> save/update history
```

### Note autosave flow

ใน `page.tsx`:

- note ผูกกับ `fileId`
- เมื่อเปิด/เปลี่ยน fileId จะเรียก `GET /notes/{file_id}`
- เมื่อผู้ใช้แก้ note จะ debounce ประมาณ 1200 ms
- แล้วเรียก `PUT /notes/{file_id}`
- แสดงสถานะ `saving`, `saved`, `error`

### History flow

ใช้ `useHistoryQuery` และ `useHistoryMutations`

หลักการ:

- list history จาก `/history/list`
- save session ใหม่ด้วย `/history/save`
- update session เดิมด้วย `/history/update/{id}`
- rename ด้วย `/history/{id}`
- delete ด้วย `/history/{id}`
- หลัง mutation จะ invalidate React Query cache หรือ patch local state ตามจุดที่จำเป็น

### Bank flow

ไฟล์ `frontend/src/hooks/useBank.ts`

ใช้ React Query:

- query key `["bank", "quizzes", authKey]`
- query key `["bank", "questions", authKey]`
- เปิด query เฉพาะเมื่อ modal/library ต้องใช้ข้อมูล

Mutations:

- create set: `POST /bank/quizzes`
- rename/edit set: `PATCH /bank/quizzes/{id}`
- delete set: `DELETE /bank/quizzes/{id}`
- save generated question to set: `POST /bank/quizzes/{setId}/questions`
- update bank question: `PATCH /bank/questions/{qid}`
- export PDF: `POST /export/quizzes/{id}`

## End-to-End Data Flow

### สรุปเอกสารและบันทึกประวัติ

```text
Frontend
  -> ผู้ใช้ใส่ข้อความหรืออัปโหลด PDF
  -> /pdf/extract ถ้าเป็น PDF
  -> /summarize พร้อม Bearer token หรือ X-User-Id
Backend
  -> get_current_user()
  -> SummarizeService
  -> OpenAI รอบ sections
  -> OpenAI รอบ overview/key_points/data_points
  -> log_user_event(users/{uid}/summaries)
Frontend
  -> render summary
  -> /history/save หรือ /history/update/{id}
Backend
  -> HistoryService
  -> Firestore users/{uid}/histories
```

### สร้างข้อสอบ

```text
Frontend useQuiz
  -> /quiz/topics เพื่อเตรียมหัวข้อ
  -> /quiz/mcq หรือ /quiz/tf พร้อม context, n, exclude, topics
Backend QuizService
  -> OpenAI สร้าง batch
  -> filter_near_dups
  -> retry ถ้ายังได้ไม่ครบ
Frontend
  -> normalize/shuffle
  -> append questions
  -> update history
```

### บันทึกคำถามเข้าคลัง

```text
Frontend useBank
  -> POST /bank/quizzes/{quiz_id}/questions
Backend BankService
  -> โหลด quizzes จาก Firestore
  -> โหลด questions จาก Firestore
  -> ตรวจ near duplicate ในชุด
  -> create question
  -> append question id เข้า quiz set
  -> อัปเดต Firestore กลับ
```

### Export PDF

```text
Frontend useBank.exportSetPdf
  -> POST /export/quizzes/{quiz_id}
Backend export route
  -> โหลด quiz set + questions
  -> render PDF ด้วย ReportLab
  -> ใช้ THSarabunNew ถ้ามี
  -> ส่ง StreamingResponse
Frontend
  -> อ่าน Content-Disposition
  -> สร้าง object URL
  -> trigger download
```

## Storage Strategy

| ข้อมูล | ที่เก็บ | เหตุผล/พฤติกรรม |
|---|---|---|
| Notes | Firestore `users/{uid}/notes` | ย้ายขึ้น Cloud เพื่อรองรับ PaaS และการเข้าถึงข้ามอุปกรณ์ |
| Quiz questions | Firestore `users/{uid}/bank/questions` | คลังคำถามรายผู้ใช้ เก็บบน Cloud |
| Quiz sets | Firestore `users/{uid}/bank/quizzes` | ชุดข้อสอบที่อ้าง question ids |
| History | Firestore `users/{uid}/histories` | ต้อง sync ข้าม session/device |
| Summary logs | Firestore `users/{uid}/summaries` | logging หลัง summarize |
| Auth | Firebase Auth | มาตรฐาน login และ token verification |

## Error Handling สำคัญ

Backend:

- empty context: `400`
- PDF ไม่ใช่ `.pdf`: `400`
- PDF อ่าน text ไม่ได้: `422`
- auth missing/invalid: `401`
- Firebase auth server ไม่พร้อมตอน verify token: `500`
- quiz/summary/qa OpenAI error: `500`
- quiz set/question ไม่พบ: `404`
- question duplicate ใน set: `409`
- Firestore ไม่เชื่อมต่อใน write operations: `500`

Frontend:

- `apiFetch` อ่าน error จาก JSON field `detail` ถ้ามี
- throw เป็น `ApiError(status, message)`
- ใช้ Zod validate response เพื่อกัน shape ไม่ตรง
- บาง feature เช่น `/quiz/topics` เป็น optional จึง catch แล้วไม่ขัด flow หลัก

## การรันระบบ

### Backend

ติดตั้ง dependencies:

```bash
pip install -r requirements.txt
# สำหรับ development (เช่น รันเทสต์)
pip install -r requirements-dev.txt
```

ตั้งค่า `.env` ที่ root:

```env
OPENAI_API_KEY=your_openai_api_key
FIREBASE_PROJECT_ID=your_firebase_project_id
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ALLOW_DEMO_AUTH=true
```

รัน API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

ค่า env ฝั่ง frontend ที่เกี่ยวข้อง:

```env
NEXT_PUBLIC_API=http://localhost:8000
NEXT_PUBLIC_ALLOW_DEMO_AUTH=true
```

URL:

```text
http://localhost:3000
```

## Tests

โฟลเดอร์ `tests/` มี backend unit tests:

```text
tests/
├── conftest.py
├── test_nlp.py
└── test_bank_service.py
```

รัน:

```bash
pytest
```

ขอบเขต test ที่เห็นจากชื่อไฟล์:

- NLP/similarity/near duplicate logic
- Bank service behavior

## จุดเด่นของระบบ

- แยก backend เป็น module ชัดเจน ไม่กระจุกในไฟล์เดียว
- Route layer บางและอ่านง่าย
- Auth dependency ใช้ซ้ำได้ทุก endpoint
- AI service แยกเป็น summarize/quiz/qa ทำให้ปรับ prompt ได้เป็นส่วน ๆ
- Summary ใช้ 2-step generation เพื่อให้ได้ sections ก่อน แล้วค่อย overview/data points
- Quiz generation มีการกันคำถามซ้ำทั้งจาก exclude และใน batch
- ข้อมูลระบบจัดเก็บลง Firestore เป็นหลัก (Notes, Quiz bank, History) เพื่อลดการพึ่งพาระบบไฟล์ Local และรองรับการทำ Scalability หรือ PaaS Hosting อย่าง Azure
- History ใช้ Firestore เหมาะกับข้อมูล session ที่ควรตาม user ไปได้
- Frontend มี service/hook layer แยก logic จาก UI มากขึ้น
- ใช้ Zod validate API response ฝั่ง frontend เพิ่มความทนทานต่อ schema ผิดรูป

## ข้อสังเกตและจุดที่ควรระวัง

- `OPENAI_API_KEY` เป็น required ตอน import config ถ้าไม่มี key แม้แต่ health endpoint ก็เริ่ม server ไม่ได้
- บาง AI endpoints เช่น `/quiz/*` และ `/qa` ยังไม่บังคับ auth ต่างจาก `/summarize`
- `shuffleChoices` ตอน export PDF ควรตรวจเรื่องการ remap เฉลยก่อนใช้จริงกับเอกสารที่ต้องแจกผู้เรียน
- ถ้า Firebase init ไม่สำเร็จ ระบบบางส่วนยังทำงานได้ แต่ history/auth แบบ Bearer จะใช้งานไม่ได้
- ข้อความภาษาไทยในบางไฟล์อาจแสดง mojibake ใน terminal บาง encoding แต่โค้ดเปิดไฟล์ด้วย UTF-8 ในจุดที่อ่าน/เขียน JSON
- `QuizHistoryIn` และบาง model ใช้ default list/dict ตรง ๆ ควรพิจารณาเปลี่ยนเป็น `Field(default_factory=...)` เพื่อความชัดเจน

## สรุปเชิงสถาปัตยกรรม

EduGen API เป็น backend ที่ออกแบบเป็นระบบชั้น ๆ ค่อนข้างชัดเจน: `routes` รับ request, `models` validate ข้อมูล, `services` ทำ business logic, `utils` รวมเครื่องมือพื้นฐาน, `db` รับผิดชอบ Firebase/Firestore และ `core` เก็บ config/security ระบบจึงขยาย feature ได้ง่าย เช่น เพิ่ม endpoint ใหม่โดยเพิ่ม route + service + model ตามรูปแบบเดิม

ในภาพรวม workflow หลักของระบบคือ frontend ส่ง context จากข้อความ/PDF ไป backend, backend ประมวลผลด้วย OpenAI แล้ว frontend นำผลลัพธ์ไปแสดงและบันทึกข้อมูลหลักทั้งหมดลง Firestore การเปลี่ยนผ่านจาก local storage ไปยัง Firestore ช่วยเพิ่มขีดความสามารถให้ระบบสามารถนำไปรันบน Container หรือบริการ PaaS เช่น Azure App Service ได้อย่างไร้รอยต่อ
