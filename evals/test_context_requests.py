from __future__ import annotations

import pytest

from data_source_ranking.context_requests import build_context_request
from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import DecisionType, SourceBundle
from data_source_ranking.ranking import rank_bundle


def test_context_request_targets_best_owner_for_validation() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")
    ranked = rank_bundle(bundle)

    request = build_context_request(bundle, ranked)

    assert request is not None
    assert request.recipient_id == "user_lina"
    assert request.recipient_name == "Lina Rao"
    assert request.recipient_reason == "Proposal owner for the 2025 pilot proposal."
    assert request.source_ids == ["src_betaworks_old_proposal_with_owner"]
    assert request.missing_information == [
        "Prior work that can be referenced in expansion messaging.",
        "Current concern or buying priority for the expansion conversation.",
    ]
    assert "BetaWorks workflow automation proposal" in request.question
    assert "especially:" in request.question
    assert request.suggested_response_format is not None
    assert request.metadata["recipient_confidence"] == 0.88


def test_context_request_asks_attendee_for_missing_meeting_details() -> None:
    fixture = load_source_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")
    bundle = SourceBundle(
        id="bundle_deltabank_meeting_title_probe",
        title="DeltaBank meeting title probe",
        context_need=fixture.context_need,
        sources=[fixture.source],
    )
    ranked = rank_bundle(bundle)

    request = build_context_request(bundle, ranked, decision=DecisionType.GENERATE_CONTEXT_REQUEST)

    assert request is not None
    assert request.recipient_id == "user_mateo"
    assert request.source_ids == ["src_deltabank_meeting_title_without_notes"]
    assert request.missing_information == [
        "Specific current concern raised by DeltaBank stakeholders.",
        "Agreed follow-up from the discovery meeting.",
    ]
    assert "What client concern, decision, or next step" in request.question
    assert "Risk workflow automation follow-up" in request.question


@pytest.mark.parametrize(
    "path",
    [
        "fixtures/bundles/acme_auto_handoff.json",
        "fixtures/bundles/delta_contradictory_sources.json",
        "fixtures/bundles/gamma_blocked.json",
    ],
)
def test_context_request_only_builds_for_context_request_decisions(path: str) -> None:
    bundle = load_source_bundle(path)
    ranked = rank_bundle(bundle)

    assert ranked.decision is not DecisionType.GENERATE_CONTEXT_REQUEST
    assert build_context_request(bundle, ranked) is None


def test_context_request_serializes_cleanly() -> None:
    bundle = load_source_bundle("fixtures/bundles/beta_needs_owner_validation.json")
    ranked = rank_bundle(bundle)

    request = build_context_request(bundle, ranked)

    assert request is not None
    payload = request.model_dump(mode="json")
    assert set(payload) == {
        "metadata",
        "missing_information",
        "question",
        "recipient_id",
        "recipient_name",
        "recipient_reason",
        "source_ids",
        "suggested_response_format",
    }
    assert payload["recipient_id"] == "user_lina"
