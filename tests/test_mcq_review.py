"""ครูตรวจปรนัย (_review_mcq) ของเล่มภาษา/ทั่วไป

ที่มา: ปรนัยวิชาที่ไม่ใช่คณิตไม่มีใครตรวจเฉลยเลย เทสไวยากรณ์อังกฤษหลุดมา
- ถาม "ผิดตรงไหน" กับประโยคที่ถูกอยู่แล้ว
- ตัวเลือกถูกมากกว่า 1 ตัว
"""
import json
import os
import types

os.environ.setdefault("OPENAI_API_KEY", "dummy-for-tests")

from app.services.quiz_service import QuizService
from app.services import prompts as P


def _mock_client(monkeypatch, results):
    payload = json.dumps({"results": results})
    calls = {"n": 0}

    class C:
        def create(self, **kw):
            calls["n"] += 1
            calls["prompt"] = kw["messages"][0]["content"]
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=payload))]
            )

    fake = types.SimpleNamespace(chat=types.SimpleNamespace(completions=C()))
    monkeypatch.setattr("app.services.quiz_service.client", fake)
    return calls


def mcq(question, answer="ก"):
    return {
        "type": "mcq",
        "question": question,
        "choices": ["ก) If she were free, she would join us.", "ข) If she is free, she would join us.",
                    "ค) If she were free, she will join us.", "ง) If she was free, she joins us."],
        "answer": answer,
        "explain": "...",
    }


def test_keeps_item_when_reviewer_agrees(monkeypatch):
    _mock_client(monkeypatch, [{"index": 0, "answer": "ก", "extra": "none"}])
    items = [mcq("ประโยคใดใช้เงื่อนไขแบบที่ 2 ได้ถูกต้อง")]
    assert QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา") == items


def test_drops_item_when_reviewer_picks_other_choice(monkeypatch):
    _mock_client(monkeypatch, [{"index": 0, "answer": "ค", "extra": "none"}])
    items = [mcq("ประโยคใดใช้เงื่อนไขแบบที่ 2 ได้ถูกต้อง")]
    assert QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา") == []


def test_drops_item_when_reviewer_says_none(monkeypatch):
    # ถาม "ผิดตรงไหน" กับประโยคที่ถูกอยู่แล้ว ตัวตรวจตอบ none = โจทย์ตั้งผิด
    _mock_client(monkeypatch, [{"index": 0, "answer": "none", "extra": "none"}])
    items = [mcq("ประโยคต่อไปนี้ผิดตรงไหน: If the alarm rings, we will leave immediately.", "ข")]
    assert QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา") == []


def test_drops_item_when_another_choice_is_also_correct(monkeypatch):
    _mock_client(monkeypatch, [{"index": 0, "answer": "ก", "extra": "ข"}])
    items = [mcq("ข้อใดใช้โครงสร้างเงื่อนไขได้ถูกต้อง โดยส่วน if ไม่ใช้ will")]
    assert QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา") == []


def test_extra_equal_to_answer_does_not_drop(monkeypatch):
    # ตัวตรวจกรอก extra ซ้ำกับ answer เอง ไม่ใช่ตัวเลือกอื่น ต้องไม่นับว่ากำกวม
    _mock_client(monkeypatch, [{"index": 0, "answer": "ก", "extra": "ก"}])
    items = [mcq("ประโยคใดใช้เงื่อนไขแบบที่ 2 ได้ถูกต้อง")]
    assert len(QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา")) == 1


def test_unanswered_index_is_kept(monkeypatch):
    # ตัวตรวจตอบไม่ครบ ข้อที่ไม่ได้ตอบไม่มีหลักฐานว่าผิด ให้ผ่าน
    _mock_client(monkeypatch, [{"index": 0, "answer": "ก", "extra": "none"}])
    items = [mcq("ข้อ 1"), mcq("ข้อ 2")]
    assert len(QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหา")) == 2


def test_reviewer_does_not_see_original_answer(monkeypatch):
    calls = _mock_client(monkeypatch, [{"index": 0, "answer": "ก", "extra": "none"}])
    items = [mcq("ประโยคใดใช้เงื่อนไขแบบที่ 2 ได้ถูกต้อง")]
    QuizService._review_mcq(items, 4, "applied", "language", "เนื้อหาอ้างอิงของจริง")
    prompt = calls["prompt"]
    assert "If she were free, she would join us." in prompt      # เห็นตัวเลือกทุกตัว
    assert "เนื้อหาอ้างอิงของจริง" in prompt                       # เห็นเนื้อหาไว้ตัดสินตามกฎ
    assert "เฉลย" not in prompt and '"answer": "ก"' not in prompt  # ไม่เห็นเฉลยเดิม


def test_failclosed_drops_all_on_error(monkeypatch):
    class Boom:
        def create(self, **kw):
            raise RuntimeError("network down")

    fake = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Boom()))
    monkeypatch.setattr("app.services.quiz_service.client", fake)
    assert QuizService._review_mcq([mcq("x")], 4, "applied", "language", "เนื้อหา") == []


def test_math_kind_skips_review_without_calling_ai(monkeypatch):
    calls = _mock_client(monkeypatch, [{"index": 0, "answer": "ข", "extra": "none"}])
    items = [mcq("ลำดับ 3, 7, 11 พจน์ที่ 5 คือเท่าใด")]
    assert QuizService._review_mcq(items, 4, "applied", "math", "เนื้อหา") == items
    assert QuizService._review_mcq(items, 4, "applied", None, "เนื้อหา") == items
    assert calls["n"] == 0


def test_source_mode_skips_review_without_calling_ai(monkeypatch):
    calls = _mock_client(monkeypatch, [{"index": 0, "answer": "ข", "extra": "none"}])
    items = [mcq("x")]
    assert QuizService._review_mcq(items, 4, "source", "language", "เนื้อหา") == items
    assert calls["n"] == 0


def test_general_kind_is_reviewed(monkeypatch):
    calls = _mock_client(monkeypatch, [{"index": 0, "answer": "ข", "extra": "none"}])
    items = [mcq("สัตว์ชนิดหนึ่งออกลูกเป็นไข่ เลือดเย็น จัดอยู่ในกลุ่มใด")]
    assert QuizService._review_mcq(items, 4, "applied", "general", "เนื้อหา") == []
    assert calls["n"] == 1


def test_prompt_is_exported_through_switch():
    text = P.mcq_review_prompt([mcq("q")], "ctx")
    assert "extra" in text and "none" in text and "[0] q" in text
