import re
from typing import List, Dict, Any
from collections import Counter
from app.core.config import settings

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
