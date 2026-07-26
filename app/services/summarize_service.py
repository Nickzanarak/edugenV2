import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from fastapi import HTTPException

from app.db.firebase import log_user_event
from app.services.ai_service import client
from app.utils.chunking import build_chunks
from app.utils.text import clean_text, numbered_sentences, safe_json_loads, truncate_text_chars

AI_MODEL = "gpt-4o-mini"
# จำนวนก้อนที่ยิง AI พร้อมกัน (มากไปเสี่ยงโดน rate limit)
MAP_CONCURRENCY = 4


class SummarizeService:
    # ---------------- helper ----------------
    @staticmethod
    def _norm_list(x):
        return x if isinstance(x, list) else []

    @staticmethod
    def _norm_str(x):
        return (x or "").strip()

    @staticmethod
    def _clean_sections(sections) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for s in SummarizeService._norm_list(sections):
            if isinstance(s, dict):
                title = SummarizeService._norm_str(s.get("title", ""))
                summary = SummarizeService._norm_str(s.get("summary", ""))
                if title and summary:
                    out.append({"title": title, "summary": summary})
        return out

    @staticmethod
    def _clean_data_points(dps) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for d in SummarizeService._norm_list(dps):
            if isinstance(d, dict):
                label = SummarizeService._norm_str(d.get("label", ""))
                value = SummarizeService._norm_str(d.get("value", ""))
                unit = SummarizeService._norm_str(d.get("unit", ""))
                if label and value:
                    item: Dict[str, str] = {"label": label, "value": value}
                    if unit:
                        item["unit"] = unit
                    out.append(item)
        return out

    # ---------------- MAP: สรุปทีละก้อน ----------------
    @staticmethod
    def _map_one_chunk(chunk: str, idx: int, total: int) -> Dict[str, Any]:
        """สรุปก้อนเดียว — เน้นเก็บรายละเอียดให้ครบ เพราะยังมีที่ว่างเยอะ"""
        prompt = f"""
คุณกำลังอ่านเอกสารส่วนที่ {idx} จากทั้งหมด {total} ส่วน
สรุปเฉพาะเนื้อหาในส่วนนี้เท่านั้น ห้ามเดาเนื้อหาส่วนอื่น

ข้อกำหนดสำคัญ:
- เก็บรายละเอียดให้ครบ: ตัวเลข ชื่อเฉพาะ นิยาม ขั้นตอน ตัวอย่าง ต้องไม่หาย
- ห้ามย่อจนเหลือแต่ใจความกว้าง ๆ
- ครอบคลุมทุกหัวข้อที่ปรากฏในส่วนนี้ แม้หัวข้อนั้นจะมีเนื้อหาสั้นก็ต้องเก็บ
- ถ้ามีคำอธิบายรูปภาพ/แผนภาพ ให้ถือเป็นเนื้อหาปกติ

ตอบ JSON: {{"sections":[{{"title":"...","summary":"..."}}],"key_points":["..."],"data_points":[{{"label":"...","value":"...","unit":"..."}}]}}

เนื้อหาส่วนที่ {idx}:
{chunk}
"""
        try:
            r = client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                response_format={"type": "json_object"},
            )
            data = safe_json_loads(
                r.choices[0].message.content,
                {"sections": [], "key_points": [], "data_points": []},
            )
            return {
                "sections": SummarizeService._clean_sections(data.get("sections", [])),
                "key_points": [
                    SummarizeService._norm_str(k)
                    for k in SummarizeService._norm_list(data.get("key_points", []))
                    if SummarizeService._norm_str(k)
                ],
                "data_points": SummarizeService._clean_data_points(data.get("data_points", [])),
            }
        except Exception:
            # ก้อนเดียวพัง ไม่ให้ล้มทั้งไฟล์
            return {"sections": [], "key_points": [], "data_points": []}

    # ---------------- REDUCE: รวมสรุปย่อย ----------------
    @staticmethod
    def _reduce(parts: List[Dict[str, Any]], total_chunks: int) -> Dict[str, Any]:
        """รวมสรุปย่อยทุกก้อน — เน้นจัดระเบียบ ไม่ใช่ย่อซ้ำ"""
        all_sections: List[Dict[str, str]] = []
        all_keys: List[str] = []
        all_dps: List[Dict[str, str]] = []
        for p in parts:
            all_sections.extend(p.get("sections", []))
            all_keys.extend(p.get("key_points", []))
            all_dps.extend(p.get("data_points", []))

        merged_input = json.dumps(
            {"sections": all_sections, "key_points": all_keys},
            ensure_ascii=False,
        )

        # ปริมาณผลลัพธ์แปรผันตามความยาวเอกสาร
        target_sections = max(5, min(30, total_chunks * 3))
        overview_sentences = max(4, min(18, total_chunks * 3))
        topic_count = len(all_sections)

        prompt = f"""
ด้านล่างคือบทสรุปย่อยจากเอกสารฉบับเดียวกันที่ถูกแบ่งอ่านเป็น {total_chunks} ส่วน
หน้าที่ของคุณคือ "รวบรวมและจัดระเบียบ" ไม่ใช่ย่อซ้ำให้สั้นลง

ข้อกำหนดเรื่องปริมาณ (สำคัญมาก):
- เอกสารนี้ยาว {total_chunks} ส่วน มีหัวข้อย่อยรวม {topic_count} หัวข้อ → ผลลัพธ์ต้องละเอียดตามขนาดนี้
- overview ต้องยาวประมาณ {overview_sentences} ประโยค ห้ามสรุปสั้นกว่านี้
- sections ให้มีประมาณ {target_sections} หัวข้อ (ยุบเฉพาะที่ซ้ำกันจริง)
- แต่ละ section summary ต้องยาว 4-8 ประโยค ไม่ใช่ประโยคเดียว

ข้อกำหนดเรื่องความครบถ้วน (สำคัญมาก):
- ให้พื้นที่แต่ละเรื่อง "ตามสัดส่วนเนื้อหาจริง" ถ้าเรื่องใดมีหลายหัวข้อย่อย ต้องได้พื้นที่มากตามนั้น
- ห้ามสรุปเรื่องหนึ่งด้วยประโยคเดียวแบบผ่าน ๆ ต่อท้าย (เช่น "นอกจากนี้ยังมีเรื่อง...") เด็ดขาด
- ถ้าเอกสารมีหลายเรื่องที่ไม่เกี่ยวกัน ให้แยกเป็นคนละหัวข้อ และอธิบายแต่ละเรื่องให้เต็ม
- ห้ามตัดตัวเลข ชื่อเฉพาะ นิยาม หรือรายละเอียดสำคัญทิ้ง
- overview ต้องเล่าครบทุกเรื่องหลัก โดยแต่ละเรื่องได้พื้นที่สมน้ำสมเนื้อกัน

ตอบ JSON: {{"overview":"...","key_points":["..."],"sections":[{{"title":"...","summary":"..."}}]}}

บทสรุปย่อย:
{merged_input}
"""
        try:
            r = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": "คุณรวบรวมบทสรุปโดยไม่ทำข้อมูลตกหล่น"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                response_format={"type": "json_object"},
            )
            data = safe_json_loads(
                r.choices[0].message.content,
                {"overview": "", "key_points": [], "sections": []},
            )
            sections = SummarizeService._clean_sections(data.get("sections", []))
            keys = [
                SummarizeService._norm_str(k)
                for k in SummarizeService._norm_list(data.get("key_points", []))
                if SummarizeService._norm_str(k)
            ]
        except Exception:
            # ถ้า reduce พัง ใช้ผลรวมดิบแทน ดีกว่าไม่ได้อะไรเลย
            sections, keys = all_sections, all_keys
            data = {"overview": ""}

        # กันข้อมูลหาย: ถ้า AI ตัดหัวข้อทิ้งเยอะเกินไป ใช้ของดิบแทน
        if len(sections) < max(1, len(all_sections) // 3):
            sections = all_sections

        # ตัด data_points ที่ซ้ำ (label+value เหมือนกัน)
        seen = set()
        uniq_dps: List[Dict[str, str]] = []
        for d in all_dps:
            k = (d.get("label", ""), d.get("value", ""))
            if k not in seen:
                seen.add(k)
                uniq_dps.append(d)

        return {
            "overview": SummarizeService._norm_str(data.get("overview", "")),
            "key_points": keys[:max(10, total_chunks * 5)],
            "sections": sections,
            "data_points": uniq_dps[:max(15, total_chunks * 8)],
        }

    # ---------------- ทางเดิม: เอกสารสั้น ----------------
    @staticmethod
    def _summarize_single(ctx: str) -> Dict[str, Any]:
        sent_items = numbered_sentences(ctx, max_sentences=800)
        if not sent_items:
            raise HTTPException(422, "เอกสารสั้นเกินไป")
        sent_block = "\n".join(f"[{it['id']}] {it['text']}" for it in sent_items)

        prompt_sections = f"""
คุณเป็นครูบรรณาธิการสรุปเอกสารแบบยึดตามข้อความเท่านั้น
- อ่านเฉพาะ "รายการประโยคมีเลขกำกับ"
- สกัดหัวข้อหลัก 5–9 หัวข้อ และสรุปหัวข้อละ 3–6 ประโยค
- ถ้าเอกสารมีหลายเรื่องที่ไม่เกี่ยวกัน ต้องแยกเป็นคนละหัวข้อ ห้ามข้ามเรื่องที่มีเนื้อหาน้อย
ตอบเป็น JSON: {{"sections":[{{"title":"...","summary":"..."}}]}}
รายการประโยค:
{sent_block}
"""
        res1 = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt_sections}],
            temperature=0.15,
            response_format={"type": "json_object"},
        )
        sec_json = safe_json_loads(res1.choices[0].message.content, {"sections": []})
        sections = SummarizeService._clean_sections(sec_json.get("sections", []))

        prompt_overview = f"""
คุณเป็นผู้ช่วยสรุประดับอาจารย์ ใช้เฉพาะข้อมูลจาก "รายการประโยค" และ "หัวข้อ" ด้านล่าง
overview ต้องกล่าวถึงทุกเรื่องหลักที่พบ ไม่ใช่เฉพาะเรื่องที่มีเนื้อหาเยอะที่สุด
ตอบ JSON เดียว: {{"overview":"...","key_points":["..."],"data_points":[{{"label":"...","value":"...","unit":"..."}}]}}

สำหรับ data_points ให้พยายามดึงข้อมูลที่เป็น:
1. ตัวเลขสถิติ หรือ จำนวน
2. ปี พ.ศ./ค.ศ. หรือ วันที่สำคัญ
3. ชื่อเฉพาะที่สำคัญ หรือ ประเภท/หมวดหมู่
ถ้าไม่มีตัวเลข ให้ดึงข้อมูลสำคัญสั้นๆ มาใส่ใน value แทน

รายการประโยค:
{ctx}
หัวข้อ:
{json.dumps({"sections": sections}, ensure_ascii=False)}
"""
        res2 = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "คุณสรุปได้กระชับ ชัด และยึดข้อความต้นฉบับเท่านั้น"},
                {"role": "user", "content": prompt_overview},
            ],
            temperature=0.15,
            response_format={"type": "json_object"},
        )
        ov_json = safe_json_loads(
            res2.choices[0].message.content,
            {"overview": "", "key_points": [], "data_points": []},
        )

        return {
            "overview": SummarizeService._norm_str(ov_json.get("overview", "")),
            "key_points": SummarizeService._norm_list(ov_json.get("key_points", [])),
            "sections": sections,
            "data_points": SummarizeService._clean_data_points(ov_json.get("data_points", [])),
        }

    # ---------------- entry point ----------------
    @staticmethod
    def summarize(context: str, uid: str) -> Dict[str, Any]:
        ctx_raw = (context or "").strip()
        if not ctx_raw:
            raise HTTPException(400, "context ว่าง")

        ctx = clean_text(ctx_raw)  # ไม่ตัดทิ้งแล้ว — ใช้ทั้งเอกสาร
        chunks = build_chunks(ctx)
        if not chunks:
            raise HTTPException(422, "เอกสารสั้นเกินไป")

        try:
            if len(chunks) == 1:
                # เอกสารสั้น — ใช้วิธีเดิม (คุณภาพดีที่สุดสำหรับไฟล์เล็ก)
                result = SummarizeService._summarize_single(chunks[0])
            else:
                # เอกสารยาว — Map-Reduce
                total = len(chunks)
                with ThreadPoolExecutor(max_workers=MAP_CONCURRENCY) as pool:
                    parts = list(
                        pool.map(
                            lambda t: SummarizeService._map_one_chunk(t[1], t[0], total),
                            [(i + 1, c) for i, c in enumerate(chunks)],
                        )
                    )
                result = SummarizeService._reduce(parts, total)

            log_user_event(
                uid,
                "summaries",
                {
                    "textLength": len(ctx_raw),
                    "chunks": len(chunks),
                    "source": "text",
                    "status": "success",
                    "summary": result,
                },
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            try:
                log_user_event(
                    uid,
                    "summaries",
                    {"textLength": len(ctx_raw), "source": "text", "status": "error", "errorMessage": str(e)},
                )
            except Exception:
                pass
            raise HTTPException(500, f"Summarize failed: {e}") from e