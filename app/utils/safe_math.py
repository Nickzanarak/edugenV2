"""ตัวคำนวณนิพจน์คณิตศาสตร์แบบปลอดภัย

ใช้ตรวจเฉลยข้อสอบถูก/ผิดของโหมดประยุกต์ โดยไม่เชื่อการคิดเลขของ AI
รับเฉพาะ literal ตัวเลข ตัวดำเนินการคณิต และฟังก์ชันในรายการที่อนุญาตเท่านั้น
ไม่ใช้ eval/exec จึงรันนิพจน์ที่ AI ส่งมาได้อย่างปลอดภัย
"""
import ast
import math
import operator
import re
from typing import List


class UnsafeExpression(ValueError):
    """นิพจน์มี node/ชื่อที่ไม่อนุญาต หรือคำนวณไม่ได้"""


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCS = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1.0 / 3.0), x),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log,          # log(x) หรือ log(x, base)
    "ln": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp,
    "factorial": math.factorial,
    "comb": math.comb, "perm": math.perm,
    "gcd": math.gcd, "lcm": getattr(math, "lcm", None),
    "abs": abs, "round": round,
    "floor": math.floor, "ceil": math.ceil, "trunc": math.trunc,
    "degrees": math.degrees, "radians": math.radians,
    "hypot": math.hypot, "fabs": math.fabs,
    "min": min, "max": max, "sum": sum,
}
_FUNCS = {k: v for k, v in _FUNCS.items() if v is not None}

_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

_MAX_POW_EXP = 128       # กันนิพจน์ระเบิด เช่น 9**9**9
_MAX_POW_BASE = 1e12
_MAX_LEN = 200
# factorial(170) เป็นค่ามากสุดที่ float เก็บได้ เกินกว่านั้นคำนวณไปก็ใช้ไม่ได้
_COMBINATORIC = ("factorial", "comb", "perm")
_MAX_FACTORIAL = 170


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeExpression(f"ค่าคงที่ไม่อนุญาต: {node.value!r}")
        return node.value

    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"ตัวดำเนินการไม่อนุญาต: {type(node.op).__name__}")
        left, right = _eval(node.left), _eval(node.right)
        if op is operator.pow and (abs(right) > _MAX_POW_EXP or abs(left) > _MAX_POW_BASE):
            raise UnsafeExpression("เลขยกกำลังใหญ่เกินไป")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"unary ไม่อนุญาต: {type(node.op).__name__}")
        return op(_eval(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise UnsafeExpression("เรียกฟังก์ชันไม่อนุญาต")
        if node.keywords:
            raise UnsafeExpression("keyword argument ไม่รองรับ")
        name = node.func.id
        args = [_eval(a) for a in node.args]
        # ฟังก์ชันกลุ่มแฟกทอเรียลโตเร็วมาก ถ้าไม่จำกัดค่า จะเผา CPU
        # ไปเปล่า ๆ ก่อนที่จะพังตอนแปลงเป็น float อยู่ดี
        if name in _COMBINATORIC and any(abs(a) > _MAX_FACTORIAL for a in args):
            raise UnsafeExpression(f"ค่าที่ส่งให้ {name} ใหญ่เกินไป")
        return _FUNCS[name](*args)

    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise UnsafeExpression(f"ชื่อไม่อนุญาต: {node.id}")

    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval(e) for e in node.elts]

    raise UnsafeExpression(f"ไวยากรณ์ไม่อนุญาต: {type(node).__name__}")


def safe_eval(expr: str) -> float:
    """คำนวณนิพจน์ คืนค่า float — โยน UnsafeExpression ถ้าไม่ปลอดภัยหรือคำนวณไม่ได้"""
    text = (expr or "").strip()
    if not text:
        raise UnsafeExpression("นิพจน์ว่าง")
    if len(text) > _MAX_LEN:
        raise UnsafeExpression("นิพจน์ยาวเกินไป")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpression(f"parse ไม่ได้: {e}") from e

    try:
        result = _eval(tree)
    except UnsafeExpression:
        raise
    except Exception as e:
        raise UnsafeExpression(f"คำนวณไม่ได้: {e}") from e

    if isinstance(result, complex):
        raise UnsafeExpression("ผลลัพธ์เป็นจำนวนเชิงซ้อน")
    if isinstance(result, (list, tuple)):
        raise UnsafeExpression("ผลลัพธ์ไม่ใช่ตัวเลขเดี่ยว")
    try:
        value = float(result)
    except (TypeError, ValueError, OverflowError) as e:
        # OverflowError เกิดเมื่อผลลัพธ์เป็นจำนวนเต็มที่ใหญ่เกินกว่า float จะเก็บได้
        # เช่น factorial(171) ถ้าไม่ดักไว้ตรงนี้ มันจะทะลุขึ้นไปถึงผู้ใช้เป็น error 500
        # เพราะตัวเรียกทุกตัวดักแค่ UnsafeExpression
        raise UnsafeExpression(f"ผลลัพธ์ไม่ใช่ตัวเลขที่ใช้ได้: {type(e).__name__}") from e
    if math.isnan(value) or math.isinf(value):
        raise UnsafeExpression("ผลลัพธ์เป็น nan/inf")
    return value


def decimals_written(text) -> int:
    """จำนวนตำแหน่งทศนิยมที่ "เขียนไว้" ในข้อความ เช่น "1.33" -> 2, "7" -> 0

    คืน -1 เมื่อไม่ใช่เลขทศนิยมธรรมดา (เช่นเศษส่วน 1/2) ซึ่งไม่ใช่การปัดเศษ
    """
    s = str(text).strip()
    if "/" in s:
        return -1
    if "." not in s:
        return 0
    return len(s.rsplit(".", 1)[-1])


def matches(expr: str, stated, rel_tol: float = 1e-9, abs_tol: float = 1e-9) -> bool:
    """True ถ้าผลของ expr เท่ากับ stated (stated เป็นนิพจน์ได้ เช่น "1/2")

    รองรับการปัดเศษ: ถ้าโจทย์เขียนทศนิยมไว้ n ตำแหน่ง จะเทียบกันที่ n ตำแหน่งนั้น
    เช่น expr ได้ 1.33333... โจทย์เขียน 1.33 ถือว่าตรงกัน

    แต่ถ้าโจทย์เขียนเป็นจำนวนเต็ม จะต้องตรงเป๊ะเท่านั้น ห้ามปัด
    ไม่งั้น "12 x (1/2)^3 มีค่าเท่ากับ 2" จะถูกตัดสินว่าจริง (เพราะ 1.5 ปัดเป็น 2)
    ทั้งที่ควรเป็นเท็จ
    """
    got = safe_eval(expr)
    want = safe_eval(str(stated))
    if math.isclose(got, want, rel_tol=rel_tol, abs_tol=abs_tol):
        return True

    places = decimals_written(stated)
    if places >= 1:
        return math.isclose(round(got, places), want, rel_tol=rel_tol, abs_tol=abs_tol)
    return False


# เลขติดลบ ทศนิยม และเศษส่วน เช่น -4, 1.5, 1/2  (คอมมาคั่นหลักถูกลบก่อนแล้ว)
_NUM_IN_TEXT = re.compile(r"-?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?")


def number_strings_in_text(text: str) -> List[str]:
    """ตัวเลขที่ปรากฏในข้อความ คืนเป็น "ข้อความตามที่เขียนไว้"

    ต่างจาก numbers_in_text ตรงที่รักษาจำนวนตำแหน่งทศนิยมไว้
    ซึ่งจำเป็นตอนเทียบกับ matches() ที่ยอมรับการปัดเศษตามที่โจทย์เขียน
    """
    return [m.group() for m in _NUM_IN_TEXT.finditer((text or "").replace(",", ""))]


def numbers_in_text(text: str) -> List[float]:
    """ดึงตัวเลขทุกตัวที่ปรากฏในข้อความออกมาเป็นค่าตัวเลข"""
    out: List[float] = []
    for m in _NUM_IN_TEXT.finditer((text or "").replace(",", "")):
        try:
            out.append(safe_eval(m.group()))
        except UnsafeExpression:
            continue
    return out


def appears_in(text: str, value, rel_tol: float = 1e-9, abs_tol: float = 1e-9) -> bool:
    """ค่า value ปรากฏเป็นตัวเลขอยู่ในข้อความนี้จริงหรือไม่

    ใช้จับกรณี AI กรอกช่อง stated ผิด — มันมักกรอก "ค่าที่คำนวณได้"
    แทน "ค่าที่เขียนอยู่ในโจทย์" ซึ่งทำให้ข้อที่เฉลยเป็นเท็จถูกตัดสินผิดทั้งหมด
    """
    try:
        want = safe_eval(str(value))
    except UnsafeExpression:
        return False
    return any(
        math.isclose(n, want, rel_tol=rel_tol, abs_tol=abs_tol)
        for n in numbers_in_text(text)
    )
