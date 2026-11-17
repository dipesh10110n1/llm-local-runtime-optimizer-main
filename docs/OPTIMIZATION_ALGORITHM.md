# Optimization algorithm

The optimizer first retrieves profiles for the requested task (falling back only to explicitly general profiles), then filters quality, latency, RAM, and optional energy constraints. Unknown energy fails an explicit energy cap. It ranks feasible candidates according to the requested preference and returns a non-dominated Pareto frontier. With no feasible candidate it returns violated constraints and closest alternatives, never a forced winner.

Measured profiles rank ahead of estimates. Each selection carries its sample count, source, and an explanation; historic results do not guarantee future quality or performance.
