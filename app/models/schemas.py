from pydantic import BaseModel
from typing import List, Dict, Optional, Union

class ContextIn(BaseModel):
    context: str

class ExcludeItem(BaseModel):
    """ข้อสอบที่มีอยู่แล้ว ส่งมาเพื่อกันไม่ให้ออกข้อซ้ำ
    ส่งเฉลยมาด้วยจะช่วยให้ AI ตัดสินได้แม่นขึ้นว่าข้อใหม่ซ้ำของเดิมจริงไหม
    """
    question: str
    answer: Optional[str] = None


class QuizIn(BaseModel):
    context: str
    n: int = 5
    # รับได้ทั้งแบบเดิม (ข้อความล้วน) และแบบใหม่ (คำถาม + เฉลย)
    exclude: Optional[List[Union[str, ExcludeItem]]] = None
    topics: Optional[List[str]] = None
    difficulty: Optional[str] = "medium"
    choices_count: Optional[int] = 4
    # "source" = ถามจากเนื้อหา (ค่าเริ่มต้น) | "applied" = ประยุกต์
    mode: Optional[str] = "source"

class QAIn(BaseModel):
    context: str
    question: str

class SummarizeOut(BaseModel):
    overview: str                       # ภาพรวม = ข้อความ
    key_points: List[str]               # ประเด็นสำคัญ = รายการข้อความ
    sections: List[Dict[str, str]]      # หัวข้อย่อย = รายการกล่อง {title, summary}
    data_points: List[Dict[str, str]]   # ตัวเลขสำคัญ = รายการกล่อง {label, value, unit}

class TopicsOut(BaseModel):
    topics: List[str]