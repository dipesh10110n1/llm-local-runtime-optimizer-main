from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from database.schema import BenchmarkExperiment, BenchmarkResult, Model, OptimizationRecommendation, RuntimeConfiguration, create_schema, make_engine


class ExperimentRepository:
    """Small transactional repository. Production URL must point to MySQL."""
    def __init__(self, url: str, create: bool = False):
        self.engine = make_engine(url)
        if create:
            create_schema(url)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def upsert_model(self, model: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            existing = session.get(Model, model["model_id"])
            if existing:
                existing.family, existing.quantization, existing.metadata_json = model["family"], model.get("quantization"), model
            else:
                session.add(Model(model_id=model["model_id"], family=model["family"], quantization=model.get("quantization"), metadata_json=model))

    def save_experiment(self, experiment_id: str, kind: str, model_id: str | None = None, configuration_id: str | None = None, dataset_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        with self.sessions.begin() as session:
            if not session.get(BenchmarkExperiment, experiment_id):
                session.add(BenchmarkExperiment(experiment_id=experiment_id, kind=kind, model_id=model_id, configuration_id=configuration_id, dataset_id=dataset_id, metadata_json=metadata or {}))

    def save_recommendation(self, request: dict[str, Any], selected: str | None, explanation: str, predicted: bool = True) -> None:
        with self.sessions.begin() as session:
            session.add(OptimizationRecommendation(request_json=request, selected_configuration_id=selected, explanation=explanation, predicted=predicted))

    def list_experiments(self, limit: int = 100) -> list[BenchmarkExperiment]:
        with self.sessions() as session:
            return list(session.scalars(select(BenchmarkExperiment).order_by(BenchmarkExperiment.started_at.desc()).limit(limit)))
