from __future__ import annotations

from dataclasses import dataclass

from data_source_ranking.models import DimensionScore, RankingDimension, Source, WeakPointType
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


@dataclass(frozen=True)
class SupportMatch:
    source_id: str
    source_type: str
    source_system: str
    needed_claim_ids: list[str]
    independent: bool


class CorroborationScorer(BaseScorer):
    dimension = RankingDimension.CORROBORATION

    def score(self, context: ScoringContext) -> DimensionScore:
        supported_ids = self._supported_needed_claim_ids(context.source)

        if not supported_ids:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                label="unsupported",
                reason="Source has no mapped claims to corroborate.",
                weak_points=[
                    weak_point(
                        WeakPointType.LOW_CORROBORATION,
                        "Source has no mapped claims that can be corroborated.",
                        context,
                        severity="high",
                    )
                ],
                metadata={"supported_needed_claim_ids": [], "support_matches": []},
            )

        support_matches = self._support_matches(context, supported_ids)
        independent_matches = [match for match in support_matches if match.independent]
        related_matches = [match for match in support_matches if not match.independent]
        score, label = self._score_matches(independent_matches, related_matches)
        weak_points = []

        if score <= 0.3:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_CORROBORATION,
                    "Source is not corroborated by independent supporting evidence.",
                    context,
                    severity="medium" if label == "single_source" else "high",
                    metadata={"support_match_count": len(support_matches)},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(label, independent_matches, related_matches),
            weak_points=weak_points,
            metadata={
                "supported_needed_claim_ids": sorted(supported_ids),
                "support_matches": [match.__dict__ for match in support_matches],
                "independent_support_count": len(independent_matches),
                "related_support_count": len(related_matches),
            },
        )

    def _supported_needed_claim_ids(self, source: Source) -> set[str]:
        return {
            needed_claim_id
            for claim in source.claims
            for needed_claim_id in claim.supports_needed_claim_ids
        }

    def _support_matches(
        self, context: ScoringContext, supported_ids: set[str]
    ) -> list[SupportMatch]:
        matches = []
        for other_source in context.bundle_sources:
            if other_source.id == context.source.id:
                continue

            overlap = supported_ids & self._supported_needed_claim_ids(other_source)
            if not overlap:
                continue

            matches.append(
                SupportMatch(
                    source_id=other_source.id,
                    source_type=other_source.type.value,
                    source_system=other_source.source_system.value,
                    needed_claim_ids=sorted(overlap),
                    independent=self._is_independent(context.source, other_source),
                )
            )
        return matches

    def _is_independent(self, source: Source, other_source: Source) -> bool:
        if source.id == other_source.id:
            return False
        return (
            source.source_system != other_source.source_system
            or source.type != other_source.type
        )

    def _score_matches(
        self, independent_matches: list[SupportMatch], related_matches: list[SupportMatch]
    ) -> tuple[float, str]:
        if len(independent_matches) >= 2:
            return 1.0, "multiple_independent"
        if len(independent_matches) == 1:
            return 0.8, "independent_support"
        if len(related_matches) >= 2:
            return 0.6, "multiple_related"
        if len(related_matches) == 1:
            return 0.45, "related_support"
        return 0.3, "single_source"

    def _reason(
        self,
        label: str,
        independent_matches: list[SupportMatch],
        related_matches: list[SupportMatch],
    ) -> str:
        if label == "multiple_independent":
            return "Claim signal is supported by multiple independent sources."
        if label == "independent_support":
            return f"Claim signal is supported by {independent_matches[0].source_id}."
        if label == "multiple_related":
            return "Claim signal has multiple related supports, but not independent ones."
        if label == "related_support":
            return f"Claim signal is supported by related source {related_matches[0].source_id}."
        return "Claim signal appears only in this source."
