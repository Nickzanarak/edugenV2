import json

import pytest
from fastapi import HTTPException

from app.models.bank import QuestionIn
from app.services.bank_service import BankService


@pytest.fixture
def bank_store(monkeypatch):
    """Mock Firestore with an in-memory dict so tests need no real database."""
    uid = "test-user"
    store = {
        "questions": [
            {
                "id": 1,
                "type": "mcq",
                "question": "แรงโน้มถ่วงคืออะไร",
                "choices": ["a", "b", "c", "d"],
                "answer": "ก",
                "explain": "",
                "topic": "",
            }
        ],
        "quizzes": [
            {
                "id": 10,
                "title": "ชุดทดสอบ",
                "question_ids": [1],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    }

    def fake_read_list(user_id: str, kind: str):
        assert user_id == uid
        return list(store.get(kind, []))

    def fake_write_list(user_id: str, kind: str, items):
        assert user_id == uid
        store[kind] = items

    monkeypatch.setattr("app.services.bank_service._read_list", fake_read_list)
    monkeypatch.setattr("app.services.bank_service._write_list", fake_write_list)
    return uid, store


def test_is_duplicate_in_set_detects_exact_duplicate(bank_store):
    uid, _ = bank_store
    assert BankService.is_duplicate_in_set(uid, 10, "แรงโน้มถ่วงคืออะไร") is True


def test_is_duplicate_in_set_allows_distinct_question(bank_store):
    uid, _ = bank_store
    assert BankService.is_duplicate_in_set(uid, 10, "ความเร็วคืออะไร") is False


def test_add_question_to_set_rejects_duplicate(bank_store):
    uid, store = bank_store
    body = QuestionIn(
        type="mcq",
        question="แรงโน้มถ่วงคืออะไร",
        choices=["a", "b", "c", "d"],
        answer="ก",
        explain="",
    )
    with pytest.raises(HTTPException) as exc:
        BankService.add_question_to_set(uid, 10, body)
    assert exc.value.status_code == 409

    assert len(store["questions"]) == 1
    assert store["quizzes"][0]["question_ids"] == [1]


def test_add_question_to_set_appends_new_question(bank_store):
    uid, store = bank_store
    body = QuestionIn(
        type="tf",
        question="แสงเดินทางเร็วกว่าเสียง",
        answer="true",
        explain="",
    )
    created = BankService.add_question_to_set(uid, 10, body)

    assert created["id"] == 2
    assert len(store["questions"]) == 2
    assert store["quizzes"][0]["question_ids"] == [1, 2]
