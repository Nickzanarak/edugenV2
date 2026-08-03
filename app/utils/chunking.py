"""
ตัวช่วยแบ่งเนื้อหาเอกสารยาว ๆ ออกเป็น "ก้อน" (chunk) สำหรับ Map-Reduce และ QA
หลักการ: แบ่งตามขอบเขตหน้าเสมอ ไม่หั่นกลางหน้า เพื่อไม่ให้เนื้อหาหน้าเดียวกันถูกฉีก
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

# ขนาดก้อนโดยประมาณ (ตัวอักษร) ~5-8 หน้า PDF ต่อก้อน
CHUNK_CHAR_SIZE = 12000
# จำนวนหน้าสูงสุดต่อก้อน — จำเป็นสำหรับสไลด์/อินโฟกราฟิกที่มีข้อความน้อยแต่หลายหน้า
# ถ้าไม่มีข้อจำกัดนี้ เอกสาร 23 หน้าที่เป็นสไลด์จะถูกยัดเป็นก้อนเดียว
MAX_PAGES_PER_CHUNK = 4
# ความยาวตัวอย่างต่อหน้า ที่ส่งให้ AI ใช้หาขอบเขตเรื่อง
TOPIC_PREVIEW_CHARS = 160
# จำนวนก้อนสูงสุดหลังแบ่งตามเรื่อง (กันเอกสารที่มีหัวข้อย่อยเยอะเกินจนยิง AI หลายรอบ)
MAX_SEMANTIC_GROUPS = 8
# ความยาวตัวอย่างเนื้อหาที่ใช้ทำ "สารบัญ" ให้ AI เลือกก้อน
INDEX_PREVIEW_CHARS = 400

_PAGE_RE = re.compile(r"\[หน้า\s*(\d+)\]")


def split_by_pages(text: str) -> List[Tuple[int, str]]:
    """แยกข้อความออกเป็นรายหน้า โดยอาศัยป้าย [หน้า X] ที่ pdf.py ใส่ไว้
    คืนค่า [(เลขหน้า, เนื้อหาหน้านั้น), ...]
    ถ้าไม่มีป้ายเลย (เช่นผู้ใช้พิมพ์เอง) จะคืนเป็นหน้าเดียว
    """
    t = (text or "").strip()
    if not t:
        return []

    matches = list(_PAGE_RE.finditer(t))
    if not matches:
        return [(1, t)]

    pages: List[Tuple[int, str]] = []
    # ถ้ามีข้อความก่อนป้ายแรก ให้ผูกไว้กับหน้าแรก
    if matches[0].start() > 0:
        lead = t[: matches[0].start()].strip()
        if lead:
            pages.append((0, lead))

    for i, m in enumerate(matches):
        page_no = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        body = t[start:end].strip()
        if body:
            pages.append((page_no, body))
    return pages


def build_chunks(
    text: str,
    max_chars: int = CHUNK_CHAR_SIZE,
    max_pages: int = MAX_PAGES_PER_CHUNK,
) -> List[str]:
    """รวมหน้าเข้าเป็นก้อน โดยแต่ละก้อนไม่เกิน max_chars และไม่เกิน max_pages หน้า
    ไม่หั่นกลางหน้า ถ้าหน้าเดียวยาวเกิน max_chars จะยอมให้ก้อนนั้นใหญ่กว่าปกติ

    เหตุผลที่ต้องจำกัดจำนวนหน้าด้วย: เอกสารประเภทสไลด์/อินโฟกราฟิก มีข้อความน้อยมาก
    ต่อหน้า ถ้าดูแต่จำนวนตัวอักษร เอกสาร 20+ หน้าอาจกลายเป็นก้อนเดียว
    ทำให้ทั้งการสรุปและการออกข้อสอบไม่ครอบคลุมทั้งเล่ม
    """
    pages = split_by_pages(text)
    if not pages:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0
    buf_pages = 0

    for page_no, body in pages:
        piece = f"[หน้า {page_no}]\n{body}" if page_no > 0 else body
        piece_len = len(piece)

        # ปิดก้อนเดิมเมื่อเกินโควตาตัวอักษร หรือเกินจำนวนหน้าที่กำหนด
        too_long = buf_len + piece_len > max_chars
        too_many_pages = buf_pages >= max_pages
        if buf and (too_long or too_many_pages):
            chunks.append("\n\n".join(buf))
            buf, buf_len, buf_pages = [], 0, 0

        buf.append(piece)
        buf_len += piece_len
        buf_pages += 1

    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def chunk_page_range(chunk: str) -> str:
    """อ่านว่าก้อนนี้ครอบคลุมหน้าไหนถึงหน้าไหน (ใช้แสดงในสารบัญ)"""
    nums = [int(n) for n in _PAGE_RE.findall(chunk)]
    if not nums:
        return "ไม่ระบุหน้า"
    lo, hi = min(nums), max(nums)
    return f"หน้า {lo}" if lo == hi else f"หน้า {lo}-{hi}"


def build_chunk_index(chunks: List[str]) -> str:
    """สร้าง 'สารบัญ' ของก้อนทั้งหมด เพื่อให้ AI เลือกว่าคำถามเกี่ยวกับก้อนไหน
    ใช้ช่วงหน้า + ตัวอย่างเนื้อหาต้นก้อน (ไม่เสียค่า AI เพิ่ม)
    """
    lines: List[str] = []
    for i, c in enumerate(chunks, start=1):
        preview = _PAGE_RE.sub("", c).strip().replace("\n", " ")
        preview = preview[:INDEX_PREVIEW_CHARS]
        lines.append(f"[ก้อน {i}] ({chunk_page_range(c)}) {preview}...")
    return "\n\n".join(lines)

def sample_across_document(text: str, max_chars: int) -> str:
    """เลือกเนื้อหา "กระจายทั่วทั้งเอกสาร" ให้อยู่ในโควตา max_chars
    ต่างจากการตัดหัว (truncate) ที่เห็นแต่ช่วงต้นเอกสาร
    ใช้กับงานที่ส่งเนื้อหาทั้งก้อนให้ AI ไม่ได้ เช่น การสกัดหัวข้อและออกข้อสอบ
    """
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= max_chars:
        return t

    pages = split_by_pages(t)
    if len(pages) <= 1:
        # ไม่มีป้ายหน้า (เช่นผู้ใช้พิมพ์เอง) → ตัดหัวตามปกติ
        return t[:max_chars]

    total = sum(len(b) for _, b in pages)
    avg = max(1, total // len(pages))
    keep_n = max(1, min(len(pages), max_chars // avg))

    step = len(pages) / keep_n
    idxs = sorted({int(i * step) for i in range(keep_n)})

    out: list = []
    used = 0
    for i in idxs:
        page_no, body = pages[i]
        piece = f"[หน้า {page_no}]\n{body}" if page_no > 0 else body
        if used + len(piece) > max_chars:
            piece = piece[: max(0, max_chars - used)]
        if not piece:
            break
        out.append(piece)
        used += len(piece)
        if used >= max_chars:
            break
    return "\n\n".join(out)


# ============================================================
#  Semantic chunking — แบ่งก้อนตาม "ขอบเขตเรื่อง" แทนการตัดทุก N หน้า
# ============================================================

# เก็บผลการหาขอบเขตไว้ เพื่อไม่ต้องยิง AI ซ้ำ
# (summarize / quiz / qa ใช้เอกสารเดียวกัน ควรเสียค่า AI แค่ครั้งเดียว)
_TOPIC_CACHE: Dict[str, List[Tuple[int, int]]] = {}
_TOPIC_CACHE_LIMIT = 20


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def build_page_index(pages: List[Tuple[int, str]]) -> str:
    """สร้างสารบัญย่อ หน้าละ 1 บรรทัด สำหรับให้ AI ดูว่าเรื่องเปลี่ยนตรงไหน"""
    lines = []
    for page_no, body in pages:
        preview = " ".join(body.split())[:TOPIC_PREVIEW_CHARS]
        lines.append(f"หน้า {page_no}: {preview}")
    return "\n".join(lines)


def _parse_groups(raw: str, valid_pages: List[int]) -> Optional[List[Tuple[int, int]]]:
    """แปลงคำตอบ AI เช่น '1-6, 7-11, 12-17' เป็นช่วงหน้า พร้อมตรวจความถูกต้อง"""
    if not raw:
        return None
    pairs = re.findall(r"(\d+)\s*[-–]\s*(\d+)", raw)
    if not pairs:
        return None

    lo_all, hi_all = min(valid_pages), max(valid_pages)
    groups: List[Tuple[int, int]] = []
    for a, b in pairs:
        start, end = int(a), int(b)
        if start > end:
            start, end = end, start
        # ตัดให้อยู่ในช่วงหน้าที่มีจริง
        start = max(start, lo_all)
        end = min(end, hi_all)
        if start <= end:
            groups.append((start, end))

    if not groups:
        return None

    groups.sort()
    # ตรวจว่าครอบคลุมทุกหน้า ไม่ซ้อนกัน ไม่มีช่องโหว่
    covered: List[Tuple[int, int]] = []
    cursor = lo_all
    for start, end in groups:
        if end < cursor:
            continue          # ซ้อนกับกลุ่มก่อนหน้า ข้ามไป
        start = max(start, cursor)
        covered.append((start, end))
        cursor = end + 1
    if cursor <= hi_all:
        covered.append((cursor, hi_all))   # เติมหน้าที่ AI ลืม

    return covered or None


def detect_topic_groups(text: str) -> Optional[List[Tuple[int, int]]]:
    """ให้ AI ดูสารบัญย่อ แล้วบอกว่าหน้าไหนถึงหน้าไหนเป็นเรื่องเดียวกัน
    คืน None ถ้าทำไม่ได้ (ผู้เรียกต้อง fallback ไปใช้การแบ่งตามจำนวนหน้า)
    """
    pages = split_by_pages(text)
    if len(pages) < 3:
        return None       # หน้าน้อยเกินกว่าจะต้องแบ่งตามเรื่อง

    key = _cache_key(text)
    if key in _TOPIC_CACHE:
        print(f"[TIME] {'chunk: topic (cache)':<22} {0.0:7.2f}s | ใช้ผลเดิม", flush=True)
        return _TOPIC_CACHE[key]

    import time as _time
    _t0 = _time.perf_counter()

    try:
        from app.core.config import settings
        from app.services.ai_service import client

        index_text = build_page_index(pages)
        prompt = f"""
ด้านล่างคือสารบัญย่อของเอกสาร แสดงเนื้อหาต้นหน้าของแต่ละหน้า
จงระบุว่า "หน้าไหนถึงหน้าไหนเป็นเรื่องเดียวกัน" โดยแบ่งตามการเปลี่ยนหัวข้อ/เรื่อง

กติกา:
- ตอบเป็นช่วงหน้าเท่านั้น คั่นด้วยจุลภาค เช่น: 1-6, 7-11, 12-17, 18-19
- ต้องครอบคลุมทุกหน้าตั้งแต่หน้าแรกถึงหน้าสุดท้าย ห้ามข้ามหน้า ห้ามซ้อนกัน
- เรื่องที่มีหน้าเดียวก็ให้เป็นกลุ่มของตัวเอง เช่น 23-23
- ห้ามอธิบายอะไรเพิ่ม ตอบเฉพาะช่วงหน้า

สารบัญย่อ:
{index_text}

ตอบ (ช่วงหน้าเท่านั้น):
"""
        r = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = (r.choices[0].message.content or "").strip()
        groups = _parse_groups(raw, [p for p, _ in pages])
    except Exception:
        return None

    if not groups:
        return None

    # ถ้าซอยละเอียดเกินไป ให้รวมกลุ่มเล็กที่ติดกันเข้าด้วยกัน
    while len(groups) > MAX_SEMANTIC_GROUPS:
        sizes = [(g[1] - g[0] + 1) for g in groups]
        i = sizes.index(min(sizes))
        j = i - 1 if i == len(groups) - 1 else i + 1
        lo = min(groups[i][0], groups[j][0])
        hi = max(groups[i][1], groups[j][1])
        groups[min(i, j)] = (lo, hi)
        groups.pop(max(i, j))

    if len(_TOPIC_CACHE) >= _TOPIC_CACHE_LIMIT:
        _TOPIC_CACHE.clear()
    _TOPIC_CACHE[key] = groups
    print(f"[TIME] {'chunk: topic detect':<22} {_time.perf_counter()-_t0:7.2f}s "
          f"| {len(pages)} หน้า -> {len(groups)} กลุ่ม", flush=True)
    return groups


def build_chunks_semantic(
    text: str,
    max_chars: int = CHUNK_CHAR_SIZE,
    max_pages_hard: int = 10,
) -> List[str]:
    """แบ่งก้อนตามขอบเขตเรื่อง (ถ้าทำได้) ไม่งั้น fallback ไปใช้ build_chunks ปกติ

    max_pages_hard = เพดานกันเรื่องเดียวยาวเกินไปจนก้อนใหญ่เกิน AI อ่านไหว
    """
    groups = detect_topic_groups(text)
    if not groups:
        return build_chunks(text, max_chars=max_chars)

    pages = split_by_pages(text)
    by_no: Dict[int, str] = {}
    for page_no, body in pages:
        by_no[page_no] = body

    chunks: List[str] = []
    for start, end in groups:
        buf: List[str] = []
        buf_len = 0
        buf_pages = 0
        for p in range(start, end + 1):
            body = by_no.get(p)
            if body is None:
                continue
            piece = f"[หน้า {p}]\n{body}"
            # เรื่องเดียวแต่ยาวมาก → ซอยย่อยภายในเรื่องนั้น
            if buf and (buf_len + len(piece) > max_chars or buf_pages >= max_pages_hard):
                chunks.append("\n\n".join(buf))
                buf, buf_len, buf_pages = [], 0, 0
            buf.append(piece)
            buf_len += len(piece)
            buf_pages += 1
        if buf:
            chunks.append("\n\n".join(buf))

    return chunks or build_chunks(text, max_chars=max_chars)