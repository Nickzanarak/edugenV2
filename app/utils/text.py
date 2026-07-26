import re
import json
from typing import List, Union

def sentences(text: str) -> List[str]: 
    s = re.split(r"[。.!?]\s+|[\n\r]+", (text or "").strip())
    return [x.strip() for x in s if x.strip()]

def clean_text(text: str) -> str:
    text = re.sub(r"\n{2,}", "\n\n", text or "")
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()

def strip_json_fence(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?", "", s).strip()
        s = re.sub(r"```$", "", s).strip()
    return s

def safe_json_loads(s: str, fallback: Union[dict, list, None] = None):
    try:
        return json.loads(strip_json_fence(s))
    except Exception:
        return fallback if fallback is not None else {}

def numbered_sentences(text: str, max_sentences: int = 800):
    sents = sentences(text)
    sents = sents[:max_sentences]
    return [{"id": i, "text": t} for i, t in enumerate(sents, start=1)]

def truncate_text_chars(text: str, max_chars: int = 45000) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text  
    else:
        return text[:max_chars]
