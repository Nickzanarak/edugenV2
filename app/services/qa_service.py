import re
from typing import List

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_service import client
from app.utils.chunking import build_chunk_index, chunk_page_range
from app.utils.timing import timed
from app.utils.chunking import build_chunks_semantic as build_chunks

AI_MODEL = settings.AI_MODEL
# จำนวนก้อนสูงสุดที่จะหยิบมาตอบ 1 คำถาม
MAX_PICKED_CHUNKS = 3

# ใช้ดึงเลขหน้าจากป้าย [หน้า X] ในเนื้อหา
_PAGE_NUM_RE = re.compile(r"\[หน้า\s*(\d+)\]")
# ใช้จับบรรทัด [หน้าอ้างอิง: 1,3] ที่ AI เขียนต่อท้ายคำตอบ
_REF_LINE_RE = re.compile(r"\[\s*หน้าอ้างอิง\s*[:：]\s*([\d\s,\-–]+)\]\s*$")


class QAService:
    @staticmethod
    def _split_ref_line(text: str):
        """แยกบรรทัด [หน้าอ้างอิง: ...] ท้ายคำตอบออกมา
        คืน (คำตอบที่ตัดบรรทัดนั้นออกแล้ว, รายการเลขหน้า)
        ถ้า AI ไม่ได้เขียนบรรทัดนี้ จะคืนคำตอบเดิมกับรายการว่าง
        """
        m = _REF_LINE_RE.search(text.strip())
        if not m:
            return text.strip(), []
        pages = sorted({int(n) for n in re.findall(r"\d+", m.group(1))})
        cleaned = _REF_LINE_RE.sub("", text.strip()).strip()
        return cleaned, pages

    @staticmethod
    def _format_pages(pages: List[int]) -> str:
        """จัดรูปแบบเลขหน้าให้อ่านง่าย เช่น [1] -> 'หน้า 1', [1,3] -> 'หน้า 1, 3'"""
        if not pages:
            return ""
        return "หน้า " + ", ".join(str(p) for p in pages)

    @staticmethod
    def _pick_chunks(index_text: str, question: str, total: int) -> List[int]:
        """ให้ AI ดูสารบัญ แล้วบอกว่าคำถามนี้น่าจะอยู่ก้อนไหน (คืนเป็นเลขก้อน เริ่มที่ 1)"""
        prompt = f"""
ด้านล่างคือสารบัญของเอกสาร แบ่งเป็นก้อน ๆ พร้อมตัวอย่างเนื้อหาต้นก้อน
จงเลือกก้อนที่ "น่าจะมีคำตอบ" ของคำถามมากที่สุด ไม่เกิน {MAX_PICKED_CHUNKS} ก้อน

- ตอบเป็นตัวเลขก้อนเท่านั้น คั่นด้วยจุลภาค เช่น: 2,5
- ถ้าไม่แน่ใจ ให้เลือกก้อนที่ใกล้เคียงที่สุด ห้ามตอบว่าไม่มี
- เลือกได้เฉพาะเลข 1 ถึง {total}

สารบัญ:
{index_text}

คำถาม: {question}

ตอบ (เลขก้อนเท่านั้น):
"""
        try:
            r = client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = (r.choices[0].message.content or "").strip()
            nums = [int(n) for n in re.findall(r"\d+", raw)]
            picked = [n for n in nums if 1 <= n <= total][:MAX_PICKED_CHUNKS]
            return picked or [1]
        except Exception:
            # เลือกไม่ได้ → ใช้ก้อนแรกไปก่อน ดีกว่าล้ม
            return [1]

    @staticmethod
    def answer(context: str, question: str) -> dict:
        ctx = (context or "").strip()
        q = (question or "").strip()
        if not ctx or not q:
            raise HTTPException(400, "context/question ว่าง")

        chunks = build_chunks(ctx)
        if not chunks:
            raise HTTPException(400, "context ว่าง")

        # เนื้อหาที่ผู้ใช้พิมพ์เองไม่มีป้าย [หน้า X] จึงไม่ควรแสดงแหล่งอ้างอิง
        # (ต้องเช็คจากข้อความต้นฉบับ เพราะตัวแบ่งก้อนจะใส่ "หน้า 1" ให้อัตโนมัติ)
        has_page_labels = "[หน้า" in ctx

        if len(chunks) == 1:
            # เอกสารสั้น — ส่งทั้งหมดเลย ไม่ต้องเลือกก้อน
            source_text = chunks[0]
            source_note = chunk_page_range(chunks[0])
        else:
            # เอกสารยาว — ให้ AI เลือกก้อนที่เกี่ยวข้องก่อน แล้วค่อยส่ง "เนื้อหาเต็ม" ของก้อนนั้นไปตอบ
            index_text = build_chunk_index(chunks)
            with timed("qa: pick chunks", f"จาก {len(chunks)} ก้อน"):
                picked = QAService._pick_chunks(index_text, q, len(chunks))
            selected = [chunks[i - 1] for i in picked]
            source_text = "\n\n".join(selected)
            ranges = ", ".join(chunk_page_range(c) for c in selected)
            source_note = ranges

        # รายการเลขหน้าที่อยู่ในเนื้อหาที่ส่งให้ AI จริง — ใช้ตรวจว่า AI ไม่ได้มั่วเลขหน้า
        pages_in_source = {int(n) for n in _PAGE_NUM_RE.findall(source_text)}

        prompt = f"""
ตอบคำถามโดยอ้างอิง "เฉพาะ" เนื้อหาที่ให้ด้านล่างเท่านั้น
- ตอบให้ละเอียด ครบถ้วน อ้างอิงข้อมูลจริงในเนื้อหา
- ห้ามใส่ป้าย [หน้า X] หรือเลขหน้าปนลงไปในเนื้อคำตอบ
- ถ้าไม่พบคำตอบจริง ๆ ให้ตอบว่า: ไม่พบในเนื้อหาที่ให้มา

เมื่อตอบเสร็จแล้ว ให้ขึ้นบรรทัดใหม่บรรทัดสุดท้าย เขียนเลขหน้าที่ใช้ตอบในรูปแบบนี้เท่านั้น
[หน้าอ้างอิง: 1,3]
โดยดูจากป้าย [หน้า X] ที่กำกับอยู่เหนือข้อความที่คุณหยิบมาตอบ
ถ้าใช้หน้าเดียวก็เขียนเลขเดียว เช่น [หน้าอ้างอิง: 2]

เนื้อหา:
{source_text}

คำถาม: {q}
ตอบ:
"""
        try:
            with timed("qa: answer", f"{len(source_text)} ตัวอักษร"):
                res = client.chat.completions.create(
                    model=AI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.15,
                )
            raw_answer = (res.choices[0].message.content or "").strip()

            # แยกบรรทัด [หน้าอ้างอิง: ...] ออกจากคำตอบ
            # ถ้า AI ระบุหน้ามาถูกต้อง จะใช้เลขหน้านั้นแทนช่วงหน้าทั้งก้อน (แม่นกว่า)
            answer_text, ai_pages = QAService._split_ref_line(raw_answer)
            valid_pages = [p for p in ai_pages if p in pages_in_source]
            if valid_pages:
                source_note = QAService._format_pages(valid_pages)

            # ไม่มีป้ายหน้าจริง (เช่นผู้ใช้พิมพ์เอง) → ไม่ต้องแสดงแหล่งอ้างอิง
            if not has_page_labels or source_note == "ไม่ระบุหน้า":
                source_note = ""
            return {"answer": answer_text, "source": source_note}
        except Exception as e:
            raise HTTPException(500, f"QA failed: {e}") from e