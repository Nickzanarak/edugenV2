"""ด่านซ้ำเพิ่มของเล่มภาษา/ทั่วไป (_content_dup) และรอบสลับใช้เล่มเดียวกับรอบหลัก

ที่มา: เทสไวยากรณ์อังกฤษ 30 ข้อ พบเฉลย "If water is heated, it melts." ซ้ำ 3 ข้อ
เพราะตัวกรองซ้ำเดิมดูแค่ประโยคคำถาม ซึ่งแต่ละข้อเขียนคนละสำนวน
"""
import os

os.environ.setdefault("OPENAI_API_KEY", "dummy-for-tests")

from app.services.quiz_service import QuizService
from app.services import prompts as P


def mcq(question, answer_text, answer="ก"):
    """ข้อปรนัยที่มีเฉลยอยู่ตัวเลือกแรก (ตามกติกาโหมดประยุกต์)"""
    return {
        "type": "mcq",
        "question": question,
        "choices": [f"ก) {answer_text}", "ข) ตัวลวง 1", "ค) ตัวลวง 2", "ง) ตัวลวง 3"],
        "answer": answer,
        "explain": "...",
    }


# ---------------------------------------------------------------------------
# ปรนัย: เฉลยประโยคเดียวกัน = ข้อเดียวกัน แม้คำถามคนละสำนวน
# ---------------------------------------------------------------------------

def test_mcq_same_answer_sentence_is_dup_even_with_different_stem():
    have = [mcq("สถานการณ์ใดใช้ประโยคเงื่อนไขแบบความจริงทั่วไปได้เหมาะสมที่สุด",
                "If water is heated, it melts.")]
    new = mcq("ประโยคใดใช้กับเหตุการณ์ที่เป็นจริงเสมอได้เหมาะสมที่สุด",
              "If water is heated, it melts.")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "language", have, []) is True


def test_mcq_near_identical_answer_is_dup():
    # วัดจริง: "If the metal is heated, it expands." กับ "If a metal ..." คล้าย 0.91
    have = [mcq("ประโยคใดเป็นเงื่อนไขแบบที่ 0", "If the metal is heated, it expands.")]
    new = mcq("สถานการณ์ใดควรใช้ประโยคเงื่อนไขที่พูดถึงสิ่งที่เป็นจริงเสมอ",
              "If a metal is heated, it expands.")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "language", have, []) is True


def test_mcq_different_answer_sentence_is_not_dup():
    have = [mcq("ประโยคใดใช้โครงสร้างเงื่อนไขแบบที่ 2 ได้ถูกต้อง", "If she were free, she would join us.")]
    new = mcq("ประโยคใดใช้โครงสร้างเงื่อนไขแบบที่ 2 ได้ถูกต้อง", "If I had time, I would read a novel.")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "language", have, []) is False


def test_mcq_answer_from_previous_round_counts_too():
    # หน้าเว็บส่งข้อรอบก่อนมาเป็น {question, answer} โดย answer คือข้อความตัวเลือก (อาจติดหัว "ก) ")
    exclude = [{"question": "สถานการณ์ใดใช้ประโยคเงื่อนไขแบบความจริงทั่วไป",
                "answer": "ง) If water is heated, it melts."}]
    new = mcq("ประโยคใดใช้กับเหตุการณ์ที่เป็นจริงเสมอ", "If water is heated, it melts.")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "language", [], exclude) is True


def test_mcq_wrong_sentence_as_answer_is_different_question():
    # ข้อ "ประโยคใดผิด" เฉลย "it melt" (ผิด) กับข้อ "ประโยคใดถูก" เฉลย "it melts" (ถูก) = คนละข้อ
    have = [mcq("ประโยคใดใช้กับเหตุการณ์ที่เป็นจริงเสมอ", "If water is heated, it melts.")]
    new = mcq("ประโยคใดผิดรูปแบบของเงื่อนไขแบบที่ 0", "If the ice is heated, it melt.")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "language", have, []) is False


# ---------------------------------------------------------------------------
# ถูก/ผิด: ประโยคตัวอย่างเดิม ต่างแค่ข้อความอ้าง = ข้อเดียวกัน
# ---------------------------------------------------------------------------

def tf(question, answer="true"):
    return {"type": "tf", "question": question, "answer": answer, "explain": "..."}


def test_tf_same_example_different_claim_is_dup():
    have = [tf("If the museum opened earlier, we would visit the new gallery. "
               "ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง")]
    new = tf("If the museum opened earlier, we would visit the new gallery. "
             "ประโยคนี้ใช้โครงสร้าง If + present simple, will + V1 ถูกต้อง", "false")
    assert QuizService._content_dup(new, "tf", None, "applied", "language", have, []) is True


def test_tf_same_frame_different_noun_is_dup():
    # วัดจริง: "he would buy a new book" กับ "he would buy a house" คล้าย 0.94
    have = [tf("If Ben had more money, he would buy a new book. ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง")]
    new = tf("If Ben had more money, he would buy a house. ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง")
    assert QuizService._content_dup(new, "tf", None, "applied", "language", have, []) is True


def test_tf_same_claim_different_example_is_not_dup():
    # กฎเดียวกัน แต่ประโยคตัวอย่างคนละเรื่อง (วัดจริงคล้าย 0.70) ต้องปล่อยผ่าน
    have = [tf("If Ben had more money, he would buy a new book. ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง")]
    new = tf("If Anna studies hard, she will pass the test. ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง", "false")
    assert QuizService._content_dup(new, "tf", None, "applied", "language", have, []) is False


# ---------------------------------------------------------------------------
# ขอบเขต: คณิตและโหมดเดิมไม่ผ่านด่านนี้เลย
# ---------------------------------------------------------------------------

def test_math_kind_never_uses_content_dup():
    # เฉลยเป็นตัวเลข เลขเดียวกันเป็นคนละข้อได้ตามปกติ
    have = [mcq("ลำดับ 3, 7, 11 พจน์ที่ 5 คือเท่าใด", "19")]
    new = mcq("ลำดับ 4, 9, 14 พจน์ที่ 4 คือเท่าใด", "19")
    assert QuizService._content_dup(new, "mcq", 4, "applied", "math", have, []) is False
    assert QuizService._content_dup(new, "mcq", 4, "applied", None, have, []) is False


def test_source_mode_never_uses_content_dup():
    have = [mcq("คำถาม ก", "If water is heated, it melts.")]
    new = mcq("คำถาม ข", "If water is heated, it melts.")
    assert QuizService._content_dup(new, "mcq", 4, "source", "language", have, []) is False


def test_general_kind_uses_content_dup():
    have = [tf("สัตว์ชนิดหนึ่งมีขนปกคลุม เลี้ยงลูกด้วยนม และออกลูกเป็นตัว จัดเป็นสัตว์เลี้ยงลูกด้วยนม")]
    new = tf("สัตว์ชนิดหนึ่งมีขนปกคลุม เลี้ยงลูกด้วยนม และออกลูกเป็นตัว จัดเป็นสัตว์เลื้อยคลาน", "false")
    assert QuizService._content_dup(new, "tf", None, "applied", "general", have, []) is True


def test_threshold_is_exported_through_switch():
    assert P.CONTENT_DUP_THRESHOLD == 0.80
    assert P.CONTENT_DUP_THRESHOLD < P.APPLIED_NEAR_DUP_THRESHOLD


def test_thai_same_case_different_claim_is_dup():
    # วัดจริงจากชีววิทยา: คู่นี้คล้าย 0.84 หลุดเกณฑ์ 0.85 ไปนิดเดียว เพราะประโยคไทยสั้น
    have = [tf("สัตว์ชนิดหนึ่งมีผิวแห้งเป็นเกล็ด หายใจด้วยปอด และออกไข่บนบก จัดเป็นสัตว์เลื้อยคลาน")]
    new = tf("สัตว์ชนิดหนึ่งมีผิวแห้งเป็นเกล็ด หายใจด้วยปอด และออกไข่บนบก จัดเป็นสัตว์สะเทินน้ำสะเทินบก", "false")
    assert QuizService._content_dup(new, "tf", None, "applied", "general", have, []) is True


def test_thai_different_case_same_frame_is_not_dup():
    # กรอบประโยคเดียวกัน แต่ลักษณะคนละชุด (วัดจริง 0.59-0.63) ต้องปล่อยผ่าน
    have = [tf("สัตว์ชนิดหนึ่งมีผิวแห้งเป็นเกล็ด หายใจด้วยปอด และออกไข่บนบก จัดเป็นสัตว์เลื้อยคลาน")]
    new = tf("สัตว์ชนิดหนึ่งวางไข่ในน้ำ ลูกอ่อนหายใจด้วยเหงือก และเมื่อโตขึ้นใช้ปอดกับผิวหนัง จัดเป็นสัตว์เลื้อยคลาน", "false")
    assert QuizService._content_dup(new, "tf", None, "applied", "general", have, []) is False


# ---------------------------------------------------------------------------
# รอบสลับ (rebalance) ต้องส่งป้ายเล่มให้ AI ด้วย
# เดิมลืมส่ง ทำให้เอกสารภาษาได้โจทย์ถูก/ผิดสไตล์คณิตปนมา 5 ใน 15 ข้อ
# ---------------------------------------------------------------------------

def test_rebalance_passes_kind_to_tf_generator(monkeypatch):
    seen = {}

    def fake_gen_tf_once(ctx, n, exclude_list, topic_hints, difficulty, mode, want, avoid, **kw):
        seen["kind"] = kw.get("kind")
        return [tf("If Tom had a car, he would drive to work. ประโยคนี้ใช้เงื่อนไขแบบที่ 1 ถูกต้อง", "false")]

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(fake_gen_tf_once))
    skewed = [tf(f"ประโยคที่ {i} ถูกต้อง") for i in range(4)]     # จริง 4 : เท็จ 0
    out = QuizService._rebalance_tf(skewed, "tf", "เนื้อหา", [], "medium", "applied", 0.97, "language")
    assert seen["kind"] == "language"
    assert sum(1 for q in out if q["answer"] == "false") == 1


def test_rebalance_drops_content_dup_replacement(monkeypatch):
    # ข้อใหม่จากรอบสลับที่เป็นประโยคตัวอย่างเดิมของข้อที่ยังอยู่ ต้องถูกด่านซ้ำกันไว้
    museum = "If the museum opened earlier, we would visit the new gallery. ประโยคนี้ใช้โครงสร้าง If + past simple, would + V1 ถูกต้อง"

    def fake_gen_tf_once(*a, **kw):
        return [tf("If the museum opened earlier, we would visit the new gallery. "
                   "ประโยคนี้ใช้โครงสร้าง If + present simple, will + V1 ถูกต้อง", "false")]

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(fake_gen_tf_once))
    # จริง 4 : เท็จ 0 -> ตัด 2 ข้อแรกออกไปรอ ข้อ museum อยู่ท้าย ๆ จึงยังอยู่ในชุดตอนเทียบ
    skewed = [tf(f"ประโยคที่ {i} ถูกต้อง") for i in range(3)] + [tf(museum)]
    out = QuizService._rebalance_tf(skewed, "tf", "เนื้อหา", [], "medium", "applied", 0.97, "language")
    assert out == skewed        # หาข้อแทนไม่ได้ (ซ้ำ) ก็คืนชุดเดิม ไม่ยัดข้อซ้ำเข้ามา
