from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_source_ranking.decisions import (
    AutomationDecision,
    DecisionAuditEvent,
    DecisionConfidence,
    DraftHandoff,
    NextAction,
    PolicyGateResult,
    SourceCitation,
)
from data_source_ranking.loader import load_source_bundle
from data_source_ranking.models import DecisionType
from data_source_ranking.ranking import rank_bundle


def test_automation_decision_serializes_to_json_contract() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    ranked_bundle = rank_bundle(bundle)

    decision = AutomationDecision(
        bundle_id=bundle.id,
        decision=DecisionType.AUTO_HANDOFF,
        confidence=DecisionConfidence(
            score=0.92,
            label="high",
            reasons=["Required claim is covered by strong same-client evidence."],
        ),
        summary="Acme has strong same-client evidence for the current renewal concern.",
        ranked_bundle=ranked_bundle,
        selected_claims=[
            {
                "claim_id": "claim_acme_timeline_concern",
                "needed_claim_id": "need_claim_current_concern",
                "text": "Acme pushed back on implementation timeline risk during renewal prep.",
                "claim_type": "client_concern",
                "source_ids": ["src_acme_recent_crm_note"],
            }
        ],
        selected_sources=["src_acme_recent_crm_note"],
        source_citations=[
            SourceCitation(
                source_id="src_acme_recent_crm_note",
                title="Acme renewal prep CRM note",
                source_type="crm_note",
                claim_id="claim_acme_timeline_concern",
                needed_claim_id="need_claim_current_concern",
                citation_label="CRM note",
            )
        ],
        weak_points=[],
        policy_gates=[
            PolicyGateResult(
                gate="required_claims_have_strong_coverage",
                status="passed",
                effect="allows_auto_handoff",
                message="All required claims have strong source coverage.",
                needed_claim_ids=["need_claim_current_concern"],
            )
        ],
        next_action=NextAction(
            type="prepare_handoff",
            label="Prepare handoff",
            description="Use selected source-backed context for downstream email generation.",
        ),
        draft_handoff=DraftHandoff(
            text="Acme is preparing for renewal and has raised implementation timeline risk.",
            supported_claim_ids=["claim_acme_timeline_concern"],
            source_ids=["src_acme_recent_crm_note"],
        ),
        audit_trace=[
            DecisionAuditEvent(
                event="ranked_bundle_reused",
                message="Decision object includes the Week 1 ranked bundle output.",
            )
        ],
    )

    payload = decision.model_dump(mode="json")

    assert set(payload) == {
        "approval_prompt",
        "audit_trace",
        "blocked_output",
        "bundle_id",
        "confidence",
        "context_request",
        "decision",
        "draft_handoff",
        "metadata",
        "next_action",
        "policy_gates",
        "ranked_bundle",
        "selected_claims",
        "selected_sources",
        "source_citations",
        "summary",
        "weak_points",
    }
    assert payload["decision"] == "auto_handoff"
    assert payload["confidence"]["label"] == "high"
    assert payload["ranked_bundle"]["id"] == "bundle_acme_auto_handoff"
    assert payload["ranked_bundle"]["decision"] == "auto_handoff"
    assert payload["selected_claims"][0]["text"]
    assert payload["source_citations"][0]["source_type"] == "crm_note"
    assert payload["policy_gates"][0]["effect"] == "allows_auto_handoff"
    assert payload["next_action"]["type"] == "prepare_handoff"


def test_automation_decision_requires_structured_confidence() -> None:
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")
    ranked_bundle = rank_bundle(bundle)

    with pytest.raises(ValidationError):
        AutomationDecision(
            bundle_id=bundle.id,
            decision=DecisionType.BLOCKED,
            confidence={"score": 1.2, "label": "high", "reasons": []},
            summary="Blocked decision.",
            ranked_bundle=ranked_bundle,
            next_action={
                "type": "stop",
                "label": "Stop automation",
                "description": "Insufficient reliable evidence.",
            },
        )


def test_decision_contract_rejects_unknown_fields() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    ranked_bundle = rank_bundle(bundle)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AutomationDecision(
            bundle_id=bundle.id,
            decision=DecisionType.AUTO_HANDOFF,
            confidence=DecisionConfidence(score=0.9, label="high"),
            summary="Strong evidence.",
            ranked_bundle=ranked_bundle,
            next_action=NextAction(
                type="prepare_handoff",
                label="Prepare handoff",
                description="Proceed with source-backed context.",
            ),
            unexpected=True,
        )
