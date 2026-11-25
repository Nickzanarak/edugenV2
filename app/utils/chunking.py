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

# แม่แบบสำหรับหาป้าย "[หน้า 5]" ในข้อความ
# (\d+) = ส่วนตัวเลข ซึ่งเป็นส่วนที่เราอยากได้
_PAGE_RE = re.compile(r"\[หน้า\s*(\d+)\]")


"""
split_by_pages(text: str)
เข้า:   "[หน้า 1]\nเซลล์...\n\n[หน้า 2]\nหัวใจ...\n\n[หน้า 3]\nปอด..."
        (ข้อความก้อนเดียว มีป้ายคั่นแต่ละหน้า)
ออก:    [(1, "เซลล์..."), (2, "หัวใจ..."), (3, "ปอด...")]
        (แยกเป็นรายการ แต่ละอันคือ (เลขหน้า, เนื้อหา))
"""
def split_by_pages(text: str) -> List[Tuple[int, str]]:
    t = (text or "").strip()
    if not t:
        return []

    matches = list(_PAGE_RE.finditer(t)) # หาป้าย [หน้า X] ทุกตัวในข้อความ

    # ไม่เจอป้ายเลย (เช่นผู้ใช้พิมพ์ข้อความเองแทนการอัปโหลด PDF)  จะนับทั้งก้อนเป็นหน้า 1
    if not matches:
        return [(1, t)]

    pages: List[Tuple[int, str]] = []

    # ถ้ามีข้อความก่อนป้ายแรก ให้ผูกไว้กับหน้าแรก
    if matches[0].start() > 0:
        lead = t[: matches[0].start()].strip()
        if lead:
            pages.append((0, lead))

    # ไล่ทีละป้าย: เนื้อหาของหน้านี้ = ตั้งแต่หลังป้ายนี้ จนถึงก่อนป้ายถัดไป
    for i, m in enumerate(matches):
        page_no = int(m.group(1)) # เลขหน้าจากป้าย
        start = m.end()           # จุดเริ่ม = ท้ายป้าย
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t) # จุดจบ = หัวป้ายถัดไป ถ้าเป็นป้ายสุดท้ายก็ไปจนสุดข้อความ
        body = t[start:end].strip()
        if body:    
            pages.append((page_no, body)) # ถ้าหน้าว่างก็ไม่เก็บ
    return pages

#  กรณีที่เช็คแล้วไม่ได้มากกว่า 3 หน้า จะมาเรียก build_chunks (นับว่าเป็น 1 ก้อน)
#  เป็นแผนสำรองสำหรับแบ่งหน้า(ถ้าเรียก AI แล้วเรียกไม่ติด หรือ เช็คแล้วหน้าน้อยกว่า 3)    ตัวอย่าง: เอกสาร 10 หน้า (หน้าละสั้นๆ) ["หน้า 1-4", "หน้า 5-8", "หน้า 9-10"]   = 3 ก้อน = ถาม AI 3 ครั้ง
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

    # ไล่ทีละหน้า ตั้งแต่หน้าแรกถึงหน้าสุดท้าย
    for page_no, body in pages:

        # แปะป้ายเลขหน้ากลับเข้าไป  ยกเว้น "หน้า 0" (ข้อความที่อยู่ก่อนป้ายแรก) ซึ่งใส่เนื้อหาไปเลยโดยไม่มีป้าย
        piece = f"[หน้า {page_no}]\n{body}" if page_no > 0 else body
        piece_len = len(piece)  # หน้านี้ยาวกี่ตัวอักษร

        # เช็กว่าตะกร้าจะเต็มไหม:
        too_long = buf_len + piece_len > max_chars      # ใส่หน้านี้แล้วเกิน 12,000 ตัวอักษร?
        too_many_pages = buf_pages >= max_pages         # ในตะกร้ามีครบ 4 หน้าแล้ว?

        if buf and (too_long or too_many_pages):        # ถ้าตะกร้ามีของอยู่และเต็มแล้ว จะ ปิดเป็น 1 ก้อน แล้วเริ่มตะกร้าใหม่
            chunks.append("\n\n".join(buf))
            buf, buf_len, buf_pages = [], 0, 0

        # ใส่หน้านี้ลงตะกร้า และอัปเดตตัวนับ
        buf.append(piece)
        buf_len += piece_len
        buf_pages += 1

    # หมดทุกหน้าแล้ว ถ้ายังมีของค้างในตะกร้า จะ ปิดเป็นก้อนสุดท้าย
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
    for i, c in enumerate(chunks, start=1):                               # ไล่ทีละก้อน นับเลขเริ่มที่ 1
        preview = _PAGE_RE.sub("", c).strip().replace("\n", " ")          # ลบป้าย [หน้า X] + เปลี่ยนการขึ้นบรรทัดเป็นเว้นวรรค
        preview = preview[:INDEX_PREVIEW_CHARS]                           # ตัดเอาแค่ 400 ตัวอักษรแรกของก้อน
        lines.append(f"[ก้อน {i}] ({chunk_page_range(c)}) {preview}...")   # เขียนเป็น 1 รายการ
    return "\n\n".join(lines) # ต่อทุกรายการ คั่นด้วยบรรทัดว่าง

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

#ทำ "สารบัญย่อ" ให้ AI ดู โดยเอาแค่ตัวหนังสือช่วงต้นของแต่ละหน้ามา หน้าละ 1 บรรทัด 
""" จะได้แบบนี้
[
  (1, "บทที่ 1 เซลล์\n\nเซลล์คือหน่วยที่เล็กที่สุด......(ยาว 2,000 ตัว)"),
  (2, "ส่วนประกอบของเซลล์   ได้แก่ นิวเคลียส......"),
  (3, "บทที่ 2 หัวใจ\nหัวใจมี 4 ห้อง......"),
]
"""

#(ทำสารบัญย่อ)
def build_page_index(pages: List[Tuple[int, str]]) -> str:
    lines = []
    # ไล่ทีละหน้า
    for page_no, body in pages:

        # รวบช่องว่างกับการขึ้นบรรทัดใหม่ทั้งหมดให้เหลือเว้นวรรคเดียว แล้วตัดเอาแค่ 160 ตัวอักษรแรกของหน้า
        preview = " ".join(body.split())[:TOPIC_PREVIEW_CHARS]

        # เขียนเป็นบรรทัดแบบ "หน้า 3: ข้อความต้นหน้า..."
        lines.append(f"หน้า {page_no}: {preview}")
    return "\n".join(lines)

#แปลงคำตอบ AI (ตัวหนังสือ) ให้เป็นช่วงหน้าที่โปรแกรมใช้ได้ และซ่อมถ้า AI ตอบผิด
def _parse_groups(raw: str, valid_pages: List[int]) -> Optional[List[Tuple[int, int]]]:
    """แปลงคำตอบ AI เช่น '1-6, 7-11, 12-17' เป็นช่วงหน้า พร้อมตรวจความถูกต้อง"""

    # AI ไม่ตอบอะไรเลย = ใช้ไม่ได้
    if not raw:
        return None

    # หาคู่ตัวเลขที่เขียนแบบ "ตัวเลข-ตัวเลข" ในคำตอบ "คำตอบคือ 1-6, 7-11 ครับ" → [("1","6"), ("7","11")]  (คำพูดอื่นถูกทิ้งไป)
    pairs = re.findall(r"(\d+)\s*[-–]\s*(\d+)", raw)

    # ถ้าไม่เจอตัวเลขสักคู่ = ใช้ไม่ได้
    if not pairs:  
        return None  

    lo_all, hi_all = min(valid_pages), max(valid_pages)  # หน้าแรก  (lo มาจาก low = ต่ำสุด),หน้าสุดท้าย (hi มาจาก high = สูงสุด)

    groups: List[Tuple[int, int]] = [] #Ex groups = [(1, 6), (7, 14), (15, 20)]

    for a, b in pairs:
        start, end = int(a), int(b)         # เปลี่ยนตัวหนังสือ "6" เป็นตัวเลข 6

        if start > end:                     # ถ้า AI เขียนกลับด้าน เช่น 10-7 จะแก้เป็น 7-10
            start, end = end, start

        # ตัดให้อยู่ในช่วงหน้าที่มีจริง
        start = max(start, lo_all)          # ต่ำกว่าหน้าแรก จะ ให้ขึ้นเป็นหน้าแรก
        end = min(end, hi_all)              # เกินหน้าสุดท้าย จะ ตัดเหลือหน้าสุดท้าย

        if start <= end:                    # ถ้าช่วงที่ยังสมเหตุสมผลถึงจะเก็บไว้
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

    #(เช็คว่ามีมากกว่า 3 หน้าไหม)
    pages = split_by_pages(text) # หั่นข้อความกลับเป็นรายหน้า → [(1, "..."), (2, "..."), ...]
    
    if len(pages) < 3:
        return None       # ไม่ต้องแบ่งตามเรื่อง


    key = _cache_key(text) # ตั้งชื่อให้เอกสารนี้ เอาไว้จำว่าเคยเจอเอกสารนี้หรือยัง

    # เปิดสมุดจดดูว่าเคยแบ่งเรื่องของเอกสารนี้ไปแล้วหรือยัง
    # ถ้าเคยแล้ว ก็เอาผลที่จดไว้มาใช้เลย ไม่ต้องเสียเวลาและเงินถาม AI ซ้ำ
    # (เช่น กด "สรุป" ไปแล้ว พอกด "ออกข้อสอบ" ด้วยไฟล์เดิมก็ใช้ผลเดิมได้ทันที)
    if key in _TOPIC_CACHE:
        print(f"[TIME] {'chunk: topic (cache)':<22} {0.0:7.2f}s | ใช้ผลเดิม", flush=True)
        return _TOPIC_CACHE[key]

    import time as _time
    _t0 = _time.perf_counter()

    try:
        from app.core.config import settings
        from app.services.ai_service import client

        #(ส่งสารบัญย่อไปให้ AI) เขียนคำสั่งแนบสารบัญย่อ
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
        #(ส่งสารบัญย่อไปให้ AI) ส่งคำถาม (prompt ที่มีสารบัญย่อ) ไปให้ AI
        r = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],  # ข้อความที่ส่งไปถาม
            temperature=0, # ให้ AI ตอบแบบเดิมทุกครั้ง ไม่ด้นสด
        )

        #สิ่งที่ AI ตอบ:    "1-3, 4-6, 7-8, 9-10"
        raw = (r.choices[0].message.content or "").strip()  # หยิบคำตอบของ AI ออกมา ถ้าไม่มีคำตอบก็ใช้ "" แทน แล้วตัดช่องว่างหัวท้ายทิ้ง
        groups = _parse_groups(raw, [p for p, _ in pages])  # แปลงคำตอบที่เป็นตัวหนังสือ ให้เป็นช่วงหน้าที่โปรแกรมใช้งานได้ (และซ่อมถ้า AI ตอบผิด)

        # groups แปลงได้:   groups = [(1, 3), (4, 6), (7, 8), (9, 10)]
        

    except Exception: # ถ้าเกิดปัญหาระหว่างทางระบบจะไปหั่นตามความยาวแทน
        return None

    if not groups:
        return None

    # ถ้า AI แบ่งออกมาเกิน 8 กลุ่ม ให้รวมกลุ่มที่เล็กที่สุดเข้ากับกลุ่มข้างๆ
    # ทำซ้ำไปเรื่อยๆ จนเหลือไม่เกิน 8 กลุ่ม (1 กลุ่ม = ถาม AI 1 ครั้ง กลุ่มเยอะ = ช้าและแพง)
    while len(groups) > MAX_SEMANTIC_GROUPS:

        sizes = [(g[1] - g[0] + 1) for g in groups] # นับว่าแต่ละกลุ่มมีกี่หน้า เช่น (7, 9) = 3 หน้า

        i = sizes.index(min(sizes)) # หาว่ากลุ่มไหนเล็กที่สุด (i = ลำดับของกลุ่มนั้น)

        j = i - 1 if i == len(groups) - 1 else i + 1 # เลือกเพื่อนบ้านไว้รวมด้วย: ปกติใช้กลุ่มถัดไป แต่ถ้ากลุ่มที่เล็กสุดเป็นกลุ่มสุดท้าย ไม่มีกลุ่มถัดไปแล้ว ก็ใช้กลุ่มก่อนหน้าแทน

        # ช่วงหน้าใหม่ = ตั้งแต่หน้าแรกของสองกลุ่ม ถึงหน้าสุดท้ายของสองกลุ่ม
        lo = min(groups[i][0], groups[j][0])
        hi = max(groups[i][1], groups[j][1])

        # ใส่ช่วงใหม่ไว้ที่ตำแหน่งของกลุ่มที่อยู่ก่อน แล้วลบกลุ่มที่อยู่หลังทิ้ง
        groups[min(i, j)] = (lo, hi)
        groups.pop(max(i, j))

    # ถ้าสมุดจดครบ 20 เอกสารแล้ว ล้างทิ้งทั้งเล่ม
    if len(_TOPIC_CACHE) >= _TOPIC_CACHE_LIMIT:
        _TOPIC_CACHE.clear()
    _TOPIC_CACHE[key] = groups

    #เอาไว้ Check Log ไม่เกี่ยวกับการทำงาน
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
    groups = detect_topic_groups(text)  #ให้ AI ดูว่าหน้าไหนถึงหน้าไหนเป็นเรื่องเดียวกัน   Ex groups = [(1, 6), (7, 14), (15, 20)]
    
    #(นับว่าเป็น 1 ก้อน) เช็คแล้วไม่ได้มีมากกว่า 3 หน้า จะเรียกใช้ build_chunks นับเป็นก้อนเดียว
    #ถ้า AI แบ่งตามเรื่องไม่ได้ จะใช้แผนสำรอง หั่นตามความยาว/จำนวนหน้าแทน (โอกาสต่ำแต่ทำกันไว้เผื่อเจ๊ง)
    if not groups:
        return build_chunks(text, max_chars=max_chars)

    #ก่อน pages เป็นรายการเรียงต่อกัน [(1, "อาหาร 5 หมู่..."), (2, "โปรตีน..."), (4, "ออกกำลังกาย...")]
    pages = split_by_pages(text)
    by_no: Dict[int, str] = {}
    for page_no, body in pages:
        by_no[page_no] = body
    #หลัง by_no เป็นตู้ที่ลิ้นชักติดเลขหน้า {1: "อาหาร 5 หมู่...", 2: "โปรตีน...", 4: "ออกกำลังกาย..."}
    #ทำเพราะ ตอนจัดก้อน โค้ดต้องหยิบหน้าตามเลข เช่น "ขอหน้า 4" ถ้าเป็นตู้ก็เปิดลิ้นชัก 4 ได้เลย (by_no.get(4)) ไม่ต้องไล่หาทีละอันในรายการ  ถ้าขอหน้าที่ไม่มีลิ้นชัก เช่นหน้า 3 ที่เป็นหน้าว่าง จะได้ None

    #(จัดก้อนตามกลุ่มเรื่อง)
    #เอาช่วงหน้าที่ได้จาก AI เช่น (1,6) ไปประกอบเป็น "ก้อนข้อความ" จริงๆ เพื่อส่งให้ AI สรุปหรือออกข้อสอบ
    chunks: List[str] = [] # กล่องใหญ่ เก็บก้อนที่ทำเสร็จแล้ว 
    """ สมมุติ   groups = [(1, 6), (7, 14), (15, 20)]   # เซลล์ / หัวใจ / ปอด    จะได้ข้อมูลประมาณนี้
        chunks = [
            # ก้อน 1 — เรื่องเซลล์ ทั้งเรื่อง
            "[หน้า 1]\nเซลล์...\n\n[หน้า 2]\n...\n\n ... \n\n[หน้า 6]\n...",

            # ก้อน 2 — เรื่องหัวใจ ส่วนแรก
            "[หน้า 7]\nหัวใจ...\n\n[หน้า 8]\n...\n\n ... \n\n[หน้า 10]\n...",

            # ก้อน 3 — เรื่องหัวใจ ส่วนหลัง (ซอยออกมาเพราะยาวเกิน)
            "[หน้า 11]\n...\n\n ... \n\n[หน้า 14]\n...",

            # ก้อน 4 — เรื่องปอด ทั้งเรื่อง
            "[หน้า 15]\nปอด...\n\n ... \n\n[หน้า 20]\n...",
        ]
    """
    # ไล่ทีละเรื่อง เช่น (1,6) แล้วต่อด้วย (7,14) ...
    for start, end in groups:               # Ex groups = [(1, 6), (7, 14), (15, 20)]
        buf: List[str] = []                 # ตะกร้าเปล่า ไว้ใส่หน้าของก้อนที่กำลังทำ

        buf_len = 0                         # ในตะกร้ามีตัวอักษรแล้วกี่ตัว
        buf_pages = 0                       # ในตะกร้ามีแล้วกี่หน้า

        # ไล่ทีละหน้าในเรื่องนี้ (end + 1 เพราะ range ไม่นับตัวสุดท้าย)
        for p in range(start, end + 1):     
            body = by_no.get(p)             # หยิบเนื้อหาของหน้า p

            if body is None:                # ถ้าหน้านี้ไม่มี (เช่นเป็นหน้าว่าง) จะ ข้าม
                continue

            piece = f"[หน้า {p}]\n{body}"    # แปะป้ายเลขหน้ากลับเข้าไป

            # ถ้าใส่หน้านี้แล้วตะกร้าจะล้น (เกิน 12,000 ตัวอักษร หรือมีครบ 10 หน้าแล้ว) จะ ปิดตะกร้าเดิมเป็น 1 ก้อน แล้วเริ่มตะกร้าใหม่
            if buf and (buf_len + len(piece) > max_chars or buf_pages >= max_pages_hard):
                chunks.append("\n\n".join(buf))
                buf, buf_len, buf_pages = [], 0, 0

            # ใส่หน้านี้ลงตะกร้า และอัปเดตตัวนับ
            buf.append(piece)               
            buf_len += len(piece)           
            buf_pages += 1

        # จบเรื่องนี้แล้ว ถ้าตะกร้ามีของ จะ ปิดเป็น 1 ก้อน (เรื่องใหม่จะเริ่มด้วยตะกร้าใหม่เสมอ สองเรื่องจึงไม่ปนกันในก้อนเดียว)
        if buf:
            chunks.append("\n\n".join(buf))

    # ถ้ามีก้อน จะส่ง chunks ออกไป ถ้าทำแล้วไม่ได้ก้อนเลย จะ ใช้แผนสำรอง หั่นตามความยาวแทน
    return chunks or build_chunks(text, max_chars=max_chars)