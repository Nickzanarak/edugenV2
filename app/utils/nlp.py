import re
from typing import List, Dict, Any
from collections import Counter
from app.core.config import settings
from app.utils import safe_math

_STOP = set("คือ ของ และ หรือ ที่ ใน เป็น ได้ มี ใด ใดๆ อะไร อย่างไร ใคร ไหน ข้อใด ต่อไปนี้ มาก น้อย ไม่ ใช่ จาก ตาม เพื่อ เช่น ดังนั้น ดังกล่าว ซึ่ง โดย เพราะ ดังนั้นจึง".split())

def tokenize(s: str) -> List[str]:
    text = (s or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = text.replace("ๆ", " ")
    words = text.split()
    
    clean_words = []
    for w in words:
        if w and (w not in _STOP):
            clean_words.append(w)
    return clean_words

def jaccard(a: str, b: str) -> float:
    A, B = set(tokenize(a)), set(tokenize(b))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    uni = len(A | B)

    if uni == 0:
        return 0.0
    
    return inter / uni

def dice_bigram(a: str, b: str) -> float:
    def bi(x: str) -> List[str]:
        t = re.sub(r"\s+", " ", x).strip()
        result = []
        if len(t) > 1:
            for i in range(len(t) - 1):
                pair = t[i] + t[i + 1]
                result.append(pair)
        return result

    A, B = bi(a), bi(b)
    if not A or not B:
        return 0.0

    CA, CB = Counter(A), Counter(B)

    inter = 0
    for k, v in CA.items():
        count_in_B = CB.get(k, 0)
        if v < count_in_B:
            inter += v
        else:
            inter += count_in_B

    return (2 * inter) / (len(A) + len(B))

def similar(a: str, b: str) -> float:
    return max(jaccard(a, b), dice_bigram(a, b))


_NUM_RE = re.compile(r"-?\d+(?:[.,/]\d+)*")


def question_skeleton(s: str) -> str:
    """ลบตัวเลขออกจากคำถาม เหลือแต่ "โครง" ของประโยค

    ใช้แยกสองอย่างที่ต่างกันออกจากกัน
      - "สูตรเดิม แต่เปลี่ยนตัวเลข"   -> โหมดประยุกต์ตั้งใจให้เป็นแบบนี้ ต้องปล่อยผ่าน
      - "โครงประโยคเดิม ซ้ำ ๆ ทั้งชุด" -> น่าเบื่อ ต้องจำกัดจำนวน

    ตัวกรองข้อซ้ำปกติแยกสองอย่างนี้ไม่ออก เพราะวัดจากข้อความที่มีตัวเลขอยู่ด้วย
    พอลบตัวเลขทิ้งก่อนแล้วค่อยวัด สองอย่างนี้จึงแยกออกจากกันได้
    """
    t = _NUM_RE.sub(" # ", s or "")
    t = re.sub(r"[^\w\s#]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()

# เลขบอกลำดับที่ AI ชอบเขียนเป็นตัวหนังสือ เช่น "พจน์ที่หก" ต้องแปลงเป็น "ที่ 6"
# ก่อนดึงเลข ไม่งั้น "พจน์ที่หก" กับ "พจน์ที่ 6" จะได้เลขไม่เท่ากันทั้งที่เป็นข้อเดียวกัน
# จับเฉพาะหลังคำว่า "ที่" เพราะ "ลำดับหนึ่ง" (แปลว่า "ลำดับหนึ่งใด ๆ") ไม่ใช่ลำดับที่ 1
_TH_ORDINAL = {
    "หนึ่ง": "1", "สอง": "2", "สาม": "3", "สี่": "4", "ห้า": "5",
    "หก": "6", "เจ็ด": "7", "แปด": "8", "เก้า": "9", "สิบ": "10",
}
_TH_ORDINAL_RE = re.compile(r"ที่(" + "|".join(_TH_ORDINAL) + r")(?![่้๊๋a-zA-Z])")


def _numbers_of(text: str) -> List[float]:
    t = _TH_ORDINAL_RE.sub(lambda m: "ที่ " + _TH_ORDINAL[m.group(1)], text or "")
    return sorted(safe_math.numbers_in_text(t))


def same_question(a: str, b: str, threshold: float) -> bool:
    """สองข้อนี้เป็นข้อเดียวกันไหม — ดูทั้งตัวหนังสือและตัวเลข

    เดิมดูแค่ตัวหนังสือคล้ายกันเกินเกณฑ์ก็ถือว่าซ้ำ ซึ่งพังกับโหมดประยุกต์
    ที่ตั้งใจแต่งโจทย์โครงเดียวกันแต่เปลี่ยนเลข เช่น
      "พจน์แรก 6 ผลต่างร่วม 4 พจน์ที่ 7"  กับ  "... พจน์ที่ 9"
    ตัวหนังสือเหมือนกัน 87% แต่คนละข้อ คนละคำตอบ (30 กับ 38)

    จึงเพิ่มขั้นที่สอง: ถ้าตัวหนังสือคล้ายกัน ให้ดูเลขในโจทย์ต่อ
    เลขไม่ตรงกัน = คนละข้อ / เลขตรงกัน หรือฝั่งใดฝั่งหนึ่งไม่มีเลข = ใช้ผลจากตัวหนังสือ

    วัดกับข้อสอบจริง 3 รอบ: คู่ที่คนละข้อแต่เคยโดนบอกว่าซ้ำ 5 คู่ หายหมด
    คู่ที่ซ้ำจริง (รวมที่เขียน "หก" กับ "6") ยังจับได้ครบ
    """
    if similar(a, b) < threshold:
        return False
    na, nb = _numbers_of(a), _numbers_of(b)
    if na and nb and na != nb:
        return False
    return True


def filter_near_dups(items: List[Dict[str, Any]], exclude: List[str], threshold: float = None) -> List[Dict[str, Any]]:
    if threshold is None:
        threshold = settings.NEAR_DUP_THRESHOLD

    kept: List[Dict[str, Any]] = []

    for q in items:
        text = str(q.get("question") or "").strip()
        if not text:
            continue
        dup = False

        for e in exclude:
            if similar(text, e) >= threshold:
                dup = True
                break

        if dup:
            continue

        for e in kept:
            if similar(text, str(e.get("question") or "")) >= threshold:
                dup = True
                break

        if not dup:
            kept.append(q)

    return kept
