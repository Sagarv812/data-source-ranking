from __future__ import annotations

from data_source_ranking.models import DimensionScore, RankingDimension, WeakPointType
from data_source_ranking.scoring.common import (
    BaseScorer,
    ScoringContext,
    latest_source_date,
    weak_point,
)


class FreshnessScorer(BaseScorer):
    dimension = RankingDimension.FRESHNESS

    def score(self, context: ScoringContext) -> DimensionScore:
        source_date = latest_source_date(context.source)

        if source_date is None:
            point = weak_point(
                WeakPointType.MISSING_DATE,
                "Source has no created, updated, or validation date.",
                context,
                severity="high",
            )
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                label="unknown",
                reason="No source date is available, so freshness cannot be trusted.",
                weak_points=[point],
                metadata={"as_of": context.as_of.isoformat()},
            )

        age_days = (context.as_of - source_date).days

        if age_days < 0:
            return DimensionScore(
                dimension=self.dimension,
                score=0.4,
                label="future_dated",
                reason="Source date is after the evaluation date, so freshness is suspicious.",
                weak_points=[
                    weak_point(
                        WeakPointType.MISSING_DATE,
                        "Source date is after the evaluation date.",
                        context,
                        severity="medium",
                        metadata={"source_date": source_date.isoformat()},
                    )
                ],
                metadata={
                    "as_of": context.as_of.isoformat(),
                    "source_date": source_date.isoformat(),
                    "age_days": age_days,
                },
            )

        score, label = self._score_age(age_days)
        weak_points = []
        if score <= 0.35:
            weak_points.append(
                weak_point(
                    WeakPointType.STALE_SOURCE,
                    f"Source is {age_days} days old relative to the evaluation date.",
                    context,
                    severity="high" if score <= 0.2 else "medium",
                    metadata={"age_days": age_days},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(label, age_days),
            weak_points=weak_points,
            metadata={
                "as_of": context.as_of.isoformat(),
                "source_date": source_date.isoformat(),
                "age_days": age_days,
            },
        )

    def _score_age(self, age_days: int) -> tuple[float, str]:
        if age_days <= 14:
            return 1.0, "current"
        if age_days <= 45:
            return 0.9, "very_recent"
        if age_days <= 120:
            return 0.75, "recent"
        if age_days <= 365:
            return 0.55, "aging"
        if age_days <= 540:
            return 0.35, "old"
        return 0.15, "stale"

    def _reason(self, label: str, age_days: int) -> str:
        if label == "current":
            return f"Source was updated or validated {age_days} days before evaluation."
        if label == "very_recent":
            return f"Source is very recent at {age_days} days old."
        if label == "recent":
            return f"Source is recent enough to be useful at {age_days} days old."
        if label == "aging":
            return f"Source is aging at {age_days} days old and may need context."
        if label == "old":
            return f"Source is old at {age_days} days and should be validated before use."
        return f"Source is stale at {age_days} days old."

