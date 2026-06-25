from __future__ import annotations

from dataclasses import dataclass

from data_source_ranking.models import (
    ClaimType,
    DimensionScore,
    RankingDimension,
    SensitivityLabel,
    SourceSystem,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


@dataclass(frozen=True)
class RiskSignal:
    score: float
    label: str
    reason: str


class SensitivityScorer(BaseScorer):
    dimension = RankingDimension.SENSITIVITY

    def score(self, context: ScoringContext) -> DimensionScore:
        signals = self._risk_signals(context)
        risk = max(signals, key=lambda signal: signal.score, default=RiskSignal(0.0, "none", ""))
        score = self._apply_validation_discount(context, risk.score)
        label = self._label(score)
        weak_points = []

        if score >= 0.6:
            weak_points.append(
                weak_point(
                    WeakPointType.SENSITIVE_SOURCE,
                    "Source has sensitivity risk that should affect automation.",
                    context,
                    severity="high" if score >= 0.8 else "medium",
                    metadata={"risk_score": score},
                )
            )

        if self._has_unsupported_inference(context):
            weak_points.append(
                weak_point(
                    WeakPointType.UNSUPPORTED_INFERENCE,
                    "Source includes an unsupported inferred claim.",
                    context,
                    severity="high",
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(score, signals),
            weak_points=weak_points,
            metadata={
                "risk_signals": [signal.__dict__ for signal in signals],
                "has_accepted_validation": self._has_accepted_validation(context),
                "sensitivity_labels": [label.value for label in context.source.sensitivity_labels],
                "source_type": context.source.type.value,
                "source_system": context.source.source_system.value,
            },
        )

    def _risk_signals(self, context: ScoringContext) -> list[RiskSignal]:
        source = context.source
        signals = [RiskSignal(0.0, "none", "No obvious sensitivity labels or inference risk.")]

        if SensitivityLabel.INTERNAL_ONLY in source.sensitivity_labels:
            signals.append(RiskSignal(0.45, "internal_caution", "Source is marked internal-only."))
        if SensitivityLabel.STALE_DATA in source.sensitivity_labels:
            signals.append(
                RiskSignal(0.45, "stale_data_caution", "Source is marked as stale data.")
            )
        if SensitivityLabel.PARTNER_CHANNEL in source.sensitivity_labels:
            signals.append(RiskSignal(0.85, "high_risk", "Source is partner-channel material."))
        if SensitivityLabel.CONFIDENTIAL in source.sensitivity_labels:
            signals.append(RiskSignal(0.85, "high_risk", "Source is marked confidential."))
        if SensitivityLabel.UNSUPPORTED_INFERENCE in source.sensitivity_labels:
            signals.append(
                RiskSignal(0.85, "high_risk", "Source is marked as unsupported inference.")
            )

        if source.type is SourceType.PARTNER_MATERIAL:
            signals.append(RiskSignal(0.65, "review_required", "Source type is partner material."))
        if source.source_system is SourceSystem.PARTNER_PORTAL:
            signals.append(RiskSignal(0.65, "review_required", "Source came from partner portal."))
        if any(claim.is_inferred for claim in source.claims):
            signals.append(RiskSignal(0.65, "review_required", "Source includes inferred claims."))
        if any(claim.claim_type is ClaimType.UNSUPPORTED_INFERENCE for claim in source.claims):
            signals.append(
                RiskSignal(0.85, "high_risk", "Source includes unsupported inference claims.")
            )

        return signals

    def _apply_validation_discount(self, context: ScoringContext, score: float) -> float:
        if not self._has_accepted_validation(context) or score <= 0.0:
            return score
        return max(0.25, round(score - 0.2, 2))

    def _has_accepted_validation(self, context: ScoringContext) -> bool:
        return any(record.outcome == "accepted" for record in context.source.validation_history)

    def _has_unsupported_inference(self, context: ScoringContext) -> bool:
        source = context.source
        return (
            SensitivityLabel.UNSUPPORTED_INFERENCE in source.sensitivity_labels
            or any(claim.is_inferred for claim in source.claims)
            or any(claim.claim_type is ClaimType.UNSUPPORTED_INFERENCE for claim in source.claims)
        )

    def _label(self, score: float) -> str:
        if score == 0.0:
            return "none"
        if score < 0.4:
            return "mild_caution"
        if score < 0.6:
            return "internal_caution"
        if score < 0.8:
            return "review_required"
        if score < 1.0:
            return "high_risk"
        return "unsafe"

    def _reason(self, score: float, signals: list[RiskSignal]) -> str:
        strongest = max(signals, key=lambda signal: signal.score)
        if score < strongest.score:
            return f"{strongest.reason} Accepted validation reduces but does not erase risk."
        return strongest.reason
