import asyncio
import base64


from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.core.config import settings
from app.core.security import get_current_user
from app.utils.text import clean_text
from app.utils.timing import timed
from app.services.ai_service import client

router = APIRouter()

# หน้าไหนมีรูปที่กินพื้นที่เกินสัดส่วนนี้ของหน้า → ถือว่า "มีรูปที่มีเนื้อหา" → ส่งเข้า vision
IMAGE_AREA_THRESHOLD = 0.15
AI_MODEL = settings.AI_MODEL


def _page_has_large_image(page) -> bool:
    """เช็คว่าหน้านี้มีรูปที่ใหญ่พอจะเป็นเนื้อหา (ไม่ใช่โลโก้/ไอคอน)"""
    page_area = abs(page.rect.width * page.rect.height)
    if page_area <= 0:
        return False
    for img in page.get_images(full=True):
        try:
            rects = page.get_image_rects(img[0])
        except Exception:
            continue
        for r in rects:
            if abs(r.width * r.height) / page_area >= IMAGE_AREA_THRESHOLD:
                return True
    return False


def _render_page_png_b64(page) -> str:
    """แปลงทั้งหน้าเป็นภาพ PNG แล้วเข้ารหัส base64 (zoom 2 เท่าให้คมพออ่านออก)"""
    import fitz
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  
    return base64.b64encode(pix.tobytes("png")).decode("ascii")


def _describe_page_with_vision(png_b64: str, page_no: int) -> str:
    """ส่งภาพหน้าเข้า vision ให้ AI อ่านทั้งข้อความและรูปในหน้า แล้วสรุปเป็นข้อความ"""
    try:
        r = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "นี่คือหน้าหนึ่งจากเอกสารการเรียน ในหน้านี้มีรูปภาพ/ไดอะแกรม/แผนภาพประกอบ\n"
                                "โปรดถอดเนื้อหาทั้งหมดในหน้านี้ออกมาเป็นข้อความ โดย:\n"
                                "1. คัดข้อความปกติออกมาให้ครบ\n"
                                "2. อธิบายสิ่งที่อยู่ในรูป/ไดอะแกรม/กราฟ ว่าสื่อถึงอะไร มีองค์ประกอบ ป้ายกำกับ ความสัมพันธ์อะไรบ้าง\n"
                                "3. เชื่อมโยงรูปกับคำบรรยายใต้/ข้างรูป (ถ้ามี)\n"
                                "ตอบเป็นข้อความล้วน ไม่ต้องมีหัวข้อ ไม่ต้องเกริ่น\n"
                                "เขียนให้กระชับ ไม่เกิน 200 คำต่อหน้า เก็บเฉพาะสาระสำคัญ ห้ามบรรยายการออกแบบของภาพ"
                                "4. ห้ามบรรยายลักษณะการออกแบบของภาพ (เช่น มีเส้นประ, ป้ายชัดเจน, เข้าใจง่าย) ให้ถอดเฉพาะ ความรู้/ข้อเท็จจริง ที่ภาพสื่อเท่านั้น\n"
                                "5. ถ้าในภาพมีองค์ประกอบย่อยที่มีความหมาย ให้ระบุให้ครบทุกชิ้น อย่าข้าม"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{png_b64}"},
                        },
                    ],
                }
            ],
            temperature=0.2,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        # ถ้าหน้านี้ vision พัง ไม่ให้ล้มทั้งไฟล์ — คืนค่าว่างแล้วไปใช้ text ปกติแทน
        return ""


#  (Backend ตรวจสอบไฟล์) สร้าง API แบบ POST ที่ path /extract (รวมกับ prefix ของ router จะกลายเป็น /pdf/extract)
@router.post("/extract")
async def pdf_extract(
    pdf: UploadFile = File(...),           # รับไฟล์จากฟิลด์ชื่อ "pdf" ห้ามว่าง
    uid: str = Depends(get_current_user)): # ตรวจบัตรผ่านก่อน ถ้าผ่านจะได้ ID ของผู้ใช้

    # รับเฉพาะไฟล์ที่ลงท้ายด้วย .pdf (ไม่สนตัวพิมพ์เล็ก/ใหญ่)
    if not (pdf.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "รองรับเฉพาะไฟล์ .pdf เท่านั้น")

    # โหลดไลบรารีอ่าน PDF ถ้ายังไม่ได้ติดตั้งให้แจ้ง error 500
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise HTTPException(500, "กรุณาติดตั้ง PyMuPDF: pip install PyMuPDF")

    # อ่านไฟล์ทั้งหมดเข้าหน่วยความจำ แล้วเปิดเป็นเอกสาร PDF
    # ถ้าเปิดไม่ได้ (ไฟล์เสียหรือไม่ใช่ PDF จริง) ตอบ 422
    try:
        raw = await pdf.read()
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:
        raise HTTPException(422, "ไม่สามารถเปิดไฟล์ PDF ได้")

    # (วนอ่านไฟล์ทีละหน้า)  รอบที่ 1 — วนทุกหน้า: เก็บ text ปกติ + จดว่าหน้าไหนต้องใช้ vision
    page_texts: list[str] = []               # ข้อความของแต่ละหน้า เรียงตามลำดับหน้า
    vision_jobs: list[tuple[int, str]] = []  # (เลขหน้า, รูปของหน้านั้นแบบ base64) ประมาณแบบว่า (2, "iVBORw0KGgo...")

    try:
        # เริ่มจับเวลา สำหรับทดลอง Log
        _t_scan = __import__("time").perf_counter()

        for i in range(doc.page_count): # เริ่มวนจากหน้า 1 ของไฟล์ PDF
            page = doc.load_page(i)

            page_texts.append(page.get_text() or "") # type: ignore   ดึงข้อความในหน้านี้ ถ้าไม่มีใช้ "" แทน
            
            if _page_has_large_image(page): # ถ้าหน้านี้มีรูปใหญ่ 
                vision_jobs.append((i, _render_page_png_b64(page))) # แปลงทั้งหน้าเป็นรูป PNG (base64) เก็บไว้ส่งให้ AI อ่านภาพ

        # พิมพ์เวลาที่ใช้ จำนวนหน้า และจำนวนหน้าที่ต้องส่ง vision (Log) 
        print(f"[TIME] {'pdf: scan+render':<22} {__import__('time').perf_counter()-_t_scan:7.2f}s "
              f"| {doc.page_count} หน้า, ส่ง vision {len(vision_jobs)} หน้า", flush=True)

    except Exception:
        # อ่านไม่ได้: ปิดไฟล์คืนหน่วยความจำ แล้วตอบ 422
        doc.close()
        raise HTTPException(422, "ไม่สามารถอ่านเนื้อหาในไฟล์ได้")


    # (ส่งให้ AI อ่านหน้าที่มีรูป) รอบที่ 2 — ยิง vision หลายหน้าพร้อมกัน (แบบเร็ว) โดยจำกัดจำนวนพร้อมกันด้วย semaphore
    if vision_jobs: # (ถ้ามีการที่จะต้องเตรียมส่ง Vision)
        sem = asyncio.Semaphore(min(len(vision_jobs), 20))# จำกัดให้ส่งพร้อมกันได้ไม่เกิน 20 หน้า

        # งานของ 1 หน้า: ส่งรูปให้ AI บรรยาย → คืนค่า (เลขหน้า, คำบรรยาย)
        async def run_one(idx: int, b64: str):
            async with sem:  # ถ้าทำอยู่ครบ 20 หน้าแล้ว หน้านี้ต้องรอคิว พอมีหน้าไหนเสร็จก็ได้เข้าไปทำต่อ
                # ฟังก์ชันเรียก OpenAI ต้องรอจนได้คำตอบ เลยแยกไปทำในเธรดอื่น
                desc = await asyncio.to_thread(_describe_page_with_vision, b64, idx)
                return idx, desc

        # จับเวลาช่วงนี้แล้วพิมพ์ลง log เช่น "vision 12 หน้า / พร้อมกัน 12"
        with timed("pdf: vision", f"{len(vision_jobs)} หน้า / พร้อมกัน {min(len(vision_jobs), 20)}"):
            # สั่งทุกหน้าเริ่มพร้อมกัน แล้วรอจนเสร็จครบทุกหน้า
            # 10 หน้าจะใช้เวลาใกล้ๆ กับ 1 หน้า
            results = await asyncio.gather(*(run_one(i, b64) for i, b64 in vision_jobs))

        # เอาผล vision ไปแทน text ปกติของหน้านั้น (ถ้า vision ได้ผลจริง)
        # ถ้า AI ล้มเหลว (desc ว่าง) สมมตุิแตกหน้า 20  จะได้ (20, "") "กรณีมีแค่รูปหน้านั้น แต่ถ้ามีข้อความจะเป็น (20, "ข้อความ")"
        for idx, desc in results:
            if desc:
                page_texts[idx] = desc
        #results = [
        #    (3,  "หัวใจมี 4 ห้อง ..."),
        #    (20, ""),
        #    (25, "กราฟแสดงอุณหภูมิ ..."),]

    doc.close()

    # (แปะเลขหน้าของแต่ละหน้า) ติดป้ายเลขหน้าให้ทุกหน้า และทิ้งหน้าที่ว่างเปล่า
    labeled = [f"[หน้า {i + 1}]\n{t}" for i, t in enumerate(page_texts) if t.strip()]

    # (จะเก็บข้อความส่งไปหน้าเว็บ) เอาทุกหน้ามาต่อกัน เป็นก้อนเดียว โดยเว้นบรรทัดคั่นระหว่างหน้า แล้วทำความสะอาดข้อความ
    text = clean_text("\n\n".join(labeled))

    #ถ้าต่อกันแล้วไม่มีอะไรเลย แปลว่าไฟล์นี้อ่านไม่ออกทั้งไฟล์ ให้แจ้ง error
    if not text:
        raise HTTPException(422, "ไม่สามารถอ่านข้อความได้ (อาจเป็นไฟล์สแกน)")
    return {"text": text} #ส่งกลับไปที่หน้าเว็บ แบบ JSON