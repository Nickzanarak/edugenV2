from openai import OpenAI

from app.core.config import settings

# timeout = กันคำขอค้างนาน (ค่าเริ่มต้นของ OpenAI คือ 600 วินาที ซึ่งนานเกินไปสำหรับเว็บ)
# max_retries = 1 เพื่อไม่ให้พลาดแล้วรอซ้ำหลายรอบจนผู้ใช้รอไม่ไหว
client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=settings.AI_TIMEOUT,
    max_retries=1,
)


def get_openai_client():
    return client