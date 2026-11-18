# API documentation

Run only on loopback by default: `uvicorn api.app:app --host 127.0.0.1 --port 8000`.

- `GET /health` reports backend reachability.
- `GET /api/v1/models` returns registry entries and local availability.
- `POST /api/v1/optimize` accepts `task_type`, optional constraints, and `preference` (`quality`, `latency`, `memory`, `energy`, `balanced`).
- `POST /api/v1/generate` adds `prompt`, optional `model_id`, and `max_output_tokens`; it returns the selected configuration and clearly labelled measured inference telemetry.
- `GET /api/v1/experiments` exposes imported historical profile rows.
- `GET /api/v1/recommendations` returns a default optimization result.

The API returns HTTP 503 when inference is unavailable; it never produces a synthetic answer as a fallback.
