from __future__ import annotations

from dataclasses import dataclass

from data_source_ranking.models import (
    DimensionScore,
    Person,
    PersonRole,
    RankingDimension,
    WeakPointType,
)
from data_source_ranking.scoring.common import BaseScorer, ScoringContext, weak_point


@dataclass(frozen=True)
class OwnerSignal:
    person_id: str
    name: str
    role: PersonRole | None
    confidence: float
    source: str
    reason: str


class OwnershipSignalScorer(BaseScorer):
    dimension = RankingDimension.OWNERSHIP_SIGNAL

    def score(self, context: ScoringContext) -> DimensionScore:
        signals = self._signals(context)

        if not signals:
            return DimensionScore(
                dimension=self.dimension,
                score=0.0,
                label="none",
                reason="Source does not identify anyone who can validate or explain it.",
                weak_points=[
                    weak_point(
                        WeakPointType.MISSING_OWNER,
                        "No owner candidate, author, attendee, or validator is available.",
                        context,
                        severity="high",
                    )
                ],
                metadata={"owner_signals": []},
            )

        best_signal = max(signals, key=lambda signal: signal.confidence)
        score, label = self._score_signals(signals, best_signal)
        weak_points = []

        if label == "unclear":
            weak_points.append(
                weak_point(
                    WeakPointType.UNCLEAR_OWNER,
                    "Several possible owners exist, but no clear best owner is available.",
                    context,
                    severity="medium",
                    metadata={"owner_signal_count": len(signals)},
                )
            )
        elif label == "weak":
            weak_points.append(
                weak_point(
                    WeakPointType.UNCLEAR_OWNER,
                    "Only weak owner signals are available.",
                    context,
                    severity="medium",
                    metadata={"owner_signal_count": len(signals)},
                )
            )

        return DimensionScore(
            dimension=self.dimension,
            score=score,
            label=label,
            reason=self._reason(label, best_signal, signals),
            weak_points=weak_points,
            metadata={
                "best_owner": best_signal.__dict__,
                "owner_signals": [signal.__dict__ for signal in signals],
            },
        )

    def _signals(self, context: ScoringContext) -> list[OwnerSignal]:
        source = context.source
        signals = [
            OwnerSignal(
                person_id=candidate.id,
                name=candidate.name,
                role=candidate.role,
                confidence=candidate.confidence,
                source="owner_candidate",
                reason=candidate.reason,
            )
            for candidate in source.owner_candidates
        ]

        if source.author is not None:
            signals.append(
                self._person_signal(source.author, "author", "Source author is available.")
            )

        for attendee in source.attendees:
            signals.append(
                self._person_signal(
                    attendee,
                    "attendee",
                    "Meeting attendee can explain the source.",
                )
            )

        for record in source.validation_history:
            if record.validated_by is not None:
                signals.append(
                    self._person_signal(
                        record.validated_by,
                        "validator",
                        "Human validator is available from validation history.",
                    )
                )

        return self._dedupe_signals(signals)

    def _person_signal(self, person: Person, source: str, reason: str) -> OwnerSignal:
        return OwnerSignal(
            person_id=person.id,
            name=person.name,
            role=person.role,
            confidence=self._role_confidence(person.role, source),
            source=source,
            reason=reason,
        )

    def _role_confidence(self, role: PersonRole | None, signal_source: str) -> float:
        if signal_source == "validator":
            return 0.9
        if role in {
            PersonRole.ACCOUNT_OWNER,
            PersonRole.OPPORTUNITY_OWNER,
            PersonRole.PROPOSAL_OWNER,
        }:
            return 0.82 if signal_source == "author" else 0.72
        if role in {PersonRole.DOCUMENT_AUTHOR, PersonRole.LAST_EDITOR}:
            return 0.65
        if role is PersonRole.MEETING_ATTENDEE:
            return 0.6
        if role is PersonRole.PARTNER_CONTACT:
            return 0.45
        return 0.3

    def _dedupe_signals(self, signals: list[OwnerSignal]) -> list[OwnerSignal]:
        best_by_person: dict[str, OwnerSignal] = {}
        for signal in signals:
            current = best_by_person.get(signal.person_id)
            if current is None or signal.confidence > current.confidence:
                best_by_person[signal.person_id] = signal
        return list(best_by_person.values())

    def _score_signals(
        self, signals: list[OwnerSignal], best_signal: OwnerSignal
    ) -> tuple[float, str]:
        strong_signals = [signal for signal in signals if signal.confidence >= 0.75]

        if len(strong_signals) >= 2 and best_signal.confidence >= 0.82:
            return 0.88, "multiple_good"
        if best_signal.confidence >= 0.9:
            return 1.0, "clear"
        if best_signal.confidence >= 0.75:
            return 0.82, "good"
        if len(signals) >= 2 and best_signal.confidence >= 0.5:
            return 0.55, "unclear"
        if best_signal.confidence >= 0.6:
            return 0.72, "plausible"
        if best_signal.confidence >= 0.4:
            return 0.3, "weak"
        return 0.2, "weak"

    def _reason(self, label: str, best_signal: OwnerSignal, signals: list[OwnerSignal]) -> str:
        if label == "clear":
            return f"{best_signal.name} is a clear owner signal: {best_signal.reason}"
        if label == "multiple_good":
            return f"Multiple good owner signals exist; best candidate is {best_signal.name}."
        if label == "good":
            return f"{best_signal.name} is a good owner candidate: {best_signal.reason}"
        if label == "plausible":
            return f"{best_signal.name} is a plausible validation contact."
        if label == "unclear":
            return (
                f"{len(signals)} possible owners exist, "
                "but no clear best candidate is available."
            )
        return f"Only weak owner signal is available from {best_signal.name}."
