# How it works

## The problem: double bookings and double payments

A user taps "Pay". The network is slow. Nothing happens on screen, so they tap again.
Or the app sends the request, the server charges the card, but the reply gets lost.
The app thinks it failed and tries again.

Now the server got the same request two times. If it does the work two times, the user pays twice.

A second problem: two different users try to book the same seat at the same moment.
Both servers check "is seat A1 free?". Both see "yes". Both book it. Now one seat has two owners.

We need two guards:

1. **Idempotency key** stops the same request from running twice.
2. **Database rules** stop two different requests from taking the same seat.

## Guard 1: the idempotency key

"Idempotent" means: doing it once or ten times has the same result.

The client makes a random key (like a UUID) for each new purchase.
It sends that key in the `Idempotency-Key` header.
If it has to retry, it sends the **same** key again.

The server keeps a table `idempotency_records`. For each key we store:

- the key (this is the primary key, so it is unique)
- a hash of the request body
- the status: `in_progress` or `done`
- the saved response (status code + body)

When a request comes in:

1. Try to insert the key with status `in_progress`.
2. If the insert works, this request owns the key. Do the booking and payment.
   In the **same transaction**, save the response and set status to `done`.
3. If the insert fails because the key already exists, look at the saved row:
   - Body hash is different: return **422**. The client reused a key for a different purchase. That is a bug on their side.
   - Status is `in_progress`: return **409**. The first request is still running. Try again soon.
   - Status is `done`: return the saved response. Do not charge again.

If the work crashes in a way we did not expect, we delete the key so the client can retry.

Why insert first and not "check, then insert"?
Because "check, then insert" has a gap. Two requests can both check, both see nothing, and both go on.
An insert with a unique key has no gap. The database lets only one of them in.

## Guard 2: the database rules

The `bookings` table has a UNIQUE rule on `(show_id, seat)`.
The `payments` table has a UNIQUE rule on `booking_id`.

So even if two different keys try to book seat A1 for show 1 at the same time,
the database will only accept one row. The other one gets an error, and we return **409 Seat already booked**.

The booking, the payment, and the "mark key as done" step all happen in **one transaction**.
Either all of it is saved, or none of it is. You never get a payment with no booking, or a booking with no saved response.

We do not read "is the seat free?" in Python first. We just try to insert and let the database say no.
The database is the one place that sees every request, so it is the right place for the final check.

## Walk-through

Riya wants seat A1 for show 1. Her app makes the key `abc-123`.

| Step | What happens | Result |
| --- | --- | --- |
| 1 | Riya taps Pay. Request with key `abc-123` arrives. | Key saved as `in_progress`. |
| 2 | Server inserts booking (show 1, A1) and payment (1500). Saves response. Commits. | Key is `done`. Riya gets **201**. |
| 3 | The reply was lost. Her app retries with key `abc-123` and the same body. | Insert of key fails. Row is `done`. Server returns the saved **201**. No new payment. |
| 4 | A bug in the app sends key `abc-123` with amount 9999. | Hash does not match. Server returns **422**. |
| 5 | At the same time, Aman tries seat A1 with his own key `xyz-789`. | His key is new, so he gets to try. The booking insert breaks the `(show_id, seat)` rule. He gets **409 Seat already booked**. |

End result: one booking, one payment, and every retry gets the same answer.
