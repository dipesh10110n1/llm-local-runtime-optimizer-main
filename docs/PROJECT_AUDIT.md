# Project audit — 2026-11-17

## Baseline and preservation

The Git baseline is commit `9aadcc3` (`initialized`). The working tree already contained user changes/untracked benchmark scripts, datasets, virtual-environment packages, and raw CSVs; none were removed or overwritten. Existing result files remain append-only. No Git commit was created because the project instructions prohibit commits without explicit permission.

## Existing architecture

The starting project was a script-based llama.cpp benchmark prototype. `benchmark.py` and `benchmark_v2.py` invoke `llama-cli`; streaming/quality/cache scripts use a loopback llama.cpp server and append CSV data. `hardware/hardware_profiler.py` uses psutil and PowerShell. `main.py` was empty.

## Working components and evidence

* The GGUF model file exists at `models/qwen2.5-1.5b-instruct-q4_k_m.gguf`.
* `llama-server.exe` and `ollama.exe` are discoverable. `ollama list` returned installed Qwen variants, including 0.5B, 1.5B, 3B, 7B, and qwen2.5-coder.
* CSV data includes 3 original benchmarks, 5 repeated benchmarks, 5 uncached and 5 cache trials, 31 combined response records, and 5 combined human-style quality scores.
* The legacy data shows roughly 1.31 GiB peak process RAM for the 1.5B Q4 GGUF, and cache warm-up reduces recorded TTFT. These are historic observations, not guarantees.

## Incomplete baseline / technical debt

There was no dependency manifest, database, model registry, standard dataset pipeline, unified telemetry, API, dashboard, tests, migration system, or optimizer. The original scripts embed configuration constants, use incompatible CSV schemas, and their quality scores are manual/general rubrics rather than task-specific benchmark metrics. Energy was not measured. Some original records lack experiment IDs, while cache/quality records cannot be joined at individual prompt/trial level.

## Runtime checks

At audit time no llama.cpp server answered on `127.0.0.1:9931`. MySQL80 is installed but stopped, and credentials were not established; MySQL setup is therefore unverified. The virtual environment initially contained only psutil and requests. The machine has a 10-core/12-thread Intel i5-1334U, 15.69 GiB RAM (3.24 GiB available at profiling), and Intel Iris Xe integrated graphics according to the supplied hardware context. Integrated graphics must not be treated as dedicated VRAM. A later local-only smoke test against already-installed `qwen2.5:0.5b` through Ollama succeeded (5 generated tokens); it did not create a benchmark record.

## Recommended sequence

1. Install Python requirements; configure MySQL credentials.
2. Initialize database schema and verify connection.
3. Review dataset licenses, then opt in to fifty-sample dataset preparation.
4. Start one local backend only, run repeatable benchmarks for at least two configurations, and persist matched task-level results.
5. Use the optimizer/API/dashboard only with those measured profiles. Add an external meter before energy-constrained recommendations.
