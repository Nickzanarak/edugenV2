"""โครงสร้างคู่มือ prompt ของโหมดประยุกต์: ทุกเล่มต้องมีของครบชุด และไม่ชนกัน"""
import pytest

from app.services import prompts as P
from app.services.prompts import source as S
from app.services.prompts import applied_math, applied_language, applied_general

# ของที่ทุกเล่มต้องมี ชื่อเดียวกัน (ดูหัวไฟล์เล่ม) — สวิตช์หยิบไปใช้โดยไม่รู้ว่าเล่มไหน
REQUIRED = {
    "NAME": str,
    "ANSWER_RULES_MCQ": str,
    "ANSWER_RULES_TF": str,
    "TF_JSON": str,
    "mcq_json": callable,
    "ANGLES": tuple,
    "ANGLE_DESC": dict,
    "ANGLES_BY_DIFFICULTY": dict,
    "ANGLES_RELAXED": dict,
    "ANGLES_WITHOUT_EXPR": tuple,
    "ANGLE_EXAMPLE_NOTE": str,
    "ANGLE_STRUCTURE_NOTE": str,
    "tf_want_block": callable,
}


@pytest.mark.parametrize("kind", P.KINDS)
def test_every_book_has_the_full_set(kind):
    """เพิ่มเล่มใหม่แล้วลืมช่องไหน เทสนี้ฟ้องทันที ไม่ต้องรอพังตอนใช้จริง"""
    book = P.book_for(kind)
    for name, typ in REQUIRED.items():
        assert hasattr(book, name), f"เล่ม {kind} ขาด {name}"
        value = getattr(book, name)
        if typ is callable:
            assert callable(value), f"เล่ม {kind}: {name} ต้องเป็นฟังก์ชัน"
        else:
            assert isinstance(value, typ), f"เล่ม {kind}: {name} ต้องเป็น {typ.__name__}"
    # มุมทุกตัวต้องมีคำอธิบาย และระดับความยากทุกระดับต้องชี้ไปมุมที่มีจริง
    assert set(book.ANGLE_DESC) == set(book.ANGLES)
    for level in ("easy", "medium", "hard"):
        assert set(book.ANGLES_BY_DIFFICULTY[level]) <= set(book.ANGLES)
        assert set(book.ANGLES_RELAXED.get(level, ())) <= set(book.ANGLES)


def test_angle_codes_do_not_collide_across_books():
    """สวิตช์ตรวจมุมรวมกันทุกเล่ม รหัสจึงต้องไม่ซ้ำ (เช่น compare ของคณิต vs contrast ของทั่วไป)"""
    all_codes = [a for k in P.KINDS for a in P.book_for(k).ANGLES]
    assert len(all_codes) == len(set(all_codes))
    assert set(P.ALL_ANGLES) == set(all_codes)


def test_books_map_to_kinds():
    assert P.BOOKS[P.KIND_MATH] is applied_math
    assert P.BOOKS[P.KIND_LANGUAGE] is applied_language
    assert P.BOOKS[P.KIND_GENERAL] is applied_general
    assert P.book_for("ไม่รู้จัก") is applied_math      # ป้ายแปลก ๆ ถอยไปคณิต


# ----- เล่มทั่วไป -----

def test_general_book_has_no_number_fields_and_requires_a_claim():
    assert "expr" not in applied_general.ANSWER_RULES_MCQ
    assert "expr" not in applied_general.ANSWER_RULES_TF
    assert "stated" not in applied_general.ANSWER_RULES_TF
    assert "expr" not in applied_general.TF_JSON
    assert "expr" not in applied_general.mcq_json('"ก) ..."', "ก|ข")
    assert "ข้อความอ้าง" in applied_general.ANSWER_RULES_TF
    assert "กรณีใหม่" in applied_general.ANSWER_RULES_MCQ
    assert applied_general.ANGLES_WITHOUT_EXPR == ()


def test_general_angles_follow_difficulty():
    easy = P.angles_for("easy", 0, P.KIND_GENERAL)
    hard = P.angles_for("hard", 0, P.KIND_GENERAL)
    assert "classify" in easy and "contrast" in hard and easy != hard
    assert set(P.angles_for("hard", 4, P.KIND_GENERAL)) == set(applied_general.ANGLES)
    guide = P.angle_guide_block("easy", "applied", "mcq", 0, P.KIND_GENERAL)
    assert "classify" in guide and "ชีววิทยา" in guide and "value" not in guide


def test_general_tf_want_block_speaks_about_cases_not_numbers():
    text = applied_general.tf_want_block("false")
    assert "false" in text and "เกณฑ์" in text
    assert "ค่าในข้อความ" not in text


# ----- โหมดเดิมไม่รู้จักเล่มไหนเลย -----

@pytest.mark.parametrize("kind", P.KINDS)
def test_source_mode_ignores_books(kind):
    assert P.answer_rules_mcq("source", kind) == S.ANSWER_RULES_MCQ
    assert P.answer_rules_tf("source", kind) == S.ANSWER_RULES_TF
    assert P.tf_json_format("source", kind) == S.TF_JSON
    assert P.angle_guide_block("easy", "source", "mcq", 0, kind) == ""
    assert P.tf_want_block("false", "source", kind) == ""
