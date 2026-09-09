"""ตรวจว่า prompt ของโหมดเดิม (source) ไม่เปลี่ยนหลังแก้โค้ด

โหมดเดิมเป็นของที่ใช้งานได้ดีอยู่แล้ว ทุกครั้งที่แก้ prompt ของโหมดประยุกต์
ต้องมั่นใจว่าโหมดเดิมไม่ถูกกระทบแม้แต่ตัวอักษรเดียว

วิธีใช้
  1) ตอนที่โค้ดยังดีอยู่ ให้บันทึกภาพถ่ายไว้ก่อน
       python tools/check_prompt.py --save

  2) หลังแก้โค้ดแล้ว รันเทียบ
       python tools/check_prompt.py

     ถ้าขึ้น "ตรงกันทุกตัวอักษร" ครบ 6 กรณี = โหมดเดิมปลอดภัย
     ถ้าขึ้น "ต่างกัน" = มีบางอย่างไปกระทบโหมดเดิม ต้องแก้ก่อน commit

ไฟล์ภาพถ่ายเก็บที่ tools/prompt_snapshot.json
"""
import difflib
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "dummy-for-check")

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_snapshot.json")

CTX = """รากที่สอง
รากที่สองของจำนวน a คือจำนวนที่เมื่อคูณตัวเองแล้วได้ a
ตัวอย่างที่ 1: 16 มีรากที่สองเป็น 4 เพราะ 4 x 4 = 16
ตัวอย่างที่ 2: 25 มีรากที่สองเป็น 5 เพราะ 5 x 5 = 25
สมบัติ รากที่สองของ (a x b) เท่ากับ รากที่สองของ a คูณรากที่สองของ b"""

EXCLUDE = ["ข้อใดเป็นค่าของรากที่สองของ 25", "ข้อใดอธิบายความหมายของรากที่สอง"]
TOPICS = ["นิยามรากที่สอง", "จำนวนกำลังสองสมบูรณ์"]


def capture():
    """ดักจับ prompt ที่จะถูกส่งให้ AI โดยไม่ยิงจริง"""
    import app.services.ai_service as ai

    box = {}

    class FakeCompletions:
        def create(self, **kw):
            box["prompt"] = kw["messages"][0]["content"]
            raise RuntimeError("หยุดก่อนยิงจริง")

    class FakeChat:
        completions = FakeCompletions()

    ai.client = types.SimpleNamespace(chat=FakeChat())

    import app.services.quiz_service as qs
    qs.client = ai.client
    Q = qs.QuizService

    out = {}
    for qtype in ("mcq", "tf"):
        for diff in ("easy", "medium", "hard"):
            try:
                if qtype == "mcq":
                    Q._gen_mcq_once(CTX, 5, EXCLUDE, TOPICS, diff, 4, "source")
                else:
                    Q._gen_tf_once(CTX, 5, EXCLUDE, TOPICS, diff, "source")
            except RuntimeError:
                pass
            except Exception as e:
                print(f"  !! เรียก {qtype}-{diff} ไม่สำเร็จ: {e}")
            out[f"{qtype}-{diff}"] = box.get("prompt", "")
            box.clear()
    return out


def main():
    current = capture()

    if "--save" in sys.argv:
        with open(SNAPSHOT, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print(f"บันทึกภาพถ่าย prompt โหมดเดิมแล้ว {len(current)} กรณี")
        print(f"ที่ {SNAPSHOT}")
        return 0

    if not os.path.exists(SNAPSHOT):
        print("ยังไม่มีไฟล์ภาพถ่าย ให้รันคำสั่งนี้ก่อน:")
        print("  python tools/check_prompt.py --save")
        return 2

    with open(SNAPSHOT, encoding="utf-8") as f:
        saved = json.load(f)

    print("=" * 62)
    print("เทียบ prompt โหมดเดิม (source)  ภาพถ่าย vs โค้ดปัจจุบัน")
    print("=" * 62)

    all_ok = True
    for key in saved:
        old = saved[key]
        new = current.get(key, "")
        same = old == new
        all_ok &= same
        print(f"  {key:12} {'ตรงกันทุกตัวอักษร' if same else 'ต่างกัน !!!'}")
        if not same:
            for line in list(difflib.unified_diff(
                    old.splitlines(), new.splitlines(),
                    "ภาพถ่าย", "ปัจจุบัน", lineterm=""))[:30]:
                print("     ", line)

    print()
    if all_ok:
        print("สรุป: โหมดเดิมไม่เปลี่ยนเลย ปลอดภัย")
        return 0
    print("สรุป: โหมดเดิมเปลี่ยนไป ต้องแก้ก่อน commit")
    return 1


if __name__ == "__main__":
    sys.exit(main())