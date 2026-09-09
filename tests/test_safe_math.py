import pytest

from app.utils import safe_math


@pytest.mark.parametrize("expr,stated,expected", [
    ("12*(1/2)**3", "1.5", True),
    ("12*(1/2)**3", "3", False),
    ("sqrt(49)", "7", True),
    ("sqrt(50)", "7", False),
    ("2+3*4", "14", True),
    ("comb(5,2)", "10", True),
    ("factorial(4)", "24", True),
    ("-3 + -3", "-6", True),
    ("1/2 + 1/3", "5/6", True),
])
def test_matches(expr, stated, expected):
    assert safe_math.matches(expr, stated) is expected


@pytest.mark.parametrize("bad", [
    '__import__("os").system("x")',
    "x + 1",
    "open(1)",
    "9**9**9",
    "(lambda: 1)()",
    "[1, 2][0]",
    "1 if True else 2",
    "",
    "a" * 300,
])
def test_rejects_unsafe(bad):
    with pytest.raises(safe_math.UnsafeExpression):
        safe_math.safe_eval(bad)


def test_division_by_zero_is_unsafe():
    with pytest.raises(safe_math.UnsafeExpression):
        safe_math.safe_eval("1/0")


# ----- ยอมรับการปัดเศษ แต่ต้องไม่ยอมมากเกินไป -----

@pytest.mark.parametrize("expr,stated,expected", [
    ("4/3", "1.33", True),          # ปัด 2 ตำแหน่งตามที่โจทย์เขียน
    ("4/3", "1.3", True),           # ปัด 1 ตำแหน่ง
    ("2/3", "0.67", True),
    ("4/3", "1.34", False),         # ปัดแล้วยังไม่ตรง = เท็จจริง
    ("12*(1/2)**3", "2", False),    # 1.5 ปัดเป็น 2 ได้ แต่โจทย์เขียนจำนวนเต็ม ต้องตรงเป๊ะ
    ("12*(1/2)**3", "1.5", True),
    ("3/2", "1.5", True),
    ("7/2", "4", False),            # 3.5 -> ห้ามปัดขึ้นเป็น 4
])
def test_rounding_tolerance(expr, stated, expected):
    assert safe_math.matches(expr, stated) is expected


@pytest.mark.parametrize("text,expected", [("1.33", 2), ("7", 0), ("1/2", -1), ("-4.5", 1)])
def test_decimals_written(text, expected):
    assert safe_math.decimals_written(text) == expected


# ----- ตรวจว่าค่าปรากฏในข้อความจริงไหม -----

def test_appears_in_finds_plain_number():
    assert safe_math.appears_in("พจน์ที่ 8 มีค่าเป็น 30", "30") is True


def test_appears_in_rejects_absent_number():
    assert safe_math.appears_in("พจน์ที่ 8 มีค่าเป็น 30", "34") is False


def test_appears_in_handles_negative_fraction_and_comma():
    assert safe_math.appears_in("พจน์ที่ 6 มีค่าเป็น -4", "-4") is True
    assert safe_math.appears_in("ครึ่งหนึ่งคือ 1/2", "1/2") is True
    assert safe_math.appears_in("ราคารวม 1,250 บาท", "1250") is True
