from __future__ import annotations

from data_source_ranking.models import DimensionScore, RankingDimension, WeakPointType
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


class CompletenessScorer(BaseScorer):
    dimension = RankingDimension.COMPLETENESS

    def score(self, context: ScoringContext) -> DimensionScore:
        required_ids = {
            needed_claim.id
            for needed_claim in context.context_need.needed_claims
            if needed_claim.required
        }
        optional_ids = {
            needed_claim.id
            for needed_claim in context.context_need.needed_claims
            if not needed_claim.required
        }
        covered_ids = {
            needed_claim_id
            for claim in context.source.claims
            for needed_claim_id in claim.supports_needed_claim_ids
        }
        covered_required = required_ids & covered_ids
        covered_optional = optional_ids & covered_ids
        missing_required = required_ids - covered_required
        score, label = self._score_coverage(
            required_ids=required_ids,
            covered_required=covered_required,
            covered_optional=covered_optional,
            covered_ids=covered_ids,
        )

        weak_points = []
        if missing_required:
            weak_points.append(
                weak_point(
                    WeakPointType.INCOMPLETE_CONTEXT,
                    "Source does not cover all required needed claims.",
                    context,
                    severity="high" if not covered_required else "medium",
                    metadata={"missing_required_claim_ids": sorted(missing_required)},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(label, required_ids, covered_required, missing_required),
            weak_points=weak_points,
            metadata={
                "required_needed_claim_ids": sorted(required_ids),
                "optional_needed_claim_ids": sorted(optional_ids),
                "covered_needed_claim_ids": sorted(covered_ids),
                "covered_required_claim_ids": sorted(covered_required),
                "covered_optional_claim_ids": sorted(covered_optional),
                "missing_required_claim_ids": sorted(missing_required),
            },
        )

    def _score_coverage(
        self,
        required_ids: set[str],
        covered_required: set[str],
        covered_optional: set[str],
        covered_ids: set[str],
    ) -> tuple[float, str]:
        if not covered_ids:
            return 0.0, "none"

        if not required_ids:
            if covered_optional:
                return 0.8, "optional_complete"
            return 0.0, "none"

        required_coverage = len(covered_required) / len(required_ids)

        if required_coverage == 1.0 and covered_optional:
            return 1.0, "complete_with_optional"
        if required_coverage == 1.0:
            return 0.9, "required_complete"
        if required_coverage >= 0.75:
            return 0.7, "mostly_complete"
        if required_coverage > 0.0:
            return 0.45, "partial"
        if covered_optional:
            return 0.3, "optional_only"
        return 0.0, "none"

    def _reason(
        self,
        label: str,
        required_ids: set[str],
        covered_required: set[str],
        missing_required: set[str],
    ) -> str:
        if label == "complete_with_optional":
            return "Source covers all required needed claims and at least one optional claim."
        if label == "required_complete":
            return "Source covers all required needed claims."
        if label == "mostly_complete":
            return "Source covers most required needed claims."
        if label == "partial":
            return (
                f"Source covers {len(covered_required)} of {len(required_ids)} "
                "required needed claims."
            )
        if label == "optional_only":
            return "Source covers optional context but misses required needed claims."
        if missing_required:
            return "Source does not cover any required needed claims."
        return "Source has no mapped claims for the context need."
