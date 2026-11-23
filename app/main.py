from typing import Annotated

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app.bookings import book_and_pay
from app.db import make_session_factory
from app.idempotency import claim_key, hash_request, release_key
from app.schemas import BookingRequest, BookingResponse


def create_app(database_url: str = "sqlite:///./bookings.db") -> FastAPI:
    app = FastAPI(title="Double payment example")
    app.state.sessions = make_session_factory(database_url)

    @app.post("/bookings", status_code=201, response_model=BookingResponse)
    def create_booking(
        req: BookingRequest,
        request: Request,
        idempotency_key: Annotated[str, Header(min_length=1, max_length=255)],
    ) -> JSONResponse:
        sessions = request.app.state.sessions
        saved = claim_key(sessions, idempotency_key, hash_request(req))
        if saved is not None:
            return saved
        try:
            return book_and_pay(sessions, idempotency_key, req)
        except Exception:
            release_key(sessions, idempotency_key)
            raise

    return app


app = create_app()
