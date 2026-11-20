# Implementation status

Completed locally: Spider structural verification and read-only execution evaluation; a controlled Q4/Q5/Q6 comparison of the same Qwen 1.5B base model; cache, compression, retrieval, and limited general-retrieval studies; dynamic GGUF discovery; and a RAM-safe full configuration-matrix runner. Results are written to separate timestamped JSONL and summary files under `logs/`.

The Qwen 1.5B Q4_K_M, Q5_K_M, and Q6_K artifacts are locally validated and the controlled quantization comparison is available under `logs/quantization_comparisons/`. `python -m benchmarks.quantization_comparison --preflight` reports local artifact validity, disk capacity, and whether `llama-quantize` is installed; it never downloads or converts a model.

MySQL is optional and used only when `DATABASE_URL` is configured. Completed live selections, benchmark trials, and hardware snapshots are mirrored after their JSONL evidence is written; a missing or failed database never blocks a response or JSONL logging. Actual energy remains unavailable until a physical meter/counter adapter provides cumulative joules; CPU utilisation is recorded only as an estimated proxy. Full-matrix records currently contain RAM safety skips and no completed calibrated profiles, so the central optimization claim is not yet empirically demonstrated. No raw log or dataset was overwritten.
