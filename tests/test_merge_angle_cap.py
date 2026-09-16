"""เพดานมุมตอนรวมข้อจากหลายก้อน ต้องคิดจากจำนวนมุมของระดับนั้น

ที่มา: ชีววิทยา 14 หน้า 5 บท ขอ 7 ข้อระดับง่าย (2 มุม) เพดานเดิมคิดจาก 5 มุม = 3 ข้อต่อมุม
ข้อจากก้อนท้าย ๆ (บท 4-5) โดนปัดตกทุกครั้ง แล้วรอบเก็บตกไปหยิบจากก้อนยาวสุดแทน
ผล: 30 ข้อมาจาก 3 บทแรก อีก 2 บทได้ 0 ข้อ
"""
import os

os.environ.setdefault("OPENAI_API_KEY", "dummy-for-tests")

from app.services import quiz_service as qs
from app.services.quiz_service import QuizService


def _mcq(text, angle):
    return {
        "type": "mcq", "question": text, "angle": angle,
        "choices": [f"ก) เฉลย {text}", "ข) ลวง 1", "ค) ลวง 2", "ง) ลวง 3"],
        "answer": "ก", "explain": "...",
    }


def _run_batch(monkeypatch, plan, mode="applied"):
    """plan = รายการมุมที่แต่ละก้อนจะส่งกลับ เช่น [["classify","classify"], ["classify","predict"], ...]"""
    chunks = [f"[หน้า {i + 1}]\nบทที่ {i + 1} " + ("x" * (500 - i * 50)) for i in range(len(plan))]
    monkeypatch.setattr(qs, "build_chunks", lambda ctx: chunks)
    monkeypatch.setattr(QuizService, "_detect_kind", staticmethod(lambda ctx, mode: "general"))

    calls = []
    # โจทย์ต้องหน้าตาต่างกันจริง ไม่งั้นด่านซ้ำ/ด่านโครงประโยคจะปัดตกก่อนถึงด่านมุม
    texts = {
        (0, 0): "สัตว์ชนิดหนึ่งมีขนเส้นและต่อมน้ำนม จัดอยู่ในกลุ่มใด",
        (0, 1): "พืชที่มีเมล็ดแต่ไม่มีดอก จัดอยู่ในกลุ่มใด",
        (1, 0): "แมลงกับแมงมุมต่างกันที่จำนวนขาอย่างไร ตัวที่มีแปดขาคือกลุ่มใด",
        (1, 1): "ถ้าผู้ล่าลำดับสูงสุดหายไปจากป่า ประชากรกวางจะเป็นอย่างไร",
        (2, 0): "ต้นไม้ที่มีเส้นใบขนานและรากฝอย เป็นพืชใบเลี้ยงชนิดใด",
        (3, 0): "ถ้าใช้ยาฆ่าแมลงในนาข้าว จำนวนกบจะเปลี่ยนไปอย่างไร",
        (4, 0): "เมื่อคนผ่าตัดถุงน้ำดีออก การย่อยไขมันจะเป็นอย่างไร",
    }

    def fake_generate(qtype, context, n, exclude, topics, difficulty, choices_count,
                      max_tries=6, mode=None, kind=None):
        idx = chunks.index(context)
        again = idx in calls                 # ถูกเรียกซ้ำ = รอบเก็บตก ต้องได้ข้อใหม่ ไม่ใช่ข้อเดิม
        calls.append(idx)
        angles = plan[idx][:n]
        spare = ["ปลาวาฬหายใจด้วยปอดและให้นมลูก จัดอยู่ในกลุ่มใด",
                 "เมล็ดถั่วที่จมน้ำทั้งเมล็ดจะเป็นอย่างไร เพราะเหตุใด",
                 "แร้งที่กินซากสัตว์ตายแล้ว มีบทบาทใดในระบบนิเวศ"]
        return [
            _mcq(spare.pop(0) if again else texts.get((idx, j), f"คำถามที่ {idx}-{j}"), a)
            for j, a in enumerate(angles)
        ]

    monkeypatch.setattr(QuizService, "_generate_from_text", staticmethod(fake_generate))
    out = QuizService._generate_batch("mcq", "เนื้อหา", 7, None, None, "easy", 4, mode)
    return out, calls, texts


def test_easy_level_with_two_angles_keeps_items_from_every_chunk(monkeypatch):
    # โควตา 7 ข้อ 5 ก้อน = 2,2,1,1,1 | จำแนก 4 ทำนาย 3 -> ระดับง่าย 2 มุม เพดานต้องเป็น 5 ไม่ใช่ 3
    plan = [["classify", "classify"], ["classify", "predict"], ["classify"], ["predict"], ["predict"]]
    out, calls, texts = _run_batch(monkeypatch, plan)

    got = {q["question"] for q in out}
    assert texts[(2, 0)] in got and texts[(3, 0)] in got and texts[(4, 0)] in got
    assert len(out) == 7
    assert calls == [0, 1, 2, 3, 4]          # ไม่มีรอบเก็บตกจากก้อนยาวสุด


def test_diversity_rule_still_blocks_one_angle_taking_everything(monkeypatch):
    # เพดานใหม่ = 5 ต่อมุม: จำแนกทั้ง 7 ข้อ ต้องโดนกันไว้บ้าง (แล้วรอบเก็บตกเติมให้)
    plan = [["classify", "classify"], ["classify", "classify"], ["classify"], ["classify"], ["classify"]]
    out, calls, _ = _run_batch(monkeypatch, plan)
    assert calls[:5] == [0, 1, 2, 3, 4]
    assert len(calls) > 5                    # ต้องมีรอบเก็บตก เพราะข้อที่ 6-7 ถูกเพดานกัน


# ---------------------------------------------------------------------------
# J: สลับฟันปลาตอนรวม — ทุกก้อนได้ข้อแรกเข้าชุดก่อน ก้อนไหนจะได้ข้อที่สอง
# ที่มา: ชีววิทยาระดับง่าย AI ออก "จัดอยู่กลุ่มใด" แทบทุกข้อ ก้อน 1-3 กินเพดานหมด
#        ก้อน 4-5 (บท 8-9) มาถึงทีหลังโดนปัดตกทุกรอบ แม้เพดานจะถูกต้องแล้ว
# ---------------------------------------------------------------------------

def test_every_chunk_gets_its_first_item_even_when_all_share_one_angle(monkeypatch):
    plan = [["classify", "classify"], ["classify", "classify"], ["classify"], ["classify"], ["classify"]]
    out, calls, texts = _run_batch(monkeypatch, plan)
    got = {q["question"] for q in out}
    # เพดานจำแนก = 5 พอดีกับ "ข้อแรกของ 5 ก้อน" ทุกบทจึงได้ข้อสอบ
    for key in [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]:
        assert texts[key] in got, f"ก้อน {key[0] + 1} ไม่มีข้อสอบในชุด"
    assert len(out) == 7


def test_source_mode_keeps_chunk_order(monkeypatch):
    # โหมดเดิมต้องไล่ทีละก้อนเหมือนเดิม (ไม่มีด่านปัดตก จึงไม่ต้องสลับ และไม่ให้ลำดับข้อเปลี่ยน)
    plan = [["classify", "classify"], ["classify", "predict"], ["classify"], ["predict"], ["predict"]]
    out, calls, texts = _run_batch(monkeypatch, plan, mode="source")
    order = [q["question"] for q in out]
    assert order[:4] == [texts[(0, 0)], texts[(0, 1)], texts[(1, 0)], texts[(1, 1)]]


def test_applied_mode_interleaves_chunks(monkeypatch):
    plan = [["classify", "classify"], ["classify", "predict"], ["classify"], ["predict"], ["predict"]]
    out, calls, texts = _run_batch(monkeypatch, plan)
    order = [q["question"] for q in out]
    assert order[:5] == [texts[(0, 0)], texts[(1, 0)], texts[(2, 0)], texts[(3, 0)], texts[(4, 0)]]
    assert order[5:] == [texts[(0, 1)], texts[(1, 1)]]
