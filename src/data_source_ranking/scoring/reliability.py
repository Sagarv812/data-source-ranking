from __future__ import annotations

from data_source_ranking.models import (
    DimensionScore,
    RankingDimension,
    SourceSystem,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point

SOURCE_TYPE_DEFAULTS = {
    SourceType.HUMAN_VALIDATED_CONTEXT: 0.9,
    SourceType.SALESFORCE_OPPORTUNITY_NOTE: 0.82,
    SourceType.CRM_NOTE: 0.78,
    SourceType.PROPOSAL: 0.72,
    SourceType.MEETING_NOTES: 0.7,
    SourceType.PRIOR_HANDOFF: 0.65,
    SourceType.FLOWCASE_MATCH: 0.55,
    SourceType.MEETING_EVENT: 0.5,
    SourceType.DECK: 0.45,
    SourceType.PARTNER_MATERIAL: 0.35,
    SourceType.OTHER: 0.4,
}

SOURCE_SYSTEM_MODIFIERS = {
    SourceSystem.HUMAN: 0.05,
    SourceSystem.SALESFORCE: 0.04,
    SourceSystem.CALENDAR: 0.0,
    SourceSystem.DRIVE: 0.0,
    SourceSystem.FLOWCASE: 0.0,
    SourceSystem.PARTNER_PORTAL: -0.08,
    SourceSystem.LOCAL_FIXTURE: 0.0,
    SourceSystem.OTHER: 0.0,
}


class HistoricalReliabilityScorer(BaseScorer):
    dimension = RankingDimension.HISTORICAL_RELIABILITY

    def score(self, context: ScoringContext) -> DimensionScore:
        source = context.source
        base, base_source = self._base_score(context)
        modifier, modifier_source = self._system_modifier(context)
        score = round(min(1.0, max(0.0, base + modifier)), 2)
        weak_points = []

        if score <= 0.45:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_HISTORICAL_RELIABILITY,
                    "Source type or system has low default historical reliability.",
                    context,
                    severity="medium",
                    metadata={"historical_reliability_score": score},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=self._label(score),
            reason=self._reason(score, base_source, modifier_source),
            weak_points=weak_points,
            metadata={
                "source_type": source.type.value,
                "source_system": source.source_system.value,
                "base_score": base,
                "base_score_source": base_source,
                "system_modifier": modifier,
                "system_modifier_source": modifier_source,
                "uses_learned_feedback": (
                    base_source == "override" or modifier_source == "override"
                ),
            },
        )

    def _base_score(self, context: ScoringContext) -> tuple[float, str]:
        source_type_key = f"source_type:{context.source.type.value}"
        if source_type_key in context.reliability_defaults:
            return context.reliability_defaults[source_type_key], "override"
        return SOURCE_TYPE_DEFAULTS[context.source.type], "static_default"

    def _system_modifier(self, context: ScoringContext) -> tuple[float, str]:
        source_system_key = f"source_system:{context.source.source_system.value}"
        if source_system_key in context.reliability_defaults:
            return context.reliability_defaults[source_system_key], "override"
        return SOURCE_SYSTEM_MODIFIERS[context.source.source_system], "static_default"

    def _label(self, score: float) -> str:
        if score >= 0.85:
            return "very_reliable_default"
        if score >= 0.7:
            return "reliable_default"
        if score >= 0.55:
            return "mixed_default"
        if score >= 0.4:
            return "low_default"
        return "very_low_default"

    def _reason(self, score: float, base_source: str, modifier_source: str) -> str:
        if base_source == "override" or modifier_source == "override":
            return (
                f"Historical reliability score is {score} using learned source-type "
                "or source-system feedback overrides."
            )
        return (
            f"Historical reliability score is {score} using {base_source} source-type "
            f"reliability and {modifier_source} source-system modifier. "
            "Learned feedback history is not available yet."
        )
