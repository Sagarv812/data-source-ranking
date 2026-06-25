from __future__ import annotations

import re
from dataclasses import dataclass

from data_source_ranking.models import (
    Claim,
    ClaimType,
    DimensionScore,
    RankingDimension,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point

TIME_PATTERN = re.compile(r"\b(q[1-4]|20\d{2}|january|february|march|april|may|june|july|august|"
                          r"september|october|november|december|autumn|spring|summer|winter)\b")

PROCESS_MARKERS = {
    "workflow",
    "handoff",
    "handoffs",
    "intake",
    "rollout",
    "routing",
    "review",
    "proposal",
    "pilot",
    "facilities",
    "facility",
    "clinic",
    "clinics",
    "support",
    "escalation",
    "compliance",
}

ACTION_MARKERS = {
    "risk",
    "concern",
    "concerned",
    "pushed",
    "bottleneck",
    "disruption",
    "selected",
    "approved",
    "agreed",
    "chose",
    "next",
    "follow-up",
    "workshop",
    "validate",
    "reduced",
}

GENERIC_MARKERS = {
    "transformation",
    "digital transformation",
    "automation opportunity",
    "efficiency",
    "modernization",
    "analytics",
    "change management",
    "interested",
    "improve operations",
}


@dataclass(frozen=True)
class TextScore:
    text: str
    score: float
    source: str
    concrete_markers: list[str]
    generic_markers: list[str]
    reason: str


class SpecificityScorer(BaseScorer):
    dimension = RankingDimension.SPECIFICITY

    def score(self, context: ScoringContext) -> DimensionScore:
        text_scores = self._text_scores(context)

        if not text_scores:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                label="none",
                reason="Source has no claims, summary, body, or title to evaluate.",
                weak_points=[
                    weak_point(
                        WeakPointType.VAGUE_CLAIM,
                        "No usable text is available for specificity scoring.",
                        context,
                        severity="high",
                    )
                ],
                metadata={"text_scores": []},
            )

        best = max(text_scores, key=lambda item: item.score)
        weak_points = []
        if best.score <= 0.35:
            weak_points.append(
                weak_point(
                    WeakPointType.VAGUE_CLAIM,
                    "Best available claim or source text is vague.",
                    context,
                    severity="high" if best.score <= 0.2 else "medium",
                    metadata={"best_text": best.text},
                )
            )

        if self._best_claim_is_unsupported(context, best):
            weak_points.append(
                weak_point(
                    WeakPointType.UNSUPPORTED_INFERENCE,
                    "Best specificity signal is based on unsupported inference.",
                    context,
                    severity="high",
                    metadata={"best_text": best.text},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=best.score,
            label=self._label(best.score),
            reason=best.reason,
            weak_points=weak_points,
            metadata={
                "best_text": best.text,
                "best_source": best.source,
                "concrete_markers": best.concrete_markers,
                "generic_markers": best.generic_markers,
                "text_scores": [score.__dict__ for score in text_scores],
            },
        )

    def _text_scores(self, context: ScoringContext) -> list[TextScore]:
        if context.source.claims:
            return [self._score_claim(claim) for claim in context.source.claims]

        fallback_scores = []
        if context.source.summary:
            fallback_scores.append(
                self._score_fallback_text(context.source.summary, "summary", 0.45)
            )
        if context.source.body:
            fallback_scores.append(self._score_fallback_text(context.source.body, "body", 0.45))
        if not fallback_scores and context.source.title:
            fallback_scores.append(self._score_fallback_text(context.source.title, "title", 0.25))
        return fallback_scores

    def _score_claim(self, claim: Claim) -> TextScore:
        text = claim.text
        lower_text = text.lower()
        concrete_markers = self._concrete_markers(lower_text)
        generic_markers = self._generic_markers(lower_text)
        score = self._base_score(claim.claim_type)

        if TIME_PATTERN.search(lower_text):
            score += 0.1
            concrete_markers.append("timeframe")
        if concrete_markers:
            score += min(0.2, 0.08 * len(set(concrete_markers)))
        if len(text.split()) >= 10:
            score += 0.05
        if generic_markers and not concrete_markers:
            score -= 0.2
        if claim.is_inferred or claim.claim_type is ClaimType.UNSUPPORTED_INFERENCE:
            score -= 0.2

        score = self._bounded(score)
        return TextScore(
            text=text,
            score=score,
            source=f"claim:{claim.id}",
            concrete_markers=sorted(set(concrete_markers)),
            generic_markers=generic_markers,
            reason=self._reason(score, text, concrete_markers, generic_markers),
        )

    def _score_fallback_text(self, text: str, source: str, ceiling: float) -> TextScore:
        lower_text = text.lower()
        concrete_markers = self._concrete_markers(lower_text)
        generic_markers = self._generic_markers(lower_text)
        score = 0.2

        if TIME_PATTERN.search(lower_text):
            score += 0.08
            concrete_markers.append("timeframe")
        if concrete_markers:
            score += min(0.18, 0.06 * len(set(concrete_markers)))
        if len(text.split()) >= 10:
            score += 0.04
        if generic_markers and not concrete_markers:
            score -= 0.12

        score = min(ceiling, self._bounded(score))
        return TextScore(
            text=text,
            score=score,
            source=source,
            concrete_markers=sorted(set(concrete_markers)),
            generic_markers=generic_markers,
            reason=self._reason(score, text, concrete_markers, generic_markers),
        )

    def _base_score(self, claim_type: ClaimType) -> float:
        match claim_type:
            case ClaimType.DECISION_FEEDBACK:
                return 0.75
            case ClaimType.NEXT_STEP:
                return 0.75
            case ClaimType.CLIENT_CONCERN:
                return 0.7
            case ClaimType.IMPLEMENTATION_RISK:
                return 0.7
            case ClaimType.PRIOR_WORK:
                return 0.65
            case ClaimType.SIMILAR_CLIENT_CONTEXT:
                return 0.55
            case ClaimType.PROGRAM_SIGNAL:
                return 0.4
            case ClaimType.OWNER_SIGNAL:
                return 0.35
            case ClaimType.UNSUPPORTED_INFERENCE:
                return 0.2
            case ClaimType.OTHER:
                return 0.35

    def _concrete_markers(self, text: str) -> list[str]:
        markers = [marker for marker in PROCESS_MARKERS if marker in text]
        markers.extend(marker for marker in ACTION_MARKERS if marker in text)
        return markers

    def _generic_markers(self, text: str) -> list[str]:
        return [marker for marker in GENERIC_MARKERS if marker in text]

    def _bounded(self, score: float) -> float:
        return round(min(1.0, max(0.0, score)), 2)

    def _label(self, score: float) -> str:
        if score >= 0.9:
            return "email_ready"
        if score >= 0.75:
            return "specific"
        if score >= 0.55:
            return "moderate"
        if score >= 0.3:
            return "vague"
        if score > 0.0:
            return "generic"
        return "none"

    def _reason(
        self,
        score: float,
        text: str,
        concrete_markers: list[str],
        generic_markers: list[str],
    ) -> str:
        if concrete_markers:
            markers = ", ".join(sorted(set(concrete_markers)))
            return f"Text is specific because it includes concrete markers: {markers}."
        if generic_markers:
            markers = ", ".join(generic_markers)
            return f"Text is vague because it relies on generic language: {markers}."
        if score <= 0.35:
            return "Text has limited concrete detail."
        return "Text has enough detail to be moderately useful."

    def _best_claim_is_unsupported(self, context: ScoringContext, best: TextScore) -> bool:
        for claim in context.source.claims:
            if best.source == f"claim:{claim.id}":
                return claim.is_inferred or claim.claim_type is ClaimType.UNSUPPORTED_INFERENCE
        return False
