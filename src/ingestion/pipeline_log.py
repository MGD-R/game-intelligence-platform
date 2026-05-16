"""Helpers for recording pipeline run status."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from src.ingestion.repository import IngestionRepository


@dataclass(slots=True)
class PipelineRunLogger:
    pipeline_name: str
    stage_name: str
    repository: IngestionRepository | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _started_at: float = field(default_factory=monotonic, init=False)

    def mark_started(self, parameters: dict[str, Any] | None = None) -> None:
        if self.repository is None:
            return
        self.repository.upsert_pipeline_run_state(
            run_id=self.run_id,
            pipeline_name=self.pipeline_name,
            stage_name=self.stage_name,
            status="started",
            parameters_json=parameters,
        )

    def mark_finished(
        self,
        *,
        status: str,
        metrics: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if self.repository is None:
            return
        duration_ms = int((monotonic() - self._started_at) * 1000)
        self.repository.upsert_pipeline_run_state(
            run_id=self.run_id,
            pipeline_name=self.pipeline_name,
            stage_name=self.stage_name,
            status=status,
            duration_ms=duration_ms,
            metrics_json=metrics,
            error_message=error_message,
            finished=True,
        )
