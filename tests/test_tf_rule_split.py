"""K2: แบ่งแผนกฎให้ฝั่งจริง/เท็จคนละครึ่ง เพื่อไม่ให้สองฝั่งหยิบกรณีเดียวกัน

ที่มา: ชีววิทยา 15 ข้อ TF มี 4 คู่ "กรณีเดียวกัน จริง 1 เท็จ 1" (มอสส์ ลูกอ๊อด หนอนตัวแบน กิ้งก่า)
เพราะสองฝั่งยิงพร้อมกันจากกฎชุดเดียวกัน ต่างคนต่างหยิบตัวอย่างเด่นสุดของกฎนั้น
"""
import os

os.environ.setdefault("OPENAI_API_KEY", "dummy-for-tests")

from app.services.quiz_service import QuizService


def test_split_alternates_rules_between_sides():
    plan = [("กฎ1", 1), ("กฎ2", 1), ("กฎ3", 1), ("กฎ4", 1), ("กฎ5", 1)]
    sides = QuizService._split_rule_plan(plan)
    assert sides["true"] == [("กฎ1", 1), ("กฎ3", 1), ("กฎ5", 1)]
    assert sides["false"] == [("กฎ2", 1), ("กฎ4", 1)]


def test_single_rule_is_shared_by_both_sides():
    plan = [("กฎเดียว", 3)]
    sides = QuizService._split_rule_plan(plan)
    assert sides["true"] == plan and sides["false"] == plan


def test_empty_plan_stays_empty():
    assert QuizService._split_rule_plan(None) == {"true": None, "false": None}
    assert QuizService._split_rule_plan([]) == {"true": [], "false": []}


def test_tf_split_sends_different_rules_to_each_side(monkeypatch):
    seen = {}

    def fake_gen_tf_once(ctx, n, exclude_list, topic_hints, difficulty, mode, want, avoid,
                         avoid_angles, rule_plan, tries, kind):
        seen[want] = [r for r, _ in (rule_plan or [])]
        return []

    monkeypatch.setattr(QuizService, "_gen_tf_once", staticmethod(fake_gen_tf_once))
    plan = [("มอสส์", 1), ("เฟิร์น", 1), ("สน", 1), ("พืชดอก", 1)]
    QuizService._gen_tf_split("เนื้อหา", 4, [], None, "easy", "applied", None, None, plan, [], 0, "general")
    assert seen["true"] == ["มอสส์", "สน"]
    assert seen["false"] == ["เฟิร์น", "พืชดอก"]
    assert not set(seen["true"]) & set(seen["false"])
