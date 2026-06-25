from __future__ import annotations

from data_source_ranking.models import (
    DimensionScore,
    PersonRole,
    RankingDimension,
    SourceSystem,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


class AuthorityScorer(BaseScorer):
    dimension = RankingDimension.AUTHORITY

    def score(self, context: ScoringContext) -> DimensionScore:
        source = context.source
        signals = self._signals(context)
        score = max(value for value, _reason in signals)
        label = self._label(score)
        weak_points = []

        if score <= 0.45:
            weak_points.append(
                weak_point(
                    WeakPointType.LOW_AUTHORITY,
                    "Source provenance is weak or unclear.",
                    context,
                    severity="high" if score <= 0.25 else "medium",
                    metadata={"authority_score": score},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(signals),
            weak_points=weak_points,
            metadata={
                "signals": [{"score": value, "reason": reason} for value, reason in signals],
                "source_type": source.type.value,
                "source_system": source.source_system.value,
                "author_role": (
                    source.author.role.value if source.author and source.author.role else None
                ),
                "owner_candidate_roles": [
                    candidate.role.value for candidate in source.owner_candidates if candidate.role
                ],
                "has_accepted_validation": self._has_accepted_validation(context),
            },
        )

    def _signals(self, context: ScoringContext) -> list[tuple[float, str]]:
        source = context.source
        signals = [(0.2, "Baseline authority for unknown or weak provenance.")]

        if self._has_accepted_validation(context):
            signals.append((0.95, "Source or claims have accepted human validation."))

        if (
            source.type is SourceType.HUMAN_VALIDATED_CONTEXT
            and self._has_accepted_validation(context)
        ):
            signals.append((1.0, "Human-validated context with accepted validation."))

        if source.type is SourceType.SALESFORCE_OPPORTUNITY_NOTE:
            signals.append((0.7, "Salesforce opportunity note is an official CRM source."))
        if source.type is SourceType.CRM_NOTE:
            signals.append((0.65, "CRM note is an official account source."))
        if source.type is SourceType.MEETING_NOTES:
            signals.append(
                (0.65, "Meeting notes provide first-party customer interaction context.")
            )
        if source.type is SourceType.MEETING_EVENT:
            signals.append((0.5, "Meeting event exists, but has limited content authority."))
        if source.type is SourceType.PROPOSAL:
            signals.append((0.65, "Proposal source can be authoritative when ownership is clear."))
        if source.type is SourceType.DECK:
            signals.append((0.35, "Deck authority depends heavily on author and specificity."))
        if source.type is SourceType.FLOWCASE_MATCH:
            signals.append((0.45, "Flowcase match is useful but may be directional."))
        if source.type is SourceType.PARTNER_MATERIAL:
            signals.append(
                (0.25, "Unvalidated partner material has low customer-specific authority.")
            )

        if source.source_system is SourceSystem.SALESFORCE:
            signals.append((0.75, "Salesforce is a primary CRM system."))
        if source.source_system is SourceSystem.HUMAN:
            signals.append((0.8, "Human-provided source has direct validation potential."))
        if source.source_system is SourceSystem.CALENDAR:
            signals.append((0.55, "Calendar system confirms customer interaction metadata."))
        if source.source_system is SourceSystem.DRIVE:
            signals.append((0.5, "Drive document authority depends on author and document status."))
        if source.source_system is SourceSystem.FLOWCASE:
            signals.append((0.5, "Flowcase source can support project-reference context."))
        if source.source_system is SourceSystem.PARTNER_PORTAL:
            signals.append((0.25, "Partner portal source has low direct customer authority."))

        if source.author and source.author.role:
            signals.append(self._role_signal(source.author.role, "author"))

        for candidate in source.owner_candidates:
            if candidate.role:
                value, reason = self._role_signal(candidate.role, "owner_candidate")
                adjusted = round(value - 0.08, 2)
                signals.append((max(0.2, adjusted), reason))

        return signals

    def _role_signal(self, role: PersonRole, signal_source: str) -> tuple[float, str]:
        source_name = "author" if signal_source == "author" else "owner candidate"

        if role is PersonRole.ACCOUNT_OWNER:
            return 0.9 if signal_source == "author" else 0.82, f"Account owner is {source_name}."
        if role is PersonRole.OPPORTUNITY_OWNER:
            return (
                0.9 if signal_source == "author" else 0.82,
                f"Opportunity owner is {source_name}.",
            )
        if role is PersonRole.PROPOSAL_OWNER:
            return 0.85 if signal_source == "author" else 0.77, f"Proposal owner is {source_name}."
        if role is PersonRole.MEETING_ATTENDEE:
            return (
                0.75 if signal_source == "author" else 0.64,
                f"Meeting attendee is {source_name}.",
            )
        if role is PersonRole.DOCUMENT_AUTHOR:
            return 0.65 if signal_source == "author" else 0.57, f"Document author is {source_name}."
        if role is PersonRole.LAST_EDITOR:
            return 0.55 if signal_source == "author" else 0.47, f"Last editor is {source_name}."
        if role is PersonRole.PARTNER_CONTACT:
            return 0.3 if signal_source == "author" else 0.25, f"Partner contact is {source_name}."
        return 0.3, f"Unknown role is {source_name}."

    def _has_accepted_validation(self, context: ScoringContext) -> bool:
        return any(record.outcome == "accepted" for record in context.source.validation_history)

    def _label(self, score: float) -> str:
        if score >= 0.95:
            return "validated"
        if score >= 0.85:
            return "authoritative"
        if score >= 0.7:
            return "strong_provenance"
        if score >= 0.55:
            return "plausible_provenance"
        if score >= 0.35:
            return "unclear_provenance"
        return "low_provenance"

    def _reason(self, signals: list[tuple[float, str]]) -> str:
        score, reason = max(signals, key=lambda signal: signal[0])
        return f"{reason} Authority score is {score}."
