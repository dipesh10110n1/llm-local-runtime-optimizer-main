# Database schema

The SQLAlchemy schema contains `models`, `hardware_profiles`, `datasets`, `runtime_configurations`, `benchmark_experiments`, `benchmark_results`, `quality_results`, `performance_metrics`, `resource_metrics`, `energy_metrics`, and `optimization_recommendations`. Credentials are only read from `DATABASE_URL`; copy `.env.example` to `.env`, create a MySQL database/user, then run `python -m database.initialize`.
