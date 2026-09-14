"""สวิตช์เลือก prompt ตาม "โหมด" และ "ชนิดเนื้อหา"

โหมด (ผู้ใช้เลือก)
  source  = ถามจากเนื้อหา (ของเดิม ค่าเริ่มต้น)  -> source.py  แช่แข็ง ห้ามแก้
  applied = ประยุกต์ แต่งโจทย์ใหม่จากกฎในเอกสาร  -> เล่มใดเล่มหนึ่งใน BOOKS

ชนิดเนื้อหา (ระบบถาม AI ครั้งเดียวต่อเอกสารก่อนเจน เฉพาะโหมดประยุกต์)
  math / language / general  -> applied_math / applied_language / applied_general

ไฟล์นี้ไม่มีข้อความ prompt ของตัวเอง มีแต่ "รับ (mode, kind) มา แล้วหยิบจากเล่มที่ถูก"
ทุกเล่มมีของชื่อเดียวกันครบชุด (ดูหัวไฟล์เล่ม) สวิตช์จึงไม่ต้องรู้ว่าเป็นเล่มไหน
ของกลางที่ไม่ขึ้นกับเล่ม (ตัวหากฎ ตัวตรวจทาน เพดาน โควตา) อยู่ใน applied_core
"""
from app.services.prompts import source as S
from app.services.prompts import applied_core as C
from app.services.prompts import applied_math, applied_language, applied_general
from app.services.prompts.applied_core import (      # ให้เรียกผ่านสวิตช์ได้เลย
    KIND_MATH, KIND_LANGUAGE, KIND_GENERAL, KINDS, KIND_DEFAULT, normalize_kind,
    content_kind_prompt, applicable_rules_prompt, MAX_APPLICABLE_RULES,
    tf_review_prompt, plan_rule_quota,
    STRUCTURE_SIM_THRESHOLD, APPLIED_STRUCTURE_CAP, APPLIED_STRUCTURE_CAP_MAX,
    structure_cap, angle_cap, APPLIED_NEAR_DUP_THRESHOLD,
)

MODE_SOURCE = "source"
MODE_APPLIED = "applied"
VALID_MODES = (MODE_SOURCE, MODE_APPLIED)

# ตารางเล่ม: อยากเพิ่มวิชาใหม่ ก๊อปเล่มไหนก็ได้ แก้ทีละช่อง แล้วเพิ่ม 1 บรรทัดตรงนี้
BOOKS = {
    KIND_MATH: applied_math,
    KIND_LANGUAGE: applied_language,
    KIND_GENERAL: applied_general,
}

# รหัสมุมของทุกเล่มรวมกัน (ต้องไม่ซ้ำกัน จึงตรวจสอบรวมได้โดยไม่ต้องรู้เล่ม)
ALL_ANGLES = tuple(a for book in BOOKS.values() for a in book.ANGLES)
assert len(ALL_ANGLES) == len(set(ALL_ANGLES)), "รหัสมุมซ้ำกันระหว่างเล่ม"


def normalize_mode(mode) -> str:
    """กันค่าแปลกปลอม ถ้าไม่รู้จักให้ถอยกลับไปโหมดเดิมเสมอ"""
    key = (mode or MODE_SOURCE).strip().lower()
    return key if key in VALID_MODES else MODE_SOURCE


def _is_applied(mode) -> bool:
    return normalize_mode(mode) == MODE_APPLIED


def book_for(kind) -> object:
    return BOOKS[normalize_kind(kind)]


# ---------------------------------------------------------------------------
# เลือกตามโหมด (+ เล่ม เมื่อเป็นโหมดประยุกต์)
# ---------------------------------------------------------------------------

DIFFICULTY_PROMPTS = {MODE_SOURCE: S.DIFFICULTY, MODE_APPLIED: C.DIFFICULTY}


def difficulty_block(difficulty, mode=MODE_SOURCE) -> str:
    """คืนบล็อกระดับความยากตามโหมด ถ้าค่าไม่ถูกต้องให้ถอยไป medium เหมือนเดิม"""
    table = DIFFICULTY_PROMPTS[normalize_mode(mode)]
    key = (difficulty or "medium").strip().lower()
    return table.get(key, table["medium"]) + "\n"


def answer_rules_mcq(mode, kind=KIND_DEFAULT) -> str:
    return book_for(kind).ANSWER_RULES_MCQ if _is_applied(mode) else S.ANSWER_RULES_MCQ


def answer_rules_tf(mode, kind=KIND_DEFAULT) -> str:
    return book_for(kind).ANSWER_RULES_TF if _is_applied(mode) else S.ANSWER_RULES_TF


def tf_json_format(mode, kind=KIND_DEFAULT) -> str:
    return book_for(kind).TF_JSON if _is_applied(mode) else S.TF_JSON


def mcq_json_format(mode, choices_example: str, answer_options: str, kind=KIND_DEFAULT) -> str:
    if _is_applied(mode):
        return book_for(kind).mcq_json(choices_example, answer_options)
    return S.mcq_json(choices_example, answer_options)


def topic_block(topic_hints, n, mode=MODE_SOURCE) -> str:
    """โหมดประยุกต์ไม่ส่งรายการหัวข้อ เพราะการบังคับ "หัวข้อละ 1 ข้อ" จะลากไปหา
    หัวข้อที่ประยุกต์ไม่ได้ (นิยาม เกร็ดความรู้) เมื่อขอข้อสอบจำนวนมาก
    """
    if _is_applied(mode):
        return ""
    return S.topic_block(topic_hints, n)


def exclude_block(exclude_list, limit, mode=MODE_SOURCE) -> str:
    return S.exclude_block(exclude_list, limit, C.EXCLUDE_TAIL if _is_applied(mode) else "")


def shuffle_answer_line(mode) -> str:
    """บรรทัด "กระจายตำแหน่งคำตอบ" ของโหมดเดิม ขัดกับกฎ "วางคำตอบไว้ตัวเลือกแรก"
    ของโหมดประยุกต์ จึงส่งเฉพาะโหมดเดิม
    """
    return "" if _is_applied(mode) else S.SHUFFLE_ANSWER_LINE


def near_dup_threshold(mode, default: float) -> float:
    return C.APPLIED_NEAR_DUP_THRESHOLD if _is_applied(mode) else default


# ---------------------------------------------------------------------------
# มุมของโจทย์ — อ่านจากเล่มตามชนิดเนื้อหา
# ---------------------------------------------------------------------------

def angles_for(difficulty, tries: int = 0, kind=KIND_DEFAULT) -> tuple:
    """มุมที่ใช้ได้กับระดับความยากนี้ ยิ่งหาข้อไม่ครบหลายรอบ ยิ่งผ่อนให้

    เหตุผลที่ต้องผ่อนได้: เนื้อหาบางเรื่องทำมุมที่กำหนดไว้ไม่ไหวจริง ๆ
    ถ้าบังคับตายตัวจะกลายเป็นไล่ล่าของที่ไม่มีอยู่ เสียเวลายิง AI ซ้ำ ๆ เปล่า ๆ
    รอบ 0-1 = เข้ม | รอบ 2-3 = ผ่อนหนึ่งขั้น | รอบ 4+ = เลิกบังคับ (ทุกมุมของเล่มนั้น)
    """
    book = book_for(kind)
    key = (difficulty or "medium").strip().lower()
    if key not in book.ANGLES_BY_DIFFICULTY:
        key = "medium"
    step = max(0, int(tries)) // 2
    if step <= 0:
        return book.ANGLES_BY_DIFFICULTY[key]
    if step == 1:
        return book.ANGLES_BY_DIFFICULTY[key] + book.ANGLES_RELAXED.get(key, ())
    return book.ANGLES


def angles_without_expr(kind=KIND_DEFAULT) -> tuple:
    return book_for(kind).ANGLES_WITHOUT_EXPR


def angle_guide_block(difficulty, mode, qtype: str = "tf", tries: int = 0, kind=KIND_DEFAULT) -> str:
    """บล็อกอธิบายมุมของโจทย์ เปิดเฉพาะมุมที่เข้ากับระดับความยากนั้น"""
    if not _is_applied(mode):
        return ""
    book = book_for(kind)
    allowed = angles_for(difficulty, tries, kind)
    lines = []
    for code in allowed:
        what, example = book.ANGLE_DESC[code]
        lines.append(f"  {code:<10} {what}\n             ตัวอย่าง: {example}")
    body = "\n".join(lines)

    tail = ""
    if qtype != "mcq":
        without = [a for a in book.ANGLES_WITHOUT_EXPR if a in allowed]
        if without:
            tail = (
                f"\n*** มุม {' และ '.join(without)} ไม่ต้องกรอก expr กับ stated ***\n"
                "- มุมเหล่านี้ไม่ได้ตัดสินจากตัวเลขค่าเดียว ให้เว้น expr และ stated เป็นค่าว่าง\n"
                "  แล้วเขียนเหตุผลให้ครบใน explain แทน\n"
            )

    return (
        "*** มุมของโจทย์ ต้องหลากหลาย (สำคัญมาก) ***\n"
        "- ก่อนเขียนแต่ละข้อ ให้ \"เลือกมุมก่อน\" แล้วจึงเขียนโจทย์ให้เข้ากับมุมนั้น\n"
        "  กรอกรหัสมุมลงในช่อง angle ระดับความยากนี้ใช้ได้เฉพาะรหัสต่อไปนี้\n\n"
        f"{body}\n\n"
        + book.ANGLE_EXAMPLE_NOTE
        + f"- ห้ามใช้รหัสมุมอื่นนอกจาก {', '.join(allowed)} เพราะไม่เข้ากับระดับความยากนี้\n"
        "- ห้ามใช้มุมเดียวเกินครึ่งหนึ่งของชุด ต้องสลับมุมไปเรื่อย ๆ\n"
        + book.ANGLE_STRUCTURE_NOTE
        + f"{tail}\n"
    )


def tf_want_block(want, mode, kind=KIND_DEFAULT) -> str:
    return book_for(kind).tf_want_block(want) if _is_applied(mode) else ""


def tf_avoid_angle_block(angles, mode, kind=KIND_DEFAULT) -> str:
    """บอก AI ว่ามุมไหนใช้ครบโควตาแล้ว ห้ามใช้มุมนั้นอีกในรอบนี้"""
    items = [str(a).strip() for a in (angles or []) if str(a).strip()]
    if not _is_applied(mode) or not items:
        return ""
    remaining = [a for a in book_for(kind).ANGLES if a not in items]
    return (
        "*** มุมที่ใช้ครบโควตาแล้ว ***\n"
        "ห้ามใช้มุมเหล่านี้อีกในรอบนี้: " + ", ".join(items) + "\n"
        + ("ให้ใช้มุมที่เหลือแทน: " + ", ".join(remaining) + "\n" if remaining else "")
        + "\n"
    )


def tf_avoid_structure_block(examples, mode) -> str:
    return C.tf_avoid_structure_block(examples) if _is_applied(mode) else ""


def rule_quota_block(plan, mode, difficulty=None) -> str:
    return C.rule_quota_block(plan, difficulty) if _is_applied(mode) else ""
