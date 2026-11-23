import hashlib
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import DONE, IN_PROGRESS, IdempotencyRecord


def hash_request(body: BaseModel) -> str:
    return hashlib.sha256(body.model_dump_json().encode()).hexdigest()


def claim_key(
    sessions: sessionmaker[Session], key: str, request_hash: str
) -> JSONResponse | None:
    """Save the key as in progress.

    Returns None if this request now owns the key.
    Returns the saved response if the key was already used for the same body.
    """
    with sessions() as db:
        db.add(IdempotencyRecord(key=key, request_hash=request_hash, status=IN_PROGRESS))
        try:
            db.commit()
            return None
        except IntegrityError:
            db.rollback()
        record = db.get(IdempotencyRecord, key)

    if record is not None and record.request_hash != request_hash:
        raise HTTPException(422, "Idempotency-Key was already used with a different body")
    if record is None or record.status == IN_PROGRESS:
        raise HTTPException(409, "A request with this Idempotency-Key is still in progress")
    return JSONResponse(
        record.response_body,
        status_code=record.response_code or 200,
        headers={"Idempotent-Replayed": "true"},
    )


def save_response(db: Session, key: str, status_code: int, body: dict[str, Any]) -> None:
    """Mark the key as done. The caller commits, so this joins its transaction."""
    db.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.key == key)
        .values(status=DONE, response_code=status_code, response_body=body)
    )


def release_key(sessions: sessionmaker[Session], key: str) -> None:
    """Drop the key after an unexpected error so the client can retry."""
    with sessions() as db:
        db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.key == key))
        db.commit()
