from __future__ import annotations

from data_source_ranking.decision_engine import decide
from data_source_ranking.loader import load_source_bundle
from data_source_ranking.models import DecisionType
from data_source_ranking.prompts import (
    CHOOSE_OWNER,
    EXCLUDE_SENSITIVE_SOURCE,
    OLD_PROPOSAL,
    REMOVE_CLAIM,
    REQUEST_VALIDATION,
    SENSITIVE_EVIDENCE_OVERLAP,
    SENSITIVE_PARTNER_MATERIAL,
    SIMILAR_CLIENT_DIRECTIONAL_CONTEXT,
    SKIP_SOURCE,
    STOP_AUTOMATION,
    UNCLEAR_OWNER,
    UNSUPPORTED_CLAIM,
    USE_CAUTIOUS_WORDING,
    USE_DIRECTIONAL_WITH_LABEL,
    USE_HISTORICAL_CONTEXT,
    USE_WITHOUT_OWNER,
)


def test_decide_builds_similar_client_directional_prompt() -> None:
    bundle = load_source_bundle("fixtures/bundles/northstar_similar_client_review.json")

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == SIMILAR_CLIENT_DIRECTIONAL_CONTEXT
    assert prompt.recommended_action == USE_DIRECTIONAL_WITH_LABEL
    assert prompt.source_ids == ["src_northstar_similar_client_proposal"]
    assert prompt.question == (
        "Use 'Retail rollout proposal for HarborMart' only as directional context for this "
        "automation, or skip it?"
    )
    assert "not the current client" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        USE_DIRECTIONAL_WITH_LABEL,
        SKIP_SOURCE,
    ]
    assert prompt.choices[0].label == "Use as directional"
    assert "clearly labels" in prompt.choices[0].effect
    assert prompt.metadata["source_titles"] == {
        "src_northstar_similar_client_proposal": "Retail rollout proposal for HarborMart"
    }
    assert prompt.metadata["similarity_reasons"] == {
        "src_northstar_similar_client_proposal": (
            "Both are multi-region retail operators evaluating store-operations workflow "
            "automation."
        )
    }


def test_decide_builds_unclear_owner_prompt() -> None:
    bundle = load_source_bundle("fixtures/bundles/gammahealth_unclear_owner_review.json")

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == UNCLEAR_OWNER
    assert prompt.recommended_action == CHOOSE_OWNER
    assert prompt.source_ids == ["src_gammahealth_useful_document_unclear_owner"]
    assert prompt.question == (
        "Who should validate or own 'GammaHealth referral intake workflow notes' before "
        "automation continues?"
    )
    assert "does not have a clear owner signal" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        CHOOSE_OWNER,
        USE_WITHOUT_OWNER,
        SKIP_SOURCE,
    ]
    assert prompt.choices[0].label == "Choose owner"
    assert prompt.choices[1].label == "Use carefully"
    assert prompt.choices[1].metadata == {
        "requires_user_acceptance": True,
        "risk": "owner_unvalidated",
    }
    assert prompt.metadata["owner_candidates"][
        "src_gammahealth_useful_document_unclear_owner"
    ][0]["id"] == "user_priya"


def test_decide_builds_sensitive_evidence_overlap_prompt() -> None:
    bundle = load_source_bundle("fixtures/bundles/delta_contradictory_sources.json")

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == SENSITIVE_EVIDENCE_OVERLAP
    assert prompt.recommended_action == EXCLUDE_SENSITIVE_SOURCE
    assert prompt.source_ids == ["src_deltabank_unverified_partner_material"]
    assert prompt.question == (
        "Sensitive evidence overlaps with usable source-backed context. Should we exclude "
        "the sensitive source, request validation, or stop?"
    )
    assert "should not be used automatically" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        EXCLUDE_SENSITIVE_SOURCE,
        REQUEST_VALIDATION,
        STOP_AUTOMATION,
    ]
    assert prompt.choices[0].label == "Exclude sensitive source"
    assert prompt.metadata["overlapping_needed_claim_ids"] == [
        "need_claim_current_concern"
    ]
    assert prompt.metadata["source_titles"] == {
        "src_deltabank_unverified_partner_material": (
            "Partner banking compliance automation brief"
        )
    }


def test_decide_builds_unsupported_claim_prompt() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_unsupported_claim_review.json")

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == UNSUPPORTED_CLAIM
    assert prompt.recommended_action == REMOVE_CLAIM
    assert prompt.source_ids == ["src_acme_unsupported_inferred_claim"]
    assert prompt.question == (
        "This source includes an unsupported inferred claim. Should we remove the claim, "
        "use only cautious wording, or stop?"
    )
    assert "not directly supported" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        REMOVE_CLAIM,
        USE_CAUTIOUS_WORDING,
        STOP_AUTOMATION,
    ]
    assert prompt.choices[1].metadata == {
        "requires_user_acceptance": True,
        "risk": "unsupported_inference",
    }
    assert prompt.metadata["unsupported_claims"][
        "src_acme_unsupported_inferred_claim"
    ][0]["id"] == "claim_acme_inferred_implementation_risk"


def test_decide_builds_sensitive_partner_material_prompt() -> None:
    bundle = load_source_bundle(
        "fixtures/bundles/deltabank_sensitive_partner_material_review.json"
    )

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == SENSITIVE_PARTNER_MATERIAL
    assert prompt.recommended_action == REQUEST_VALIDATION
    assert prompt.source_ids == ["src_deltabank_unverified_partner_material"]
    assert prompt.question == (
        "This source is sensitive partner material. Should we request validation, "
        "exclude it, or stop?"
    )
    assert "should not be used automatically" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        REQUEST_VALIDATION,
        EXCLUDE_SENSITIVE_SOURCE,
        STOP_AUTOMATION,
    ]
    assert prompt.choices[1].label == "Exclude source"
    assert prompt.metadata["source_risks"]["src_deltabank_unverified_partner_material"] == {
        "source_type": "partner_material",
        "source_system": "partner_portal",
        "sensitivity_labels": ["partner_channel", "internal_only"],
    }


def test_decide_builds_old_proposal_prompt() -> None:
    bundle = load_source_bundle("fixtures/bundles/betaworks_old_proposal_review.json")

    decision = decide(bundle)
    prompt = decision.approval_prompt

    assert decision.decision is DecisionType.NEEDS_USER_REVIEW
    assert prompt is not None
    assert prompt.issue_type == OLD_PROPOSAL
    assert prompt.recommended_action == REQUEST_VALIDATION
    assert prompt.source_ids == ["src_betaworks_old_proposal_with_owner"]
    assert prompt.question == (
        "This proposal may be stale. Should we request validation, use it only as "
        "historical context, or skip it?"
    )
    assert "should not be used as current fact" in prompt.explanation
    assert [choice.id for choice in prompt.choices] == [
        REQUEST_VALIDATION,
        USE_HISTORICAL_CONTEXT,
        SKIP_SOURCE,
    ]
    assert prompt.choices[1].metadata == {
        "requires_user_acceptance": True,
        "risk": "stale_proposal",
    }
    assert prompt.metadata["source_titles"] == {
        "src_betaworks_old_proposal_with_owner": "BetaWorks workflow automation proposal"
    }
