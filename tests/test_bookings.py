from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.idempotency import hash_request
from app.main import create_app
from app.models import IN_PROGRESS, Booking, IdempotencyRecord, Payment
from app.schemas import BookingRequest

BODY = {"show_id": 1, "seat": "A1", "user_id": 7, "amount_cents": 1500}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}"))


def count(client: TestClient, model: type) -> int:
    with client.app.state.sessions() as db:
        return db.scalar(select(func.count()).select_from(model))


def post(client: TestClient, key: str, body: dict = BODY):
    return client.post("/bookings", json=body, headers={"Idempotency-Key": key})


def test_same_key_twice_gives_one_payment(client: TestClient) -> None:
    first = post(client, "key-1")
    second = post(client, "key-1")

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert count(client, Payment) == 1


def test_same_key_different_body_is_rejected(client: TestClient) -> None:
    post(client, "key-1")
    response = post(client, "key-1", {**BODY, "amount_cents": 9999})

    assert response.status_code == 422
    assert count(client, Payment) == 1


def test_same_key_in_progress_returns_409(client: TestClient) -> None:
    with client.app.state.sessions() as db:
        request_hash = hash_request(BookingRequest(**BODY))
        db.add(IdempotencyRecord(key="key-1", request_hash=request_hash, status=IN_PROGRESS))
        db.commit()

    response = post(client, "key-1")

    assert response.status_code == 409
    assert count(client, Payment) == 0


def test_parallel_requests_for_same_seat_give_one_booking(client: TestClient) -> None:
    keys = [f"key-{i}" for i in range(10)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(lambda k: post(client, k), keys))

    codes = sorted(r.status_code for r in responses)
    assert codes == [201] + [409] * 9
    assert count(client, Booking) == 1
    assert count(client, Payment) == 1
