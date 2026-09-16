import hashlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_service import client
from app.utils.nlp import filter_near_dups, question_skeleton, similar
from app.utils.chunking import sample_across_document
from app.utils.chunking import build_chunks_semantic as build_chunks
from app.utils.timing import timed
from app.utils.text import safe_json_loads
from app.utils import safe_math
from app.services import prompts as P


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
    def _is_valid_tf(q: Dict[str, Any]) -> bool:
        """ตาข่ายกันพลาด: ตรวจแค่รูปแบบว่าข้อสอบถูก/ผิดใช้งานได้ (มีคำถาม, answer ตีความได้)

        ไม่ได้พิสูจน์ว่าเฉลยถูกตามความจริง — หน้าที่นั้นอยู่ที่ _review_tf
        (โหมดประยุกต์เคยมีช่อง verdict ไว้เช็คไขว้ในนี้ด้วย แต่หลังใช้ _review_tf
        ซึ่งตรวจทานอิสระและทิ้งข้อที่ไม่ตรงกัน verdict ไม่มีผลต่อผลลัพธ์แล้ว จึงตัดออก)
        """
        if not str(q.get("question") or "").strip():
            return False
        ans = str(q.get("answer") or "").strip().lower()
        return ans in ("true", "จริง", "ถูก", "t", "1", "false", "เท็จ", "ผิด", "f", "0")

    @staticmethod
    def _review_tf(items: List[Dict[str, Any]], mode: str, context: str = "") -> List[Dict[str, Any]]:
        """ส่งข้อสอบถูก/ผิดกลับไปให้ AI ตัดสินใหม่ทั้งชุด แล้วแก้ข้อที่ไม่ตรงกัน

        ใช้เฉพาะโหมดประยุกต์ เพราะโหมดเดิมไม่เคยพบเฉลยผิดจากการทดสอบ
        ตัวตรวจไม่เห็นเฉลยเดิม จึงตัดสินโดยไม่ถูกชี้นำ แล้วโค้ดเป็นผู้เทียบเอง

        ถ้าส่ง context มาด้วย จะตรวจขอบเขตเพิ่มอีกชั้น (ทิ้งข้อที่ใช้กฎนอกเนื้อหา)
        โดยใช้ call เดิม ไม่ได้ยิง AI เพิ่ม

        fail-closed: ถ้าตรวจไม่สำเร็จ (error หรือได้ผลที่ใช้ไม่ได้เลย) จะทิ้งทั้งชุด
        แล้วปล่อยให้ลูปสร้างข้อสอบวนสร้างใหม่ ดีกว่าปล่อยข้อที่ยังไม่ถูกตรวจผ่านไป
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED or not items:
            return items

        try:
            with timed("quiz: review", f"{len(items)} ข้อ"):
                r = client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=[{"role": "user", "content": P.tf_review_prompt(items, context)}],
                    temperature=0,          # ตรวจทานไม่ต้องการความสร้างสรรค์
                    response_format={"type": "json_object"},
                )
            data = safe_json_loads(r.choices[0].message.content, {"results": []})
        except Exception:
            print("[TIME] quiz: review ล้มเหลว ทิ้งทั้งชุด (fail-closed)")
            return []                        # ตรวจไม่ได้ = ไม่การันตีความถูกต้อง จึงไม่ให้ผ่าน

        # ผลตัดสินของตัวตรวจ ต่อ index (ไม่เชื่อ 100% แค่ใช้เทียบว่าตรงกับตัวสร้างไหม)
        verdicts: Dict[int, str] = {}
        out_of_scope: set = set()
        for res in data.get("results", []):
            try:
                i = int(res.get("index", -1))
            except (TypeError, ValueError):
                continue
            if not (0 <= i < len(items)):
                continue
            ans = str(res.get("answer", "")).strip().lower()
            if ans in ("true", "false"):
                verdicts[i] = ans
            # ตีตกเฉพาะที่ตอบ out ตรง ๆ ค่าอื่น/ไม่ตอบ ถือว่าอยู่ในขอบเขต
            if str(res.get("scope", "")).strip().lower() == "out":
                out_of_scope.add(i)

        if not verdicts:
            print("[TIME] quiz: review ไม่ได้ผลที่ใช้ได้ ทิ้งทั้งชุด (fail-closed)")
            return []                        # ตรวจแล้วไม่มีผลใช้ได้เลย ถือว่าตรวจไม่สำเร็จ

        # ตัวสร้างกับตัวตรวจไม่ตรงกัน = ไม่รู้ว่าใครถูก จึงทิ้งข้อนั้นทั้งข้อ
        # ปลอดภัยกว่าการเดาว่าฝ่ายไหนถูก เพราะข้อสอบสร้างทดแทนได้ ไม่ใช่ของหายาก
        kept: List[Dict[str, Any]] = []
        dropped = 0
        scoped_out = 0
        for i, q in enumerate(items):
            if i in out_of_scope:
                scoped_out += 1
                continue
            # Python คำนวณยืนยันเฉลยไปแล้ว เชื่อ Python ไม่เชื่อตัวตรวจ เหลือแค่ด่านขอบเขต
            if q.get("_math_ok"):
                kept.append(q)
                continue
            original = str(q.get("answer", "")).strip().lower()
            verdict = verdicts.get(i)
            if verdict is not None and verdict != original:
                dropped += 1
                continue
            kept.append(q)

        if dropped:
            print(f"[TIME] quiz: review dropped  {dropped} ข้อ (สร้างกับตรวจไม่ตรงกัน)")
        if scoped_out:
            print(f"[TIME] quiz: review dropped  {scoped_out} ข้อ (ใช้กฎนอกเนื้อหา)")
        return kept

    @staticmethod
    def _review_mcq(
        items: List[Dict[str, Any]],
        cc: int,
        mode: str,
        kind: Optional[str],
        context: str,
    ) -> List[Dict[str, Any]]:
        """ส่งข้อสอบปรนัยกลับไปให้ AI เลือกคำตอบใหม่ทั้งชุด แล้วทิ้งข้อที่ไม่ตรงกัน

        ใช้เฉพาะโหมดประยุกต์ + เล่มภาษา/ทั่วไป (คณิตมี Python คำนวณตรวจอยู่แล้ว
        ใน _mcq_math_ok ไม่ต้องเสียคำถาม AI เพิ่ม) โครงเดียวกับ _review_tf:
        ตัวตรวจไม่เห็นเฉลยเดิม เลือกเอง แล้วโค้ดเทียบ

        ทิ้งข้อเมื่อ: ตัวตรวจเลือกคนละตัว / ตอบ none (ไม่มีตัวถูก หรือโจทย์ตั้งผิด
        เช่น ถาม "ผิดตรงไหน" กับประโยคที่ถูกอยู่แล้ว) / ชี้ว่ามีตัวเลือกอื่นถูกด้วย

        fail-closed เหมือน _review_tf: ตรวจไม่สำเร็จ = ทิ้งทั้งชุด ให้ลูปสร้างใหม่
        """
        if (P.normalize_mode(mode) != P.MODE_APPLIED or P.normalize_kind(kind) == P.KIND_MATH
                or not items):
            return items

        try:
            with timed("quiz: mcq review", f"{len(items)} ข้อ"):
                r = client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=[{"role": "user", "content": P.mcq_review_prompt(items, context)}],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
            data = safe_json_loads(r.choices[0].message.content, {"results": []})
        except Exception:
            print("[TIME] quiz: mcq review ล้มเหลว ทิ้งทั้งชุด (fail-closed)")
            return []

        letters = QuizService.CHOICE_LETTERS[:cc]
        verdicts: Dict[int, Tuple[str, str]] = {}      # index -> (answer, extra)
        for res in data.get("results", []):
            try:
                i = int(res.get("index", -1))
            except (TypeError, ValueError):
                continue
            if not (0 <= i < len(items)):
                continue
            ans = str(res.get("answer", "")).strip()
            extra = str(res.get("extra", "")).strip().lower()
            verdicts[i] = (ans, extra)

        if not verdicts:
            print("[TIME] quiz: mcq review ไม่ได้ผลที่ใช้ได้ ทิ้งทั้งชุด (fail-closed)")
            return []

        kept: List[Dict[str, Any]] = []
        mismatch = broken = ambiguous = 0
        for i, q in enumerate(items):
            verdict = verdicts.get(i)
            if verdict is None:
                kept.append(q)                  # ตัวตรวจไม่ตอบข้อนี้ ไม่มีหลักฐานว่าผิด
                continue
            ans, extra = verdict
            if ans not in letters:
                broken += 1                     # none หรือค่าแปลก = ไม่มีตัวถูก/โจทย์ตั้งผิด
                continue
            if ans != str(q.get("answer", "")).strip():
                mismatch += 1
                continue
            if extra in [l.lower() for l in letters] and extra != ans.lower():
                ambiguous += 1
                continue
            kept.append(q)

        if mismatch:
            print(f"[TIME] quiz: mcq review dropped {mismatch} ข้อ (เฉลยไม่ตรงกับตัวตรวจ)")
        if broken:
            print(f"[TIME] quiz: mcq review dropped {broken} ข้อ (ไม่มีตัวเลือกถูก/โจทย์ตั้งผิด)")
        if ambiguous:
            print(f"[TIME] quiz: mcq review dropped {ambiguous} ข้อ (ถูกได้มากกว่าหนึ่งตัวเลือก)")
        return kept

    @staticmethod
    def _math_verdict(q: Dict[str, Any]) -> Optional[str]:
        """เฉลยที่ถูกต้องของข้อคำนวณ ตัดสินโดย Python ไม่ใช่ AI

        คืน "true"/"false" เมื่อข้อนี้มี expr+stated ที่เชื่อถือได้และคำนวณได้
        คืน None เมื่อไม่ใช่ข้อคำนวณ นิพจน์ไม่ปลอดภัย หรือ stated ดูไม่น่าเชื่อถือ
        (กรณี None ให้ _review_tf จัดการต่อ ไม่ใช่ทิ้งข้อนั้น)

        ด่านสำคัญคือการเช็คว่า stated มีอยู่ในประโยคโจทย์จริง
        เพราะพบว่า AI มักกรอก "ค่าที่มันคำนวณได้" แทน "ค่าที่เขียนในโจทย์"
        ซึ่งทำให้ข้อที่เฉลยเป็นเท็จทุกข้อถูกตัดสินว่าขัดแย้งกันแล้วโดนทิ้งเรียบ
        """
        expr = str(q.get("expr") or "").strip()
        stated = q.get("stated")
        if not expr or stated is None or str(stated).strip() == "":
            return None

        question = str(q.get("question") or "")
        if not safe_math.appears_in(question, stated):
            return None      # กรอกช่องผิด ไม่รู้ว่าโจทย์อ้างค่าอะไร → ให้ AI ตรวจแทน

        try:
            return "true" if safe_math.matches(expr, stated) else "false"
        except safe_math.UnsafeExpression:
            return None

    @staticmethod
    def _verify_tf(items: List[Dict[str, Any]], mode: str, context: str = "") -> List[Dict[str, Any]]:
        """ตรวจเฉลยข้อสอบถูก/ผิด (เฉพาะโหมดประยุกต์)

        ข้อที่เป็นการคำนวณ (มี expr) ให้ Python คำนวณตัดสินเอง
        ถ้าเฉลยของ AI ไม่ตรงกับที่ Python คำนวณได้ ให้ทิ้งข้อนั้นทันที

        ข้อที่รอดจากด่านแรกทุกข้อ (รวมข้อที่ Python ตัดสินแล้ว) ยังต้องผ่าน _review_tf
        เพราะด่านนั้นตรวจ "ขอบเขต" ด้วย ซึ่ง Python ตรวจแทนไม่ได้
        ข้อที่ Python ตัดสินเฉลยไปแล้ว จะไม่ให้ตัวตรวจมาแย้งเรื่องเฉลยอีก (ติดธง _math_ok)
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED or not items:
            return items

        survived: List[Dict[str, Any]] = []
        math_dropped = 0
        for q in items:
            verdict = QuizService._math_verdict(q)
            if verdict is None:
                survived.append(q)                    # ไม่ใช่ข้อคำนวณ ให้ AI ตัดสินเฉลย
            elif verdict == str(q.get("answer", "")).strip().lower():
                q["_math_ok"] = True                  # Python ยืนยันเฉลยแล้ว
                survived.append(q)
            else:
                math_dropped += 1                     # Python ชี้ว่าเฉลยผิด → ทิ้ง

        if math_dropped:
            print(f"[TIME] quiz: math check dropped {math_dropped} ข้อ (เฉลยไม่ตรงผลคำนวณ)")

        out = QuizService._review_tf(survived, mode, context)
        for q in out:
            q.pop("_math_ok", None)      # ธงชั่วคราวของด่านนี้ ใช้เสร็จแล้วทิ้ง
        # ฟิลด์ angle/expr/stated ยังต้องอยู่ต่อ เพราะลูปเก็บข้อใช้ angle คุมความหลากหลาย
        # จะถูกตัดออกทีเดียวตอนท้ายสุด (_strip_internal)
        return out

    @staticmethod
    def _structure_texts(
        collected: List[Dict[str, Any]],
        prior: Optional[List[str]] = None,
    ) -> List[str]:
        """รวมคำถามที่ต้องนับโครง = ข้อที่เก็บได้ในรอบนี้ + ข้อที่มีอยู่แล้ว

        ข้อที่มีอยู่แล้วสำคัญมาก เพราะตอนผู้ใช้กดขอข้อสอบเพิ่ม มันเป็นคำขอใหม่
        ถ้าไม่นับของเดิมด้วย ระบบจะไม่รู้ว่าโครงไหนถูกใช้ไปแล้ว แล้วเติมโครงซ้ำเข้ามา
        """
        texts = [str(e.get("question", "")) for e in collected]
        texts.extend(str(t) for t in (prior or []))
        return [t for t in texts if t.strip()]

    @staticmethod
    def _structure_full(
        question: str,
        collected: List[Dict[str, Any]],
        mode: str,
        prior: Optional[List[str]] = None,
        cap: Optional[int] = None,
    ) -> bool:
        """โครงประโยคของข้อนี้ ถูกใช้ครบเพดานแล้วหรือยัง

        ใช้กับทั้งปรนัยและถูก/ผิด ในโหมดประยุกต์
        (เดิมเปิดเฉพาะถูก/ผิด แต่ตรวจแล้วพบว่าปรนัยก็จำเจแบบเดียวกัน
         เพราะไม่เคยมีตัวคุมความหลากหลายเลยสักตัว)
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return False
        skeleton = question_skeleton(question)
        if not skeleton:
            return False

        limit = P.APPLIED_STRUCTURE_CAP if cap is None else cap
        same = 0
        for text in QuizService._structure_texts(collected, prior):
            other = question_skeleton(text)
            if other and similar(skeleton, other) >= P.STRUCTURE_SIM_THRESHOLD:
                same += 1
                if same >= limit:
                    return True
        return False

    @staticmethod
    def _overused_questions(
        collected: List[Dict[str, Any]],
        mode: str,
        limit: int = 3,
        prior: Optional[List[str]] = None,
    ) -> List[str]:
        """ตัวอย่างคำถามของโครงที่ใช้ครบเพดานแล้ว เอาไปบอก AI ว่าอย่าออกซ้ำโครงนี้"""
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return []

        groups: List[tuple] = []          # [(skeleton, [คำถามในกลุ่มนี้]), ...]
        for text in QuizService._structure_texts(collected, prior):
            skeleton = question_skeleton(text)
            if not skeleton:
                continue
            for known, members in groups:
                if similar(skeleton, known) >= P.STRUCTURE_SIM_THRESHOLD:
                    members.append(text)
                    break
            else:
                groups.append((skeleton, [text]))

        full = [m[0] for _, m in groups if len(m) >= P.APPLIED_STRUCTURE_CAP]
        return full[:limit]

    # ลิสต์กฎต่อเอกสาร ถามครั้งเดียวใช้ได้ตลอด (เอกสารเดิม = ผลเดิม)
    _RULES_CACHE: Dict[str, List[str]] = {}
    _RULES_CACHE_LIMIT = 20
    # เอกสารยาวถูกซอยเป็นหลายชิ้นแล้วสร้างพร้อมกันหลายเธรด ถ้าไม่กั้นไว้
    # ทุกเธรดจะเห็น cache ว่างพร้อมกันแล้วยิงถาม AI คนละครั้ง cache ก็ไม่ได้ช่วยอะไร
    # ใช้ล็อกแยกตามเอกสาร คนที่ทำคนละเอกสารจะได้ไม่ต้องมารอกัน
    _RULES_LOCK = threading.Lock()
    _RULES_KEY_LOCKS: Dict[str, threading.Lock] = {}

    @staticmethod
    def _rules_key_lock(key: str) -> threading.Lock:
        """ล็อกประจำเอกสารนี้ สร้างให้ถ้ายังไม่มี"""
        with QuizService._RULES_LOCK:
            lock = QuizService._RULES_KEY_LOCKS.get(key)
            if lock is None:
                if len(QuizService._RULES_KEY_LOCKS) >= QuizService._RULES_CACHE_LIMIT:
                    QuizService._RULES_KEY_LOCKS.clear()
                lock = QuizService._RULES_KEY_LOCKS[key] = threading.Lock()
            return lock

    @staticmethod
    def _applicable_rules(ctx: str, mode: str) -> List[str]:
        """กฎที่เนื้อหาสอนและเอาไปแต่งโจทย์ใหม่ได้ (เฉพาะโหมดประยุกต์)

        ใช้แบ่งโควตาข้อสอบให้ครบทุกกฎ แทนที่จะปล่อยให้ AI เลือกเอง
        (ปล่อยให้เลือกเองแล้ววัดได้ว่ามันกระจุกอยู่ 3 สูตรแรก สูตรที่ยากไม่ออกเลย)

        ถ้าหาไม่ได้ด้วยเหตุใดก็ตาม คืนลิสต์ว่าง = ถอยไปใช้วิธีเดิม ไม่ให้ล้มทั้งคำขอ
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return []

        content = sample_across_document(ctx, settings.CTX_CHAR_LIMIT)
        key = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()
        # เธรดแรกที่เข้ามาเป็นคนถาม AI ที่เหลือรอแล้วได้ของจาก cache ไปใช้
        with QuizService._rules_key_lock(key):
            cached = QuizService._RULES_CACHE.get(key)
            if cached is not None:
                return cached

            try:
                with timed("quiz: rules", "หากฎที่ประยุกต์ได้"):
                    r = client.chat.completions.create(
                        model=settings.AI_MODEL,
                        messages=[{"role": "user", "content": P.applicable_rules_prompt(content)}],
                        temperature=0,
                        response_format={"type": "json_object"},
                    )
                data = safe_json_loads(r.choices[0].message.content, {"rules": []})
            except Exception:
                return []

            rules = [str(x).strip() for x in data.get("rules", []) if str(x).strip()]
            rules = rules[:P.MAX_APPLICABLE_RULES]
            if len(QuizService._RULES_CACHE) >= QuizService._RULES_CACHE_LIMIT:
                QuizService._RULES_CACHE.clear()
            QuizService._RULES_CACHE[key] = rules
            if rules:
                print(f"[TIME] quiz: rules พบ {len(rules)} กฎ | {', '.join(rules[:5])}")
            return rules

    # ป้ายชนิดเนื้อหาต่อเอกสาร ถามครั้งเดียวก่อนซอยเป็นชิ้น (เอกสารเดิม = ป้ายเดิม)
    _KIND_CACHE: Dict[str, str] = {}

    @staticmethod
    def _detect_kind(context: str, mode: str) -> str:
        """ถาม AI ว่าเนื้อหาทั้งเล่มเป็นแบบไหน: math / language / general (เฉพาะโหมดประยุกต์)

        ถามที่ระดับ "ทั้งเอกสาร" ไม่ใช่ทีละชิ้น เพราะเอกสารยาวถูกซอยหลายชิ้น
        ถ้าถามทีละชิ้นจะได้หลายป้ายที่อาจไม่ตรงกัน (ชิ้นที่มีแต่แบบฝึกหัดอาจถูกมองต่าง
        จากชิ้นที่มีตารางกฎ) ข้อสอบชุดเดียวกันจะได้คู่มือปนกัน

        ถ้าถามไม่สำเร็จด้วยเหตุใดก็ตาม ถือเป็นคณิต = ทำงานเหมือนเดิมทุกประการ
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return P.KIND_DEFAULT
        content = sample_across_document(context, settings.CTX_CHAR_LIMIT)
        key = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()
        cached = QuizService._KIND_CACHE.get(key)
        if cached:
            return cached
        try:
            with timed("quiz: kind", "ดูว่าเนื้อหาเป็นแบบไหน"):
                r = client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=[{"role": "user", "content": P.content_kind_prompt(content)}],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
            data = safe_json_loads(r.choices[0].message.content, {})
        except Exception:
            return P.KIND_DEFAULT
        kind = P.normalize_kind(data.get("kind"))
        if len(QuizService._KIND_CACHE) >= QuizService._RULES_CACHE_LIMIT:
            QuizService._KIND_CACHE.clear()
        QuizService._KIND_CACHE[key] = kind
        print(f"[TIME] quiz: kind = {kind} ({P.book_for(kind).NAME})")
        return kind

    @staticmethod
    def _angle_of(q: Dict[str, Any]) -> Optional[str]:
        """มุมของโจทย์ข้อนี้ หรือ None ถ้าไม่ระบุ (รหัสมุมของทุกชนิดเนื้อหาไม่ซ้ำกัน)"""
        angle = str(q.get("angle") or "").strip().lower()
        return angle if angle in P.ALL_ANGLES else None

    @staticmethod
    def _angle_allowed(
        q: Dict[str, Any],
        difficulty: Optional[str],
        mode: str,
        tries: int = 0,
        kind: str = P.KIND_DEFAULT,
    ) -> bool:
        """มุมของข้อนี้ เข้ากับระดับความยากที่ผู้ใช้เลือกไหม

        เดิมบอกไว้ใน prompt เฉย ๆ ไม่มีโค้ดตรวจ AI จึงไม่ทำตาม
        วัดจากของจริง: ชุด "ง่าย" มีข้อถามย้อน (ซึ่งกติกาข้อง่ายห้ามไว้)
        และชุด "ยาก" มีข้อที่แค่ห่อเรื่องเล่า ง่ายเท่ากับชุดง่าย

        รายการมุมที่ใช้ได้จะกว้างขึ้นเองเมื่อหาข้อไม่ครบ (ดู angles_for)
        เอกสารที่ทำมุมเข้ม ๆ ไม่ไหวจึงไม่ถูกบังคับจนออกข้อสอบไม่ได้
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return True
        angle = QuizService._angle_of(q)
        if not angle:
            return True      # ไม่ได้แจ้งมุมมา ไม่มีข้อมูลพอจะตัดสิน ปล่อยผ่าน
        return angle in P.angles_for(difficulty, tries, kind)

    @staticmethod
    def _angle_full(
        angle: Optional[str],
        collected: List[Dict[str, Any]],
        mode: str,
        cap: int,
    ) -> bool:
        """มุมนี้ถูกใช้ครบโควตาแล้วหรือยัง

        คุมคนละชั้นกับ _structure_full — อันนั้นดู "หน้าตาประโยค"
        อันนี้ดู "สิ่งที่ผู้สอบต้องทำ" ซึ่งเป็นตัวที่ทำให้ข้อสอบรู้สึกซ้ำจริง ๆ
        ใช้กับทั้งปรนัยและถูก/ผิด
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED or not angle:
            return False
        same = sum(1 for e in collected if QuizService._angle_of(e) == angle)
        return same >= cap

    @staticmethod
    def _overused_angles(
        collected: List[Dict[str, Any]],
        mode: str,
        cap: int,
    ) -> List[str]:
        """มุมที่ใช้ครบโควตาแล้ว เอาไปบอก AI ว่าอย่าใช้มุมนี้อีก"""
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return []
        counts: Dict[str, int] = {}
        for e in collected:
            angle = QuizService._angle_of(e)
            if angle:
                counts[angle] = counts.get(angle, 0) + 1
        return [a for a in P.ALL_ANGLES if counts.get(a, 0) >= cap]

    # ฟิลด์ที่ใช้ช่วยตรวจ/คุมความหลากหลายเท่านั้น ไม่ต้องส่งออกไปกับข้อสอบ
    _INTERNAL_FIELDS = ("expr", "stated", "angle", "rule", "_math_ok")

    @staticmethod
    def _strip_internal(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for q in items:
            for field in QuizService._INTERNAL_FIELDS:
                q.pop(field, None)
        return items

    _TF_TRUE_WORDS = ("true", "จริง", "ถูก", "t", "1")

    @staticmethod
    def _tf_want(collected: List[Dict[str, Any]], mode: str) -> Optional[str]:
        """รอบเก็บตกควรขอเฉลยด้านใด — คืน "true"/"false"/None

        เฉพาะโหมดประยุกต์ และเฉพาะเมื่อเฉลยที่เก็บได้เอียงไปด้านหนึ่งตั้งแต่ 2 ข้อขึ้นไป
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED or not collected:
            return None
        n_true = sum(1 for q in collected if QuizService._is_true_answer(q))
        n_false = len(collected) - n_true
        if n_true - n_false >= 2:
            return "false"
        if n_false - n_true >= 2:
            return "true"
        return None

    @staticmethod
    def _is_true_answer(q: Dict[str, Any]) -> bool:
        return str(q.get("answer", "")).strip().lower() in QuizService._TF_TRUE_WORDS

    @staticmethod
    def _rebalance_tf(
        collected: List[Dict[str, Any]],
        qtype: str,
        source_text: str,
        exclude_list: List[Dict[str, str]],
        difficulty: Optional[str],
        mode: Optional[str],
        dup_threshold: float,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """ปรับสัดส่วนเฉลย จริง/เท็จ หลังได้ข้อสอบครบแล้ว (เฉพาะถูก/ผิด โหมดประยุกต์)

        ทำไมต้องมาปรับตรงนี้: ตัวปรับสมดุลในลูปสร้างข้อสอบ ดูแค่ข้อที่ตัวเองเก็บได้
        พอเป็นเอกสารยาวที่ถูกหั่นเป็นก้อนแล้วรันขนานกัน แต่ละก้อนได้โควตาแค่ 1-2 ข้อ
        มันจึงไม่มีทางเห็นว่าเฉลยทั้งชุดเอียง ต้องมาวัดตอนรวมผลเสร็จแล้วเท่านั้น

        วิธีปรับ: ขอข้อฝั่งที่ขาดมาเพิ่ม แล้วสลับแทนข้อฝั่งที่เกิน
        """
        if qtype != "tf" or not collected:
            return collected
        want = QuizService._tf_want(collected, mode)
        if want is None:            # สมดุลดีอยู่แล้ว หรือไม่ใช่โหมดประยุกต์
            return collected

        n_true = sum(1 for q in collected if QuizService._is_true_answer(q))
        swap = abs(n_true - (len(collected) - n_true)) // 2
        if swap <= 0:
            return collected

        want_true = (want == "true")
        prior = [x["question"] for x in exclude_list]

        # ตัดข้อฝั่งที่เกินออกก่อน เพื่อ "เปิดที่ว่าง" ให้ข้อใหม่เข้ามาแทนได้จริง
        # ถ้าไม่ตัดก่อน ข้อใหม่จะโดนเพดานโครงประโยคปัดตกทั้งหมด เพราะโครงเต็มอยู่
        # แล้วการปรับสมดุลจะไม่มีทางสำเร็จเลย
        kept: List[Dict[str, Any]] = []
        removed: List[Dict[str, Any]] = []
        for q in collected:
            if len(removed) < swap and QuizService._is_true_answer(q) != want_true:
                removed.append(q)
            else:
                kept.append(q)

        try:
            with timed("quiz: rebalance", f"ขอฝั่ง {want} {swap} ข้อ"):
                extra = QuizService._gen_tf_once(
                    source_text,
                    swap + 3,          # ขอเผื่อ เพราะฝั่งที่ขาดมักถูกตรวจทิ้งบ่อยกว่า
                    exclude_list + QuizService._normalize_exclude(collected),
                    None,
                    difficulty,
                    mode,
                    want,
                    QuizService._overused_questions(kept, mode, prior=prior),
                    kind=kind,      # รอบสลับต้องใช้เล่มเดียวกับรอบหลัก ไม่งั้นได้โจทย์สไตล์คณิตปนมา
                )
        except Exception:
            return collected        # ปรับไม่ได้ ก็ใช้ของเดิม ดีกว่าล้มทั้งคำขอ

        fresh: List[Dict[str, Any]] = []
        for q in extra:
            if len(fresh) >= swap:
                break
            if QuizService._is_true_answer(q) != want_true:
                continue           # AI ไม่ทำตามที่ขอ ข้ามไป
            text = str(q.get("question", ""))
            if any(similar(text, str(e.get("question", ""))) >= dup_threshold
                   for e in kept + fresh):
                continue
            if QuizService._content_dup(q, "tf", None, mode, kind, kept + fresh, exclude_list):
                continue
            # ผ่อนเพดานตอนสลับ ไม่งั้นโครงเต็มแล้วจะสลับไม่สำเร็จ เฉลยก็เอียงต่อไป
            if QuizService._structure_full(
                text, kept + fresh, mode, prior, P.structure_cap(2)
            ):
                continue
            fresh.append(q)

        if not fresh:
            return collected        # หาของมาแทนไม่ได้ คืนชุดเดิมไปทั้งหมด ดีกว่าได้ข้อน้อยลง

        # หาแทนได้ไม่ครบ ก็เอาข้อที่ตัดไว้ใส่คืนเท่าที่ขาด จะได้ไม่เสียจำนวนข้อไป
        out = kept + fresh + removed[len(fresh):]
        print(f"[TIME] quiz: rebalance สลับ {len(fresh)} ข้อ เป็นฝั่ง {want}")
        return out

    @staticmethod
    def _guidance_block(
        qtype: str,
        difficulty: Optional[str],
        mode: str,
        n: int,
        avoid: Optional[List[str]],
        avoid_angles: Optional[List[str]],
        rule_plan: Optional[List[Tuple[str, int]]],
        tries: int,
        kind: str = P.KIND_DEFAULT,
    ) -> str:
        """คำสั่งเสริมของโหมดประยุกต์ที่ต่อท้าย prompt — ปรนัยกับถูก/ผิดใช้ชุดเดียวกัน

        รวมไว้ที่เดียวเพราะเดิมเขียนซ้ำกันสองที่ ถ้าเพิ่มบล็อกใหม่แล้วลืมแก้ที่ใดที่หนึ่ง
        รูปแบบข้อสอบสองแบบจะได้คำสั่งไม่เท่ากันโดยไม่มีใครรู้
        โหมดเดิมได้ค่าว่างทุกบล็อก prompt จึงไม่เปลี่ยนแม้แต่ตัวอักษรเดียว
        """
        return (
            P.angle_guide_block(difficulty, mode, qtype, tries, kind)
            + P.tf_avoid_structure_block(avoid, mode)
            + P.tf_avoid_angle_block(avoid_angles, mode, kind)
            + P.rule_quota_block(
                P.plan_rule_quota([r for r, _ in (rule_plan or [])], n), mode, difficulty
            )
        )

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
    def _mcq_math_ok(q: Dict[str, Any], cc: int, kind: Optional[str] = None) -> Optional[bool]:
        """ตัวเลือกที่เฉลยไว้ ตรงกับผลคำนวณของ Python ไหม

        คืน None เมื่อตรวจไม่ได้ (ไม่ใช่ข้อคำนวณ / ตัวเลือกไม่ใช่ตัวเลขเดี่ยว)
        ซึ่งให้ถือว่าผ่าน ไม่ใช่ทิ้ง — เหมือนที่ทำกับข้อสอบถูก/ผิด

        มีไว้เพราะปรนัยไม่เคยมีตัวตรวจเลขเลย และเจอของจริงแล้วว่าพลาดได้
        (โจทย์ที่นั่งโรงละคร AI เขียนวิธีถูกหมด แต่คูณผิด 4.5x48 ได้ 180
         แถมคำตอบจริง 216 ไม่มีอยู่ในตัวเลือกเลยสักข้อ)
        """
        # มุมที่คำตอบไม่ใช่ตัวเลขเดี่ยว (เช่น "ชุดที่ 3") ตรวจแบบนี้ไม่ได้
        if QuizService._angle_of(q) in P.angles_without_expr(P.normalize_kind(kind)):
            return None

        picked = QuizService._picked_choice(q, cc)
        if picked is None:
            return None

        nums = safe_math.number_strings_in_text(picked)
        if len(nums) != 1:
            return None      # ตัวเลือกมีหลายตัวเลขหรือไม่มีเลย ตัดสินไม่ได้

        expr = str(q.get("expr") or "").strip()
        if not expr:
            # ไม่มีสูตร = ตรวจไม่ได้ ไม่ใช่ตรวจแล้วผิด จึงปล่อยผ่าน
            #
            # เคยลองทิ้งข้อที่ไม่ส่งสูตรมาเมื่อคำถาม "ดูเหมือนมีการคำนวณ"
            # (นับว่ามีตัวเลขตั้งแต่ 2 ตัวขึ้นไป) แต่วัดของจริงแล้วแยกไม่ออก
            # ข้อความรู้ทั่วไปก็มีตัวเลข 2 ตัวได้ง่าย ๆ เช่น
            # "ปี 2006 ... ดาวเคราะห์ 8 ดวง ... อยู่ลำดับที่เท่าไหร่"
            # หรือ "เงื่อนไขแบบที่ 2 กับประธาน 3 ตัว" ของวิชาภาษา
            # ผลคือข้อดี ๆ ถูกทิ้งเงียบ ๆ ผู้ใช้ขอ 15 ข้อแล้วได้ไม่ครบ
            # จึงเลิกเดา เหลือแค่ตรวจตอนที่มีสูตรให้ตรวจจริง ๆ
            return None

        try:
            return safe_math.matches(expr, nums[0])
        except safe_math.UnsafeExpression:
            return None

    # คำที่โผล่ตอน AI คำนวณไม่ลงตัวแล้วมั่วคำตอบ
    #
    # สองคำแรกแรงที่สุด เป็นตอนที่ AI ยอมรับออกมาตรง ๆ ว่ากำลังเลือกคำตอบให้
    # เข้ากับตัวเลือกแทนที่จะเชื่อผลคำนวณ ("จึงปรับให้ตรงกับตัวเลือกที่ถูกต้อง",
    # "จึงต้องใช้ค่าที่สอดคล้องกับผลบวกจริงของชุดนี้") คนที่คิดออกจริงไม่เขียนแบบนี้
    # เพราะไม่ต้องประกาศว่าคำตอบไหนถูก มันบอกผลลัพธ์ไปตรง ๆ เลย
    #
    # วัดกับข้อสอบจริง 37 ข้อ (ผิด 7 ถูก 30) จับได้ 6 ใน 7 โดยไม่ทิ้งข้อดีเลยสักข้อ
    # ข้อที่เหลือเป็นแบบกาผิดช่อง ซึ่งตัวเทียบเลขข้างล่างจับได้
    #
    # ห้ามใส่ "ไม่ใช่" เคยลองแล้วทิ้งข้อดี 4 ข้อทันที เพราะข้อที่เฉลยเป็นเท็จ
    # ต้องพูดคำนี้ตามปกติ ("ได้ 45 ไม่ใช่ 21 จึงเป็นเท็จ")
    _FLAILING_WORDS = (
        "ที่ถูกต้อง", "ที่สอดคล้อง",
        "ไม่ตรง", "อย่างไรก็ตาม", "ไม่เป็นจำนวนเต็ม",
    )
    # "= 38" หรือ "2 × 3" = คำอธิบายนี้มีการคำนวณ (วัดกับไวยากรณ์ 12 ข้อ ไม่โดนเลย
    # คณิตที่ผิด 8 ข้อ โดนครบ) ไม่ใส่เครื่องหมายลบ เพราะ "ข้อ 1-3" เป็นช่วง ไม่ใช่ลบ
    _LOOKS_LIKE_CALC = re.compile(r"=\s*-?\d|\d\s*[×x*^÷/+]\s*-?\d")

    @staticmethod
    def _explain_unreliable(q: Dict[str, Any], cc: int, mode: str, kind: str = P.KIND_DEFAULT) -> bool:
        """คำอธิบายส่อว่าเฉลยเชื่อไม่ได้ ใช้ตอนไม่มีสูตรให้ Python ตรวจ

        จับสองอย่างที่เจอของจริงในโจทย์ลำดับและอนุกรม

        1. AI คำนวณไม่ลงตัวแล้วมั่ว — คำอธิบายวนไปมาว่า "ได้ 216 ไม่ตรง
           ได้ 260 ไม่ตรงเช่นกัน ดังนั้นตอบ 10" คนที่คิดออกจริงไม่เขียนแบบนี้
           ต้นเหตุคือ AI แต่งโจทย์ที่หาคำตอบเป็นจำนวนเต็มไม่ได้ตั้งแต่แรก

        2. AI คิดถูกแต่กาผิดช่อง — เลขของตัวเลือกที่กาไว้ไม่โผล่ในคำอธิบายเลย
           (คำอธิบายสรุปว่าพจน์สุดท้ายคือ 30 ตลอดทั้งย่อหน้า แต่ไปกาช่อง 28)

        เฉพาะโหมดประยุกต์ โหมดเดิมอธิบายด้วยคำพูดล้วน เช่น "โลกเป็นดาวเคราะห์
        ดวงที่สามจากดวงอาทิตย์" ไม่มีเลข 3 เขียนไว้ให้เทียบ ถ้าไม่กั้นจะทิ้งเรียบ
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return False
        # ตัวดักชุดนี้อ่าน "ร่องรอยการมั่วเลข" จึงใช้ได้กับเนื้อหาคณิตเท่านั้น
        # วิชาภาษาพูดคำว่า "ประโยคที่ถูกต้องคือ" ตามปกติโดยไม่ได้มั่วอะไร
        # เดิมเคยเดาจากคำอธิบายว่าเป็นคณิตไหม (นับเลข -> ดูเครื่องหมาย =) เดาผิดกับ
        # วิชาใหม่ทุกครั้ง ตอนนี้อ่านป้ายที่ตัวหากฎติดมาให้แทน ไม่ต้องเดา
        if P.normalize_kind(kind) != P.KIND_MATH:
            return False

        explain = str(q.get("explain") or "")
        if not explain:
            return False

        # ในเอกสารคณิตเองก็มีข้อแนวคิดที่ไม่คำนวณ (ลู่เข้า/ไม่ลู่เข้า) คำอธิบายพวกนั้น
        # ไม่มี "เลข = เลข" ให้ตรวจ ตัวดักคำจึงต้องข้ามไป ไม่งั้นจะทิ้งข้อดี
        if not QuizService._LOOKS_LIKE_CALC.search(explain):
            return False
        if any(w in explain for w in QuizService._FLAILING_WORDS):
            return True

        picked = QuizService._picked_choice(q, cc)
        if picked is None:
            return False

        # กาช่องที่คำอธิบายไม่เคยพูดถึงเลย
        nums = safe_math.number_strings_in_text(picked)
        if len(nums) == 1 and not safe_math.appears_in(explain, nums[0]):
            return True

        # ตัวเลือกเป็นตัวเลขล้วนทุกข้อ = โจทย์คำนวณตรง ๆ เลขตัวสุดท้ายที่คำอธิบาย
        # สรุปไว้ ต้องเป็นหนึ่งในตัวเลือกนั้น
        #
        # (เคสจริง: คำอธิบายสรุปเองว่า "ผลต่างคือ 162 - 54 = 108" แต่ 108 ไม่มีอยู่
        #  ในตัวเลือกเลยสักข้อ AI จึงไปกา 54 ซึ่งเป็นแค่เลขระหว่างทาง ตัวเทียบ
        #  ข้างบนจับไม่ได้เพราะ 54 "มีอยู่" ในคำอธิบายจริง)
        choices = q.get("choices") or []
        plain = [QuizService._strip_choice_prefix(str(c)).strip() for c in choices[:cc]]
        if len(plain) < cc:
            return False
        for text in plain:
            got = safe_math.number_strings_in_text(text)
            if len(got) != 1 or got[0] != text:
                return False      # มีคำประกอบ เช่น "124 ใบ" เทียบแบบนี้ไม่ได้

        written = safe_math.number_strings_in_text(explain)
        if not written:
            return False
        try:
            return not any(safe_math.matches(written[-1], c) for c in plain)
        except safe_math.UnsafeExpression:
            return False

    @staticmethod
    def _picked_choice(q: Dict[str, Any], cc: int) -> Optional[str]:
        """ข้อความของตัวเลือกที่ AI กาไว้ (ตัดหัว "ก) " ออกแล้ว)

        คืน None เมื่อกาตัวอักษรที่ไม่มีอยู่ หรือชี้ไปยังตัวเลือกที่ไม่มีจริง
        ผู้เรียกตัดสินเองว่ากรณีนั้นจะถือว่า "ตรวจไม่ได้" หรือ "ไม่น่าสงสัย"
        """
        letters = QuizService.CHOICE_LETTERS[:cc]
        ans = str(q.get("answer", "")).strip()
        choices = q.get("choices") or []
        if ans not in letters or letters.index(ans) >= len(choices):
            return None
        return QuizService._strip_choice_prefix(str(choices[letters.index(ans)]))

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
    def _content_dup(
        q: Dict[str, Any],
        qtype: str,
        choices_count: Optional[int],
        mode: Optional[str],
        kind: Optional[str],
        collected: List[Dict[str, Any]],
        exclude_list: List[Dict[str, str]],
    ) -> bool:
        """ด่านซ้ำเพิ่มของเล่มภาษา/ทั่วไป: เทียบ "เนื้อ" ของข้อ ไม่ใช่แค่ประโยคคำถาม

        ตัวกรองซ้ำปกติดูแต่ประโยคคำถาม ซึ่งพอกับคณิต (โจทย์คือคำถาม) แต่โจทย์ภาษา
        ถามด้วยสำนวนต่างกันได้ไม่รู้จบ ("ประโยคใดใช้..." / "สถานการณ์ใดเหมาะกับ...")
        ทั้งที่เฉลยเป็นประโยคเดียวกัน ตัวกรองจึงมองว่าคนละข้อ
        (วัดจริงจากไวยากรณ์อังกฤษ 15 ข้อ: เฉลย "If water is heated, it melts." ซ้ำ 3 ข้อ)
          ปรนัย   เทียบประโยคเฉลย (ตัวเลือกที่กาไว้) กับเฉลยของข้อที่มีแล้ว
                  รวมข้อจากรอบก่อน ๆ ที่หน้าเว็บส่งมา (ส่งเฉลยเป็นข้อความตัวเลือกอยู่แล้ว)
          ถูก/ผิด เทียบตัวโจทย์ทั้งข้อ แต่ใช้เกณฑ์เข้มกว่าปกติ เพราะไม่มีเลขให้ต่างกัน
        คณิตไม่ผ่านด่านนี้: เฉลยเป็นตัวเลข เลขเดียวกันเป็นคนละข้อได้เป็นเรื่องปกติ
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED or P.normalize_kind(kind) == P.KIND_MATH:
            return False
        if qtype == "mcq":
            cc = QuizService._clamp_choices(choices_count)
            mine = QuizService._picked_choice(q, cc) or ""
            seen = [QuizService._picked_choice(e, cc) or "" for e in collected]
            seen += [QuizService._strip_choice_prefix(str(e.get("answer") or "")) for e in exclude_list]
        else:
            mine = str(q.get("question") or "")
            seen = [str(e.get("question") or "") for e in collected + exclude_list]
        mine = mine.strip()
        if not mine:
            return False
        return any(t and similar(mine, t) >= P.CONTENT_DUP_THRESHOLD for t in seen)

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
        kind = QuizService._detect_kind(ctx, mode)     # ถามครั้งเดียวทั้งเล่ม ทุกชิ้นใช้ป้ายเดียวกัน

        chunks = build_chunks(ctx)
        exclude_list = QuizService._normalize_exclude(exclude)
        dup_threshold = P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD)

        # เอกสารสั้น -> ทางเดิม
        if len(chunks) <= 1:
            collected = QuizService._generate_from_text(
                qtype, ctx, count, exclude, topics, difficulty, choices_count, mode=mode, kind=kind
            )
            return QuizService._strip_internal(QuizService._rebalance_tf(
                collected, qtype, ctx, exclude_list, difficulty, mode, dup_threshold, kind
            ))

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

        # โหมดประยุกต์ไม่ใช้รายการหัวข้อเลย (topic_block คืนค่าว่างเสมอ)
        # จึงไม่ต้องเสียเวลาสร้าง/กรองรายการนี้
        topic_list = []
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()]
        prior = [x["question"] for x in exclude_list]

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
                    kind=kind,
                )
            except Exception:
                return []   # ก้อนเดียวพัง ไม่ให้ล้มทั้งคำขอ

        with timed("quiz: map", f"{len(picked)} ก้อน จาก {len(chunks)} ก้อน, ขอ {count} ข้อ"):
            with ThreadPoolExecutor(max_workers=len(picked)) as pool:
                results = list(pool.map(work, picked))

        # ---- รวมผล + กรองข้อซ้ำข้ามก้อน (รวมโครงประโยคซ้ำ ซึ่งแต่ละก้อนมองไม่เห็นกัน) ----
        #
        # ลำดับการหยิบ:
        #   โหมดเดิม     ไล่ทีละก้อนจนหมด (ของเดิม ไม่แตะ) — ตอนรวมมีแค่ด่านกันซ้ำ ไม่มีใครโดนปัดตก
        #   โหมดประยุกต์ สลับฟันปลา: หยิบข้อแรกของทุกก้อนก่อน แล้วค่อยวนหยิบข้อที่สอง
        #     เพราะด่านโครง/ด่านมุมข้างล่างปัดตกจริง ถ้าไล่ทีละก้อน ก้อนท้าย (บทท้าย) มาถึง
        #     ตอนเพดานเต็มพอดีและแพ้ทุกครั้ง วัดจริงกับชีววิทยา 14 หน้า 5 บท: ระดับง่ายออก
        #     "จัดอยู่กลุ่มใด" แทบทุกข้อ บท 5-7 กินเพดานหมด บท 8-9 ได้ 0 ข้อ
        #     สลับฟันปลาทำให้ทุกก้อนได้ข้อแรกเข้าชุดก่อนที่ก้อนไหนจะได้ข้อที่สอง
        if P.normalize_mode(mode) == P.MODE_APPLIED:
            ordered = [
                batch[i]
                for i in range(max((len(b) for b in results), default=0))
                for batch in results
                if i < len(batch)
            ]
        else:
            ordered = [q for batch in results for q in batch]

        collected: List[Dict[str, Any]] = []
        for q in ordered:
            if len(collected) >= count:
                break
            text = str(q.get("question", ""))
            if any(similar(text, str(e.get("question", ""))) >= dup_threshold for e in collected):
                continue
            if QuizService._content_dup(q, qtype, choices_count, mode, kind, collected, exclude_list):
                continue      # แต่ละก้อนมองไม่เห็นกัน เฉลยเดียวกันมาจากคนละก้อนได้
            if QuizService._structure_full(text, collected, mode, prior):
                continue
            # เพดานต้องคิดจาก "จำนวนมุมที่ระดับนี้ใช้ได้" เหมือนในลูปหลัก ไม่ใช่ 5 มุมเสมอ
            # เดิมลืมส่ง -> ระดับง่าย/ยากมี 2 มุม ขอ 7 ข้อได้เพดานแค่ 3 ต่อมุม ข้อจากก้อนท้าย ๆ
            # โดนปัดตกทุกครั้ง แล้วรอบเก็บตกไปหยิบจากก้อนที่ยาวที่สุดแทน
            # วัดจริงกับชีววิทยา 14 หน้า 5 บท: 30 ข้อมาจาก 3 บทแรก อีก 2 บทได้ 0 ข้อ
            if QuizService._angle_full(
                QuizService._angle_of(q), collected, mode,
                P.angle_cap(count, 0, len(P.angles_for(difficulty, 0, kind))),
            ):
                continue      # แต่ละก้อนมองไม่เห็นกัน ต้องคุมมุมตอนรวมผลด้วย
            collected.append(q)

        # ---- ถ้ายังไม่ครบ (บางก้อนเนื้อหาบาง) เก็บตกจากก้อนที่ยาวที่สุด ----
        richest = max(range(len(chunks)), key=lambda i: len(chunks[i]))
        if len(collected) < count:
            need = count - len(collected)
            excludes_now = exclude_list + QuizService._normalize_exclude(collected)
            try:
                extra = QuizService._generate_from_text(
                    qtype, chunks[richest], need, excludes_now, None,
                    difficulty, choices_count, max_tries=3, mode=mode, kind=kind,
                )
                for q in extra:
                    if len(collected) >= count:
                        break
                    text = str(q.get("question", ""))
                    if any(similar(text, str(e.get("question", ""))) >= dup_threshold for e in collected):
                        continue
                    if QuizService._content_dup(q, qtype, choices_count, mode, kind, collected, exclude_list):
                        continue
                    # รอบเก็บตกแล้ว ผ่อนเพดานให้เหมือนกัน ไม่งั้นเก็บตกไม่ได้เลย
                    if QuizService._structure_full(
                        text, collected, mode, prior, P.structure_cap(2)
                    ):
                        continue
                    collected.append(q)
            except Exception:
                pass

        return QuizService._strip_internal(QuizService._rebalance_tf(
            collected[:count], qtype, chunks[richest], exclude_list, difficulty, mode, dup_threshold, kind
        ))

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
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """ออกข้อสอบจากข้อความก้อนเดียว (ตรรกะเดิม) — ใช้ทั้งกรณีเอกสารสั้นและแต่ละก้อนของเอกสารยาว

        kind = ป้ายชนิดเนื้อหาที่ _generate_batch ถามมาให้ (ถ้าไม่มีถือเป็นคณิต)
        """
        ctx = (context or "").strip()
        count = max(1, min(15, int(n or 5)))
        if not ctx:
            raise HTTPException(400, "context ว่าง")

        exclude_list = QuizService._normalize_exclude(exclude)
        # โหมดประยุกต์ไม่ใช้รายการหัวข้อเลย (topic_block คืนค่าว่างเสมอ)
        # จึงไม่ต้องเสียเวลาสร้าง/กรองรายการนี้
        topic_list = None
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()] or None
        dup_threshold = P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD)
        # ข้อสอบที่มีอยู่แล้ว ต้องนับโครงด้วย ไม่งั้นตอนกดขอเพิ่มจะได้โครงซ้ำของเดิม
        prior = [x["question"] for x in exclude_list]
        # แผนกระจายข้อตามกฎที่เนื้อหาสอน (โหมดประยุกต์เท่านั้น ว่างได้ = ถอยไปใช้วิธีเดิม)
        # หมุนจุดเริ่มตามจำนวนข้อที่มีอยู่แล้ว ไม่งั้นเจนทีละชุดจะได้กฎชุดเดิมทุกครั้ง
        rule_plan = P.plan_rule_quota(
            QuizService._applicable_rules(ctx, mode), count, offset=len(exclude_list)
        )
        kind = P.normalize_kind(kind)

        collected: List[Dict[str, Any]] = []
        # ข้อที่ตรวจผ่านแล้ว แต่ถูกกันไว้เพราะซ้ำมุมหรือซ้ำโครง
        # เก็บไว้เผื่อสุดท้ายหาไม่ครบ จะได้ไม่ต้องยิง AI ใหม่ และไม่คืนข้อสอบน้อยเกินไป
        spare: List[Dict[str, Any]] = []
        tries = 0

        while len(collected) < count and tries < max_tries:
            need = count - len(collected)
            excludes_now = exclude_list + QuizService._normalize_exclude(collected)
            topic_hints = topic_list[:need] if topic_list else None
            request_n = need + 5

            # ยิ่งพยายามมาหลายรอบแล้วยังไม่ครบ ยิ่งผ่อนให้
            # ได้ข้อครบตามที่ผู้ใช้ขอ ดีกว่าคืนไม่ครบเพราะเนื้อหามีมุม/โครงให้ใช้จำกัด
            cap = P.structure_cap(tries)
            allowed_angles = P.angles_for(difficulty, tries, kind)
            acap = P.angle_cap(count, tries, len(allowed_angles))

            # โครง/มุมที่ใช้ครบโควตาแล้ว บอก AI ไปด้วยว่าห้ามออกซ้ำ (ใช้ทั้งปรนัยและถูก/ผิด)
            avoid = QuizService._overused_questions(collected, mode, prior=prior)
            avoid_angles = QuizService._overused_angles(collected, mode, acap)

            if qtype == "mcq":
                batch = QuizService._gen_mcq_once(
                    ctx, request_n, excludes_now, topic_hints, difficulty, choices_count, mode,
                    avoid, avoid_angles, rule_plan, tries, kind,
                )
            else:
                batch = QuizService._gen_tf_split(
                    ctx, request_n, excludes_now, topic_hints, difficulty, mode,
                    avoid, avoid_angles, rule_plan, collected, tries, kind,
                )

            for q in batch:
                if len(collected) >= count:
                    break
                text = str(q.get("question", ""))
                if any(similar(text, str(e.get("question", ""))) >= dup_threshold for e in collected):
                    continue
                if QuizService._content_dup(q, qtype, choices_count, mode, kind, collected, exclude_list):
                    continue            # เฉลยประโยคเดิม = ข้อเดิม แม้คำถามจะเขียนคนละสำนวน
                if not QuizService._angle_allowed(q, difficulty, mode, tries, kind):
                    spare.append(q)     # มุมไม่เข้ากับระดับความยากที่ผู้ใช้เลือก
                    continue
                if QuizService._structure_full(text, collected, mode, prior, cap):
                    spare.append(q)     # โครงประโยคนี้มีพอแล้ว รอบหน้าจะขอแบบอื่นแทน
                    continue
                if QuizService._angle_full(QuizService._angle_of(q), collected, mode, acap):
                    spare.append(q)     # มุมนี้มีพอแล้ว ต้องให้มุมอื่นได้ที่บ้าง
                    continue
                collected.append(q)

            if topic_list:
                used = {str(q.get("topic", "")).strip().lower() for q in collected}
                topic_list = [t for t in topic_list if str(t).strip().lower() not in used]
            tries += 1

        # ---- ทางออกสุดท้าย: ถ้ายังไม่ครบ ให้ยอมลดความหลากหลายลง ----
        # เนื้อหาบางเรื่องมีมุม/โครงให้ใช้จำกัดจริง ๆ การคืนข้อสอบน้อยกว่าที่ขอมาก ๆ
        # แย่กว่าการยอมให้โจทย์ซ้ำมุมกันบ้าง (ข้อพวกนี้ตรวจผ่านมาแล้ว ไม่ต้องยิง AI ซ้ำ)
        if len(collected) < count and spare:
            before = len(collected)
            for q in spare:
                if len(collected) >= count:
                    break
                text = str(q.get("question", ""))
                if any(similar(text, str(e.get("question", ""))) >= dup_threshold for e in collected):
                    continue
                if QuizService._content_dup(q, qtype, choices_count, mode, kind, collected, exclude_list):
                    continue
                collected.append(q)
            if len(collected) > before:
                print(f"[TIME] quiz: ใช้ข้อสำรอง {len(collected) - before} ข้อ (เนื้อหามีมุมให้ใช้จำกัด)")

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
        avoid: Optional[List[str]] = None,
        avoid_angles: Optional[List[str]] = None,
        rule_plan: Optional[List[Tuple[str, int]]] = None,
        tries: int = 0,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        mode = P.normalize_mode(mode)
        kind = P.normalize_kind(kind)
        exclude_block = P.exclude_block(exclude_list, settings.EXCLUDE_LIST_LIMIT, mode)
        topic_block = P.topic_block(topic_hints, n, mode)

        difficulty_block = P.difficulty_block(difficulty, mode)
        answer_rules = P.answer_rules_mcq(mode, kind)
        shuffle_line = P.shuffle_answer_line(mode)

        cc = QuizService._clamp_choices(choices_count)
        letters = QuizService.CHOICE_LETTERS[:cc]
        letters_text = " ".join(letters)
        choices_example = ", ".join(f'"{l}) ..."' for l in letters)
        answer_options = "|".join(letters)

        # โหมดเดิมได้ข้อความเดิมทุกตัวอักษร โหมดประยุกต์ได้บล็อกความหลากหลายเพิ่ม
        mcq_json = P.mcq_json_format(mode, choices_example, answer_options, kind)
        avoid_block = QuizService._guidance_block(
            "mcq", difficulty, mode, n, avoid, avoid_angles, rule_plan, tries, kind
        )

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
{shuffle_line}- คำถามต้องอ่านเข้าใจได้ด้วยตัวเอง ห้ามอ้างถึงสิ่งที่ผู้สอบมองไม่เห็น เช่น "จากภาพด้านบน", "ตามตารางนี้"
- ถ้าเนื้อหาไม่พอจะสร้างตัวเลือกลวงที่ดีครบ {cc} ตัว ให้เปลี่ยนไปตั้งคำถามจากแง่มุมอื่นของเนื้อหาแทน
- ตอบ JSON: {mcq_json}

{avoid_block}{difficulty_block}
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

        # ให้ Python คำนวณตรวจเฉลยซ้ำ ไม่ตรงก็ทิ้ง (ตรวจไม่ได้ = ปล่อยผ่าน)
        checked, math_dropped = [], 0
        for q in questions:
            if QuizService._mcq_math_ok(q, cc, kind) is False:
                math_dropped += 1
                continue
            if QuizService._explain_unreliable(q, cc, mode, kind):
                math_dropped += 1
                continue
            checked.append(q)
        if math_dropped:
            print(f"[TIME] quiz: mcq math dropped {math_dropped} ข้อ (เฉลยไม่ตรงผลคำนวณ)")

        # เล่มภาษา/ทั่วไปไม่มี Python ตรวจเฉลย ให้ AI ตรวจทานแทน (คณิตข้ามด่านนี้)
        checked = QuizService._review_mcq(
            checked, cc, mode, kind, sample_across_document(ctx, settings.CTX_CHAR_LIMIT)
        )

        return filter_near_dups(
            checked,
            [x["question"] for x in QuizService._normalize_exclude(exclude_list)],
            threshold=P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD),
        )

    @staticmethod
    def _split_rule_plan(
        rule_plan: Optional[List[Tuple[str, int]]],
    ) -> Dict[str, Optional[List[Tuple[str, int]]]]:
        """แบ่งแผนกฎให้ฝั่งจริง/เท็จคนละครึ่ง สลับกัน (จริงได้ตัวที่ 1,3,5 เท็จได้ 2,4,6)

        แบ่งไม่ได้ (ว่าง หรือมีกฎเดียว) ให้ทั้งสองฝั่งได้แผนเดิมทั้งชุด
        """
        plan = list(rule_plan or [])
        if len(plan) < 2:
            return {"true": rule_plan, "false": rule_plan}
        return {"true": plan[0::2], "false": plan[1::2]}

    @staticmethod
    def _gen_tf_split(
        ctx: str,
        n: int,
        exclude_list: List[Dict[str, str]],
        topic_hints: Optional[List[str]],
        difficulty: Optional[str],
        mode: Optional[str],
        avoid: Optional[List[str]],
        avoid_angles: Optional[List[str]],
        rule_plan: Optional[List[Tuple[str, int]]],
        collected: List[Dict[str, Any]],
        tries: int = 0,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """ขอข้อสอบถูก/ผิด โดยแยกฝั่ง "จริง" กับ "เท็จ" เป็นคนละคำสั่ง ยิงพร้อมกัน

        ทำไมต้องแยก: เมื่อสั่งรวดเดียวว่า "เอาจริงกี่ข้อ เท็จกี่ข้อ" AI ต้องสลับ
        โหมดคิดไปมาในคำสั่งเดียว ซึ่งคอมเมนต์ในโค้ดนี้เคยบันทึกไว้เองว่าทำให้มัน
        "ตัดสินใจว่าข้อนี้เป็นเท็จไว้ล่วงหน้า แล้วลืมแก้ค่าในข้อความให้ผิดจริง"
        พอแยกคำสั่ง แต่ละคำสั่งทำอย่างเดียวรวดเดียว ความกดดันเรื่องโควตาหายไป

        วัดจากของจริง: ปล่อยให้ออกเองแล้วมาสลับทีหลัง ได้เฉลย 14 จริง : 1 เท็จ
        เอียงเกินกว่าที่การสลับไม่กี่ข้อจะแก้ไหว จึงต้องแบ่งตั้งแต่ต้นทาง
        """
        if P.normalize_mode(mode) != P.MODE_APPLIED:
            return QuizService._gen_tf_once(
                ctx, n, exclude_list, topic_hints, difficulty, mode
            )

        # เติมฝั่งที่ยังขาดให้มากกว่า โดยดูจากที่เก็บได้แล้ว
        n_true_have = sum(1 for q in collected if QuizService._is_true_answer(q))
        n_false_have = len(collected) - n_true_have
        half = max(1, n // 2)
        # ฝั่งเท็จสั่งเผื่อเสมอ เพราะสร้างยากกว่าและถูกตรวจทิ้งบ่อยกว่าฝั่งจริง
        jobs = [
            ("true", max(1, half - max(0, n_true_have - n_false_have))),
            ("false", max(1, half + 2 + max(0, n_true_have - n_false_have))),
        ]

        # สองฝั่งยิงพร้อมกันและไม่เห็นกัน ถ้าได้กฎชุดเดียวกันจะหยิบ "ตัวอย่างเด่นสุดของกฎนั้น"
        # มาเหมือนกัน แล้วออกมาเป็นคู่ กรณีเดียวกัน จริง 1 ข้อ เท็จ 1 ข้อ (ชีววิทยา 4 คู่ใน 15)
        # แบ่งกฎให้คนละครึ่ง (ตัวที่ 1,3,5 / 2,4,6) ให้สองฝั่งทำงานคนละกฎ = คนละกรณีโดยธรรมชาติ
        # โดยไม่ต้องรอกันจึงไม่ช้าขึ้น ถ้ามีกฎเดียวแบ่งไม่ได้ ก็ให้ทั้งสองฝั่งเหมือนเดิม
        plans = QuizService._split_rule_plan(rule_plan)

        def work(job):
            want, quota = job
            try:
                return QuizService._gen_tf_once(
                    ctx, quota, exclude_list, topic_hints, difficulty, mode,
                    want, avoid, avoid_angles, plans[want], tries, kind,
                )
            except Exception:
                return []       # ฝั่งเดียวพัง ไม่ให้ล้มทั้งรอบ

        with timed("quiz: tf split", f"จริง {jobs[0][1]} + เท็จ {jobs[1][1]} ข้อ"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                sides = list(pool.map(work, jobs))

        # สลับฟันปลาระหว่างสองฝั่ง เพื่อให้ลูปเก็บข้อได้ทั้งสองฝั่งสลับกันไป
        # ถ้าต่อกันตรง ๆ ฝั่งแรกจะกินโควตาโครง/มุมไปหมดก่อน
        merged: List[Dict[str, Any]] = []
        for i in range(max((len(s) for s in sides), default=0)):
            for side in sides:
                if i < len(side):
                    merged.append(side[i])
        return merged

    @staticmethod
    def _gen_tf_once(
        ctx: str,
        n: int,
        exclude_list: List[str],
        topic_hints: Optional[List[str]] = None,
        difficulty: Optional[str] = "medium",
        mode: Optional[str] = P.MODE_SOURCE,
        want: Optional[str] = None,
        avoid: Optional[List[str]] = None,
        avoid_angles: Optional[List[str]] = None,
        rule_plan: Optional[List[Tuple[str, int]]] = None,
        tries: int = 0,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        mode = P.normalize_mode(mode)
        kind = P.normalize_kind(kind)
        exclude_block = P.exclude_block(exclude_list, settings.EXCLUDE_LIST_LIMIT, mode)
        topic_block = P.topic_block(topic_hints, n, mode)

        difficulty_block = P.difficulty_block(difficulty, mode)
        answer_rules = P.answer_rules_tf(mode, kind)
        rules_block = (answer_rules + "\n\n") if answer_rules else ""
        want_block = P.tf_want_block(want, mode, kind)
        avoid_block = QuizService._guidance_block(
            "tf", difficulty, mode, n, avoid, avoid_angles, rule_plan, tries, kind
        )
        tf_json = P.tf_json_format(mode, kind)

        # เนื้อหาชุดเดียวกับที่ส่งให้ตัวสร้าง จะถูกส่งให้ตัวตรวจใช้ตรวจขอบเขตด้วย
        # (ต้องเป็นชุดเดียวกัน ไม่งั้นตัวตรวจจะตีตกข้อที่ดีเพราะมองไม่เห็นกฎที่ตัวสร้างเห็น)
        content = sample_across_document(ctx, settings.CTX_CHAR_LIMIT)

        prompt = f"""
สร้างข้อสอบ ถูก/ผิด จำนวน {n} ข้อ จากเนื้อหาด้านล่าง
- ให้เหตุผลสั้น ๆ ทุกข้อ
- ตอบ JSON: {tf_json}

{avoid_block}{want_block}{rules_block}{difficulty_block}
{topic_block}{exclude_block}
เนื้อหา:
{content}
"""
        r = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        data = safe_json_loads(r.choices[0].message.content, {"questions": []})
        questions = [q for q in data.get("questions", []) if QuizService._is_valid_tf(q)]
        questions = QuizService._verify_tf(questions, mode, content)
        return filter_near_dups(
            questions,
            [x["question"] for x in QuizService._normalize_exclude(exclude_list)],
            threshold=P.near_dup_threshold(mode, settings.NEAR_DUP_THRESHOLD),
        )