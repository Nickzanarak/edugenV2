"""ตัวช่วยวัดเวลาแต่ละขั้นตอน — ใช้หาคอขวดว่าช้าตรงไหน
ผลจะพิมพ์ออกที่ terminal ของ backend
"""
import time
from contextlib import contextmanager


@contextmanager
def timed(label: str, extra: str = ""):
    start = time.perf_counter()
    try:
        yield
    finally:
        sec = time.perf_counter() - start
        tail = f" | {extra}" if extra else ""
        print(f"[TIME] {label:<22} {sec:7.2f}s{tail}", flush=True)