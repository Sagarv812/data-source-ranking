from __future__ import annotations

from data_source_ranking.models import (
    DimensionScore,
    DirectnessRelation,
    RankingDimension,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


class DirectnessScorer(BaseScorer):
    dimension = RankingDimension.DIRECTNESS

    def score(self, context: ScoringContext) -> DimensionScore:
        relation = context.source.directness_relation
        base_score, label = self._score_relation(relation)
        mismatches = self._find_mismatches(context)
        score = max(0.0, base_score - (0.12 if mismatches else 0.0))

        weak_points = []
        if relation is DirectnessRelation.SAME_CLIENT_ADJACENT_OPPORTUNITY:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_DIRECTNESS,
                    "Source is same-client context but from an adjacent opportunity.",
                    context,
                    severity="low",
                    metadata={"directness_relation": relation.value},
                )
            )
        elif base_score <= 0.45:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_DIRECTNESS,
                    self._low_directness_message(relation),
                    context,
                    severity=self._severity(relation),
                    metadata={"directness_relation": relation.value},
                )
            )

        if mismatches:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_DIRECTNESS,
                    "Declared directness relation is tighter than the available IDs support.",
                    context,
                    severity="medium",
                    metadata={"mismatches": mismatches},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=round(score, 2),
            label=label,
            reason=self._reason(relation, mismatches),
            weak_points=weak_points,
            metadata={
                "directness_relation": relation.value,
                "client_id": context.source.client_id,
                "account_id": context.source.account_id,
                "opportunity_id": context.source.opportunity_id,
                "similar_to_client_id": context.source.similar_to_client_id,
                "mismatches": mismatches,
            },
        )

    def _score_relation(self, relation: DirectnessRelation) -> tuple[float, str]:
        match relation:
            case DirectnessRelation.SAME_CLIENT_SAME_OPPORTUNITY:
                return 1.0, "same_client_same_opportunity"
            case DirectnessRelation.SAME_CLIENT_ADJACENT_OPPORTUNITY:
                return 0.78, "same_client_adjacent_opportunity"
            case DirectnessRelation.SAME_ACCOUNT_GROUP:
                return 0.65, "same_account_group"
            case DirectnessRelation.CLOSELY_RELATED_STAKEHOLDER:
                return 0.6, "closely_related_stakeholder"
            case DirectnessRelation.SIMILAR_CLIENT:
                return 0.42, "similar_client_directional"
            case DirectnessRelation.GENERIC_INDUSTRY:
                return 0.22, "generic_industry"
            case DirectnessRelation.WEAK_MATCH:
                return 0.15, "weak_match"
            case DirectnessRelation.UNKNOWN:
                return 0.0, "unknown"

    def _find_mismatches(self, context: ScoringContext) -> list[str]:
        source = context.source
        need = context.context_need
        relation = source.directness_relation
        mismatches = []

        if relation is DirectnessRelation.SAME_CLIENT_SAME_OPPORTUNITY:
            if source.client_id and source.client_id != need.client_id:
                mismatches.append("client_id")
            if source.account_id and need.account_id and source.account_id != need.account_id:
                mismatches.append("account_id")
            if (
                source.opportunity_id
                and need.opportunity_id
                and source.opportunity_id != need.opportunity_id
            ):
                mismatches.append("opportunity_id")

        if relation is DirectnessRelation.SAME_CLIENT_ADJACENT_OPPORTUNITY:
            if source.client_id and source.client_id != need.client_id:
                mismatches.append("client_id")
            if source.account_id and need.account_id and source.account_id != need.account_id:
                mismatches.append("account_id")

        if (
            relation is DirectnessRelation.SIMILAR_CLIENT
            and source.similar_to_client_id
            and source.similar_to_client_id != need.client_id
        ):
            mismatches.append("similar_to_client_id")

        return mismatches

    def _reason(self, relation: DirectnessRelation, mismatches: list[str]) -> str:
        if relation is DirectnessRelation.SAME_CLIENT_SAME_OPPORTUNITY:
            reason = "Source is tied to the same client and same opportunity as the context need."
        elif relation is DirectnessRelation.SAME_CLIENT_ADJACENT_OPPORTUNITY:
            reason = "Source is same-client context, but from an adjacent opportunity."
        elif relation is DirectnessRelation.SAME_ACCOUNT_GROUP:
            reason = "Source is related at the account-group level, not the exact opportunity."
        elif relation is DirectnessRelation.CLOSELY_RELATED_STAKEHOLDER:
            reason = "Source is tied to a closely related stakeholder."
        elif relation is DirectnessRelation.SIMILAR_CLIENT:
            reason = "Source is similar-client context and should be treated as directional."
        elif relation is DirectnessRelation.GENERIC_INDUSTRY:
            reason = "Source is generic industry context rather than client-specific evidence."
        elif relation is DirectnessRelation.WEAK_MATCH:
            reason = "Source has only a weak relationship to the context need."
        else:
            reason = "Source relationship to the context need is unknown."

        if mismatches:
            reason += f" Metadata mismatch found for: {', '.join(mismatches)}."

        return reason

    def _low_directness_message(self, relation: DirectnessRelation) -> str:
        if relation is DirectnessRelation.SIMILAR_CLIENT:
            return "Source is similar-client context and must be labeled directional."
        if relation is DirectnessRelation.GENERIC_INDUSTRY:
            return "Source is generic industry context, not direct client evidence."
        if relation is DirectnessRelation.WEAK_MATCH:
            return "Source has only a weak match to the current context need."
        return "Source relationship to the current context need is unknown."

    def _severity(self, relation: DirectnessRelation) -> str:
        if relation is DirectnessRelation.SIMILAR_CLIENT:
            return "medium"
        if relation is DirectnessRelation.GENERIC_INDUSTRY:
            return "high"
        if relation is DirectnessRelation.WEAK_MATCH:
            return "high"
        return "high"
