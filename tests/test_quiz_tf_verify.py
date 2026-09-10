import json
import types

import pytest

from app.services.quiz_service import QuizService
from app.services import quiz_prompts as P


# ----- _math_verdict -----

def test_math_verdict_true_when_stated_matches():
    q = {"question": "สี่เหลี่ยมจัตุรัสด้าน 8 หน่วย มีพื้นที่ 64 ตารางหน่วย",
         "expr": "8**2", "stated": "64", "answer": "true"}
    assert QuizService._math_verdict(q) == "true"


def test_math_verdict_false_when_stated_wrong():
    q = {"question": "12 x (1/2)^3 มีค่าเท่ากับ 3",
         "expr": "12*(1/2)**3", "stated": "3", "answer": "false"}
    assert QuizService._math_verdict(q) == "false"


def test_math_verdict_none_without_expr():
    assert QuizService._math_verdict({"question": "x", "answer": "true"}) is None


def test_math_verdict_none_on_unsafe_expr():
    q = {"question": "ค่าเท่ากับ 1", "expr": "foo(1)", "stated": "1"}
    assert QuizService._math_verdict(q) is None


# ----- ด่านกันการกรอกช่อง stated ผิด (ต้นเหตุที่ข้อ "เท็จ" หายเกลี้ยง) -----

def test_math_verdict_none_when_stated_not_in_question():
    """AI กรอกค่าที่คำนวณได้ (34) แทนค่าที่เขียนในโจทย์ (30) -> ห้ามตัดสิน ให้ถอยไปใช้ตัวตรวจ"""
    q = {
        "question": "ลำดับเลขคณิตที่มีพจน์แรกเป็น 6 และผลต่างร่วมเป็น 4 พจน์ที่ 8 มีค่าเป็น 30",
        "expr": "6+(8-1)*4",     # = 34
        "stated": "34",          # ผิดช่อง! ในโจทย์เขียน 30 ไม่ใช่ 34
        "answer": "false",
    }
    assert QuizService._math_verdict(q) is None


def test_math_verdict_works_when_stated_is_copied_correctly():
    """กรอกถูกช่อง (30 ซึ่งอยู่ในโจทย์จริง) -> ตัดสินได้ว่าเป็นเท็จ"""
    q = {
        "question": "ลำดับเลขคณิตที่มีพจน์แรกเป็น 6 และผลต่างร่วมเป็น 4 พจน์ที่ 8 มีค่าเป็น 30",
        "expr": "6+(8-1)*4",     # = 34 ไม่ตรงกับ 30
        "stated": "30",
        "answer": "false",
    }
    assert QuizService._math_verdict(q) == "false"


def test_math_verdict_handles_negative_and_fraction():
    neg = {"question": "ลำดับที่มีพจน์แรก 11 และผลต่างร่วม -3 พจน์ที่ 6 มีค่าเป็น -4",
           "expr": "11+(6-1)*(-3)", "stated": "-4"}
    assert QuizService._math_verdict(neg) == "true"
    frac = {"question": "ครึ่งหนึ่งของ 1 คือ 1/2", "expr": "1/2", "stated": "1/2"}
    assert QuizService._math_verdict(frac) == "true"


# ----- _verify_tf -----

def _mock_client(monkeypatch, results):
    payload = json.dumps({"results": results})

    class C:
        def create(self, **kw):
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=payload))]
            )

    fake = types.SimpleNamespace(chat=types.SimpleNamespace(completions=C()))
    monkeypatch.setattr("app.services.quiz_service.client", fake)


def test_verify_tf_drops_item_whose_answer_contradicts_python(monkeypatch):
    _mock_client(monkeypatch, [{"index": 0, "answer": "false", "scope": "in"}])
    items = [
        # เขียน 4 ในโจทย์ และ 2+2=4 จริง แต่เฉลยว่าเท็จ -> ขัดกัน ต้องทิ้ง
        {"question": "2 บวก 2 มีค่าเท่ากับ 4", "expr": "2+2", "stated": "4", "answer": "false"},
        # เขียน 5 ในโจทย์ แต่ 2+2=4 ไม่ตรง -> เฉลยเท็จถูกต้อง เก็บไว้
        {"question": "2 บวก 2 มีค่าเท่ากับ 5", "expr": "2+2", "stated": "5", "answer": "false"},
    ]
    kept = QuizService._verify_tf(items, "applied")
    assert [q["question"] for q in kept] == ["2 บวก 2 มีค่าเท่ากับ 5"]
    # ธงชั่วคราวถูกเก็บกวาดทันที ส่วน expr/stated/angle ยังอยู่ต่อ
    # เพราะลูปเก็บข้อยังต้องใช้ angle คุมความหลากหลาย (ตัดออกทีเดียวตอนท้าย)
    assert "_math_ok" not in kept[0]


def test_verify_tf_trusts_python_over_reviewer(monkeypatch):
    """Python คำนวณยืนยันแล้ว ตัวตรวจมาแย้งเรื่องเฉลยไม่ได้"""
    _mock_client(monkeypatch, [{"index": 0, "answer": "false", "scope": "in"}])
    items = [{"question": "2 บวก 2 มีค่าเท่ากับ 4", "expr": "2+2", "stated": "4", "answer": "true"}]
    assert len(QuizService._verify_tf(items, "applied")) == 1


def test_verify_tf_keeps_false_item_when_ai_misfilled_stated(monkeypatch):
    """ข้อ "เท็จ" ที่ AI กรอก stated ผิด ต้องไม่ถูกทิ้ง แต่ให้ตัวตรวจ AI ตัดสินแทน

    นี่คือเคสที่ทำให้เฉลยออกมาเป็น "จริง" ทั้ง 15 ข้อ
    """
    _mock_client(monkeypatch, [{"index": 0, "answer": "false", "scope": "in"}])
    items = [{
        "question": "ลำดับเลขคณิตที่มีพจน์แรกเป็น 6 และผลต่างร่วมเป็น 4 พจน์ที่ 8 มีค่าเป็น 30",
        "expr": "6+(8-1)*4",
        "stated": "34",          # กรอกค่าที่คำนวณได้ แทนค่าที่เขียนในโจทย์
        "answer": "false",
    }]
    assert len(QuizService._verify_tf(items, "applied")) == 1


def test_verify_tf_drops_out_of_scope_even_when_math_is_right(monkeypatch):
    """เลขถูก แต่ใช้กฎที่เนื้อหาไม่ได้สอน → ต้องถูกทิ้ง"""
    _mock_client(monkeypatch, [{"index": 0, "answer": "true", "scope": "out"}])
    items = [{"question": "a", "expr": "2*3", "stated": "6", "answer": "true"}]
    assert QuizService._verify_tf(items, "applied", "เนื้อหาสอนแค่บวกลบ") == []


def test_verify_tf_passes_non_math_to_review(monkeypatch):
    _mock_client(monkeypatch, [{"index": 0, "answer": "true"}])
    items = [{"question": "ภาษา", "answer": "true"}]
    assert len(QuizService._verify_tf(items, "applied")) == 1


def test_missing_scope_field_counts_as_in_scope(monkeypatch):
    """ตัวตรวจไม่ตอบ scope มา ต้องไม่ตีตกทิ้ง (เอนไปทางเก็บไว้)"""
    _mock_client(monkeypatch, [{"index": 0, "answer": "true"}])
    items = [{"question": "ภาษา", "answer": "true"}]
    assert len(QuizService._verify_tf(items, "applied", "เนื้อหา")) == 1


def test_verify_tf_review_failclosed_drops_all_on_error(monkeypatch):
    class Boom:
        def create(self, **kw):
            raise RuntimeError("network down")

    fake = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Boom()))
    monkeypatch.setattr("app.services.quiz_service.client", fake)
    items = [{"question": "ภาษา", "answer": "true"}]
    assert QuizService._verify_tf(items, "applied") == []


def test_verify_tf_noop_for_source_mode(monkeypatch):
    items = [{"question": "x", "answer": "true"}]
    assert QuizService._verify_tf(items, "source") == items


# ----- _tf_want -----

def test_tf_want_asks_false_when_true_heavy():
    collected = [{"answer": "true"}] * 4 + [{"answer": "false"}] * 1
    assert QuizService._tf_want(collected, "applied") == "false"


def test_tf_want_asks_true_when_false_heavy():
    collected = [{"answer": "false"}] * 3 + [{"answer": "true"}] * 1
    assert QuizService._tf_want(collected, "applied") == "true"


def test_tf_want_none_when_balanced():
    collected = [{"answer": "true"}, {"answer": "false"}]
    assert QuizService._tf_want(collected, "applied") is None


def test_tf_want_none_for_source():
    collected = [{"answer": "true"}] * 5
    assert QuizService._tf_want(collected, "source") is None


# ----- prompt wiring -----

def test_tf_want_block_empty_for_source():
    assert P.tf_want_block("false", "source") == ""


def test_tf_want_block_present_for_applied():
    assert "เท็จ" in P.tf_want_block("false", "applied")


def test_applied_tf_json_has_explain_before_answer():
    j = P.TF_JSON_FORMAT["applied"]
    assert j.index("explain") < j.index('"answer"')
    assert "expr" in j and "stated" in j


# ----- ความหลากหลายของโครงประโยค -----

# ตัวอย่างจริงจากที่ผู้ใช้รายงาน: โครงเดียวกัน เปลี่ยนแค่ตัวเลข
_NTH_TERM = [
    "ถ้าลำดับเลขคณิตมีพจน์แรก 6 และผลต่างร่วม 3 พจน์ที่ 8 มีค่าเท่ากับ 27",
    "ลำดับเลขคณิตที่มีพจน์แรก 5 และผลต่างร่วม 2 พจน์ที่ 9 มีค่าเท่ากับ 21",
    "ลำดับเลขคณิตที่มีพจน์แรก 9 และผลต่างร่วม 3 พจน์ที่ 5 มีค่าเท่ากับ 20",
]
_SUM_FORMULA = "ผลบวก 6 พจน์แรกของลำดับเลขคณิตที่มีพจน์แรก 3 และพจน์สุดท้าย 18 เท่ากับ 60"


def test_structure_full_blocks_third_clone():
    collected = [{"question": q} for q in _NTH_TERM[:2]]
    assert QuizService._structure_full(_NTH_TERM[2], collected, "applied") is True


def test_structure_full_allows_second_of_a_shape():
    collected = [{"question": _NTH_TERM[0]}]
    assert QuizService._structure_full(_NTH_TERM[1], collected, "applied") is False


def test_structure_full_allows_different_shape():
    """สูตรผลบวก เป็นคนละโครงกับสูตรพจน์ที่ n จึงต้องผ่าน"""
    collected = [{"question": q} for q in _NTH_TERM[:2]]
    assert QuizService._structure_full(_SUM_FORMULA, collected, "applied") is False


def test_structure_full_off_for_source_mode():
    collected = [{"question": q} for q in _NTH_TERM[:2]]
    assert QuizService._structure_full(_NTH_TERM[2], collected, "source") is False


def test_overused_questions_reports_only_full_shapes():
    collected = [{"question": q} for q in _NTH_TERM[:2]] + [{"question": _SUM_FORMULA}]
    out = QuizService._overused_questions(collected, "applied")
    assert out == [_NTH_TERM[0]]        # โครงพจน์ที่ n เต็มแล้ว / โครงผลบวกยังมีข้อเดียว


def test_structure_full_counts_existing_questions(monkeypatch):
    """บั๊กตอนกดขอเพิ่มข้อ: โครงที่ข้อเก่าใช้ไปแล้ว ต้องนับด้วย"""
    prior = _NTH_TERM[:2]                       # ข้อเก่า 2 ข้อ ใช้โครงนี้ไปแล้ว
    assert QuizService._structure_full(_NTH_TERM[2], [], "applied", prior) is True
    # ถ้าไม่ส่งข้อเก่ามา จะมองไม่เห็น (พฤติกรรมเดิมที่เป็นบั๊ก)
    assert QuizService._structure_full(_NTH_TERM[2], [], "applied") is False


def test_overused_questions_counts_existing_questions():
    out = QuizService._overused_questions([], "applied", prior=_NTH_TERM[:2])
    assert out == [_NTH_TERM[0]]


def test_avoid_structure_block_empty_for_source():
    assert P.tf_avoid_structure_block([_NTH_TERM[0]], "source") == ""


def test_avoid_structure_block_lists_examples():
    block = P.tf_avoid_structure_block([_NTH_TERM[0]], "applied")
    assert _NTH_TERM[0] in block


# ----- prompt ตรวจขอบเขต -----

def test_review_prompt_without_context_has_no_scope_field():
    p = P.tf_review_prompt([{"question": "x"}])
    assert "scope" not in p


def test_review_prompt_with_context_asks_for_scope():
    p = P.tf_review_prompt([{"question": "x"}], "เนื้อหาสอนแค่บวกลบ")
    assert '"scope":"in|out"' in p
    assert "เนื้อหาสอนแค่บวกลบ" in p


# ----- ปรับสมดุลตอนรวมผล (บั๊กที่ 3: เอกสารยาวไม่เคยถูกปรับสมดุล) -----

def _tf(question, answer):
    return {"question": question, "answer": answer}


def test_rebalance_swaps_surplus_true_for_false(monkeypatch):
    """เฉลยจริงล้วน 6 ข้อ -> ต้องขอฝั่งเท็จมาสลับ"""
    # โครงประโยคต้องต่างกัน ไม่งั้นโดนเพดานโครง (2 ข้อต่อโครง) ปัดตกเอง
    shapes = [
        "สี่เหลี่ยมผืนผ้ากว้าง 3 ยาว 5 มีพื้นที่ 20 ตารางหน่วย",
        "ห้องกว้าง 4 เมตร ยาว 6 เมตร ต้องใช้กระเบื้อง 30 แผ่น",
        "ลำดับเลขคณิตพจน์แรก 2 ผลต่างร่วม 3 พจน์ที่ 5 มีค่าเป็น 15",
        "รถวิ่ง 60 กิโลเมตรต่อชั่วโมง เป็นเวลา 3 ชั่วโมง ได้ระยะทาง 200 กิโลเมตร",
        "จำนวนเต็มบวกที่น้อยกว่า 10 และหารด้วย 3 ลงตัว มีทั้งหมด 5 จำนวน",
    ]
    replacements = [
        {"type": "tf", "question": q, "answer": "false", "explain": "x"}
        for q in shapes
    ]
    calls = {"n": 0}

    def fake_gen(*a, **kw):
        calls["n"] += 1
        return replacements

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(fake_gen))
    collected = [_tf(f"ข้อจริงที่ {i}", "true") for i in range(6)]

    out = QuizService._rebalance_tf(collected, "tf", "เนื้อหา", [], "medium", "applied", 0.97)

    assert calls["n"] == 1
    n_true = sum(1 for q in out if QuizService._is_true_answer(q))
    assert len(out) == 6
    assert n_true == 3 and (len(out) - n_true) == 3      # 6:0 -> 3:3


def test_rebalance_noop_when_already_balanced(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("ไม่ควรถูกเรียกเมื่อสมดุลอยู่แล้ว")

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(boom))
    collected = [_tf("ก", "true"), _tf("ข", "false"), _tf("ค", "true")]
    assert QuizService._rebalance_tf(collected, "tf", "x", [], "medium", "applied", 0.97) == collected


def test_rebalance_noop_for_source_and_mcq(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("ไม่ควรถูกเรียก")

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(boom))
    skewed = [_tf(f"ข้อ {i}", "true") for i in range(6)]
    assert QuizService._rebalance_tf(skewed, "tf", "x", [], "medium", "source", 0.97) == skewed
    assert QuizService._rebalance_tf(skewed, "mcq", "x", [], "medium", "applied", 0.97) == skewed


def test_rebalance_survives_generation_failure(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(boom))
    skewed = [_tf(f"ข้อ {i}", "true") for i in range(6)]
    assert QuizService._rebalance_tf(skewed, "tf", "x", [], "medium", "applied", 0.97) == skewed


# ----- ผ่อนเพดานโครงเมื่อหาข้อไม่ครบ -----

def test_structure_cap_starts_strict_then_relaxes():
    assert P.structure_cap(0) == 2
    assert P.structure_cap(1) == 2
    assert P.structure_cap(2) == 3
    assert P.structure_cap(4) == 4
    assert P.structure_cap(99) == P.APPLIED_STRUCTURE_CAP_MAX


def test_structure_full_respects_explicit_cap():
    collected = [{"question": q} for q in _NTH_TERM[:2]]
    # เพดาน 2 -> ข้อที่ 3 เข้าไม่ได้
    assert QuizService._structure_full(_NTH_TERM[2], collected, "applied") is True
    # ผ่อนเป็น 3 -> เข้าได้
    assert QuizService._structure_full(_NTH_TERM[2], collected, "applied", None, 3) is False


# ----- คุมความหลากหลายด้วย "มุมของโจทย์" -----

def _q(angle, question="ข้อสอบ", answer="true"):
    return {"angle": angle, "question": question, "answer": answer}


def test_angle_of_reads_known_angles():
    assert QuizService._angle_of({"angle": "compare"}) == "compare"
    assert QuizService._angle_of({"angle": "VALUE"}) == "value"
    assert QuizService._angle_of({"angle": "ไม่รู้จัก"}) is None
    assert QuizService._angle_of({}) is None


def test_angle_full_blocks_when_quota_reached():
    collected = [_q("value"), _q("value")]
    assert QuizService._angle_full("value", collected, "applied", 2) is True
    assert QuizService._angle_full("compare", collected, "applied", 2) is False


def test_angle_full_off_for_source_mode():
    collected = [_q("value")] * 5
    assert QuizService._angle_full("value", collected, "source", 2) is False


def test_angle_cap_forces_several_angles():
    assert P.angle_cap(15, n_angles=5) == 4   # 5 มุม x 4 = 20 พอสำหรับ 15 ข้อ
    assert P.angle_cap(1, n_angles=5) == 2
    assert P.angle_cap(15, tries=2, n_angles=5) == 5   # ผ่อนเมื่อหาไม่ครบ


def test_angle_cap_scales_with_how_many_angles_are_allowed():
    """ระดับยากใช้ได้แค่ 2 มุม เพดานต้องโตตาม ไม่งั้นสองกฎจะล็อกกันเอง

    ถ้าเพดานยังเป็น 2 จะได้อย่างมาก 2x2 = 4 ข้อ ทั้งที่ผู้ใช้ขอ 5
    แล้วระบบจะวนหาไม่ครบไปเรื่อย ๆ
    """
    cap = P.angle_cap(5, n_angles=2)
    assert cap * 2 >= 5


def test_overused_angles_lists_only_full_ones():
    collected = [_q("value"), _q("value"), _q("compare")]
    assert QuizService._overused_angles(collected, "applied", 2) == ["value"]


def test_avoid_angle_block_empty_for_source():
    assert P.tf_avoid_angle_block(["value"], "source") == ""


def test_avoid_angle_block_names_used_and_remaining():
    block = P.tf_avoid_angle_block(["value"], "applied")
    assert "value" in block and "compare" in block


def test_compare_and_property_are_exempt_from_expr():
    assert set(P.TF_ANGLES_WITHOUT_EXPR) == {"compare", "property"}
    # ระดับกลางมีมุม property -> ต้องบอกว่าไม่ต้องกรอก expr
    assert "ไม่ต้องกรอก expr" in P.angle_guide_block("medium", "applied", "tf")


def test_applied_json_puts_angle_before_question():
    j = P.TF_JSON_FORMAT["applied"]
    assert j.index('"angle"') < j.index('"question"')


def test_internal_fields_are_stripped_from_output():
    items = [{"question": "q", "answer": "true", "angle": "value",
              "expr": "1+1", "stated": "2", "_math_ok": True}]
    out = QuizService._strip_internal(items)
    assert set(out[0]) == {"question", "answer"}


# ----- กระจายข้อสอบตามกฎที่เนื้อหาสอน -----

_RULES = ["พจน์ที่ n เลขคณิต", "ผลบวกเลขคณิต", "พจน์ที่ n เรขาคณิต",
          "ผลบวกเรขาคณิตจำกัด", "อนุกรมอนันต์"]


def test_plan_rule_quota_splits_evenly():
    plan = P.plan_rule_quota(_RULES, 15)
    assert [n for _, n in plan] == [3, 3, 3, 3, 3]
    assert sum(n for _, n in plan) == 15


def test_plan_rule_quota_handles_remainder():
    plan = P.plan_rule_quota(_RULES, 13)
    assert sum(n for _, n in plan) == 13
    assert max(n for _, n in plan) - min(n for _, n in plan) <= 1


def test_plan_rule_quota_spreads_when_more_rules_than_questions():
    """กฎ 5 ข้อ แต่ขอ 3 ข้อ -> ต้องเลือกแบบกระจาย ไม่ใช่หยิบ 3 กฎแรก"""
    plan = P.plan_rule_quota(_RULES, 3)
    picked = [name for name, _ in plan]
    assert len(picked) == 3
    assert picked != _RULES[:3]
    assert _RULES[-1] in picked          # กฎท้ายสุด (อนุกรมอนันต์) ต้องไม่ถูกทิ้ง


def test_plan_rule_quota_empty_when_no_rules():
    assert P.plan_rule_quota([], 10) == []


def test_rule_quota_block_empty_for_source():
    plan = P.plan_rule_quota(_RULES, 15)
    assert P.rule_quota_block(plan, "source") == ""


def test_rule_quota_block_lists_every_rule():
    block = P.rule_quota_block(P.plan_rule_quota(_RULES, 15), "applied")
    for name in _RULES:
        assert name in block


def test_applicable_rules_prompt_excludes_standalone_facts():
    p = P.applicable_rules_prompt("เนื้อหา")
    assert "เกร็ดความรู้" in p
    assert "ปีที่เกิดเหตุการณ์" in p


def test_applicable_rules_prompt_allows_rules_named_after_people():
    """กฎของนิวตัน/พีทาโกรัส มีชื่อคนแต่ใช้กับข้อมูลชุดใหม่ได้ ต้องไม่ถูกตัดทิ้ง

    เกณฑ์ต้องเป็น "ใช้กับกรณีใหม่ได้ไหม" ไม่ใช่ "มีชื่อคนไหม"
    ไม่งั้นวิชาวิทยาศาสตร์จะเหลือกฎให้ออกข้อสอบน้อยมาก
    """
    p = P.applicable_rules_prompt("เนื้อหา")
    assert "กฎของนิวตัน" in p
    assert "ชื่อที่มีชื่อบุคคลอยู่ด้วยก็ใส่ได้" in p


# ----- JSON ปรนัย: โหมดเดิมห้ามเปลี่ยน / โหมดประยุกต์เพิ่ม angle+rule -----

def test_mcq_json_source_is_unchanged():
    got = P.mcq_json_format("source", '"ก) ...", "ข) ..."', "ก|ข")
    assert got == ('{"questions":[{"type":"mcq","question":"...",'
                   '"choices":["ก) ...", "ข) ..."],"answer":"ก|ข",'
                   '"explain":"...","topic":"..."}]}')


def test_mcq_json_applied_puts_angle_and_rule_first():
    got = P.mcq_json_format("applied", '"ก) ..."', "ก")
    assert got.index('"angle"') < got.index('"question"')
    assert got.index('"rule"') < got.index('"question"')
    # ลำดับช่องที่เหลือต้องเหมือนเดิม เพื่อไม่ให้กระทบความถูกต้องของปรนัย
    assert got.index('"question"') < got.index('"choices"') < got.index('"answer"') < got.index('"explain"')


def test_mcq_gets_angle_guidance_in_applied_only():
    assert "มุมของโจทย์ ต้องหลากหลาย" in P.angle_guide_block("medium", "applied", "mcq")
    assert P.angle_guide_block("medium", "source", "mcq") == ""


def test_mcq_applied_asks_for_expr_but_source_does_not():
    assert "ช่อง expr" in P.ANSWER_RULES_MCQ["applied"]
    assert "expr" not in P.ANSWER_RULES_MCQ["source"]


# ----- มุมต้องสอดคล้องกับระดับความยาก -----

def test_easy_excludes_reverse_and_compare():
    """กติกาข้อง่ายเขียนไว้ว่า 'ห้ามถามย้อนจากผลลัพธ์' มุมจึงต้องไม่มี reverse"""
    easy = P.angles_for("easy")
    assert "reverse" not in easy and "compare" not in easy
    assert "value" in easy


def test_hard_uses_angles_that_need_more_work():
    hard = P.angles_for("hard")
    assert "compare" in hard and "reverse" in hard
    assert "value" not in hard          # แทนค่าครั้งเดียวไม่ควรอยู่ในระดับยาก


def test_angle_guide_lists_only_allowed_angles():
    block = P.angle_guide_block("easy", "applied", "tf")
    assert "reverse" not in block
    assert "value" in block and "situation" in block


def test_hard_rule_quota_tells_ai_to_combine_rules():
    """โควตากฎแบบเดิมสื่อว่า 1 ข้อ = 1 กฎ ซึ่งขัดกับนิยามข้อยาก"""
    plan = P.plan_rule_quota(_RULES, 9)
    hard = P.rule_quota_block(plan, "applied", "hard")
    normal = P.rule_quota_block(plan, "applied", "easy")
    assert "2 ข้อร่วมกัน" in hard
    assert "2 ข้อร่วมกัน" not in normal


# ----- หมุนกฎที่เลือก เมื่อเจนทีละชุด -----

def test_rule_plan_rotates_so_every_rule_eventually_appears():
    """6 กฎ เจนทีละ 5 ข้อ 3 รอบ ต้องแตะครบทุกกฎ ไม่ใช่ข้ามกฎเดิมทุกรอบ"""
    rules = _RULES + ["กฎที่หก"]
    seen = set()
    for round_no in range(3):
        plan = P.plan_rule_quota(rules, 5, offset=round_no * 5)
        seen.update(name for name, _ in plan)
    assert seen == set(rules)


def test_rule_plan_without_offset_repeats_same_choice():
    """ยืนยันว่าถ้าไม่หมุน จะได้กฎชุดเดิมทุกครั้ง (ต้นเหตุที่บางกฎไม่เคยออก)"""
    rules = _RULES + ["กฎที่หก"]
    a = [n for n, _ in P.plan_rule_quota(rules, 5)]
    b = [n for n, _ in P.plan_rule_quota(rules, 5)]
    assert a == b
    assert len(set(a)) < len(rules)


# ----- ตรวจเลขปรนัยด้วย Python -----

def _mcq(answer="ก", choices=None, **kw):
    q = {"type": "mcq", "question": "โจทย์", "answer": answer,
         "choices": choices or ["ก) 216", "ข) 180", "ค) 171", "ง) 162"]}
    q.update(kw)
    return q


def test_mcq_math_catches_wrong_answer():
    """เคสจริง: ที่นั่งโรงละคร AI ตอบ 180 แต่คำตอบจริงคือ 216"""
    q = _mcq(answer="ข", expr="(9/2)*(12+36)", angle="situation")
    assert QuizService._mcq_math_ok(q, 4) is False


def test_mcq_math_passes_correct_answer():
    q = _mcq(answer="ก", expr="(9/2)*(12+36)", angle="situation")
    assert QuizService._mcq_math_ok(q, 4) is True


def test_mcq_math_skips_when_no_expr():
    assert QuizService._mcq_math_ok(_mcq(), 4) is None


def test_mcq_math_skips_compare_angle():
    """ตัวเลือกแบบ 'ชุดที่ 3' ตรวจด้วยตัวเลขไม่ได้ ต้องข้าม ไม่ใช่ทิ้ง"""
    q = _mcq(answer="ก", expr="117", angle="compare",
             choices=["ก) ชุดที่ 3", "ข) ชุดที่ 1", "ค) ชุดที่ 2", "ง) เท่ากันทุกชุด"])
    assert QuizService._mcq_math_ok(q, 4) is None


def test_mcq_math_skips_choice_with_many_numbers():
    q = _mcq(answer="ก", expr="10", angle="value",
             choices=["ก) 5 และ 10", "ข) 20", "ค) 30", "ง) 40"])
    assert QuizService._mcq_math_ok(q, 4) is None


def test_mcq_math_handles_unit_in_choice():
    q = _mcq(answer="ก", expr="5+(9-1)*2", angle="situation",
             choices=["ก) 21 กล่อง", "ข) 23 กล่อง", "ค) 19 กล่อง", "ง) 25 กล่อง"])
    assert QuizService._mcq_math_ok(q, 4) is True


# ----- ข้อซ้ำเชิงแนวคิด -----

_CONCEPT_A = "ข้อใดเป็นเงื่อนไขที่ทำให้อนุกรมเรขาคณิตอนันต์มีผลบวกเป็นค่าจำกัด"
_CONCEPT_B = "ข้อใดเป็นเงื่อนไขที่ทำให้อัตราส่วนร่วมของอนุกรมเรขาคณิตอนันต์มีผลบวกเป็นค่าจำกัด"
_SAME_ANSWER = "ค่าสัมบูรณ์ของอัตราส่วนร่วมต้องน้อยกว่า 1"


def _concept(question, correct):
    return {"type": "mcq", "question": question, "answer": "ก",
            "choices": [f"ก) {correct}", "ข) อื่น ๆ", "ค) อื่น ๆ 2", "ง) อื่น ๆ 3"]}


def test_concept_duplicate_caught(monkeypatch):
    """เคสจริง: ข้อ 2 กับ ข้อ 9 ถามเรื่องเดียวกัน เฉลยเดียวกัน"""
    collected = [_concept(_CONCEPT_A, _SAME_ANSWER)]
    dup = _concept(_CONCEPT_B, _SAME_ANSWER)
    assert QuizService._is_concept_duplicate(dup, collected, "mcq", "applied") is True


def test_similar_question_with_different_answer_is_kept():
    """วิชาภาษา: 'ข้อใดใช้ ... ถูกต้อง' กับ 'ไม่ถูกต้อง' คำถามคล้ายมากแต่คนละข้อ"""
    collected = [_concept("ข้อใดใช้ present perfect ถูกต้อง", "She has gone home")]
    other = _concept("ข้อใดใช้ present perfect ไม่ถูกต้อง", "She have went home")
    assert QuizService._is_concept_duplicate(other, collected, "mcq", "applied") is False


def test_numeric_questions_are_never_concept_duplicates():
    """โจทย์ที่มีตัวเลข เปลี่ยนเลขแล้วถือเป็นคนละข้อ ห้ามตัด"""
    a = _concept("ลำดับที่มีพจน์แรก 6 ผลต่างร่วม 4 พจน์ที่ 9 มีค่าเท่าใด", "38")
    b = _concept("ลำดับที่มีพจน์แรก 2 ผลต่างร่วม 4 พจน์ที่ 10 มีค่าเท่าใด", "38")
    assert QuizService._is_concept_duplicate(b, [a], "mcq", "applied") is False


def test_concept_duplicate_off_for_source():
    collected = [_concept(_CONCEPT_A, _SAME_ANSWER)]
    dup = _concept(_CONCEPT_B, _SAME_ANSWER)
    assert QuizService._is_concept_duplicate(dup, collected, "mcq", "source") is False


# ----- แผนกระจายกฎ ต้องไม่ตกกฎใดถาวร ไม่ว่าจะมีกี่กฎ -----

@pytest.mark.parametrize("n_rules", range(1, 15))
@pytest.mark.parametrize("per_round", [3, 5, 10])
def test_rule_plan_covers_everything_it_can(n_rules, per_round):
    """เจนทีละชุด 3 รอบ ต้องแตะกฎให้ได้มากที่สุดเท่าที่จำนวนข้อจะอำนวย

    เคสที่เคยพัง: 10 กฎ ขอรอบละ 5 (รวม 15 ข้อ) แตะได้แค่ 6 กฎ
    เพราะการหมุนไม่ลงล็อกกับจังหวะการเลือก บางกฎถูกหยิบซ้ำ บางกฎไม่เคยถูกหยิบ
    """
    rules = [f"r{i}" for i in range(n_rules)]
    seen = set()
    for rnd in range(3):
        plan = P.plan_rule_quota(rules, per_round, offset=rnd * per_round)
        assert sum(c for _, c in plan) == per_round        # โควตาต้องครบพอดี
        assert len({n for n, _ in plan}) == len(plan)      # ห้ามมีกฎซ้ำในรอบเดียว
        seen.update(n for n, _ in plan)
    assert len(seen) >= min(3 * per_round, n_rules)


@pytest.mark.parametrize("n_rules,count", [(12, 5), (10, 5), (8, 3), (7, 4)])
def test_walk_stride_visits_every_rule_before_repeating(n_rules, count):
    """หัวใจของการแก้: ระยะก้าวต้องหารร่วมกับจำนวนกฎได้ 1"""
    import math as _math
    assert _math.gcd(P._walk_stride(n_rules, count), n_rules) == 1


# ----- บังคับให้ส่งสูตรมา เมื่อคำตอบเป็นตัวเลขที่ตรวจได้ -----

def test_mcq_missing_expr_is_rejected_when_answer_is_a_number():
    """เคสจริง ข้อ 15: คำอธิบายสรุปเอง n = 7 แต่กรอกเฉลย "พจน์ที่ 8"

    AI ไม่ส่งสูตรมาเพราะเห็นคำตอบมีตัวหนังสือปน เลยคิดว่าไม่ใช่ตัวเลข
    ผลคือไม่มีใครตรวจ เฉลยผิดจึงหลุดออกไป
    """
    q = {"type": "mcq", "angle": "reverse",
         "question": "ลำดับเลขคณิตพจน์แรก 9 ผลต่างร่วม 6 ค่า 45 เป็นพจน์ที่เท่าใด",
         "answer": "ข",
         "choices": ["ก) พจน์ที่ 7", "ข) พจน์ที่ 8", "ค) พจน์ที่ 9", "ง) พจน์ที่ 6"]}
    assert QuizService._mcq_math_ok(q, 4) is False


def test_mcq_with_expr_on_worded_number_is_checked():
    """ส่งสูตรมาแล้ว ต้องตรวจได้จริงแม้คำตอบจะมีคำประกอบ"""
    base = {"type": "mcq", "angle": "reverse",
            "question": "ลำดับเลขคณิตพจน์แรก 9 ผลต่างร่วม 6 ค่า 45 เป็นพจน์ที่เท่าใด",
            "choices": ["ก) พจน์ที่ 7", "ข) พจน์ที่ 8", "ค) พจน์ที่ 9", "ง) พจน์ที่ 6"]}
    assert QuizService._mcq_math_ok({**base, "answer": "ก", "expr": "(45-9)/6+1"}, 4) is True
    assert QuizService._mcq_math_ok({**base, "answer": "ข", "expr": "(45-9)/6+1"}, 4) is False


def test_language_question_without_expr_is_not_rejected():
    """วิชาภาษา คำตอบบังเอิญมีตัวเลข แต่ไม่ใช่การคำนวณ ต้องไม่ถูกทิ้ง"""
    q = {"type": "mcq", "angle": "value",
         "question": "ข้อใดใช้ present perfect ได้ถูกต้อง",
         "answer": "ก",
         "choices": ["ก) She has read 2 books", "ข) อื่น", "ค) อื่น", "ง) อื่น"]}
    assert QuizService._mcq_math_ok(q, 4) is None


def test_concept_answer_without_numbers_is_not_rejected():
    q = {"type": "mcq", "angle": "value",
         "question": "ลำดับที่มีพจน์แรก 5 และผลต่างร่วม 2 เป็นลำดับแบบใด",
         "answer": "ก",
         "choices": ["ก) ลำดับเลขคณิต", "ข) ลำดับเรขาคณิต", "ค) ไม่ใช่ทั้งสอง", "ง) ลำดับฟีโบนักชี"]}
    assert QuizService._mcq_math_ok(q, 4) is None


# ----- บังคับมุมตามระดับ พร้อมตัวถอยอัตโนมัติ -----

def _angled(angle):
    return {"type": "mcq", "question": "โจทย์", "answer": "ก", "angle": angle}


def test_hard_rejects_situation_at_first():
    """ห่อโจทย์ง่ายด้วยเรื่องเล่า ไม่ได้ทำให้ยากขึ้น จึงไม่ควรอยู่ในระดับยาก"""
    assert QuizService._angle_allowed(_angled("situation"), "hard", "applied", tries=0) is False
    assert QuizService._angle_allowed(_angled("reverse"), "hard", "applied", tries=0) is True
    assert QuizService._angle_allowed(_angled("compare"), "hard", "applied", tries=0) is True


def test_easy_rejects_reverse():
    """กติกาข้อง่ายเขียนไว้ว่าห้ามถามย้อนจากผลลัพธ์"""
    assert QuizService._angle_allowed(_angled("reverse"), "easy", "applied", tries=0) is False
    assert QuizService._angle_allowed(_angled("value"), "easy", "applied", tries=0) is True


def test_relaxes_after_a_couple_of_failed_rounds():
    """เนื้อหาที่ทำมุมเข้ม ๆ ไม่ไหว ต้องไม่ถูกบังคับจนออกข้อสอบไม่ได้"""
    q = _angled("situation")
    assert QuizService._angle_allowed(q, "hard", "applied", tries=0) is False
    assert QuizService._angle_allowed(q, "hard", "applied", tries=2) is True   # ผ่อนขั้นแรก
    assert QuizService._angle_allowed(q, "hard", "applied", tries=4) is True   # เลิกบังคับ


def test_gives_up_enforcing_entirely_at_the_end():
    """รอบท้าย ๆ ต้องรับทุกมุม ไม่งั้นเอกสารบางจะได้ข้อสอบน้อยเกินไป"""
    for angle in P.TF_ANGLES:
        assert QuizService._angle_allowed(_angled(angle), "easy", "applied", tries=4) is True


def test_angle_rule_off_for_source_mode():
    assert QuizService._angle_allowed(_angled("compare"), "easy", "source", tries=0) is True


def test_question_without_declared_angle_passes():
    """ไม่ได้แจ้งมุมมา = ไม่มีข้อมูลพอจะตัดสิน ต้องไม่ทิ้ง (กันวิชาที่ AI ไม่แจ้ง)"""
    q = {"type": "mcq", "question": "โจทย์", "answer": "ก"}
    assert QuizService._angle_allowed(q, "hard", "applied", tries=0) is True


def test_angles_widen_step_by_step():
    assert set(P.angles_for("hard", 0)) == {"reverse", "compare"}
    assert set(P.angles_for("hard", 2)) == {"reverse", "compare", "situation"}
    assert set(P.angles_for("hard", 4)) == set(P.TF_ANGLES)


def test_angle_guide_block_follows_the_relaxation():
    strict = P.angle_guide_block("hard", "applied", "mcq", tries=0)
    loose = P.angle_guide_block("hard", "applied", "mcq", tries=4)
    assert "situation" not in strict          # ยังไม่ผ่อน ห้ามใช้
    assert "situation" in loose               # ผ่อนแล้ว บอก AI ด้วย
