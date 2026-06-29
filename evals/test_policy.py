from __future__ import annotations

import pytest

from data_source_ranking.decisions import PolicyGateEffect, PolicyGateStatus
from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import SourceBundle
from data_source_ranking.policy import evaluate_policy_gates
from data_source_ranking.ranking import rank_bundle


def gates_for(path: str) -> dict[str, object]:
    bundle = load_source_bundle(path)
    ranked = rank_bundle(bundle)
    return {gate.gate: gate for gate in evaluate_policy_gates(ranked)}


def test_policy_gates_pass_for_auto_handoff_bundle() -> None:
    gates = gates_for("fixtures/bundles/acme_auto_handoff.json")

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.PASSED
    assert gates["required_claims_have_strong_coverage"].status is PolicyGateStatus.PASSED
    assert gates["required_claims_have_strong_coverage"].effect is (
        PolicyGateEffect.ALLOWS_AUTO_HANDOFF
    )
    assert gates["sensitivity_allows_automation"].status is PolicyGateStatus.PASSED
    assert gates["sensitive_evidence_overlap_absent"].status is PolicyGateStatus.PASSED
    assert gates["stale_unvalidated_source_absent"].status is PolicyGateStatus.PASSED
    assert gates["unsupported_inference_absent"].status is PolicyGateStatus.PASSED
    assert gates["owner_signal_available"].status is PolicyGateStatus.PASSED


def test_policy_gates_surface_context_request_requirements() -> None:
    gates = gates_for("fixtures/bundles/beta_needs_owner_validation.json")

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.PASSED
    assert gates["required_claims_have_strong_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["required_claims_have_strong_coverage"].effect is (
        PolicyGateEffect.PREVENTS_AUTO_HANDOFF
    )
    assert gates["required_claims_have_strong_coverage"].needed_claim_ids == [
        "need_claim_current_concern",
        "need_claim_prior_work",
    ]
    assert gates["stale_unvalidated_source_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["stale_unvalidated_source_absent"].effect is (
        PolicyGateEffect.REQUIRES_CONTEXT_REQUEST
    )
    assert gates["stale_unvalidated_source_absent"].source_ids == [
        "src_betaworks_old_proposal_with_owner",
        "src_betaworks_stale_account_context",
    ]
    assert gates["owner_signal_available"].status is PolicyGateStatus.PASSED


def test_policy_gates_surface_sensitive_review_requirements() -> None:
    gates = gates_for("fixtures/bundles/delta_contradictory_sources.json")

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.PASSED
    assert gates["required_claims_have_strong_coverage"].status is PolicyGateStatus.PASSED
    assert gates["sensitivity_allows_automation"].status is PolicyGateStatus.TRIGGERED
    assert gates["sensitivity_allows_automation"].effect is (
        PolicyGateEffect.PREVENTS_AUTO_HANDOFF
    )
    assert gates["sensitivity_allows_automation"].source_ids == [
        "src_deltabank_unverified_partner_material"
    ]
    assert gates["sensitive_evidence_overlap_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["sensitive_evidence_overlap_absent"].effect is (
        PolicyGateEffect.REQUIRES_USER_REVIEW
    )
    assert gates["sensitive_evidence_overlap_absent"].needed_claim_ids == [
        "need_claim_current_concern"
    ]


def test_policy_gates_surface_blocking_requirements() -> None:
    gates = gates_for("fixtures/bundles/gamma_blocked.json")

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["required_claims_have_usable_coverage"].effect is (
        PolicyGateEffect.BLOCKS_AUTOMATION
    )
    assert gates["required_claims_have_usable_coverage"].needed_claim_ids == [
        "need_claim_current_concern"
    ]
    assert gates["required_claims_have_strong_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["owner_signal_available"].status is PolicyGateStatus.TRIGGERED
    assert gates["owner_signal_available"].effect is PolicyGateEffect.BLOCKS_AUTOMATION


def test_policy_gates_route_meeting_title_to_context_request() -> None:
    fixture = load_source_fixture("fixtures/medium/deltabank_meeting_title_without_notes.json")
    bundle = SourceBundle(
        id="bundle_deltabank_meeting_title_probe",
        title="DeltaBank meeting title probe",
        context_need=fixture.context_need,
        sources=[fixture.source],
    )
    ranked = rank_bundle(bundle)
    gates = {gate.gate: gate for gate in evaluate_policy_gates(ranked)}

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.TRIGGERED
    assert gates["required_claims_have_usable_coverage"].effect is (
        PolicyGateEffect.REQUIRES_CONTEXT_REQUEST
    )
    assert gates["required_claims_have_usable_coverage"].source_ids == [
        "src_deltabank_meeting_title_without_notes"
    ]
    assert gates["owner_signal_available"].status is PolicyGateStatus.PASSED


def test_policy_gates_route_similar_client_to_user_review() -> None:
    fixture = load_source_fixture("fixtures/medium/northstar_similar_client_proposal.json")
    bundle = SourceBundle(
        id="bundle_northstar_similar_client_probe",
        title="Northstar similar client probe",
        context_need=fixture.context_need,
        sources=[fixture.source],
    )
    ranked = rank_bundle(bundle)
    gates = {gate.gate: gate for gate in evaluate_policy_gates(ranked)}

    assert gates["directional_context_review_absent"].status is PolicyGateStatus.TRIGGERED
    assert gates["directional_context_review_absent"].effect is (
        PolicyGateEffect.REQUIRES_USER_REVIEW
    )
    assert gates["directional_context_review_absent"].source_ids == [
        "src_northstar_similar_client_proposal"
    ]


def test_policy_gates_route_unclear_owner_to_user_review_when_evidence_is_usable() -> None:
    fixture = load_source_fixture("fixtures/medium/gammahealth_useful_document_unclear_owner.json")
    bundle = SourceBundle(
        id="bundle_gammahealth_unclear_owner_probe",
        title="GammaHealth unclear owner probe",
        context_need=fixture.context_need,
        sources=[fixture.source],
    )
    ranked = rank_bundle(bundle)
    gates = {gate.gate: gate for gate in evaluate_policy_gates(ranked)}

    assert gates["required_claims_have_usable_coverage"].status is PolicyGateStatus.PASSED
    assert gates["owner_signal_available"].status is PolicyGateStatus.TRIGGERED
    assert gates["owner_signal_available"].effect is PolicyGateEffect.REQUIRES_USER_REVIEW
    assert gates["owner_signal_available"].source_ids == [
        "src_gammahealth_useful_document_unclear_owner"
    ]


@pytest.mark.parametrize(
    "path",
    [
        "fixtures/bundles/acme_auto_handoff.json",
        "fixtures/bundles/beta_needs_owner_validation.json",
        "fixtures/bundles/delta_contradictory_sources.json",
        "fixtures/bundles/gamma_blocked.json",
    ],
)
def test_policy_gates_are_json_serializable(path: str) -> None:
    gates = gates_for(path)

    payload = [gate.model_dump(mode="json") for gate in gates.values()]

    assert {gate["gate"] for gate in payload} == {
        "directional_context_review_absent",
        "owner_signal_available",
        "required_claims_have_strong_coverage",
        "required_claims_have_usable_coverage",
        "sensitive_evidence_overlap_absent",
        "sensitivity_allows_automation",
        "stale_unvalidated_source_absent",
        "unsupported_inference_absent",
    }
