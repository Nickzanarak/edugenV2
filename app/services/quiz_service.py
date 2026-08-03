from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_service import client
from app.utils.nlp import filter_near_dups, similar
from app.utils.chunking import chunk_page_range, sample_across_document
from app.utils.chunking import build_chunks_semantic as build_chunks
from app.utils.timing import timed
from app.utils.text import safe_json_loads


class QuizService:
    CHOICE_LETTERS = ["ก", "ข", "ค", "ง", "จ", "ฉ"]

    # จำนวนก้อนที่ยิง AI พร้อมกันตอนออกข้อสอบจากเอกสารยาว
    QUIZ_MAP_CONCURRENCY = 4

    BANNED_PATTERNS = [
        "ทั้งหมดที่กล่าวมา", "ทุกข้อข้างต้น", "ถูกทุกข้อ", "ผิดทุกข้อ",
        "ทั้งหมดข้างต้น", "ไม่มีข้อใดถูก", "ไม่มีข้อถูก", "ไม่ถูกสักข้อ",
        "all of the above", "none of the above",
    ]

    DIFFICULTY_PROMPTS = {
        "easy": """ระดับความยาก: ง่าย
- ถามข้อเท็จจริงตรง ๆ ที่ปรากฏชัดเจนในเนื้อหา จำได้ก็ตอบได้
- ห้ามต้องตีความหรือวิเคราะห์
- ตัวเลือกลวงต้องผิดชัดเจน แยกออกง่ายทันที""",
        "medium": """ระดับความยาก: ปานกลาง
- ต้องเข้าใจความหมาย ไม่ใช่แค่จำข้อความ
- อาจต้องเชื่อมโยงข้อมูล 2 จุดในเนื้อหาเข้าด้วยกัน
- ตัวเลือกลวงดูมีเหตุผลระดับหนึ่ง ต้องอ่านให้ดีก่อนตัด""",
        "hard": """ระดับความยาก: ยาก
- ต้องใช้การวิเคราะห์ เปรียบเทียบ คำนวณ หรือเชื่อมโยงข้อมูลหลายจุดเข้าด้วยกัน จึงจะตอบได้
- คำตอบต้องไม่ใช่ข้อความที่ลอกมาจากเนื้อหาตรง ๆ ผู้ตอบต้องคิดต่อเอง
- ห้ามถามวนกลับ: ห้ามให้โจทย์บอกคำตอบไว้ในตัวคำถามเอง
- ห้ามใส่ฉากสมมติที่ไม่ได้เพิ่มการคิด (ห่อคำถามง่ายด้วยสถานการณ์ปลอม)
- ตัวเลือกลวงต้องใกล้เคียงคำตอบจริง ถูกบางส่วนแต่ผิดรายละเอียด จนต้องคิดรอบคอบ
- ถ้าเนื้อหาไม่ลึกพอจะออกข้อยากได้จริง ให้ออกข้อที่ต้องคำนวณหรือเปรียบเทียบจากข้อมูลที่มี แทนการแต่งฉากสมมติ""",
    }

    @staticmethod
    def _difficulty_block(difficulty: Optional[str]) -> str:
        key = (difficulty or "medium").strip().lower()
        block = QuizService.DIFFICULTY_PROMPTS.get(key, QuizService.DIFFICULTY_PROMPTS["medium"])
        return block + "\n"

    @staticmethod
    def _clamp_choices(choices_count: Optional[int]) -> int:
        try:
            c = int(choices_count or 4)
        except (TypeError, ValueError):
            c = 4
        return max(4, min(6, c))

    @staticmethod
    def _has_banned_choice(q: Dict[str, Any]) -> bool:
        for c in q.get("choices") or []:
            text = str(c).lower()
            if any(p in text for p in QuizService.BANNED_PATTERNS):
                return True
        return False

    @staticmethod
    def extract_topics(context: str) -> List[str]:
        ctx = (context or "").strip()
        if not ctx:
            raise HTTPException(400, "context ว่าง")

        prompt = f"""
สกัดหัวข้อ/แนวคิดสำคัญจากเนื้อหาด้านล่าง (ไม่เกิน 30 หัวข้อ)
ตอบ JSON: {{"topics":["หัวข้อ1","หัวข้อ2"]}}
เนื้อหา:
{sample_across_document(ctx, settings.CTX_CHAR_LIMIT)}
"""
        try:
            r = client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = safe_json_loads(r.choices[0].message.content, {"topics": []})
            return [str(t).strip() for t in data.get("topics", []) if str(t).strip()]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Topics generation failed: {e}") from e

    @staticmethod
    def generate_mcq(
        context: str,
        n: int,
        exclude: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
        choices_count: Optional[int] = 4,
    ) -> List[Dict[str, Any]]:
        return QuizService._generate_batch("mcq", context, n, exclude, topics, difficulty, choices_count)

    @staticmethod
    def generate_tf(
        context: str,
        n: int,
        exclude: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
    ) -> List[Dict[str, Any]]:
        return QuizService._generate_batch("tf", context, n, exclude, topics, difficulty, 4)

    @staticmethod
    def _generate_batch(
        qtype: str,
        context: str,
        n: int,
        exclude: Optional[List[str]],
        topics: Optional[List[str]],
        difficulty: Optional[str] = "medium",
        choices_count: Optional[int] = 4,
    ) -> List[Dict[str, Any]]:
        """ตัวกระจายงาน:
        - เอกสารสั้น (ก้อนเดียว) -> ใช้วิธีเดิม ยิงรอบเดียว
        - เอกสารยาว (หลายก้อน) -> แบ่งโควตาข้อไปตามก้อน แล้วออกข้อสอบจากทุกก้อน
          เพื่อให้ข้อสอบครอบคลุมทั้งเอกสาร ไม่กระจุกอยู่ช่วงใดช่วงหนึ่ง
        """
        ctx = (context or "").strip()
        if not ctx:
            raise HTTPException(400, "context ว่าง")
        count = max(1, min(15, int(n or 5)))

        chunks = build_chunks(ctx)

        # เอกสารสั้น -> ทางเดิม
        if len(chunks) <= 1:
            return QuizService._generate_from_text(
                qtype, ctx, count, exclude, topics, difficulty, choices_count
            )

        # ---- เอกสารยาว: แบ่งโควตาข้อให้แต่ละก้อน ----
        # ถ้าจำนวนข้อน้อยกว่าจำนวนก้อน ให้เลือกก้อนแบบกระจาย (ก้อนละ 1 ข้อ)
        if count <= len(chunks):
            step = len(chunks) / count
            picked = [(int(i * step), 1) for i in range(count)]
        else:
            base = count // len(chunks)
            remainder = count % len(chunks)
            picked = [
                (i, base + (1 if i < remainder else 0))
                for i in range(len(chunks))
            ]
            picked = [(i, q) for i, q in picked if q > 0]

        exclude_list = [str(x).strip() for x in (exclude or []) if str(x).strip()]
        topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()]

        def work(job):
            idx, quota = job
            # แบ่ง topic hints ให้แต่ละก้อนคนละส่วน กันออกข้อซ้ำหัวข้อกัน
            hints = topic_list[idx::len(chunks)] if topic_list else None
            try:
                return QuizService._generate_from_text(
                    qtype,
                    chunks[idx],
                    quota,
                    exclude_list,
                    hints,
                    difficulty,
                    choices_count,
                    max_tries=3,   # ต่อก้อนไม่ต้องพยายามหนักเท่ากรณีก้อนเดียว
                )
            except Exception:
                return []   # ก้อนเดียวพัง ไม่ให้ล้มทั้งคำขอ

        with timed("quiz: map", f"{len(picked)} ก้อน จาก {len(chunks)} ก้อน, ขอ {count} ข้อ"):
            with ThreadPoolExecutor(max_workers=len(picked)) as pool:
                results = list(pool.map(work, picked))

        # ---- รวมผล + กรองข้อซ้ำข้ามก้อน ----
        collected: List[Dict[str, Any]] = []
        for batch in results:
            for q in batch:
                if len(collected) >= count:
                    break
                if all(
                    similar(str(q.get("question", "")), str(e.get("question", "")))
                    < settings.NEAR_DUP_THRESHOLD
                    for e in collected
                ):
                    collected.append(q)

        # ---- ถ้ายังไม่ครบ (บางก้อนเนื้อหาบาง) เก็บตกจากก้อนที่ยาวที่สุด ----
        if len(collected) < count:
            need = count - len(collected)
            richest = max(range(len(chunks)), key=lambda i: len(chunks[i]))
            excludes_now = exclude_list + [str(q.get("question") or "") for q in collected]
            try:
                extra = QuizService._generate_from_text(
                    qtype, chunks[richest], need, excludes_now, None,
                    difficulty, choices_count, max_tries=3,
                )
                for q in extra:
                    if len(collected) >= count:
                        break
                    if all(
                        similar(str(q.get("question", "")), str(e.get("question", "")))
                        < settings.NEAR_DUP_THRESHOLD
                        for e in collected
                    ):
                        collected.append(q)
            except Exception:
                pass

        return collected[:count]

    @staticmethod
    def _generate_from_text(
        qtype: str,
        context: str,
        n: int,
        exclude: Optional[List[str]],
        topics: Optional[List[str]],
        difficulty: Optional[str] = "medium",
        choices_count: Optional[int] = 4,
        max_tries: int = 6,
    ) -> List[Dict[str, Any]]:
        """ออกข้อสอบจากข้อความก้อนเดียว (ตรรกะเดิม) — ใช้ทั้งกรณีเอกสารสั้นและแต่ละก้อนของเอกสารยาว"""
        ctx = (context or "").strip()
        count = max(1, min(15, int(n or 5)))
        if not ctx:
            raise HTTPException(400, "context ว่าง")

        exclude_list = [str(x).strip() for x in (exclude or []) if str(x).strip()]
        topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()] or None

        collected: List[Dict[str, Any]] = []
        tries = 0

        while len(collected) < count and tries < max_tries:
            need = count - len(collected)
            excludes_now = exclude_list + [str(q.get("question") or "") for q in collected]
            topic_hints = topic_list[:need] if topic_list else None
            request_n = need + 5

            if qtype == "mcq":
                batch = QuizService._gen_mcq_once(ctx, request_n, excludes_now, topic_hints, difficulty, choices_count)
            else:
                batch = QuizService._gen_tf_once(ctx, request_n, excludes_now, topic_hints, difficulty)

            for q in batch:
                if len(collected) >= count:
                    break   
                if all(
                    similar(str(q.get("question", "")), str(e.get("question", "")))
                    < settings.NEAR_DUP_THRESHOLD
                    for e in collected
                ):
                    collected.append(q)

            if topic_list:
                used = {str(q.get("topic", "")).strip().lower() for q in collected}
                topic_list = [t for t in topic_list if str(t).strip().lower() not in used]
            tries += 1

        return collected[:count]

    @staticmethod
    def _gen_mcq_once(
        ctx: str,
        n: int,
        exclude_list: List[str],
        topic_hints: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
        choices_count: Optional[int] = 4,
    ) -> List[Dict[str, Any]]:
        exclude_block = ""
        if exclude_list:
            exclude_block = (
                "หลีกเลี่ยงการตั้งคำถามคล้ายกับ:\n"
                + "\n".join(f"- {q}" for q in exclude_list[: settings.EXCLUDE_LIST_LIMIT])
                + "\n"
            )
        topic_block = ""
        if topic_hints:
            topic_block = (
                "ให้สร้าง 'หัวข้อละ 1 ข้อ' จากหัวข้อต่อไปนี้:\n"
                + "\n".join(f"- {t}" for t in topic_hints[:n])
                + "\n"
            )

        difficulty_block = QuizService._difficulty_block(difficulty)

        cc = QuizService._clamp_choices(choices_count)
        letters = QuizService.CHOICE_LETTERS[:cc]
        letters_text = " ".join(letters)
        choices_example = ", ".join(f'"{l}) ..."' for l in letters)
        answer_options = "|".join(letters)

        prompt = f"""
สร้างข้อสอบปรนัย {n} ข้อ จากเนื้อหาด้านล่าง
- แต่ละข้อต้องมีตัวเลือก {cc} ตัวเลือกพอดี คือ {letters_text} เท่านั้น ห้ามมากหรือน้อยกว่านี้
- คำตอบถูกมีเพียงข้อเดียว

*** ข้อห้ามเด็ดขาด (สำคัญที่สุด) ***
ห้ามสร้างตัวเลือกที่รวมตัวเลือกอื่น เช่น "ทั้งหมดที่กล่าวมา", "ถูกทุกข้อ", "ข้อ ก และ ข", "ไม่มีข้อใดถูก", "ทุกข้อข้างต้น" หรือข้อความใด ๆ ที่มีความหมายทำนองนี้ — เด็ดขาด ทุกกรณี
ตัวเลือกทุกตัวต้องเป็นคำตอบที่เป็นอิสระต่อกัน และมีเพียงตัวเดียวที่ถูก

- ตัวเลือกลวงทุกตัวต้องเกี่ยวข้องกับเนื้อหา ห้ามใส่ตัวเลือกที่ไม่มีความหมายเพื่อให้ครบจำนวน
- ถ้าเนื้อหาไม่พอจะสร้างตัวเลือกลวงที่ดีครบ {cc} ตัว ให้เปลี่ยนไปตั้งคำถามจากแง่มุมอื่นของเนื้อหาแทน
- ตอบ JSON: {{"questions":[{{"type":"mcq","question":"...","choices":[{choices_example}],"answer":"{answer_options}","explain":"...","topic":"..."}}]}}

{difficulty_block}
{topic_block}{exclude_block}
เนื้อหา:
{sample_across_document(ctx, settings.CTX_CHAR_LIMIT)}
"""
        r = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = safe_json_loads(r.choices[0].message.content, {"questions": []})
        questions = [q for q in data.get("questions", []) if not QuizService._has_banned_choice(q)]
        return filter_near_dups(questions, exclude_list, threshold=settings.NEAR_DUP_THRESHOLD)

    @staticmethod
    def _gen_tf_once(
        ctx: str,
        n: int,
        exclude_list: List[str],
        topic_hints: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
    ) -> List[Dict[str, Any]]:
        exclude_block = ""
        if exclude_list:
            exclude_block = (
                "หลีกเลี่ยงการตั้งคำถามคล้ายกับ:\n"
                + "\n".join(f"- {q}" for q in exclude_list[: settings.EXCLUDE_LIST_LIMIT])
                + "\n"
            )
        topic_block = ""
        if topic_hints:
            topic_block = (
                "ให้สร้าง 'หัวข้อละ 1 ข้อ' จากหัวข้อต่อไปนี้:\n"
                + "\n".join(f"- {t}" for t in topic_hints[:n])
                + "\n"
            )

        difficulty_block = QuizService._difficulty_block(difficulty)

        prompt = f"""
สร้างข้อสอบ ถูก/ผิด จำนวน {n} ข้อ จากเนื้อหาด้านล่าง
- ให้เหตุผลสั้น ๆ ทุกข้อ
- ตอบ JSON: {{"questions":[{{"type":"tf","question":"...","answer":"true|false","explain":"...","topic":"..."}}]}}

{difficulty_block}
{topic_block}{exclude_block}
เนื้อหา:
{sample_across_document(ctx, settings.CTX_CHAR_LIMIT)}
"""
        r = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        data = safe_json_loads(r.choices[0].message.content, {"questions": []})
        return filter_near_dups(data.get("questions", []), exclude_list, threshold=settings.NEAR_DUP_THRESHOLD)