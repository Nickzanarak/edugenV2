from app.utils.nlp import jaccard, similar, filter_near_dups


def test_jaccard_identical():
    assert jaccard("สวัสดีครับ วันนี้อากาศดี", "สวัสดีครับ วันนี้อากาศดี") == 1.0


def test_jaccard_disjoint():
    assert jaccard("แมว กิน ปลา", "รถ วิ่ง เร็ว") == 0.0


def test_similar_identical():
    text = "แรงโน้มถ่วงคืออะไร"
    assert similar(text, text) == 1.0


def test_filter_near_dups_excludes_identical():
    text = "แรงโน้มถ่วงคืออะไร"
    items = [{"question": text}, {"question": text}]
    kept = filter_near_dups(items, exclude=[], threshold=0.78)
    assert len(kept) == 1


def test_filter_near_dups_respects_exclude_list():
    text = "ความเร็วคืออะไร"
    items = [{"question": text}]
    kept = filter_near_dups(items, exclude=[text], threshold=0.78)
    assert len(kept) == 0
