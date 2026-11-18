# Optimization algorithm

Candidates must have a positive historical sample count. Hard constraints are applied first: minimum quality, maximum latency, RAM, and energy. Missing requested values fail a constraint rather than being guessed. Remaining options are preference-scored and a non-dominated quality/latency/RAM Pareto frontier is returned. The response labels its evidence as measured or predicted and includes alternatives/violations when no feasible choice exists.
