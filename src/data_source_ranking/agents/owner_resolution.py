from __future__ import annotations

from datetime import date

from data_source_ranking.agents.state import (
    AuditEvent,
    AuditEventLevel,
    OwnerResponse,
    OwnerResponseOutcome,
    OwnerResponseResult,
)
from data_source_ranking.models import (
    OwnerCandidate,
    Person,
    Source,
    SourceBundle,
    ValidationRecord,
)
from data_source_ranking.scoring.common import DEFAULT_AS_OF


def apply_owner_response(
    bundle: SourceBundle,
    response: OwnerResponse,
    as_of: date = DEFAULT_AS_OF,
) -> OwnerResponseResult:
    errors = _validation_errors(bundle, response)
    source = _source_by_id(bundle, response.source_id)
    owner = _owner_candidate(source, response) if source else None

    if errors or source is None or owner is None:
        return _rejected_result(bundle, response, errors)

    validation_record = ValidationRecord(
        validated_by=Person(
            id=response.owner_id,
            name=response.owner_name,
            role=owner.role,
            role_title=owner.role_title,
        ),
        validated_at=as_of,
        validated_claim_ids=response.validated_claim_ids,
        outcome="accepted",
        notes=response.notes,
    )
    updated_source = source.model_copy(
        update={
            "validation_history": [
                *source.validation_history,
                validation_record,
            ]
        }
    )
    updated_bundle = bundle.model_copy(
        update={
            "sources": [
                updated_source if current.id == response.source_id else current
                for current in bundle.sources
            ]
        }
    )
    metadata = _metadata(response)
    return OwnerResponseResult(
        accepted=True,
        response=response,
        original_bundle=bundle,
        updated_bundle=updated_bundle,
        applied_effects=[
            "owner_response_validated",
            "source_validation_recorded",
        ],
        audit_events=[
            AuditEvent(
                sequence=1,
                event_type="owner_response_applied",
                title="Owner response applied",
                detail="Accepted owner response was recorded on the source validation history.",
                action_type="apply_owner_response",
                source_ids=[response.source_id],
                claim_ids=response.validated_claim_ids,
                metadata=metadata,
            )
        ],
        metadata={
            **metadata,
            "validated_at": as_of.isoformat(),
        },
    )


def _validation_errors(bundle: SourceBundle, response: OwnerResponse) -> list[str]:
    errors: list[str] = []
    source = _source_by_id(bundle, response.source_id)

    if response.bundle_id != bundle.id:
        errors.append("Owner response bundle_id does not match the source bundle.")
    if source is None:
        errors.append("Owner response source_id does not exist in the source bundle.")
        return errors
    if _owner_candidate(source, response) is None:
        errors.append(
            "Owner response owner_id and owner_name do not match a source owner candidate."
        )
    if _outcome_value(response) != OwnerResponseOutcome.ACCEPTED.value:
        errors.append("Owner response outcome is not supported yet.")
    if not response.validated_claim_ids:
        errors.append("Accepted owner response requires at least one validated claim id.")

    source_claim_ids = {claim.id for claim in source.claims}
    unknown_claim_ids = [
        claim_id for claim_id in response.validated_claim_ids if claim_id not in source_claim_ids
    ]
    if unknown_claim_ids:
        errors.append(
            "Owner response validated_claim_ids must exist on the selected source: "
            + ", ".join(unknown_claim_ids)
        )

    return errors


def _source_by_id(bundle: SourceBundle, source_id: str) -> Source | None:
    return next((source for source in bundle.sources if source.id == source_id), None)


def _owner_candidate(source: Source, response: OwnerResponse) -> OwnerCandidate | None:
    return next(
        (
            candidate
            for candidate in source.owner_candidates
            if candidate.id == response.owner_id and candidate.name == response.owner_name
        ),
        None,
    )


def _rejected_result(
    bundle: SourceBundle,
    response: OwnerResponse,
    errors: list[str],
) -> OwnerResponseResult:
    return OwnerResponseResult(
        accepted=False,
        response=response,
        original_bundle=bundle,
        validation_errors=errors,
        audit_events=[
            AuditEvent(
                sequence=1,
                event_type="owner_response_rejected",
                title="Owner response rejected",
                detail="Owner response could not be applied to the source bundle.",
                level=AuditEventLevel.WARNING,
                action_type="apply_owner_response",
                source_ids=[response.source_id],
                claim_ids=response.validated_claim_ids,
                metadata={
                    **_metadata(response),
                    "validation_errors": errors,
                },
            )
        ],
        metadata={
            **_metadata(response),
            "validation_only": True,
        },
    )


def _metadata(response: OwnerResponse) -> dict[str, str | list[str]]:
    return {
        "validated_source_id": response.source_id,
        "validated_claim_ids": response.validated_claim_ids,
        "owner_id": response.owner_id,
        "owner_name": response.owner_name,
        "outcome": _outcome_value(response),
    }


def _outcome_value(response: OwnerResponse) -> str:
    if isinstance(response.outcome, OwnerResponseOutcome):
        return response.outcome.value
    return str(response.outcome)
