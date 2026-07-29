import re
from typing import List

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_service import client
from app.utils.chunking import build_chunk_index, chunk_page_range
from app.utils.chunking import build_chunks_semantic as build_chunks

AI_MODEL = settings.AI_MODEL
# จำนวนก้อนสูงสุดที่จะหยิบมาตอบ 1 คำถาม
MAX_PICKED_CHUNKS = 3


class QAService:
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

        if len(chunks) == 1:
            # เอกสารสั้น — ส่งทั้งหมดเลย ไม่ต้องเลือก
            source_text = chunks[0]
            source_note = ""
        else:
            # เอกสารยาว — ให้ AI เลือกก้อนที่เกี่ยวข้องก่อน แล้วค่อยส่ง "เนื้อหาเต็ม" ของก้อนนั้นไปตอบ
            index_text = build_chunk_index(chunks)
            picked = QAService._pick_chunks(index_text, q, len(chunks))
            selected = [chunks[i - 1] for i in picked]
            source_text = "\n\n".join(selected)
            ranges = ", ".join(chunk_page_range(c) for c in selected)
            source_note = ranges

        prompt = f"""
ตอบคำถามโดยอ้างอิง "เฉพาะ" เนื้อหาที่ให้ด้านล่างเท่านั้น
- ตอบให้ละเอียด ครบถ้วน อ้างอิงข้อมูลจริงในเนื้อหา
- ถ้าเนื้อหามีเลขหน้ากำกับ ให้ระบุด้วยว่าอ้างอิงจากหน้าไหน
- ถ้าไม่พบคำตอบจริง ๆ ให้ตอบว่า: ไม่พบในเนื้อหาที่ให้มา

เนื้อหา:
{source_text}

คำถาม: {q}
ตอบ:
"""
        try:
            res = client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
            )
            answer_text = (res.choices[0].message.content or "").strip()
            return {"answer": answer_text, "source": source_note}
        except Exception as e:
            raise HTTPException(500, f"QA failed: {e}") from e