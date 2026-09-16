"""ตรวจว่า prompt ของโหมดประยุกต์ (applied) ไม่เปลี่ยนโดยไม่ตั้งใจ

คู่กับ check_prompt.py ที่คุมโหมดเดิม ตัวนี้คุมโหมดประยุกต์
ใช้ตอน "ย้ายโค้ด" (แยกไฟล์ จัดโครงสร้าง) ที่ตั้งใจให้ผลลัพธ์เหมือนเดิมทุกตัวอักษร

ต่างจากโหมดเดิมตรงที่ prompt ประยุกต์ประกอบจากหลายส่วนและมีหลายแบบ
(ตามเล่ม คณิต/ภาษา/ทั่วไป ตามมุม ตามกฎ ตามรอบที่ขอซ้ำ) จึงถ่ายไว้หลายกรณี
รวมถึง prompt ถามชนิดเนื้อหา prompt หากฎ และ prompt ตรวจทานถูก/ผิด ที่ยิงแยกต่างหาก

วิธีใช้
  python tools/check_prompt_applied.py --save   # ถ่ายภาพก่อนย้าย
  python tools/check_prompt_applied.py          # เทียบหลังย้าย

ไฟล์ภาพถ่ายเก็บที่ tools/prompt_snapshot_applied.json
"""
import difflib
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "dummy-for-check")

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_snapshot_applied.json")

CTX = """ลำดับเลขคณิต
พจน์ที่ n ของลำดับเลขคณิต an = a1 + (n-1)d
ผลบวก n พจน์แรก Sn = (n/2)(a1 + an)
ตัวอย่าง: ลำดับ 3, 7, 11 มีพจน์แรก 3 ผลต่างร่วม 4 พจน์ที่ 5 คือ 19"""

EXCLUDE = [
    {"question": "ลำดับที่มีพจน์แรก 3 ผลต่างร่วม 4 พจน์ที่ 5 มีค่าเท่าใด", "answer": "19"},
    "ผลบวก 4 พจน์แรกของลำดับ 2, 5, 8 เท่ากับเท่าใด",
]
TOPICS = ["พจน์ทั่วไป", "ผลบวกอนุกรม"]
RULES = ["พจน์ที่ n: an = a1 + (n-1)d", "ผลบวก: Sn = (n/2)(a1 + an)", "ผลต่างร่วม d = a2 - a1"]
AVOID = ["ลำดับเลขคณิตที่มีพจน์แรก # ผลต่างร่วม # พจน์ที่ # เท่ากับ #"]
AVOID_ANGLES = ["value"]
REVIEW_ITEMS = [
    {"question": "ลำดับ 5, 8, 11 พจน์ที่ 4 คือ 14", "answer": "true", "explain": "5+3*3=14"},
    {"question": "ผลบวก 3 พจน์แรกของ 2, 4, 6 คือ 10", "answer": "false", "explain": "2+4+6=12"},
]
MCQ_REVIEW_ITEMS = [
    {"question": "ประโยคใดใช้เงื่อนไขแบบที่ 2 ได้ถูกต้อง",
     "choices": ["ก) If she were free, she would join us.", "ข) If she is free, she would join us.",
                 "ค) If she were free, she will join us.", "ง) If she was free, she joins us."],
     "answer": "ก"},
    {"question": "ประโยคต่อไปนี้ผิดตรงไหน: If the alarm rings, we will leave immediately.",
     "choices": ["ก) เปลี่ยน rings เป็น rang", "ข) เปลี่ยน will leave เป็น leave",
                 "ค) เปลี่ยน alarm เป็น alarms", "ง) เปลี่ยน immediately เป็น immediate"],
     "answer": "ข"},
]


def capture():
    import app.services.ai_service as ai
    import app.services.quiz_service as qs
    from app.services import prompts as P

    box = {}

    class FakeCompletions:
        def create(self, **kw):
            box["prompt"] = kw["messages"][0]["content"]
            raise RuntimeError("หยุดก่อนยิงจริง")

    ai.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
    qs.client = ai.client
    Q = qs.QuizService

    out = {}

    def grab(key, fn):
        box.clear()
        try:
            fn()
        except RuntimeError:
            pass
        except Exception as e:
            print(f"  !! {key} ไม่สำเร็จ: {e}")
        out[key] = box.get("prompt", "")

    # ปรนัย/ถูกผิด x ระดับ x (รอบแรก, รอบขอซ้ำที่มีของหลีกเลี่ยง)
    for diff in ("easy", "medium", "hard"):
        plan = P.plan_rule_quota(RULES, 5, 0)
        grab(f"mcq-{diff}", lambda: Q._gen_mcq_once(
            CTX, 5, EXCLUDE, TOPICS, diff, 4, "applied", None, None, plan, 0))
        grab(f"mcq-{diff}-retry", lambda: Q._gen_mcq_once(
            CTX, 5, EXCLUDE, TOPICS, diff, 4, "applied", AVOID, AVOID_ANGLES, plan, 3))
        for want in ("true", "false"):
            grab(f"tf-{diff}-{want}", lambda: Q._gen_tf_once(
                CTX, 5, EXCLUDE, TOPICS, diff, "applied", want, None, None, plan, 0))
        grab(f"tf-{diff}-false-retry", lambda: Q._gen_tf_once(
            CTX, 5, EXCLUDE, TOPICS, diff, "applied", "false", AVOID, AVOID_ANGLES, plan, 3))

    # ชุดภาษาและชุดทั่วไป: ส่งป้ายเข้าไปตรง ๆ แล้วถ่ายทั้งปรนัยและถูก/ผิด
    for tag, kind, used_angle in (("lang", P.KIND_LANGUAGE, "identify"), ("gen", P.KIND_GENERAL, "classify")):
        for diff in ("easy", "medium", "hard"):
            plan = P.plan_rule_quota(RULES, 5, 0)
            grab(f"{tag}-mcq-{diff}", lambda: Q._gen_mcq_once(
                CTX, 5, EXCLUDE, TOPICS, diff, 4, "applied", None, [used_angle], plan, 0, kind))
            grab(f"{tag}-tf-{diff}-false", lambda: Q._gen_tf_once(
                CTX, 5, EXCLUDE, TOPICS, diff, "applied", "false", AVOID, [used_angle], plan, 2, kind))

    # prompt ที่ยิงแยก: หากฎ และ ตรวจทานถูก/ผิด
    out["rules"] = P.applicable_rules_prompt(CTX)
    out["kind"] = P.content_kind_prompt(CTX)
    out["tf-review"] = P.tf_review_prompt(REVIEW_ITEMS, CTX)
    out["mcq-review"] = P.mcq_review_prompt(MCQ_REVIEW_ITEMS, CTX)
    return out


def main():
    current = capture()

    if "--save" in sys.argv:
        with open(SNAPSHOT, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print(f"บันทึกภาพถ่าย prompt โหมดประยุกต์แล้ว {len(current)} กรณี")
        print(f"ที่ {SNAPSHOT}")
        return 0

    if not os.path.exists(SNAPSHOT):
        print("ยังไม่มีไฟล์ภาพถ่าย ให้รันคำสั่งนี้ก่อน:")
        print("  python tools/check_prompt_applied.py --save")
        return 2

    with open(SNAPSHOT, encoding="utf-8") as f:
        saved = json.load(f)

    print("=" * 62)
    print("เทียบ prompt โหมดประยุกต์ (applied)  ภาพถ่าย vs โค้ดปัจจุบัน")
    print("=" * 62)

    all_ok = True
    for key in saved:
        old, new = saved[key], current.get(key, "")
        same = old == new
        all_ok &= same
        print(f"  {key:22} {'ตรงกันทุกตัวอักษร' if same else 'ต่างกัน !!!'}")
        if not same:
            for line in list(difflib.unified_diff(
                    old.splitlines(), new.splitlines(),
                    "ภาพถ่าย", "ปัจจุบัน", lineterm=""))[:30]:
                print("     ", line)

    print()
    if all_ok:
        print("สรุป: โหมดประยุกต์ไม่เปลี่ยนเลย ย้ายโค้ดสำเร็จ")
        return 0
    print("สรุป: โหมดประยุกต์เปลี่ยนไป ตรวจสอบก่อน commit")
    return 1


if __name__ == "__main__":
    sys.exit(main())
