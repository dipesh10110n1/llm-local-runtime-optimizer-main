# Database schema

MySQL is the production store. Credentials are supplied via `DATABASE_URL`, never code. Tables: `models`, `hardware_profiles`, `datasets`, `runtime_configurations`, `benchmark_experiments`, `benchmark_results`, `quality_results`, `performance_metrics`, `resource_metrics`, `energy_metrics`, and `optimization_recommendations`.

Create a MySQL database/user, set `DATABASE_URL` as shown in `.env.example`, then run `python -m database.init_db`. The repository uses transactions and rejects SQLite unless `allow_sqlite_for_tests=True`. `migrations/001_initial.sql` records the schema migration baseline.
