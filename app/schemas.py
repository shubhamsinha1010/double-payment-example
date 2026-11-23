from pydantic import BaseModel, Field


class BookingRequest(BaseModel):
    show_id: int
    seat: str = Field(min_length=1, max_length=10)
    user_id: int
    amount_cents: int = Field(gt=0)


class BookingResponse(BaseModel):
    booking_id: int
    payment_id: int
    show_id: int
    seat: str
    amount_cents: int
