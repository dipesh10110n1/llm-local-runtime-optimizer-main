# API

Run `python main.py`, then use `http://127.0.0.1:8000/docs`.

* `GET /health` reports local backend reachability.
* `GET /api/v1/models` returns registry records.
* `POST /api/v1/optimize` accepts `prompt`, task/quality/latency/RAM/energy constraints, and preference.
* `POST /api/v1/generate` optimizes then runs only a reachable selected backend.
* `GET /api/v1/experiments` returns the read-only legacy aggregate profile.
* `GET /api/v1/recommendations` documents the recommendation entrypoint.

The API returns `measured` or `estimated` evidence labels. It stays loopback-only by default.
