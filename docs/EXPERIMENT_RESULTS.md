# Existing experiment results

Historical raw CSV files under `logs/` are preserved. `benchmark_results_v2.csv` has five repeated trials of Qwen2.5 1.5B Q4_K_M at four threads and context 2048; the recorded RAM range is about 1310 MiB. `streaming_results_v2.csv` has cache-disabled and cache-enabled trials; its warm cached TTFT observations are lower than uncached values. `combined_quality_scores.csv` contains five 100% general/human-style scores, which must not be interpreted as MMLU/GSM8K/MBPP/IFEval/CNN benchmark accuracy.

No energy, MySQL-persisted, or matched task-level benchmark result has been created by this implementation.
