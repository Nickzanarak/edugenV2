from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_service import client
from app.utils.nlp import filter_near_dups, similar
from app.utils.chunking import sample_across_document
from app.utils.chunking import build_chunks_semantic as build_chunks
from app.utils.timing import timed
from app.utils.text import safe_json_loads
from app.services import quiz_prompts as P


class QuizService:
    CHOICE_LETTERS = ["ก", "ข", "ค", "ง", "จ", "ฉ"]

    BANNED_PATTERNS = [
        "ทั้งหมดที่กล่าวมา", "ทุกข้อข้างต้น", "ถูกทุกข้อ", "ผิดทุกข้อ",
        "ทั้งหมดข้างต้น", "ไม่มีข้อใดถูก", "ไม่มีข้อถูก", "ไม่ถูกสักข้อ",
        "all of the above", "none of the above",
    ]

    @staticmethod
    def _normalize_exclude(exclude) -> List[Dict[str, str]]:
        """ทำรายการข้อที่มีอยู่แล้วให้เป็นรูปเดียวกัน {question, answer}

        รับได้ทั้งข้อความล้วน (แบบเดิม) และ dict ที่มีเฉลยมาด้วย (แบบใหม่)
        เฉลยช่วยให้ AI ตัดสินได้ว่าข้อใหม่ซ้ำของเดิมจริงไหม
        """
        out: List[Dict[str, str]] = []
        for x in (exclude or []):
            if isinstance(x, dict):
                q = str(x.get("question") or "").strip()
                a = str(x.get("answer") or x.get("answer_text") or "").strip()
            elif hasattr(x, "question"):
                # Pydantic แปลง JSON เป็นอ็อบเจ็กต์ ไม่ใช่ dict จึงต้องรับกรณีนี้ด้วย
                q = str(getattr(x, "question", "") or "").strip()
                a = str(getattr(x, "answer", "") or "").strip()
            else:
                q, a = str(x).strip(), ""
            if q:
                out.append({"question": q, "answer": a})
        return out

    @staticmethod
    def _is_valid_tf(q: Dict[str, Any], mode: str) -> bool:
        """ตาข่ายกันพลาดของข้อสอบถูก/ผิด (ไม่ได้พิสูจน์ว่าเฉลยถูกตามความจริง)

        โหมดประยุกต์เพิ่มการเทียบช่อง verdict กับ answer
        เพราะพบว่า AI คิดคำตอบถูกแต่กรอก answer สลับข้าง
        """
        if not str(q.get("question") or "").strip():
            return False

        ans = str(q.get("answer") or "").strip().lower()
        if ans in ("true", "จริง", "ถูก", "t", "1"):
            ans = "true"
        elif ans in ("false", "เท็จ", "ผิด", "f", "0"):
            ans = "false"
        else:
            return False

        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return True

        verdict = str(q.get("verdict") or "").strip()
        if not verdict:
            return False
        if verdict == P.VERDICT_TRUE:
            return ans == "true"
        if verdict == P.VERDICT_FALSE:
            return ans == "false"
        return False

    @staticmethod
    def _clamp_choices(choices_count: Optional[int]) -> int:
        try:
            c = int(choices_count or 4)
        except (TypeError, ValueError):
            c = 4
        return max(4, min(6, c))

    @staticmethod
    def _is_valid_mcq(q: Dict[str, Any], cc: int) -> bool:
        """ตาข่ายกันพลาด: ตรวจว่าข้อสอบที่ AI ส่งมาใช้งานได้จริง
        (prompt สั่งไปแล้วแต่ AI ไม่ทำตามได้เสมอ จึงต้องเช็คซ้ำที่โค้ด)
        """
        choices = q.get("choices") or []
        if not isinstance(choices, list) or len(choices) != cc:
            return False

        # ตัวเลือกต้องไม่ว่างและไม่ซ้ำกันเอง
        texts = []
        for c in choices:
            t = QuizService._strip_choice_prefix(str(c)).strip().lower()
            if not t:
                return False
            texts.append(t)
        if len(set(texts)) != len(texts):
            return False

        # answer ต้องเป็นตัวอักษรที่อยู่ในช่วงตัวเลือกจริง
        ans = str(q.get("answer", "")).strip()
        valid_letters = QuizService.CHOICE_LETTERS[:cc]
        if ans not in valid_letters:
            return False
        return True

    @staticmethod
    def _strip_choice_prefix(text: str) -> str:
        """ตัดหัวข้อแบบ 'ก) ' หรือ 'ก. ' ออก เพื่อเทียบเนื้อความจริง"""
        t = text.strip()
        for letter in QuizService.CHOICE_LETTERS:
            for sep in (") ", ". ", ")", "."):
                pre = letter + sep
                if t.startswith(pre):
                    return t[len(pre):]
        return t

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
        mode: Optional[str] = P.MODE_SOURCE,
    ) -> List[Dict[str, Any]]:
        return QuizService._generate_batch("mcq", context, n, exclude, topics, difficulty, choices_count, mode)

    @staticmethod
    def generate_tf(
        context: str,
        n: int,
        exclude: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
        mode: Optional[str] = P.MODE_SOURCE,
    ) -> List[Dict[str, Any]]:
        return QuizService._generate_batch("tf", context, n, exclude, topics, difficulty, 4, mode)

    @staticmethod
    def _generate_batch(
        qtype: str,
        context: str,
        n: int,
        exclude: Optional[List[str]],
        topics: Optional[List[str]],
        difficulty: Optional[str] = "medium",
        choices_count: Optional[int] = 4,
        mode: Optional[str] = P.MODE_SOURCE,
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
                qtype, ctx, count, exclude, topics, difficulty, choices_count, mode=mode
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

        exclude_list = QuizService._normalize_exclude(exclude)
        topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()]
        dup_threshold = P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD)

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
                    mode=mode,
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
                    < dup_threshold
                    for e in collected
                ):
                    collected.append(q)

        # ---- ถ้ายังไม่ครบ (บางก้อนเนื้อหาบาง) เก็บตกจากก้อนที่ยาวที่สุด ----
        if len(collected) < count:
            need = count - len(collected)
            richest = max(range(len(chunks)), key=lambda i: len(chunks[i]))
            excludes_now = exclude_list + QuizService._normalize_exclude(collected)
            try:
                extra = QuizService._generate_from_text(
                    qtype, chunks[richest], need, excludes_now, None,
                    difficulty, choices_count, max_tries=3, mode=mode,
                )
                for q in extra:
                    if len(collected) >= count:
                        break
                    if all(
                        similar(str(q.get("question", "")), str(e.get("question", "")))
                        < dup_threshold
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
        mode: Optional[str] = P.MODE_SOURCE,
    ) -> List[Dict[str, Any]]:
        """ออกข้อสอบจากข้อความก้อนเดียว (ตรรกะเดิม) — ใช้ทั้งกรณีเอกสารสั้นและแต่ละก้อนของเอกสารยาว"""
        ctx = (context or "").strip()
        count = max(1, min(15, int(n or 5)))
        if not ctx:
            raise HTTPException(400, "context ว่าง")

        exclude_list = QuizService._normalize_exclude(exclude)
        topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()] or None
        dup_threshold = P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD)

        collected: List[Dict[str, Any]] = []
        tries = 0

        while len(collected) < count and tries < max_tries:
            need = count - len(collected)
            excludes_now = exclude_list + QuizService._normalize_exclude(collected)
            topic_hints = topic_list[:need] if topic_list else None
            request_n = need + 5

            if qtype == "mcq":
                batch = QuizService._gen_mcq_once(ctx, request_n, excludes_now, topic_hints, difficulty, choices_count, mode)
            else:
                batch = QuizService._gen_tf_once(ctx, request_n, excludes_now, topic_hints, difficulty, mode)

            for q in batch:
                if len(collected) >= count:
                    break   
                if all(
                    similar(str(q.get("question", "")), str(e.get("question", "")))
                    < dup_threshold
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
        mode: Optional[str] = P.MODE_SOURCE,
    ) -> List[Dict[str, Any]]:
        mode = P.normalize_mode(mode)
        exclude_block = P.exclude_block(exclude_list, settings.EXCLUDE_LIST_LIMIT, mode)
        topic_block = P.topic_block(topic_hints, n, mode)

        difficulty_block = P.difficulty_block(difficulty, mode)
        answer_rules = P.ANSWER_RULES_MCQ[mode]

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

{answer_rules}

*** คุณภาพของตัวเลือก ***
- ตัวเลือกลวงทุกตัวต้องเกี่ยวข้องกับเนื้อหา ห้ามใส่ตัวเลือกที่ไม่มีความหมายเพื่อให้ครบจำนวน
- ความยาวของทุกตัวเลือกต้องใกล้เคียงกัน ห้ามให้ข้อที่ถูกยาวกว่าข้ออื่นอย่างชัดเจน
  (ไม่งั้นผู้สอบเดาได้จากความยาวโดยไม่ต้องอ่านเนื้อหา)
- ตัวเลือกห้ามซ้ำกันเอง และห้ามมีสองตัวเลือกที่ความหมายเหมือนกัน
- กระจายตำแหน่งคำตอบที่ถูกให้สม่ำเสมอ อย่าให้อยู่ตำแหน่งเดิมทุกข้อ
- คำถามต้องอ่านเข้าใจได้ด้วยตัวเอง ห้ามอ้างถึงสิ่งที่ผู้สอบมองไม่เห็น เช่น "จากภาพด้านบน", "ตามตารางนี้"
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
        questions = [
            q for q in data.get("questions", [])
            if not QuizService._has_banned_choice(q) and QuizService._is_valid_mcq(q, cc)
        ]
        return filter_near_dups(
            questions,
            [x["question"] for x in QuizService._normalize_exclude(exclude_list)],
            threshold=P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD),
        )

    @staticmethod
    def _gen_tf_once(
        ctx: str,
        n: int,
        exclude_list: List[str],
        topic_hints: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
        mode: Optional[str] = P.MODE_SOURCE,
    ) -> List[Dict[str, Any]]:
        mode = P.normalize_mode(mode)
        exclude_block = P.exclude_block(exclude_list, settings.EXCLUDE_LIST_LIMIT, mode)
        topic_block = P.topic_block(topic_hints, n, mode)

        difficulty_block = P.difficulty_block(difficulty, mode)
        answer_rules = P.ANSWER_RULES_TF[mode]
        rules_block = (answer_rules + "\n\n") if answer_rules else ""
        if mode == P.MODE_APPLIED:
            rules_block += P.TF_VERDICT_RULE
        tf_json = P.TF_JSON_FORMAT[mode]

        prompt = f"""
สร้างข้อสอบ ถูก/ผิด จำนวน {n} ข้อ จากเนื้อหาด้านล่าง
- ให้เหตุผลสั้น ๆ ทุกข้อ
- ตอบ JSON: {tf_json}

{rules_block}{difficulty_block}
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
        questions = [q for q in data.get("questions", []) if QuizService._is_valid_tf(q, mode)]
        return filter_near_dups(
            questions,
            [x["question"] for x in QuizService._normalize_exclude(exclude_list)],
            threshold=P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD),
        )