# Architecture

`datasets` prepares official sources into a common JSONL contract. `benchmarks` sends normalized samples to a modular local backend, evaluates them by task type, and emits a `TelemetryRecord`. `database` persists the record in MySQL. `optimizer` consumes measured candidate profiles, filters hard constraints, computes a Pareto frontier, and produces an explainable selection. `api` exposes the pipeline on loopback, while `dashboard.py` displays recorded data.

The original script files and CSVs remain independent historical artifacts. `optimizer/profile_loader.py` reads their data without changing it and labels aggregation limitations.
