import os
import re
import pathlib
from io import BytesIO
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
from app.core.security import get_current_user
from app.services.bank_service import _read_list
from app.models.bank import ExportOpts

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
except ImportError:
    A4 = None

router = APIRouter()

# Issue 2: Use __file__-based path instead of os.getcwd() — reliable on Azure App Service
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

def _load_th_font():
    font_dir = _PROJECT_ROOT / "fonts"
    f1 = font_dir / "THSarabunNew.ttf"
    try:
        if f1.exists():
            pdfmetrics.registerFont(TTFont("THSarabunNew", str(f1)))
            return "THSarabunNew"
        else:
            print("❌ ไม่พบฟอนต์:", f1)
    except Exception as e:
        print("Font load error:", e)
    return "Helvetica"

def _render_pdf_quiz(title: str, questions: List[Dict[str, Any]], opts: ExportOpts) -> bytes:
    if A4 is None:
        raise HTTPException(500, "reportlab ยังไม่ได้ติดตั้ง (pip install reportlab)")
    buf = BytesIO()
    font_name = _load_th_font()
    style_normal = ParagraphStyle("Normal", fontName=font_name, fontSize=16, leading=20)
    style_title = ParagraphStyle("Title", fontName=font_name, fontSize=18, leading=22, spaceAfter=8)
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story = [Paragraph(title or "แบบทดสอบ", style_title), Spacer(1, 6)]
    def _mcq_lines(ch: List[str]):
        labels = ["ก", "ข", "ค", "ง", "จ", "ฉ"]
        items = [c for c in (ch or []) if str(c).strip()][:6]
        out = []
        for i, t in enumerate(items):
            lab = labels[i]
            cleaned = (t or "").strip()
            if not cleaned.startswith(tuple(labels)):
                cleaned = f"{lab}. {cleaned}"
            out.append(cleaned)
        return out
    
    for idx, q in enumerate(questions, start=1):
        qtext = str(q.get("question", "")).strip()
        qtype = (q.get("type", "mcq") or "").lower()
        story.append(Paragraph(f"{idx}) {qtext}", style_normal))
        if qtype == "tf":
            chs = ["ก. จริง", "ข. เท็จ"]
        else:
            ch_raw = q.get("choices") or []
            chs = _mcq_lines(ch_raw)
        for line in chs:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{line}", style_normal))
        if opts.showAnswers:
            ans = str(q.get("answer", "")).strip()
            if qtype == "tf":
                ans = "ก" if ans.lower() in ["true", "จริง"] else "ข"
            explain = str(q.get("explain") or "").strip()
            story.append(Paragraph(f"<b>เฉลย:</b> {ans}{(' — ' + explain) if explain else ''}", style_normal))
        story.append(Spacer(1, 6))
        
    def _on_page(canvas, doc):
        name = _load_th_font()
        canvas.setFont(name, 12 if name != "Helvetica" else 10)
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"หน้า {doc.page}")
        
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.read()

@router.post("/quizzes/{quiz_id}")
def export_quiz_pdf(quiz_id: int, opts: ExportOpts = Body(...), uid: str = Depends(get_current_user)):
    quizzes = _read_list(uid, "quizzes")
    questions = _read_list(uid, "questions")
    qz = next((x for x in quizzes if int(x.get("id", -1)) == quiz_id), None)
    if not qz:
        raise HTTPException(404, "Quiz not found")
    by_id = {int(q["id"]): q for q in questions}
    bundle = [by_id[i] for i in qz.get("question_ids", []) if i in by_id]
    pdf_bytes = _render_pdf_quiz(qz.get("title", "แบบทดสอบ"), bundle, opts)
    raw_name = (qz.get("title", "quiz") or "quiz").strip()
    base_no_pdf = re.sub(r"\.pdf$", "", raw_name, flags=re.IGNORECASE)
    fallback = re.sub(r"[^A-Za-z0-9_.-]+", "_", base_no_pdf) or "quiz"
    fallback = f"{fallback}.pdf"
    utf8_name = quote(f"{base_no_pdf}.pdf".encode("utf-8"))
    content_disp = f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{utf8_name}'
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disp},
    )