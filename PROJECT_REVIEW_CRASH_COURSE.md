# Orbit project review crash course

## Explain it in 30 seconds

“Orbit is a local LLM runtime optimizer. It compares local Qwen GGUF configurations using task quality, response latency, RAM use, and physical energy only when a real meter is available. It applies hard constraints first—for example minimum measured quality and safe RAM—then recommends the lowest-cost qualifying configuration and explains why alternatives were rejected. The current strongest evidence is Spider text-to-SQL; I do not claim general-chat quality or physical energy measurement without the relevant completed experiments.”

## Explain it in 2 minutes

“A local LLM has real deployment trade-offs. A larger model can improve quality but consume more RAM and respond more slowly. Quantization can reduce memory but may affect task quality. Orbit turns those trade-offs into a reproducible local decision process.

The user enters a prompt and optional constraints. Orbit discovers local GGUF models, checks whether a configuration fits with a RAM reserve, then either uses recorded benchmark profiles or performs an explicit sequential live comparison. llama.cpp is the primary CPU runtime. The system records TTFT, total latency, output throughput, process RSS, task quality when a valid evaluator exists, and energy taxonomy.

For Spider, it generates SQL from a local database schema and compares execution results against the gold SQL using read-only SQLite. For repeated trials, a conservative quality lower confidence bound can be used as a gate. Only after a candidate passes does Orbit select by a documented measured-cost ordering. JSONL is the raw source of evidence and MySQL is an optional mirror.

The project is a functional early prototype, not a completed universal optimizer. It has good local-first, privacy, RAM-safety, and measurement-labelling design, but it still needs a working llama.cpp verification session, complete predefined benchmark coverage, general task-quality runs, and a real physical meter before stronger claims.”

## Explain it in 5 minutes

Start with the 30-second explanation, then add:

1. **Models and runtime.** The repository contains Qwen2.5 0.5B, 1.5B, and 3B Q4 models, plus 1.5B Q5 and Q6 variants. GGUF is used because llama.cpp can run it efficiently on CPU. `runtime/supervisor.py` owns only Orbit-managed loopback servers, avoiding termination of unrelated processes.
2. **Safety before performance.** Before loading, estimated memory is `1.3 × model file size + 300 MiB + 0.15 × context size`, plus a configurable reserve. It is an admission estimate; runtime RSS is the measured value.
3. **Experiments.** The project has Q4/Q5/Q6 same-base Spider experiments, three model-size experiments, cache/compression/retrieval scripts, and partial full-matrix records. Warm-ups are distinct from measured trials. The data does not yet cover all candidate configurations equally.
4. **Quality.** Spider is integrated because SQL can be objectively scored through execution equivalence against a local database. This supports text-to-SQL only. GSM8K/MMLU/IFEval preparation and runner code exist, but completed standard-quality results are absent; IFEval is intentionally unavailable without its official checker.
5. **Optimization.** Hard constraints remove candidates below quality or over resource caps. For a repeated profile, quality lower confidence bound is safer than its mean. Then selection uses explicit lexicographic ordering, not hidden proxy-energy weights. A Pareto frontier shows non-dominated quality/latency/RAM choices.
6. **Energy honesty.** CPU percent is not electricity consumption. Orbit displays a CPU-utilisation proxy but rejects the bundled simulated meter as physical measurement. Energy-first selection requires valid cumulative physical joule readings before and after inference.
7. **Governance.** Prompts remain local by design; live response text is redacted from selection history by default. The dashboard exposes constraints, alternatives, evidence coverage, and limitations so a human can challenge or override a recommendation.

## Architecture walkthrough

```text
Prompt / constraints
      |
      +--> Dashboard or FastAPI
                 |
                 +--> optimizer profiles + hard constraints
                 |       |
                 |       +--> selected config / alternatives / explanation
                 |
                 +--> RAM admission --> managed llama.cpp runtime
                                        |
                 +--> compression + local lexical retrieval
                                        |
                                        v
                               streamed local generation
                                        |
                    task evaluator + resource/energy telemetry
                                        |
                          JSONL evidence + optional MySQL mirror
                                        |
                      response + metrics + dashboard trade-offs
```

## Ten technical concepts to know

1. **Parameters:** model capacity scale; larger usually costs more compute/RAM.
2. **Tokens:** model-specific text units; not equivalent to words/characters.
3. **GGUF:** llama.cpp-friendly model container/quantization format.
4. **Quantization:** lower-bit weights trade precision for resource use.
5. **Context window:** prompt/history capacity; larger context consumes KV-cache memory.
6. **TTFT:** delay before the first visible token; user-perceived responsiveness.
7. **Generation tokens/s:** output speed, separate from prompt processing.
8. **Peak RSS:** observed inference-process memory, not total device memory.
9. **Prompt cache:** server reuse of repeated prompt processing; not response cache.
10. **Joules versus watts:** energy versus power rate; CPU utilization is neither directly.

## Ten important implementation decisions

1. Use local Qwen GGUF files rather than a cloud inference API.
2. Use llama.cpp as the primary benchmark runtime; keep Ollama optional.
3. Bind the intended services to loopback interfaces.
4. Manage only registered Orbit `llama-server` processes.
5. Keep a RAM safety reserve before launch.
6. Separate warm-up, measured, failure, skipped, and deferred trial states.
7. Use Spider execution matching rather than only answer-string matching.
8. Make JSONL raw evidence authoritative; mirror to MySQL optionally.
9. Reject simulated/proxy meter exports from actual-energy logic.
10. Make quality a hard gate and keep proxy energy outside automatic ranking.

## Ten limitations and honest explanations

1. **Live runtime was unavailable during latest verification.** “The code is tested, but I will not claim a fresh local-generation run until llama.cpp is running.”
2. **Matrix coverage is incomplete.** “The recommendation is only over measured qualifying profiles, not every theoretical setting.”
3. **General benchmark results are absent.** “Spider quality is task-specific; general quality is not established.”
4. **No physical meter is connected.** “Energy is currently unavailable for actual energy constraints; proxies are exploratory only.”
5. **IFEval checker is not integrated.** “Instruction-following quality remains unavailable rather than heuristically overstated.”
6. **RAG is lexical.** “It provides transparent local retrieval, not semantic-vector retrieval proof.”
7. **Memory admission is estimated.** “Measured RSS validates it after execution; the estimate protects the system before execution.”
8. **Trials are limited.** “Three is a prototype minimum, not a statistically comprehensive campaign.”
9. **Legacy CSV is incomplete.** “It is preserved for history but not equivalent to modern provenance-rich JSONL.”
10. **Migration needs clean-environment exercise.** “Existing MySQL schema was verified; a disposable clean deployment remains a release test.”

## Twenty likely director-level questions

1. What makes this an optimizer, not a dashboard?
2. What is your formal definition of lowest cost?
3. How do you keep quality from being sacrificed for speed?
4. What happens when no model safely fits in RAM?
5. Why choose Qwen and GGUF?
6. Why llama.cpp rather than only Ollama?
7. What does Q4/Q5/Q6 mean?
8. How did you control the quantization experiment?
9. What is TTFT and why report it?
10. Why separate model activation from response latency?
11. What does peak RSS miss?
12. What is the difference between prompt cache and response cache?
13. How do you prove retrieval helped?
14. Why is Spider a useful but insufficient evaluator?
15. How is SQL evaluation made read-only?
16. Is your energy number measured or estimated?
17. Why is JSONL authoritative over MySQL?
18. How can a human override the recommendation?
19. What information is redacted for privacy?
20. What must be done before calling this demonstration-ready?

## Ten difficult follow-ups and safe answers

| Follow-up | Answer |
|---|---|
| “Your Q6 is slower; does that prove Q4 is better?” | No. It supports an observed trade-off on this workload. Quality threshold and the user’s cost objective decide. |
| “Why not claim CPU proxy joules as energy?” | It assumes a power model and does not measure wall/device energy. We label it estimate and exclude it from automatic energy selection. |
| “How do you prevent cherry-picking?” | Use declared datasets, same prompts/settings, warm-up policy, repeated trials, raw JSONL, and preserve failures/skips. |
| “Why only five quantization questions?” | It is a pilot controlled study. It does not establish broad model quality; larger held-out coverage is required. |
| “Can the largest model win automatically?” | Only if it passes constraints and is preferable under measured evidence. Parameter count alone is not a quality score. |
| “Does local inference guarantee privacy?” | It avoids sending prompts to a cloud service in this design, but local logging, access, and dataset governance still matter. |
| “Why accept user-supplied gold SQL in live comparison?” | It enables task-valid single-request evaluation, but it is not a replacement for held-out benchmark evidence. |
| “Is a Pareto frontier a final recommendation?” | No. It shows non-dominated choices; the documented constraints/objective produce a single recommendation when appropriate. |
| “Could RAM measurements be wrong?” | Sampling can miss brief peaks and system conditions vary. That is why estimates are conservative and raw trial variability is retained. |
| “What is the most important next experiment?” | A predefined, completed, repeated benchmark subset across all selectable candidates on a working local runtime. |

## Final project status

**Current director-level position:** Early functional prototype. It has strong implementation foundations and responsible measurement boundaries, but the central “best local configuration” claim is limited to the currently recorded, task-valid evidence.

## Never claim unless it has been verified

- “We measure actual energy” without a valid physical meter trace.
- “The optimizer finds the globally best configuration” without complete comparable coverage.
- “The model is generally accurate” from Spider or a small custom pilot.
- “Prompt compression improves quality” from character reduction alone.
- “Retrieval grounds answers” merely because context was appended.
- “The app was tested end-to-end today” without a successful live runtime execution.
- “All quantizations/models were compared fairly” when candidates were deferred, skipped, or run on different workloads.
- “MySQL is required” when JSONL remains the primary local evidence store.
