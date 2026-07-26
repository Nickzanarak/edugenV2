"""
ตัวช่วยแบ่งเนื้อหาเอกสารยาว ๆ ออกเป็น "ก้อน" (chunk) สำหรับ Map-Reduce และ QA
หลักการ: แบ่งตามขอบเขตหน้าเสมอ ไม่หั่นกลางหน้า เพื่อไม่ให้เนื้อหาหน้าเดียวกันถูกฉีก
"""
import re
from typing import List, Tuple

# ขนาดก้อนโดยประมาณ (ตัวอักษร) ~5-8 หน้า PDF ต่อก้อน
CHUNK_CHAR_SIZE = 12000
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


def build_chunks(text: str, max_chars: int = CHUNK_CHAR_SIZE) -> List[str]:
    """รวมหน้าเข้าเป็นก้อน โดยแต่ละก้อนไม่เกิน max_chars และไม่หั่นกลางหน้า
    ถ้าหน้าเดียวยาวเกิน max_chars จะยอมให้ก้อนนั้นใหญ่กว่าปกติ (ดีกว่าฉีกหน้า)
    """
    pages = split_by_pages(text)
    if not pages:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    for page_no, body in pages:
        piece = f"[หน้า {page_no}]\n{body}" if page_no > 0 else body
        piece_len = len(piece)

        # ถ้าใส่หน้านี้แล้วเกินขนาด และในก้อนมีของอยู่แล้ว → ปิดก้อนเดิมก่อน
        if buf and buf_len + piece_len > max_chars:
            chunks.append("\n\n".join(buf))
            buf, buf_len = [], 0

        buf.append(piece)
        buf_len += piece_len

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