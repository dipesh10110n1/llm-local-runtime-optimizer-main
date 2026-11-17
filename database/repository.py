"""Transactional MySQL repository. SQLite is rejected unless explicitly allowed in tests."""

from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base, BenchmarkExperiment, Model, RuntimeConfigurationRow


class ExperimentRepository:
    def __init__(self, database_url: str, allow_sqlite_for_tests: bool = False):
        if database_url.startswith("sqlite") and not allow_sqlite_for_tests:
            raise ValueError("SQLite is only supported for isolated tests; configure MySQL with DATABASE_URL.")
        if not database_url.startswith(("mysql+pymysql://", "sqlite")):
            raise ValueError("DATABASE_URL must use mysql+pymysql:// for production.")
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def transaction(self):
        session: Session = self.sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_model(self, model_id: str, metadata: dict) -> None:
        with self.transaction() as session:
            row = session.scalar(select(Model).where(Model.model_id == model_id))
            if row:
                row.metadata_json = metadata
            else:
                session.add(Model(model_id=model_id, metadata_json=metadata))

    def upsert_configuration(self, configuration_id: str, configuration: dict) -> None:
        with self.transaction() as session:
            row = session.scalar(select(RuntimeConfigurationRow).where(RuntimeConfigurationRow.configuration_id == configuration_id))
            if row:
                row.configuration_json = configuration
            else:
                session.add(RuntimeConfigurationRow(configuration_id=configuration_id, configuration_json=configuration))

    def add_experiment(self, experiment_id: str, model_id: str, configuration_id: str, backend: str, dataset_id: str | None = None) -> bool:
        with self.transaction() as session:
            if session.scalar(select(BenchmarkExperiment).where(BenchmarkExperiment.experiment_id == experiment_id)):
                return False
            session.add(BenchmarkExperiment(experiment_id=experiment_id, model_id=model_id, configuration_id=configuration_id, backend=backend, dataset_id=dataset_id))
            return True

    def experiments(self, limit: int = 100) -> list[BenchmarkExperiment]:
        with self.transaction() as session:
            return list(session.scalars(select(BenchmarkExperiment).order_by(BenchmarkExperiment.created_at.desc()).limit(limit)))
