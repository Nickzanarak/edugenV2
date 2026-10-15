from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import ContextIn, SummarizeOut
from app.services.summarize_service import SummarizeService

router = APIRouter()

# รับคำขอแบบ POST ที่ /summarize   "" = ไม่ต่อท้ายอะไรเพิ่ม เพราะ main.py ตั้ง prefix "/summarize" ไว้แล้ว  response_model = คำตอบที่ส่งกลับไปจะมีหน้าตาแบบ SummarizeOut
@router.post("", response_model=SummarizeOut)
def summarize(
        body: ContextIn,                       # แกะ JSON ที่หน้าเว็บส่งมา
        uid: str = Depends(get_current_user)): # ตรวจบัตรล็อกอินก่อน ถ้าผ่านจะได้ ID ผู้ใช้มา
    return SummarizeService.summarize(body.context or "", uid) # ส่งต่อให้ SummarizeService (ถ้า context ว่าง ใช้ "" แทน)

#Ex
#   { "overview": "หัวใจเป็นอวัยวะที่สูบฉีดเลือด...",
#     "key_points": ["หัวใจมี 4 ห้อง", "..."],
#     "sections": [{"title": "โครงสร้างหัวใจ", "summary": "..."}],
#     "data_points": [{"label": "อัตราการเต้นปกติ", "value": "60-100", "unit": "ครั้ง/นาที"}] }