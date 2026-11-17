# Benchmark methodology

Use a unique experiment ID per benchmark, record warm-up separately from cold runs, repeat trials, and interleave configurations when practical. Hold prompt, task, output limit, and decoding parameters fixed for controlled comparisons. Report mean, median, standard deviation, sample count, and confidence intervals when enough trials exist.

Telemetry tracks client-observed latency, TTFT/TPOT when streaming instrumentation is available, token counts/throughput, process and process-tree memory, system RAM, CPU, and optional GPU values. `EnergyMetrics` is null/unavailable unless an actual telemetry source is integrated; utilization is not energy.
