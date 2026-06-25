from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from data_source_ranking.models import (
    ContextNeed,
    DimensionScore,
    RankingDimension,
    Source,
    WeakPoint,
    WeakPointType,
)

DEFAULT_AS_OF = date(2026, 6, 21)


class ScoringContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    context_need: ContextNeed
    source: Source
    bundle_sources: list[Source] = Field(default_factory=list)
    as_of: date = DEFAULT_AS_OF
    reliability_defaults: dict[str, float] = Field(default_factory=dict)


class BaseScorer(ABC):
    dimension: RankingDimension

    @abstractmethod
    def score(self, context: ScoringContext) -> DimensionScore:
        raise NotImplementedError


def weak_point(
    point_type: WeakPointType,
    message: str,
    context: ScoringContext,
    severity: str = "medium",
    metadata: dict[str, Any] | None = None,
) -> WeakPoint:
    return WeakPoint(
        type=point_type,
        message=message,
        source_id=context.source.id,
        severity=severity,
        metadata=metadata or {},
    )


def latest_source_date(source: Source) -> date | None:
    dates = [source.created_at, source.updated_at]
    dates.extend(record.validated_at for record in source.validation_history)
    present_dates = [value for value in dates if value is not None]
    if not present_dates:
        return None
    return max(present_dates)

