from pydantic import BaseModel
from typing import List, Dict, Any

class QAPair(BaseModel):
    question: str
    answer: str
    # ช่วงหน้าที่ AI ใช้อ้างอิงตอบ (เช่น "หน้า 12-18")
    # ต้องมี field นี้ ไม่งั้น Pydantic จะตัดทิ้งเงียบ ๆ ทำให้ป้ายอ้างอิงหายตอนเปิดประวัติเก่า
    source: str = ""

class QuizHistoryIn(BaseModel):
    file_name: str
    overview: str = ""
    key_points: List[str] = []
    sections: List[Dict[str, str]] = [] 
    data_points: List[Dict[str, str]] = []
    questions: List[Dict[str, Any]]
    answers: Dict[str, str]
    score: int
    content: str = ""
    qa_history: List[QAPair] = [] 

class RenameHistoryIn(BaseModel):
    new_name: str