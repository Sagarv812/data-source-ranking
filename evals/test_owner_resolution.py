from __future__ import annotations

from datetime import date

from data_source_ranking.agents.owner_resolution import apply_owner_response
from data_source_ranking.agents.state import OwnerResponse
from data_source_ranking.loader import load_owner_response_fixture, load_source_bundle


def test_apply_owner_response_records_validation_history_without_mutating_bundle() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response

    result = apply_owner_response(
        bundle,
        response,
        as_of=date.fromisoformat(fixture.as_of or "2026-06-21"),
    )

    assert result.accepted is True
    assert result.updated_bundle is not None
    assert result.validation_errors == []
    assert result.applied_effects == [
        "owner_response_validated",
        "source_validation_recorded",
    ]
    assert result.original_bundle is bundle
    assert result.metadata == {
        "validated_source_id": "src_betaworks_old_proposal_with_owner",
        "validated_claim_ids": [
            "claim_betaworks_prior_pilot",
            "claim_betaworks_disruption_concern",
        ],
        "owner_id": "user_lina",
        "owner_name": "Lina Rao",
        "outcome": "accepted",
        "validated_at": "2026-06-21",
    }
    assert result.audit_events[0].event_type.value == "owner_response_applied"
    assert result.audit_events[0].action_type.value == "apply_owner_response"

    original_source = next(source for source in bundle.sources if source.id == response.source_id)
    updated_source = next(
        source for source in result.updated_bundle.sources if source.id == response.source_id
    )
    assert original_source.validation_history == []
    assert len(updated_source.validation_history) == 1

    record = updated_source.validation_history[0]
    assert record.validated_at == date(2026, 6, 21)
    assert record.validated_claim_ids == response.validated_claim_ids
    assert record.outcome == "accepted"
    assert record.notes == response.notes
    assert record.validated_by is not None
    assert record.validated_by.id == "user_lina"
    assert record.validated_by.name == "Lina Rao"
    assert record.validated_by.role.value == "proposal_owner"
    assert record.validated_by.role_title == "Proposal Owner"


def test_apply_owner_response_rejects_bundle_mismatch() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"bundle_id": "other_bundle"})

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == [
        "Owner response bundle_id does not match the source bundle."
    ]
    assert result.applied_effects == []
    assert result.audit_events[0].event_type.value == "owner_response_rejected"


def test_apply_owner_response_rejects_unknown_source() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"source_id": "src_missing"})

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == [
        "Owner response source_id does not exist in the source bundle."
    ]


def test_apply_owner_response_rejects_owner_mismatch() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"owner_id": "user_wrong"})

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == [
        "Owner response owner_id and owner_name do not match a source owner candidate."
    ]


def test_apply_owner_response_rejects_unknown_claim_ids() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(
        update={"validated_claim_ids": ["claim_betaworks_prior_pilot", "claim_missing"]}
    )

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == [
        "Owner response validated_claim_ids must exist on the selected source: claim_missing"
    ]


def test_apply_owner_response_rejects_unsupported_outcome() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"outcome": "rejected"})

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == ["Owner response outcome is not supported yet."]


def test_apply_owner_response_requires_validated_claims_for_acceptance() -> None:
    fixture = load_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    bundle = load_source_bundle(fixture.bundle_path)
    response = fixture.response.model_copy(update={"validated_claim_ids": []})

    result = apply_owner_response(bundle, response)

    assert result.accepted is False
    assert result.updated_bundle is None
    assert result.validation_errors == [
        "Accepted owner response requires at least one validated claim id."
    ]


def test_apply_owner_response_accepts_plain_response_object() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")
    response = OwnerResponse(
        bundle_id=bundle.id,
        source_id="src_betaworks_old_proposal_with_owner",
        owner_id="user_lina",
        owner_name="Lina Rao",
        outcome="accepted",
        validated_claim_ids=["claim_betaworks_prior_pilot"],
    )

    result = apply_owner_response(bundle, response)

    assert result.accepted is True
    assert result.updated_bundle is not None
