from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.idempotency import save_response
from app.models import Booking, Payment
from app.schemas import BookingRequest, BookingResponse


def book_and_pay(
    sessions: sessionmaker[Session], key: str, req: BookingRequest
) -> JSONResponse:
    """Create booking + payment and save the response in one transaction."""
    with sessions() as db:
        try:
            booking = Booking(show_id=req.show_id, seat=req.seat, user_id=req.user_id)
            db.add(booking)
            db.flush()
            payment = Payment(booking_id=booking.id, amount_cents=req.amount_cents)
            db.add(payment)
            db.flush()
            status_code = 201
            body = BookingResponse(
                booking_id=booking.id,
                payment_id=payment.id,
                show_id=req.show_id,
                seat=req.seat,
                amount_cents=req.amount_cents,
            ).model_dump()
        except IntegrityError:
            db.rollback()
            status_code = 409
            body = {"detail": "Seat already booked"}

        save_response(db, key, status_code, body)
        db.commit()
    return JSONResponse(body, status_code=status_code)
