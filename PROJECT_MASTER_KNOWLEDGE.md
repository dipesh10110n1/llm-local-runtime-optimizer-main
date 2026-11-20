# Orbit: master technical knowledge guide

> Prepared from the repository as inspected on 20 November 2026. Status labels describe evidence, not ambition: **Implemented and verified**, **Implemented but unverified**, **Partially implemented**, **Estimated**, **Planned**, **Missing**, and **Unavailable**.

## 1. Project introduction

### In plain language

Orbit is a local-first assistant that tries to answer a prompt using a local Qwen model while choosing a configuration that is safe for the laptop and supported by benchmark evidence. Instead of assuming that the largest model is always best, it records quality, delay, RAM use, and—only when a real meter exists—energy. It then explains its recommendation.

The intended user is someone running models privately on a laptop or workstation. They provide a prompt and may provide a quality threshold, latency/RAM/energy limits, or an explicit model override. The expected output is a generated answer plus the selected model/configuration, telemetry, evidence/provenance, and rejection reasons.

### Technical definition

The project combines a Streamlit UI (`dashboard.py`), FastAPI service (`api/app.py`), local llama.cpp/Ollama clients (`runtime/`), benchmark harnesses (`benchmarks/`), a constraint-based optimizer (`optimizer/`), JSONL evidence, and an optional MySQL mirror (`database/`). Its strongest quality evidence is Spider text-to-SQL execution equivalence; it must not be generalized to ordinary chat, coding, or reasoning.

### End-to-end workflow

1. Discover valid local GGUF files with `core.model_registry.load_models()`.
2. Read historical/calibrated benchmark profiles and apply requested constraints.
3. If using historical recommendation, resolve the exact measured runtime configuration; if using live comparison, build safe candidates and run them sequentially.
4. Estimate required RAM, retain a reserve, and start/switch only Orbit-managed `llama-server` processes.
5. Optionally compress the prompt and add local lexical retrieval context.
6. Generate locally, collecting TTFT, elapsed time, throughput, process RSS, CPU-utilisation proxy, and any valid physical energy delta.
7. For supported benchmark tasks, score quality; persist provenance and telemetry; return explanation and alternatives.

**Review statement:** “Orbit is an evidence-first local configuration selector. Its demonstrated quality claim is currently Spider text-to-SQL, not general LLM quality.”

## 2. Architecture

```text
User
  | prompt + optional constraints
  v
Streamlit dashboard (dashboard.py) ---- FastAPI (/api/v1/*)
  |                                        |
  | live comparison                         +--> Optimizer
  v                                        |     historical_profiles + calibrated profiles
live_comparator ---------------------------+     hard constraints + Pareto + objective
  |                                               |
  +--> RAM admission (live_matrix/request_router) |
  +--> runtime.supervisor.ensure_runtime <---------+
  |       owns one loopback llama-server
  +--> prompt_pipeline: compression + lexical RAG
  +--> runtime.clients.generate
              |
              v
     llama.cpp at 127.0.0.1:9931 / optional Ollama
              |
              +--> Spider/task evaluator (benchmark paths)
              +--> JSONL primary evidence --> optional MySQL mirror
              +--> dashboard/API explanation, tables, Pareto views
```

| Component | Responsibility | Inputs / outputs | Dependencies | Status |
|---|---|---|---|---|
| `dashboard.py` | Chat UI, constraints, comparison tables, trade-off charts | Prompt -> answer/telemetry | Streamlit, optimizer/runtime modules | Implemented but live-unverified |
| `api/app.py` | Validated REST entrypoints | Pydantic body -> recommendation/generation JSON | FastAPI, optimizer, runtime | Implemented and unit-tested |
| `core/model_registry.py` | Discover valid-header GGUF files and registry entries | `models/` -> model dicts | filesystem | Implemented and verified by inventory |
| `runtime/supervisor.py` | Own/start/stop one Orbit llama.cpp server | model + config -> active state | psutil, `llama-server` | Implemented but current runtime unavailable |
| `runtime/clients.py` | Streaming llama.cpp/Ollama calls and resource sampling | prompt -> answer + telemetry | requests, psutil | Implemented; live llama.cpp unavailable in last check |
| `optimizer/` | Candidate feasibility, profile selection, explanations | profiles + constraints -> selection | benchmark evidence | Partially verified |
| `benchmarks/` | Produce controlled task/performance evidence | datasets/models -> timestamped JSONL/summary | llama.cpp, Spider/data | Implemented; coverage incomplete |
| `database/` | JSONL verification and optional MySQL mirror | records -> durable telemetry | SQLAlchemy/MySQL | Implemented and schema verified |

## 3. Folder and file guide

The table covers the important executable modules. Small `__init__.py` files exist to make packages importable.

| Path/group | Purpose and important functions | Called by / calls | Status |
|---|---|---|---|
| `core/settings.py` | Loads `.env`; defines root, URLs, timeout, RAM reserve, privacy flag | Almost all runtime/database modules | Implemented |
| `core/model_registry.py` | `load_models`, `get_model`, valid GGUF header discovery | API/dashboard/benchmarks; calls `config/models.json` and filesystem | Implemented |
| `core/provenance.py`, `ids.py`, `telemetry.py` | SHA-256, hardware/runtime metadata, unique IDs, shared telemetry helpers | benchmark runners | Implemented |
| `config/models.json`, `benchmark_matrix.json` | Static known models and thread/context/cache/compression/RAG matrix | registry/config catalog | Implemented |
| `optimizer/configuration_catalog.py` | `baseline_configuration`, full Cartesian benchmark configurations, cache flags | live comparator, runner, API | Implemented |
| `optimizer/live_matrix.py` | RAM estimation, safe candidate expansion, stratified sampling | API/readiness/full matrix | Implemented; estimate is conservative, not measured |
| `optimizer/request_router.py` | Task keyword classification, RAM-safe routing, private selection history | live comparator/dashboard | Partially implemented: parameter-count fallback is not quality evidence |
| `optimizer/optimizer.py`, `constraint_manager.py` | `OptimizationRequest`, hard constraint checks, `Optimizer.recommend` | API | Implemented and unit-tested |
| `optimizer/calibrated_profiles.py` | Aggregate repeated JSONL by configuration and experiment; lower confidence bound; deterministic selection | API/evidence report | Implemented; profile coverage is still partial |
| `optimizer/weighted_selection.py`, `scoring_engine.py` | Live normalized comparison / legacy preference score | live comparator/optimizer | Partially implemented; live score is not a substitute for benchmark profiles |
| `optimizer/pareto_optimizer.py`, `recommendation_engine.py`, `evidence_report.py` | Pareto, explanatory text, dashboard-ready evidence/readiness views | API/dashboard | Implemented |
| `optimizer/profile_store.py`, `profile_loader.py`, `calibration_profiles.py` | Legacy CSV and calibrated-profile compatibility paths | API/older flows | Partially implemented; legacy data lacks modern provenance |
| `runtime/supervisor.py` | `ensure_runtime`, safe managed process stop/adoption | API/live benchmarks | Implemented but requires llama.cpp executable |
| `runtime/clients.py` | `generate`, `tokenize`, health checks, RSS/CPU proxy sampling | API/benchmarks | Implemented; energy proxy is explicitly estimated |
| `runtime/prompt_pipeline.py` | `compress_prompt`, lexical `retrieve`, `prepare_prompt` | API/live comparator/benchmarks | Implemented; lexical RAG only |
| `inference/backends.py`, `runtime_optimizer/types.py` | Older Ollama abstraction and typed legacy profiles | opt-in live Ollama test/compatibility paths | Implemented but secondary |
| `hardware/hardware_profiler.py`, `monitoring.py` | CPU/RAM/GPU/storage/backend snapshots, resource samples | provenance/readiness | Implemented |
| `hardware/energy_capability.py` | Validates physical meter export and calculates monotonic joule deltas | runtime client/evidence report | Implemented and tested |
| `hardware/simulated_meter.py`, `meter_export.json` | Explicit demonstration proxy; now rejected as physical energy | manual demo only | Estimated, not measurement |
| `benchmarks/full_matrix_benchmark.py` | Sequential Spider matrix, warm-up, checkpoints, provenance | campaign/manual CLI | Implemented; not all candidates completed |
| `quantization_comparison.py`, `three_model_comparison.py` | Same-base Q4/Q5/Q6 and 0.5/1.5/3B studies | manual CLI | Implemented with logged evidence |
| `context_thread_calibration.py`, `cache_prompt_experiments.py`, `prompt_compression_experiment.py` | Controlled context/thread/cache/compression studies | manual CLI | Implemented; evidence varies by study |
| `local_retrieval_benchmark.py`, `general_retrieval_evaluation.py` | Spider-schema and local-document RAG comparisons | manual CLI | Partially implemented |
| `spider_calibration.py`, `spider_verifier.py`, `task_quality.py` | Spider prompt/schema build, dataset layout verification, safe exact/execution scoring | most Spider runners | Implemented and unit-tested |
| `standard_quality_benchmark.py`, `quality_metrics/metrics.py` | GSM8K/MMLU/MBPP/IFEval/CNN-style runner and metrics | campaign/manual CLI | Implemented but no standard run logs; IFEval official checker unavailable |
| `prepare_datasets.py`, `prepare_mmlu_csv.py`, `prepare_ifeval_official.py`, loaders/validators | Normalize reviewed local datasets with manifests | standard quality runner | Implemented |
| legacy `benchmark*.py`, `evaluation_runner.py`, `quality_evaluator.py`, CSV scoring scripts | Earlier direct benchmark/CSV workflow | historical evidence only | Implemented but legacy/less complete |
| `database/schema.py`, `repository.py` | SQLAlchemy ORM, transactional mirror, schema evolution | telemetry/API/benchmarks | Implemented and MySQL verified |
| `database/telemetry.py`, `verify_telemetry.py`, `initialize.py` | JSONL integrity report, MySQL read-only verification, schema initialization | API/CLI | Implemented |
| `database/migrations/001_initial_schema.sql` | Clean-install MySQL schema | operator | Implemented; clean MySQL SQL run itself remains unverified |
| `tests/` | 102 unit tests plus one opt-in live test | pytest | Implemented and verified: 102 pass, 1 skipped |
| `logs/` | Immutable-style raw JSONL, summaries, legacy CSV, profiles | dashboard/API/review | Evidence, not source code |

## 4. Actual end-to-end execution trace

### Dashboard live comparison

1. `dashboard.py` accepts `st.chat_input`.
2. It calls `optimizer.live_comparator.compare_on_spot(prompt, models, ...)`.
3. `request_router.recommend_runtime()` classifies the task and calculates available RAM as OS available memory plus safely reclaimable Orbit server RSS.
4. `live_matrix.full_live_candidates()` can expand thread/context/cache/compression/retrieval variants; unsafe candidates are rejected with a reason.
5. For each candidate, `runtime.supervisor.ensure_runtime()` verifies/restarts only an Orbit-owned loopback `llama-server`.
6. `runtime.prompt_pipeline.prepare_prompt()` applies selected compression and optional retrieval.
7. `runtime.clients.generate()` sends OpenAI-compatible streaming chat-completions to llama.cpp, observes first content for TTFT, samples RSS/CPU, and reads a validated physical meter at start/end if available.
8. `optimizer.task_quality.evaluate_spider_sql()` scores only when a gold SQL reference was supplied; otherwise quality is unavailable.
9. `weighted_selection.score_candidates()` compares available direct metrics for a live response. With a threshold, quality is a gate rather than a reward.
10. The dashboard displays the exact winning draft rather than generating it again, then calls `request_router.record_selection()` with response text redacted by default.

### Historical API generation

`POST /api/v1/generate` calls `Optimizer.recommend(historical_profiles(), request)`. `api.app._profile_configuration()` resolves the measured profile configuration, `configuration_is_safe()` rechecks current RAM, `ensure_runtime()` starts that configuration, and `prepare_prompt()`/`generate()` execute it. This corrected flow matters: a recommendation must correspond to the model settings actually used.

### Failure behaviour

- No safe model: return a reason; do not force a load.
- Missing quality reference for a live threshold: reject the thresholded comparison.
- Missing physical energy with an energy cap: constraint fails rather than silently passing.
- Runtime failure: record/return an unavailable failure; do not select it.
- Missing dataset/evaluator: score is unavailable, not zero-quality evidence.

**Review statement:** “The system separates selecting a configuration from simply generating text. It rechecks RAM at execution time because laptop memory can change after a benchmark.”

## 5. Technology choices

| Technology | What and use here | Why / alternatives | Advantages and limitations |
|---|---|---|---|
| Python | Orchestration language for all modules | Alternatives: Java/Go; Python suits ML tooling and readable experiments | Fast development; GIL is not a bottleneck because inference is external process/network I/O |
| Streamlit | Local dashboard/chat UI | Alternatives: React, Flask templates | Rapid local UI; script reruns require disciplined state handling |
| FastAPI + Pydantic | Local typed API | Alternatives: Flask | Automatic validation/docs; API is local only by deployment convention |
| Qwen2.5 Instruct | Local models: 0.5B, 1.5B, 3B and 1.5B quant variants | Other open models: Llama, Mistral, Phi | Same-family variants make comparisons more meaningful; only tested task evidence supports claims |
| GGUF | mmap-friendly llama.cpp model format | Safetensors/Transformers/GPTQ/AWQ | Practical CPU inference and quantization distribution; header validation is not full architecture validation |
| llama.cpp | Primary local inference server | Ollama, vLLM, Transformers | CPU-friendly, exposes timings/tokenize/cache flags; executable was unavailable during last live verification |
| Ollama | Optional backend/client and opt-in test | llama.cpp only | Easier model management; not the main controlled benchmark path |
| psutil | RAM, CPU, process telemetry | OS-specific tools | Cross-platform practical data; CPU percent is not joules |
| SQLite | Spider evaluation databases, test DBs | MySQL/PostgreSQL | Read-only local query evaluation; not telemetry primary store |
| JSONL | Authoritative experiment evidence | MySQL-only/CSV | Append-friendly, portable raw record trail; requires validation and careful schemas |
| MySQL + SQLAlchemy | Optional searchable telemetry mirror | SQLite-only, Postgres | Relational history and schema; not required to answer locally |

## 6. LLM fundamentals in Orbit

| Concept | Simple meaning | Relation to code |
|---|---|---|
| LLM / parameters | A neural text predictor; more parameters usually means more capacity and more memory | Registry records 0.5B/1.5B/3B. Parameter count is never treated as measured quality. |
| Token | Model text unit, not necessarily a word | `runtime.clients.tokenize()` asks llama.cpp; absence is retained as `None`, not guessed. |
| Context window | Maximum prompt/history tokens considered | Matrix tests 1024/2048/4096; models advertise 32768 limit. Longer context costs KV memory. |
| Inference | Producing tokens one after another | `generate()` streams `/v1/chat/completions`. |
| CPU/GPU inference | Compute location | Current configurations use `gpu_layers: 0`; GPU info is informative only. |
| GGUF | Binary model format tailored to llama.cpp | Valid header discovery in `model_registry.py`; model file hashes in provenance. |
| Quantization | Store weights with fewer bits | Q4/Q5/Q6 trade accuracy/memory/speed; experiments compare same 1.5B base where possible. |
| Q4_K_M/Q5_K_M/Q6_K | Increasing precision/size quantizations | Q4 usually smallest; the repository’s logged study must be cited rather than generalized. |
| KV cache | Stored attention keys/values for prior tokens | Consumes RAM; llama.cpp manages it. The app does not claim to implement custom KV-cache storage. |
| Prompt cache | Reuse prompt processing inside server | Cache study uses `--cache-prompt` / `--no-cache-prompt`; it is not response caching. |
| TTFT | Time until first generated token | Measured when first streaming content arrives. It captures responsiveness, unlike total time. |
| Tokens/s | Generation rate after/sometimes reported by server | Collected from timings or calculated only when required values exist. |
| Peak RAM | Highest observed inference-process RSS | 50 ms monitor sampling; useful but not total machine energy/memory. |
| Temperature | Randomness control | Benchmark runners use 0 for repeatability; dashboard exposes a user control. |
| Cold/warm | First request/start versus repeated request | Cache runner force-restarts for cold runs and immediately repeats identical prompt for warm runs. |

## 7. Optimization methodology

### Candidate construction and RAM safety

`configuration_catalog.benchmark_configurations()` forms the Cartesian matrix from `config/benchmark_matrix.json`: threads 2/4/6/8 × context 1024/2048/4096 × cache modes × three compression modes × retrieval on/off. `live_matrix.required_memory_mb()` uses:

```text
required_MiB = 1.3 × GGUF_file_size_MiB + 300 + 0.15 × context_size
safe when required_MiB + RAM_reserve_MiB <= available_MiB
```

This is an **estimated admission rule**, not a measured memory claim. Measured peak RSS is later stored in benchmark telemetry. `safe_available_memory_mb()` may add RSS from a registered Orbit server because it is deliberately stopped before switching models; it does not assume unrelated processes are reclaimable.

### Quality gates and selection

`constraint_manager.violations()` treats requested quality, latency, RAM, and energy limits as hard constraints. For repeated profiles it uses `quality_lower_confidence_bound` rather than the mean. Missing required values fail the constraint.

`calibrated_profiles.select_lowest_cost()` first retains profiles that meet the quality gate and have at least three recorded trial identifiers. It then uses an explicit lexicographic objective:

- balanced/latency: minimize measured latency, then RAM, then maximize throughput;
- memory: minimize RAM, then latency;
- quality: maximize quality, then minimize latency/RAM;
- energy: requires actual comparable joules; proxies cannot rank.

`pareto_optimizer.pareto_frontier()` separately reports non-dominated quality/latency/RAM profiles. This is not a proof that every possible configuration was tested.

### Energy rule

Actual joules are valid only if `energy_capability.read_meter_export()` accepts a physical/hardware-counter cumulative source and `joule_delta()` sees a non-decreasing same-source pair. CPU utilisation produces `energy_proxy_joules` and is displayed as an estimate only.

### What is incomplete

The optimizer operates on recorded profiles, but available profiles cover a limited, non-complete configuration subset. General quality profiles are absent. Therefore it can honestly recommend the lowest-cost feasible configuration **among its qualifying evidence**, not prove a global optimum for all local models or all tasks.

## 8. Benchmarking and evaluation

### Recorded experiments

| Study | Evidence | Legitimate conclusion / limitation |
|---|---|---|
| Quantization | Latest Q4/Q5/Q6 summary has 15 requests per variant, five Spider development examples, three trials | Controlled same-base comparison exists; five inputs are not general model accuracy. |
| Three model | 0.5B/1.5B/3B Q4 Spider comparison | Shows observed size/quality/latency/RAM trade-offs, with recorded failures; not a full matrix. |
| Full matrix | Partial runs, including one six-configuration 1.5B run with 25 samples × 3 trials; many deferred/skipped | Some repeated configuration evidence; not all 144 configurations/model completed. |
| Context/thread | Scripts and logs include 1024/2048/4096, 2/4/6/8 attempts | RAM safety skips prevent broad conclusions. |
| Cache/compression/RAG | Controlled scripts and timestamped JSONL/summaries | Features are measured locally; cache/lexical-retrieval findings are workload-specific. |
| General quality | Prepared GSM8K 50, MMLU 25, IFEval 25 datasets | No `standard_quality_benchmarks` result files were found; no general threshold claim. |

### Spider evaluation

`spider_calibration.prompt_for()` builds “write one SQLite SELECT” prompts from the question and local database schema. `task_quality.evaluate_spider_sql()` first normalizes/extracts SQL. With the matching local SQLite DB, it executes read-only `SELECT`, `WITH`, or `EXPLAIN` SQL through a read-only URI, compares unordered results as multisets unless the reference requires `ORDER BY`, and returns a binary execution-match score. Invalid/non-read-only SQL scores zero. This is stronger than text matching but still only evaluates Spider-style text-to-SQL.

### Metrics

- **TTFT:** client wall time to first streaming content.
- **End-to-end latency:** request start to stream completion.
- **Generation tokens/s:** server timing when available or defensible derivation.
- **Peak RAM:** sampled `llama-server` RSS.
- **Quality:** task-specific score; unavailable is not passable.
- **Energy:** physical joules when valid; CPU proxy otherwise.

Raw trials are timestamped JSONL under `logs/`; summaries are derived. `core.provenance.benchmark_provenance()` includes model SHA-256, configuration, hardware snapshot, and llama.cpp version when discoverable.

## 9. Quantization, context, caching, and compression

### Quantization

Quantization reduces weight precision, shrinking disk/RAM and often improving memory-bandwidth-limited CPU inference. It can lower quality, but not monotonically for every prompt. `benchmarks/quantization_comparison.py` checks the Qwen 1.5B Q4/Q5/Q6 artifacts and runs a controlled Spider study. File size alone is not energy or quality proof.

### Context and threads

More context accommodates longer input but expands KV-cache memory. More threads can improve CPU throughput up to contention/thermal limits. `context_thread_calibration.py` tests these dimensions sequentially, but safety skips and incomplete runs limit recommendation confidence.

### Prompt compression

`compress_prompt()` supports `none`, `whitespace`, and `conservative`. Whitespace collapses line spacing; conservative mode only removes redundant blank lines and preserves code indentation. The original prompt is retained by caller; metadata records character counts. Exact tokenizer counts depend on active llama.cpp `/tokenize`, so character reduction must not be presented as guaranteed token reduction or quality improvement.

### Prompt cache

`cache_server_arguments()` maps experiment settings to llama.cpp `--cache-prompt` and `--no-cache-prompt`. The cache experiment defines cold as first request after a managed restart and warm as immediate identical repeat. This is server prompt/KV reuse, not semantic response caching; it must be tested with identical workloads.

## 10. Retrieval and datasets

`runtime.prompt_pipeline.retrieve()` is a local lexical-overlap retriever. It reads `.txt`/`.md`, splits deterministic paragraph chunks, scores token-set overlap, takes top-k, and prefixes the prompt with source path/chunk labels. It does not generate embeddings, use a vector database, or prove factual grounding. `local_retrieval_benchmark.py` can create Spider-schema corpora without gold SQL; `general_retrieval_evaluation.py` uses local project documents and labelled questions.

### Spider data present

`spider_data/spider_data/` contains `dev.json`, `test.json`, `tables.json`, database directories, and SQLite databases. Text-to-SQL means translating a natural-language question into SQL against a supplied schema. `tables.json` contains schema metadata; `dev.json` has development examples and gold queries; test data should not be used to tune claims. The runner reads schemas from each local database, not from remote services. Safe execution is read-only and uses a progress handler, but it is still evaluation code—not a general SQL sandbox for untrusted arbitrary input.

## 11. Energy and sustainable AI

**Power** is an instantaneous rate in watts. **Energy** is power integrated over time, commonly joules or watt-hours (`1 Wh = 3600 J`). Energy per inference is joules consumed over one request; energy/token divides by generated tokens only when both are valid.

Orbit currently measures elapsed time, CPU utilisation, process RSS, and an estimated CPU-utilisation power/joule proxy. It can measure physical joules only through a valid cumulative physical-meter export read before and after inference. The bundled `hardware/meter_export.json` explicitly identifies a simulated proxy and is rejected from actual-energy use.

Do not say “faster,” “less RAM,” or “lower CPU utilisation” automatically means lower energy. Quality-per-watt is meaningful only with real comparable watt/power measurements; estimated proxy ratios are exploratory and excluded from automated ranking.

## 12. Database and telemetry

### Data flow

Raw JSONL is the authoritative local evidence store. Benchmark runners create experiment IDs via `core.ids.new_experiment_id()`, append/periodically checkpoint JSONL, and may call `database.telemetry.mirror_benchmark_trial()`. Live selections are redacted by `request_router.record_selection()` unless `ORBIT_RETAIN_LIVE_RESPONSE_TEXT=true`.

### MySQL schema

`database/schema.py` declares models, hardware profiles, datasets, runtime configurations, experiments, results, quality results, performance metrics, resource metrics, energy metrics, and recommendations. `EnergyMetric` separates `energy_joules` from `energy_proxy_joules`, includes measurement kind/method, and marks measured values. `ExperimentRepository` writes transactionally; a DB failure does not block local inference. SQLite is used in isolated tests and Spider task databases, not as production telemetry primary.

`database/telemetry.verify_jsonl_store()` now reports malformed JSON/provenance gaps; `database/verify_telemetry.py` checks MySQL tables/energy columns without writes. The configured local MySQL schema was verified after initialization, but a fresh production MySQL deployment of raw SQL still needs its own operator test.

## 13. Responsible AI and governance

| Principle | Concrete implementation | Remaining gap |
|---|---|---|
| Transparency | API/dashboard return alternatives, constraints, metric labels, Pareto/evidence data | Users need to understand limited coverage before trusting a winner |
| Reliability | RAM reserve, managed-process ownership, timeouts, failure recording | No live llama.cpp validation in most recent session |
| Reproducibility | Trial JSONL, config, model hash, runtime/hardware provenance | Matrix and general evaluation coverage are incomplete |
| Privacy | Loopback runtime/API guidance; live response redaction default | Benchmarks/logs can still contain supplied dataset content |
| Human oversight | Model override, visible constraints/rejections, no silent full-matrix run | Override can intentionally depart from recommendation |
| Fairness | Same-base quant study and controlled prompts/trials | Different model sizes/families require controlled common workload |
| Measurement integrity | Proxy/physical energy separation, unavailable quality fails gates | External physical meter absent |
| Sustainability | Measures proxies and supports physical measurement boundary | Cannot claim realized energy reduction yet |

## 14. Important incomplete features and drawbacks

| Gap | Why it matters / risk | Best technical next step | Priority |
|---|---|---|---|
| No current live llama.cpp server/executable evidence | End-to-end generation cannot be claimed from last validation | Install/point to supported `llama-server`, run read-only health then controlled smoke test | Critical |
| Incomplete full matrix | Global “best configuration” claim is unsupported | Declare feasible candidate set; complete same samples/trials for every selectable candidate | Critical |
| General benchmark logs absent | Spider scores do not measure general chat/reasoning | Run reviewed GSM8K/MMLU; use official IFEval checker before instruction-following claims | Critical |
| Physical meter absent | Energy cap/energy-first optimization cannot operate | Integrate a validated wall meter or hardware counter adapter with calibration/idle baseline | High |
| IFEval official checker unavailable | Heuristic instruction tests would be misleading | Vendor/integrate official checker in isolated reproducible environment | High |
| RAG is lexical only | Retrieval relevance/grounding is limited | Add embedding retrieval only if evaluated against a labelled corpus; retain citations | Medium |
| Legacy CSV schemas incomplete | They lack task/config/provenance fields | Preserve but exclude from high-confidence selection; migrate only with labels | Medium |
| SQL migration clean install untested | Deployment uncertainty | Test migration against disposable clean MySQL instance | Medium |
| Energy proxy can still be displayed | Reviewer could misread it | Keep prominent “estimated” label; never call it measured energy | Medium |

Unknown historical reasons should not be invented. A technically plausible explanation (for example, limited laptop RAM causing deferred runs) is not proof of the author’s reason.

## 15. Final assessment

| Dimension | Assessment | Evidence |
|---|---:|---|
| Code implementation | 70/100 | Major modules exist, API path corrected, tests pass; some legacy overlap remains |
| Verified functionality | 55/100 | 102 unit tests pass, MySQL schema verified, recorded experiments exist; current live llama.cpp unavailable |
| Experimental evidence | 50/100 | Quantization/Spider/cache/etc. records exist; incomplete matrix and no general-quality runs |
| Responsible AI readiness | 60/100 | Strong labelling/privacy/RAM safeguards; missing physical energy and task coverage constrain claims |
| End-to-end prototype readiness | 45/100 | Architecture is viable but needs a live runtime smoke test and complete declared benchmark set |

**Defensible closing statement:** “Orbit is an early functional local optimization prototype with credible Spider and performance instrumentation. It selects from measured evidence where available, but it is not yet proven as a complete general-purpose, energy-optimized LLM selector.”
