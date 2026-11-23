from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

IN_PROGRESS = "in_progress"
DONE = "done"


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    response_code: Mapped[int | None]
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("show_id", "seat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int]
    seat: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int]


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    amount_cents: Mapped[int]
