# Double payment example

A small FastAPI app that shows how to stop double bookings and double payments.

## What we built

One endpoint: `POST /bookings`. It books a seat for a show and records a payment.

- The client must send an `Idempotency-Key` header.
- Same key + same body again: you get the first response back. No second payment.
- Same key + different body: **422**.
- Same key while the first request is still running: **409**.
- Seat already taken by someone else: **409 Seat already booked**.

Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for the full story with an example.

## Why this approach

Retries are normal. Phones lose signal, users tap twice, and load balancers retry.
So the server has to be safe when the same request comes in more than once.

We use two guards together:

1. **Idempotency key.** The client gives each purchase a key. The server saves the key and the response. A retry gets the saved response instead of running again. Payment companies like Stripe use this same idea.
2. **Database UNIQUE rules.** One seat per show, and one payment per booking. The work and the saved response go in one transaction. So even two requests that arrive at the exact same moment cannot both win.

The key alone is not enough, because two different users have two different keys.
The database rule alone is not enough, because a retry should get its first answer back, not an error.
Together they cover both cases.

We used SQLite to keep it simple. The same idea works the same way on Postgres or MySQL.

## Project layout

```
app/
  main.py         # FastAPI app and the /bookings route
  idempotency.py  # claim a key, save a response, release a key
  bookings.py     # book the seat + take the payment in one transaction
  models.py       # database tables and their UNIQUE rules
  schemas.py      # request and response models
  db.py           # database setup
tests/
  test_bookings.py
```

## How to run

You need Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs, or try it with curl:

```bash
curl -i -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: abc-123" \
  -d '{"show_id": 1, "seat": "A1", "user_id": 7, "amount_cents": 1500}'
```

Run the same command again. You get the same answer and an `Idempotent-Replayed: true` header.

## How to test

```bash
pytest
```

The tests check that:

- the same key twice gives one payment
- the same key with a different body is rejected
- the same key while still in progress gets 409
- ten parallel requests for the same seat give only one booking
