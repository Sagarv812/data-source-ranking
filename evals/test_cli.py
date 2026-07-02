from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from data_source_ranking.cli import app
from data_source_ranking.models import RankingDimension

runner = CliRunner()


def test_rank_source_command_prints_readable_summary() -> None:
    result = runner.invoke(app, ["rank-source", "fixtures/strong/acme_recent_crm_note.json"])

    assert result.exit_code == 0
    assert "Source: src_acme_recent_crm_note" in result.stdout
    assert "Tier: strong" in result.stdout
    assert "- freshness:" in result.stdout
    assert "Metadata:" not in result.stdout


def test_rank_bundle_command_prints_readable_summary() -> None:
    result = runner.invoke(app, ["rank-bundle", "fixtures/bundles/acme_auto_handoff.json"])

    assert result.exit_code == 0
    assert "Bundle: bundle_acme_auto_handoff" in result.stdout
    assert "Decision: auto_handoff" in result.stdout
    assert "- src_acme_recent_crm_note: strong" in result.stdout
    assert "Metadata:" not in result.stdout


def test_rank_bundle_command_can_print_json() -> None:
    result = runner.invoke(
        app,
        ["rank-bundle", "fixtures/bundles/acme_auto_handoff.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "bundle_acme_auto_handoff"
    assert payload["decision"] == "auto_handoff"
    assert payload["metadata"]["decision_policy"] == "rule_based_v1"


def test_decide_command_prints_readable_summary() -> None:
    result = runner.invoke(app, ["decide", "fixtures/bundles/beta_needs_owner_validation.json"])

    assert result.exit_code == 0
    assert "Bundle: bundle_beta_needs_owner_validation" in result.stdout
    assert "Decision: generate_context_request" in result.stdout
    assert "Confidence: 0.72 (medium)" in result.stdout
    assert "Context request:" in result.stdout
    assert "to: Lina Rao" in result.stdout
    assert "Policy gates:" in result.stdout


def test_decide_command_prints_blocked_output() -> None:
    result = runner.invoke(app, ["decide", "fixtures/bundles/gamma_blocked.json"])

    assert result.exit_code == 0
    assert "Decision: blocked" in result.stdout
    assert "Blocked output:" in result.stdout
    assert (
        "reason: One or more required claims do not have usable source coverage."
        in result.stdout
    )
    assert "missing evidence:" in result.stdout
    assert "Specific current concern that would make re-engagement relevant." in result.stdout
    assert "sources considered:" in result.stdout
    assert "src_gammahealth_vague_crm_note" in result.stdout
    assert "src_gammahealth_old_generic_deck" in result.stdout
    assert "blocking gates:" in result.stdout
    assert "required_claims_have_usable_coverage" in result.stdout
    assert "owner_signal_available" in result.stdout
    assert "manual next step:" in result.stdout


def test_decide_command_prints_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/northstar_similar_client_review.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "similar_client_directional_context" in result.stdout
    assert "recommended: use_directional_with_label" in result.stdout
    assert "Use as directional" in result.stdout


def test_decide_command_prints_unclear_owner_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/gammahealth_unclear_owner_review.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "unclear_owner" in result.stdout
    assert "recommended: choose_owner" in result.stdout
    assert "Use carefully" in result.stdout


def test_decide_command_prints_sensitive_overlap_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/delta_contradictory_sources.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "sensitive_evidence_overlap" in result.stdout
    assert "recommended: exclude_sensitive_source" in result.stdout
    assert "Exclude sensitive source" in result.stdout


def test_decide_command_prints_unsupported_claim_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/acme_unsupported_claim_review.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "unsupported_claim" in result.stdout
    assert "recommended: remove_claim" in result.stdout
    assert "Use cautiously" in result.stdout


def test_decide_command_prints_sensitive_partner_material_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/deltabank_sensitive_partner_material_review.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "sensitive_partner_material" in result.stdout
    assert "recommended: request_validation" in result.stdout
    assert "Exclude source" in result.stdout


def test_decide_command_prints_old_proposal_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/betaworks_old_proposal_review.json"],
    )

    assert result.exit_code == 0
    assert "Decision: needs_user_review" in result.stdout
    assert "Approval prompt:" in result.stdout
    assert "old_proposal" in result.stdout
    assert "recommended: request_validation" in result.stdout
    assert "Use as historical" in result.stdout


def test_decide_command_can_print_json() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/acme_auto_handoff.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["bundle_id"] == "bundle_acme_auto_handoff"
    assert payload["decision"] == "auto_handoff"
    assert payload["confidence"]["label"] == "high"
    assert payload["next_action"]["type"] == "prepare_handoff"
    assert payload["ranked_bundle"]["id"] == "bundle_acme_auto_handoff"


def test_decide_command_json_includes_blocked_output() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/gamma_blocked.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    blocked_output = payload["blocked_output"]
    assert payload["decision"] == "blocked"
    assert blocked_output["blocking_reason"] == (
        "One or more required claims do not have usable source coverage."
    )
    assert blocked_output["missing_evidence"] == [
        "Specific current concern that would make re-engagement relevant."
    ]
    assert blocked_output["sources_considered"] == [
        "src_gammahealth_vague_crm_note",
        "src_gammahealth_old_generic_deck",
    ]
    assert blocked_output["blocking_policy_gates"] == [
        "required_claims_have_usable_coverage",
        "owner_signal_available",
    ]
    assert payload["draft_handoff"] is None
    assert payload["context_request"] is None
    assert payload["approval_prompt"] is None


def test_decide_command_json_includes_approval_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/northstar_similar_client_review.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "similar_client_directional_context"
    assert prompt["recommended_action"] == "use_directional_with_label"
    assert prompt["choices"][0]["id"] == "use_directional_with_label"
    assert payload["next_action"]["question"] == prompt["question"]


def test_decide_command_json_includes_unclear_owner_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/gammahealth_unclear_owner_review.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "unclear_owner"
    assert prompt["recommended_action"] == "choose_owner"
    assert prompt["choices"][1]["id"] == "use_without_owner"
    assert prompt["choices"][1]["metadata"]["requires_user_acceptance"] is True


def test_decide_command_json_includes_sensitive_overlap_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/delta_contradictory_sources.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "sensitive_evidence_overlap"
    assert prompt["recommended_action"] == "exclude_sensitive_source"
    assert prompt["choices"][0]["id"] == "exclude_sensitive_source"
    assert prompt["metadata"]["sensitive_source_ids"] == [
        "src_deltabank_unverified_partner_material"
    ]


def test_decide_command_json_includes_unsupported_claim_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/acme_unsupported_claim_review.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "unsupported_claim"
    assert prompt["recommended_action"] == "remove_claim"
    assert prompt["choices"][1]["id"] == "use_cautious_wording"
    assert prompt["choices"][1]["metadata"]["risk"] == "unsupported_inference"


def test_decide_command_json_includes_sensitive_partner_material_prompt() -> None:
    result = runner.invoke(
        app,
        [
            "decide",
            "fixtures/bundles/deltabank_sensitive_partner_material_review.json",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "sensitive_partner_material"
    assert prompt["recommended_action"] == "request_validation"
    assert prompt["choices"][1]["id"] == "exclude_sensitive_source"
    assert prompt["metadata"]["source_risks"]["src_deltabank_unverified_partner_material"][
        "source_system"
    ] == "partner_portal"


def test_decide_command_json_includes_old_proposal_prompt() -> None:
    result = runner.invoke(
        app,
        ["decide", "fixtures/bundles/betaworks_old_proposal_review.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    prompt = payload["approval_prompt"]
    assert payload["decision"] == "needs_user_review"
    assert prompt["issue_type"] == "old_proposal"
    assert prompt["recommended_action"] == "request_validation"
    assert prompt["choices"][1]["id"] == "use_historical_context"
    assert prompt["choices"][1]["metadata"]["risk"] == "stale_proposal"


def test_run_agent_command_prints_readable_summary() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/beta_needs_owner_validation.json",
            "--as-of",
            "2026-06-21",
        ],
    )

    assert result.exit_code == 0
    assert "Agent run: bundle_beta_needs_owner_validation" in result.stdout
    assert "Initial decision: generate_context_request" in result.stdout
    assert "Final decision: generate_context_request" in result.stdout
    assert "Stop reason: pending_owner_response" in result.stdout
    assert "Execution mode: single_action_skeleton" in result.stdout
    assert "Selected action:" in result.stdout
    assert "ask_owner: Ask owner for validation" in result.stdout
    assert "question:" in result.stdout
    assert "Steps:" in result.stdout
    assert "#1 ask_owner -> pending_owner_response" in result.stdout
    assert "Audit:" in result.stdout
    assert "#1 bundle_loaded: Bundle loaded" in result.stdout
    assert "#4 action_selected: Action selected" in result.stdout


def test_run_agent_command_can_print_json() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/northstar_similar_client_review.json",
            "--json",
            "--max-iterations",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["bundle_id"] == "bundle_northstar_similar_client_review"
    assert payload["initial_decision"]["decision"] == "needs_user_review"
    assert payload["final_decision"]["decision"] == "needs_user_review"
    assert payload["stop_reason"] == "pending_user_review"
    assert payload["metadata"]["execution_mode"] == "single_action_skeleton"
    assert payload["metadata"]["max_iterations"] == 1
    assert payload["state"]["iteration_count"] == 1
    assert payload["steps"][0]["action"]["type"] == "ask_user_review"
    assert payload["audit_trace"]["events"][-1]["event_type"] == "action_selected"


def test_run_agent_command_applies_owner_response_fixture() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/beta_needs_owner_validation.json",
            "--owner-response",
            "fixtures/owner_responses/beta_lina_validates_old_proposal.json",
        ],
    )

    assert result.exit_code == 0
    assert "Agent run: bundle_beta_needs_owner_validation" in result.stdout
    assert "Initial decision: generate_context_request" in result.stdout
    assert "Final decision: auto_handoff" in result.stdout
    assert "Stop reason: final_decision_ready" in result.stdout
    assert "Execution mode: owner_response_rerun" in result.stdout
    assert "stop_auto_handoff: Prepare handoff" in result.stdout
    assert "Owner response:" in result.stdout
    assert "accepted: true" in result.stdout
    assert "source: src_betaworks_old_proposal_with_owner" in result.stdout
    assert "owner_response_validated" in result.stdout
    assert "source_validation_recorded" in result.stdout
    assert "#2 apply_owner_response -> pending_owner_response" in result.stdout
    assert "#3 stop_auto_handoff -> final_decision_ready" in result.stdout
    assert "owner_response_applied: Owner response applied" in result.stdout


def test_run_agent_command_owner_response_can_print_json() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/beta_needs_owner_validation.json",
            "--owner-response",
            "fixtures/owner_responses/beta_lina_validates_old_proposal.json",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    owner_result = payload["state"]["owner_response_result"]
    validated_source = next(
        source
        for source in payload["state"]["current_sources"]
        if source["id"] == "src_betaworks_old_proposal_with_owner"
    )
    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "owner_response_rerun"
    assert owner_result["accepted"] is True
    assert owner_result["applied_effects"] == [
        "owner_response_validated",
        "source_validation_recorded",
    ]
    assert validated_source["validation_history"][0]["validated_by"]["id"] == "user_lina"
    assert payload["steps"][1]["action"]["type"] == "apply_owner_response"
    assert payload["steps"][2]["action"]["type"] == "stop_auto_handoff"


def test_run_agent_command_as_of_overrides_owner_response_fixture_date() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/beta_needs_owner_validation.json",
            "--owner-response",
            "fixtures/owner_responses/beta_lina_validates_old_proposal.json",
            "--as-of",
            "2026-07-01",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    validated_source = next(
        source
        for source in payload["state"]["current_sources"]
        if source["id"] == "src_betaworks_old_proposal_with_owner"
    )
    assert payload["metadata"]["as_of"] == "2026-07-01"
    assert validated_source["validation_history"][0]["validated_at"] == "2026-07-01"


def test_run_agent_command_rejects_mismatched_owner_response_bundle() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/acme_auto_handoff.json",
            "--owner-response",
            "fixtures/owner_responses/beta_lina_validates_old_proposal.json",
        ],
    )

    assert result.exit_code == 1
    assert "Owner response fixture bundle_id" in result.stderr
    assert "does not match bundle 'bundle_acme_auto_handoff'" in result.stderr


def test_run_agent_command_applies_simulated_retrieval_fixture() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/gamma_blocked.json",
            "--simulated-retrieval",
            "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json",
        ],
    )

    assert result.exit_code == 0
    assert "Agent run: bundle_gamma_blocked" in result.stdout
    assert "Initial decision: blocked" in result.stdout
    assert "Final decision: auto_handoff" in result.stdout
    assert "Stop reason: final_decision_ready" in result.stdout
    assert "Execution mode: simulated_retrieval_rerun" in result.stdout
    assert "stop_auto_handoff: Prepare handoff" in result.stdout
    assert "Simulated retrieval:" in result.stdout
    assert "accepted: true" in result.stdout
    assert "retrieved sources:" in result.stdout
    assert "src_gammahealth_human_validated_context" in result.stdout
    assert "sources_added" in result.stdout
    assert "#2 retrieve_more_context -> blocked_no_reliable_path" in result.stdout
    assert "#3 stop_auto_handoff -> final_decision_ready" in result.stdout
    assert "simulated_retrieval_applied: Simulated retrieval applied" in result.stdout


def test_run_agent_command_simulated_retrieval_can_print_json() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/gamma_blocked.json",
            "--simulated-retrieval",
            "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    retrieval_result = payload["state"]["simulated_retrieval_result"]
    assert payload["initial_decision"]["decision"] == "blocked"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "simulated_retrieval_rerun"
    assert payload["metadata"]["as_of"] == "2026-06-21"
    assert retrieval_result["accepted"] is True
    assert retrieval_result["added_source_ids"] == [
        "src_gammahealth_human_validated_context"
    ]
    assert payload["steps"][1]["action"]["type"] == "retrieve_more_context"
    assert payload["steps"][2]["action"]["type"] == "stop_auto_handoff"


def test_run_agent_command_no_hit_simulated_retrieval_remains_blocked() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/gamma_blocked.json",
            "--simulated-retrieval",
            "fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json",
        ],
    )

    assert result.exit_code == 0
    assert "Agent run: bundle_gamma_blocked" in result.stdout
    assert "Initial decision: blocked" in result.stdout
    assert "Final decision: blocked" in result.stdout
    assert "Stop reason: blocked_no_reliable_path" in result.stdout
    assert "Execution mode: simulated_retrieval_rerun" in result.stdout
    assert "Simulated retrieval:" in result.stdout
    assert "accepted: true" in result.stdout
    assert "retrieved sources:" in result.stdout
    assert "added sources:" in result.stdout
    assert "no_new_sources" in result.stdout
    assert "#1 stop_blocked -> blocked_no_reliable_path" in result.stdout
    assert "#2 retrieve_more_context -> blocked_no_reliable_path" in result.stdout
    assert "#3 stop_auto_handoff" not in result.stdout


def test_run_agent_command_rejects_mismatched_simulated_retrieval_bundle() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/acme_auto_handoff.json",
            "--simulated-retrieval",
            "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json",
        ],
    )

    assert result.exit_code == 1
    assert "Simulated retrieval fixture bundle_id" in result.stderr
    assert "does not match bundle 'bundle_acme_auto_handoff'" in result.stderr


def test_run_agent_command_rejects_combined_owner_response_and_simulated_retrieval() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/beta_needs_owner_validation.json",
            "--owner-response",
            "fixtures/owner_responses/beta_lina_validates_old_proposal.json",
            "--simulated-retrieval",
            "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json",
        ],
    )

    assert result.exit_code == 1
    assert "Use either --owner-response or --simulated-retrieval, not both." in result.stderr


def test_run_agent_command_rejects_invalid_max_iterations() -> None:
    result = runner.invoke(
        app,
        [
            "run-agent",
            "fixtures/bundles/acme_auto_handoff.json",
            "--max-iterations",
            "0",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid --max-iterations. Use a value of 1 or greater." in result.stderr


def test_apply_review_command_prints_readable_summary() -> None:
    result = runner.invoke(
        app,
        ["apply-review", "fixtures/reviews/similar_client_use_directional.json"],
    )

    assert result.exit_code == 0
    assert "Review fixture: fixtures/reviews/similar_client_use_directional.json" in result.stdout
    assert "Bundle: bundle_northstar_similar_client_review" in result.stdout
    assert "Status: accepted" in result.stdout
    assert "Accepted: true" in result.stdout
    assert "Selected choice:" in result.stdout
    assert "use_directional_with_label" in result.stdout
    assert "Applied effects:" in result.stdout
    assert "caveat_accepted" in result.stdout
    assert "Updated decision:" in result.stdout
    assert "decision: needs_user_review" in result.stdout
    assert "next action: manual_review" in result.stdout


def test_apply_review_command_can_print_json() -> None:
    result = runner.invoke(
        app,
        ["apply-review", "fixtures/reviews/similar_client_skip_source.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "accepted"
    assert payload["accepted"] is True
    assert payload["response"]["selected_choice_id"] == "skip_source"
    assert payload["applied_effects"] == [
        "response_validated",
        "choice:skip_source",
        "source_excluded",
    ]
    assert payload["updated_decision"]["decision"] == "blocked"
    assert payload["updated_decision"]["approval_prompt"] is None
    assert payload["updated_decision"]["blocked_output"]["blocking_reason"] == (
        "Review response excluded all selected source evidence."
    )


def test_apply_review_command_supports_owner_selection_fixture() -> None:
    result = runner.invoke(
        app,
        ["apply-review", "fixtures/reviews/unclear_owner_choose_owner.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["applied_effects"] == [
        "response_validated",
        "choice:choose_owner",
        "owner_selected",
    ]
    assert payload["updated_decision"]["decision"] == "generate_context_request"
    assert payload["updated_decision"]["context_request"]["recipient_id"] == "user_priya"
    assert payload["updated_decision"]["next_action"]["type"] == "ask_owner"


def test_apply_review_command_can_show_metadata() -> None:
    result = runner.invoke(
        app,
        [
            "apply-review",
            "fixtures/reviews/old_proposal_use_historical_context.json",
            "--show-metadata",
        ],
    )

    assert result.exit_code == 0
    assert "Metadata:" in result.stdout
    assert '"accepted_caveat": "historical_context_only"' in result.stdout
    assert '"accepted_risk": "stale_proposal"' in result.stdout


def test_rank_source_json_output_shape_is_stable() -> None:
    result = runner.invoke(
        app,
        ["rank-source", "fixtures/strong/acme_recent_crm_note.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "metadata",
        "reasons",
        "scores",
        "source_id",
        "tier",
        "weak_points",
    }
    assert payload["source_id"] == "src_acme_recent_crm_note"
    assert payload["tier"] == "strong"
    assert payload["metadata"]["tier_policy"] == "rule_based_v1"
    assert payload["metadata"]["tier_scope"] == "source_evidence_strength"
    assert set(payload["scores"]) == {dimension.value for dimension in RankingDimension}
    for dimension, score in payload["scores"].items():
        assert_score_shape(score, dimension)


def test_rank_bundle_json_output_shape_is_stable() -> None:
    result = runner.invoke(
        app,
        ["rank-bundle", "fixtures/bundles/acme_auto_handoff.json", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "decision",
        "id",
        "metadata",
        "ranked_sources",
        "reasons",
        "weak_points",
    }
    assert payload["id"] == "bundle_acme_auto_handoff"
    assert payload["decision"] == "auto_handoff"
    assert payload["metadata"]["decision_policy"] == "rule_based_v1"
    assert set(payload["metadata"]) >= {
        "target_needed_claim_ids",
        "strong_coverage",
        "usable_coverage",
        "source_tiers",
    }
    assert payload["ranked_sources"]
    first_source = payload["ranked_sources"][0]
    assert set(first_source["scores"]) == {dimension.value for dimension in RankingDimension}
    assert first_source["metadata"]["tier_scope"] == "source_evidence_strength"
    for dimension, score in first_source["scores"].items():
        assert_score_shape(score, dimension)


def test_rank_source_command_can_show_metadata() -> None:
    result = runner.invoke(
        app,
        [
            "rank-source",
            "fixtures/strong/acme_recent_crm_note.json",
            "--show-metadata",
        ],
    )

    assert result.exit_code == 0
    assert "Metadata:" in result.stdout
    assert '"age_days": 19' in result.stdout
    assert '"tier_policy": "rule_based_v1"' in result.stdout


def test_rank_bundle_command_can_show_metadata() -> None:
    result = runner.invoke(
        app,
        [
            "rank-bundle",
            "fixtures/bundles/acme_auto_handoff.json",
            "--show-metadata",
        ],
    )

    assert result.exit_code == 0
    assert "Metadata:" in result.stdout
    assert '"decision_policy": "rule_based_v1"' in result.stdout
    assert '"source_tiers"' in result.stdout


def test_rank_source_command_respects_as_of_date() -> None:
    result = runner.invoke(
        app,
        [
            "rank-source",
            "fixtures/strong/acme_recent_crm_note.json",
            "--json",
            "--as-of",
            "2026-07-01",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["scores"]["freshness"]["metadata"]["as_of"] == "2026-07-01"
    assert payload["scores"]["freshness"]["metadata"]["age_days"] == 29


def test_rank_bundle_command_respects_as_of_date() -> None:
    result = runner.invoke(
        app,
        [
            "rank-bundle",
            "fixtures/bundles/acme_auto_handoff.json",
            "--json",
            "--as-of",
            "2026-07-01",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    first_source = payload["ranked_sources"][0]
    assert first_source["scores"]["freshness"]["metadata"]["as_of"] == "2026-07-01"


def test_rank_source_command_rejects_invalid_as_of_date() -> None:
    result = runner.invoke(
        app,
        [
            "rank-source",
            "fixtures/strong/acme_recent_crm_note.json",
            "--as-of",
            "07-01-2026",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid --as-of date" in result.stderr


def test_validate_fixtures_command_prints_counts() -> None:
    result = runner.invoke(app, ["validate-fixtures", "fixtures"])

    assert result.exit_code == 0
    assert result.stdout.startswith("Validated ")
    assert " source, " in result.stdout
    assert " bundle, " in result.stdout
    assert " review, " in result.stdout
    assert " owner response, " in result.stdout
    assert " simulated retrieval." in result.stdout


def test_validate_fixtures_command_fails_for_invalid_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text('{"id": "not-a-source-fixture"}', encoding="utf-8")

    result = runner.invoke(app, ["validate-fixtures", str(fixture_path)])

    assert result.exit_code == 1
    assert "Fixture validation failed" in result.stderr
    assert "invalid fixture" in result.stderr


def assert_score_shape(score: dict, expected_dimension: str) -> None:
    assert set(score) == {
        "dimension",
        "label",
        "metadata",
        "reason",
        "score",
        "weak_points",
    }
    assert score["dimension"] == expected_dimension
    assert isinstance(score["score"], float | int)
    assert 0.0 <= score["score"] <= 1.0
    assert isinstance(score["label"], str)
    assert isinstance(score["reason"], str)
    assert isinstance(score["weak_points"], list)
    assert isinstance(score["metadata"], dict)
