from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import api.main
from api.main import app


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: bytes

    def json(self) -> dict:
        return json.loads(self.body.decode("utf-8"))


def get(path: str) -> ApiResponse:
    return asyncio.run(_request("GET", path))


def post(path: str, payload: dict) -> ApiResponse:
    return asyncio.run(_request("POST", path, payload=payload))


async def _request(method: str, path: str, payload: dict | None = None) -> ApiResponse:
    parsed_path = urlsplit(path)
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else b""
    messages = [
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ]
    status_code = 500
    body_parts: list[bytes] = []

    async def receive() -> dict:
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        if message["type"] == "http.response.body":
            body_parts.append(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": method,
        "path": parsed_path.path,
        "raw_path": parsed_path.path.encode("utf-8"),
        "query_string": parsed_path.query.encode("utf-8"),
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("utf-8")),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    await app(scope, receive, send)
    return ApiResponse(status_code=status_code, body=b"".join(body_parts))


def test_health_endpoint_returns_ok() -> None:
    response = get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "data-source-ranking-api",
        "status": "ok",
    }


def test_fixtures_endpoint_lists_fixture_summaries() -> None:
    response = get("/fixtures")

    assert response.status_code == 200
    payload = response.json()
    fixture_by_id = {fixture["id"]: fixture for fixture in payload["fixtures"]}
    assert "bundles/acme_auto_handoff" in fixture_by_id
    assert "strong/acme_recent_crm_note" in fixture_by_id
    assert "reviews/similar_client_use_directional" in fixture_by_id
    assert "owner_responses/beta_lina_validates_old_proposal" in fixture_by_id
    assert "simulated_retrieval/gammahealth_retrieves_validated_context" in fixture_by_id
    assert "feedback/acme_handoff_accepted" in fixture_by_id
    assert fixture_by_id["bundles/acme_auto_handoff"] == {
        "id": "bundles/acme_auto_handoff",
        "kind": "bundle",
        "path": "bundles/acme_auto_handoff.json",
        "title": "Acme auto handoff",
        "object_id": "bundle_acme_auto_handoff",
        "bundle_id": "bundle_acme_auto_handoff",
        "source_id": None,
        "expected_decision": "auto_handoff",
        "expected_tier": None,
    }
    assert payload["counts"]["bundle"] == 9
    assert payload["counts"]["source"] == 18
    assert payload["groups"] == {}


def test_fixtures_endpoint_filters_by_kind() -> None:
    response = get("/fixtures?kind=bundle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == {"bundle": 9}
    assert {fixture["kind"] for fixture in payload["fixtures"]} == {"bundle"}
    assert "bundles/acme_auto_handoff" in {
        fixture["id"] for fixture in payload["fixtures"]
    }


def test_fixtures_endpoint_can_return_grouped_fixtures() -> None:
    response = get("/fixtures?grouped=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == {
        "bundle": 9,
        "feedback": 1,
        "owner_response": 1,
        "review": 8,
        "simulated_retrieval": 2,
        "source": 18,
    }
    assert set(payload["groups"]) == set(payload["counts"])
    assert payload["groups"]["bundle"][0]["id"] == "bundles/acme_auto_handoff"
    assert payload["groups"]["feedback"][0]["id"] == "feedback/acme_handoff_accepted"


def test_fixtures_endpoint_groups_filtered_kind() -> None:
    response = get("/fixtures?kind=review&grouped=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == {"review": 8}
    assert list(payload["groups"]) == ["review"]
    assert len(payload["groups"]["review"]) == 8
    assert {fixture["kind"] for fixture in payload["fixtures"]} == {"review"}


def test_fixtures_endpoint_returns_422_for_invalid_kind_filter() -> None:
    response = get("/fixtures?kind=unknown")

    assert response.status_code == 422


def test_fixture_detail_returns_loaded_bundle_payload() -> None:
    response = get("/fixtures/bundles/acme_auto_handoff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture"]["id"] == "bundles/acme_auto_handoff"
    assert payload["fixture"]["kind"] == "bundle"
    assert payload["payload"]["id"] == "bundle_acme_auto_handoff"
    assert payload["payload"]["context_need"]["email_goal"] == (
        "Prepare account handoff before renewal pitch."
    )
    assert payload["payload"]["sources"][0]["id"] == "src_acme_recent_crm_note"


def test_fixture_detail_returns_source_fixture_payload() -> None:
    response = get("/fixtures/strong/acme_recent_crm_note")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture"]["kind"] == "source"
    assert payload["fixture"]["source_id"] == "src_acme_recent_crm_note"
    assert payload["payload"]["source"]["id"] == "src_acme_recent_crm_note"


def test_fixture_detail_returns_404_for_unknown_fixture() -> None:
    response = get("/fixtures/bundles/does_not_exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fixture not found."}


def test_fixture_detail_rejects_path_traversal() -> None:
    response = get("/fixtures/../pyproject")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fixture not found."}


def test_rank_endpoint_returns_ranked_bundle_for_bundle_fixture() -> None:
    response = post(
        "/rank",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "as_of": "2026-06-21",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "bundle_acme_auto_handoff"
    assert payload["decision"] == "auto_handoff"
    assert payload["ranked_sources"][0]["source_id"] == "src_acme_recent_crm_note"
    assert payload["ranked_sources"][0]["tier"] == "strong"
    assert payload["metadata"]["decision_policy"] == "rule_based_v1"
    assert payload["metadata"]["bundle_title"] == "Acme auto handoff"
    assert payload["metadata"]["source_titles"]["src_acme_recent_crm_note"] == (
        "Acme renewal prep note"
    )


def test_custom_rank_endpoint_returns_ranked_manual_bundle() -> None:
    response = post(
        "/rank/custom",
        {
            "as_of": "2026-06-21",
            "bundle": {
                "id": "bundle_manual_acme",
                "title": "Manual Acme evidence",
                "context_need": {
                    "id": "need_manual_acme",
                    "client_id": "client_manual_acme",
                    "email_goal": "Prepare a renewal handoff.",
                    "needed_claims": [
                        {
                            "id": "need_claim_current_concern",
                            "type": "current_client_concern",
                            "description": "Current client concern.",
                            "required": True,
                        }
                    ],
                    "risk_tolerance": "normal",
                },
                "sources": [
                    {
                        "id": "src_manual_account_note",
                        "type": "crm_note",
                        "title": "Manual account note",
                        "summary": "The client asked for a tighter implementation plan.",
                        "client_id": "client_manual_acme",
                        "directness_relation": "same_client_same_opportunity",
                        "created_at": "2026-06-15",
                        "updated_at": "2026-06-15",
                        "author": {
                            "id": "user_mina",
                            "name": "Mina Patel",
                            "role": "account_owner",
                        },
                        "owner_candidates": [
                            {
                                "id": "user_mina",
                                "name": "Mina Patel",
                                "role": "account_owner",
                                "reason": "Account owner and note author.",
                                "confidence": 0.9,
                            }
                        ],
                        "source_system": "salesforce",
                        "claims": [
                            {
                                "id": "claim_manual_timeline",
                                "text": "The client asked for a tighter implementation plan.",
                                "claim_type": "client_concern",
                                "supports_needed_claim_ids": ["need_claim_current_concern"],
                                "source_ids": ["src_manual_account_note"],
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "bundle_manual_acme"
    assert payload["ranked_sources"][0]["source_id"] == "src_manual_account_note"
    assert payload["metadata"]["bundle_title"] == "Manual Acme evidence"
    assert payload["metadata"]["source_titles"] == {
        "src_manual_account_note": "Manual account note"
    }


def test_decide_endpoint_returns_automation_decision_for_bundle_fixture() -> None:
    response = post(
        "/decide",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "as_of": "2026-06-21",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bundle_id"] == "bundle_beta_needs_owner_validation"
    assert payload["decision"] == "generate_context_request"
    assert payload["context_request"]["recipient_name"] == "Lina Rao"
    assert payload["metadata"]["as_of"] == "2026-06-21"
    assert payload["ranked_bundle"]["id"] == "bundle_beta_needs_owner_validation"


def test_decide_endpoint_uses_request_as_of_date() -> None:
    response = post(
        "/decide",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "as_of": "2026-07-01",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    first_source = payload["ranked_bundle"]["ranked_sources"][0]
    assert payload["metadata"]["as_of"] == "2026-07-01"
    assert first_source["scores"]["freshness"]["metadata"]["as_of"] == "2026-07-01"


def test_rank_endpoint_rejects_non_bundle_fixture() -> None:
    response = post(
        "/rank",
        {"fixture_id": "strong/acme_recent_crm_note"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fixture must be a bundle for this endpoint.",
    }


def test_decide_endpoint_returns_404_for_unknown_fixture() -> None:
    response = post(
        "/decide",
        {"fixture_id": "bundles/does_not_exist"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Fixture not found."}


def test_rank_endpoint_returns_422_for_malformed_body() -> None:
    response = post("/rank", {})

    assert response.status_code == 422


def test_run_agent_endpoint_returns_initial_agent_run() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "as_of": "2026-06-21",
            "max_iterations": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bundle_id"] == "bundle_beta_needs_owner_validation"
    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "generate_context_request"
    assert payload["stop_reason"] == "pending_owner_response"
    assert payload["steps"][0]["action"]["type"] == "ask_owner"
    assert payload["metadata"]["max_iterations"] == 3


def test_run_agent_endpoint_applies_owner_response_fixture() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "owner_response_fixture_id": "owner_responses/beta_lina_validates_old_proposal",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["initial_decision"]["decision"] == "generate_context_request"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "owner_response_rerun"
    assert payload["state"]["owner_response_result"]["accepted"] is True
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "ask_owner",
        "apply_owner_response",
        "stop_auto_handoff",
    ]


def test_run_agent_endpoint_applies_simulated_retrieval_fixture() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/gamma_blocked",
            "simulated_retrieval_fixture_id": (
                "simulated_retrieval/gammahealth_retrieves_validated_context"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["initial_decision"]["decision"] == "blocked"
    assert payload["final_decision"]["decision"] == "auto_handoff"
    assert payload["stop_reason"] == "final_decision_ready"
    assert payload["metadata"]["execution_mode"] == "simulated_retrieval_rerun"
    assert payload["state"]["simulated_retrieval_result"]["added_source_ids"] == [
        "src_gammahealth_human_validated_context"
    ]
    assert [step["action"]["type"] for step in payload["steps"]] == [
        "stop_blocked",
        "retrieve_more_context",
        "stop_auto_handoff",
    ]


def test_run_agent_endpoint_rejects_combined_owner_and_retrieval() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "owner_response_fixture_id": "owner_responses/beta_lina_validates_old_proposal",
            "simulated_retrieval_fixture_id": (
                "simulated_retrieval/gammahealth_retrieves_validated_context"
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Use either owner_response_fixture_id or "
            "simulated_retrieval_fixture_id, not both."
        )
    }


def test_run_agent_endpoint_rejects_invalid_max_iterations() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "max_iterations": 0,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "max_iterations must be at least 1."}


def test_run_agent_endpoint_rejects_wrong_owner_response_kind() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "owner_response_fixture_id": "strong/acme_recent_crm_note",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fixture must be an owner-response fixture.",
    }


def test_run_agent_endpoint_rejects_mismatched_owner_response_bundle() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "owner_response_fixture_id": "owner_responses/beta_lina_validates_old_proposal",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Owner response fixture bundle_id does not match bundle.",
    }


def test_run_agent_endpoint_rejects_wrong_simulated_retrieval_kind() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/gamma_blocked",
            "simulated_retrieval_fixture_id": "strong/acme_recent_crm_note",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fixture must be a simulated-retrieval fixture.",
    }


def test_run_agent_endpoint_rejects_mismatched_simulated_retrieval_bundle() -> None:
    response = post(
        "/run-agent",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "simulated_retrieval_fixture_id": (
                "simulated_retrieval/gammahealth_retrieves_validated_context"
            ),
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Simulated retrieval fixture bundle_id does not match bundle.",
    }


def test_apply_review_endpoint_applies_review_fixture() -> None:
    response = post(
        "/apply-review",
        {"review_fixture_id": "reviews/similar_client_use_directional"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["accepted"] is True
    assert payload["response"]["selected_choice_id"] == "use_directional_with_label"
    assert payload["original_decision"]["bundle_id"] == (
        "bundle_northstar_similar_client_review"
    )
    assert payload["updated_decision"]["decision"] == "needs_user_review"
    assert payload["applied_effects"] == [
        "response_validated",
        "choice:use_directional_with_label",
        "caveat_accepted",
    ]


def test_apply_review_endpoint_allows_as_of_override() -> None:
    response = post(
        "/apply-review",
        {
            "review_fixture_id": "reviews/old_proposal_use_historical_context",
            "as_of": "2026-07-01",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_decision"]["metadata"]["as_of"] == "2026-07-01"
    first_source = payload["original_decision"]["ranked_bundle"]["ranked_sources"][0]
    assert first_source["scores"]["freshness"]["metadata"]["as_of"] == "2026-07-01"


def test_apply_review_endpoint_rejects_non_review_fixture() -> None:
    response = post(
        "/apply-review",
        {"review_fixture_id": "bundles/acme_auto_handoff"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Fixture must be a review fixture."}


def test_apply_review_endpoint_returns_404_for_unknown_review_fixture() -> None:
    response = post(
        "/apply-review",
        {"review_fixture_id": "reviews/does_not_exist"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Fixture not found."}


def test_apply_review_endpoint_returns_422_for_malformed_body() -> None:
    response = post("/apply-review", {})

    assert response.status_code == 422


def test_feedback_endpoint_appends_feedback_fixture_to_api_owned_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", store_path)

    response = post(
        "/feedback",
        {"feedback_fixture_id": "feedback/acme_handoff_accepted"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "feedback_acme_handoff_accepted"
    assert payload["bundle_id"] == "bundle_acme_auto_handoff"
    assert store_path.exists()
    assert store_path.read_text(encoding="utf-8").count("\n") == 1


def test_feedback_snapshot_endpoint_returns_learned_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", store_path)
    post("/feedback", {"feedback_fixture_id": "feedback/acme_handoff_accepted"})

    response = get("/feedback/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reliability_defaults"] == {
        "source_system:salesforce": 0.05,
        "source_type:crm_note": 0.81,
    }
    assert payload["metadata"]["feedback_event_count"] == 1
    assert payload["metadata"]["source_outcome_count"] == 1


def test_feedback_snapshot_endpoint_allows_missing_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "missing_feedback_events.jsonl",
    )

    response = get("/feedback/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reliability_defaults"] == {}
    assert payload["updates"] == []
    assert payload["metadata"]["feedback_event_count"] == 0


def test_feedback_endpoint_rejects_non_feedback_fixture() -> None:
    response = post(
        "/feedback",
        {"feedback_fixture_id": "bundles/acme_auto_handoff"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Fixture must be a feedback fixture."}


def test_feedback_endpoint_returns_404_for_unknown_feedback_fixture() -> None:
    response = post(
        "/feedback",
        {"feedback_fixture_id": "feedback/does_not_exist"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Fixture not found."}


def test_feedback_endpoint_returns_422_for_malformed_body() -> None:
    response = post("/feedback", {})

    assert response.status_code == 422


def test_feedback_snapshot_endpoint_returns_500_for_malformed_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "feedback_events.jsonl"
    store_path.write_text("{not json}\n", encoding="utf-8")
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", store_path)

    response = get("/feedback/snapshot")

    assert response.status_code == 500
    assert "invalid feedback event on line 1" in response.json()["detail"]


def test_admin_reset_local_data_clears_selected_product_stores(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_store_path = tmp_path / "api_runs.jsonl"
    review_store_path = tmp_path / "api_run_reviews.jsonl"
    feedback_store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", run_store_path)
    monkeypatch.setattr(api.main, "API_RUN_REVIEW_STORE_PATH", review_store_path)
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", feedback_store_path)

    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/northstar_similar_client_review"},
    )
    run_id = run_response.json()["run_id"]
    review_response = post(
        f"/runs/{run_id}/review",
        {"selected_choice_id": "use_directional_with_label"},
    )
    feedback_response = post(
        "/feedback",
        {"feedback_fixture_id": "feedback/acme_handoff_accepted"},
    )

    assert run_response.status_code == 200
    assert review_response.status_code == 200
    assert feedback_response.status_code == 200
    assert run_store_path.exists()
    assert review_store_path.exists()
    assert feedback_store_path.exists()

    response = post(
        "/admin/reset-local-data",
        {"runs": True, "reviews": True, "feedback": True},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reset": ["runs", "reviews", "feedback"],
        "counts_before": {"runs": 1, "reviews": 1, "feedback": 1},
    }
    assert not run_store_path.exists()
    assert not review_store_path.exists()
    assert not feedback_store_path.exists()
    assert get("/runs").json() == {"runs": []}
    assert get("/reviews/queue").json() == {"items": [], "counts": {}}
    assert get("/feedback/snapshot").json()["metadata"]["feedback_event_count"] == 0


def test_admin_reset_local_data_requires_a_selected_scope() -> None:
    response = post("/admin/reset-local-data", {})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Choose at least one local data area to reset.",
    }


def test_runs_decide_endpoint_persists_decision_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "api_runs.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", store_path)
    monkeypatch.setattr(
        api.main,
        "API_RUN_REVIEW_STORE_PATH",
        tmp_path / "api_run_reviews.jsonl",
    )

    response = post(
        "/runs/decide",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "as_of": "2026-06-21",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"].startswith("run_")
    assert payload["kind"] == "decision"
    assert payload["bundle_id"] == "bundle_acme_auto_handoff"
    assert payload["fixture_id"] == "bundles/acme_auto_handoff"
    assert payload["request"] == {
        "fixture_id": "bundles/acme_auto_handoff",
        "as_of": "2026-06-21",
    }
    assert payload["result"]["decision"] == "auto_handoff"
    assert store_path.exists()
    assert store_path.read_text(encoding="utf-8").count("\n") == 1

    list_response = get("/runs")
    assert list_response.status_code == 200
    summaries = list_response.json()["runs"]
    assert summaries == [
        {
            "run_id": payload["run_id"],
            "kind": "decision",
            "bundle_id": "bundle_acme_auto_handoff",
            "fixture_id": "bundles/acme_auto_handoff",
            "title": None,
            "created_at": payload["created_at"],
            "decision": "auto_handoff",
            "final_decision": None,
        }
    ]

    detail_response = get(f"/runs/{payload['run_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == payload


def test_runs_custom_decide_endpoint_persists_manual_scenario(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "api_runs.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", store_path)
    payload = {
        "as_of": "2026-06-21",
        "bundle": {
            "id": "bundle_manual_acme",
            "title": "Manual Acme renewal context",
            "context_need": {
                "id": "need_manual_acme",
                "client_id": "client_manual_acme",
                "email_goal": "Prepare a renewal handoff.",
                "needed_claims": [
                    {
                        "id": "need_claim_current_concern",
                        "type": "current_client_concern",
                        "description": "Current concern to mention.",
                        "required": True,
                    }
                ],
                "risk_tolerance": "normal",
            },
            "sources": [
                {
                    "id": "src_manual_crm_note",
                    "type": "crm_note",
                    "title": "Manual CRM note",
                    "summary": "Acme asked for a clearer implementation plan.",
                    "client_id": "client_manual_acme",
                    "directness_relation": "same_client_same_opportunity",
                    "created_at": "2026-06-15",
                    "updated_at": "2026-06-15",
                    "author": {
                        "id": "user_manual_owner",
                        "name": "Mina Patel",
                        "role": "account_owner",
                    },
                    "owner_candidates": [
                        {
                            "id": "user_manual_owner",
                            "name": "Mina Patel",
                            "role": "account_owner",
                            "reason": "Source author and account owner.",
                            "confidence": 0.92,
                        }
                    ],
                    "source_system": "salesforce",
                    "claims": [
                        {
                            "id": "claim_manual_current_concern",
                            "text": "Acme asked for a clearer implementation plan.",
                            "claim_type": "client_concern",
                            "supports_needed_claim_ids": ["need_claim_current_concern"],
                        }
                    ],
                }
            ],
            "metadata": {"created_from": "manual_builder"},
        },
    }

    response = post("/runs/custom/decide", payload)

    assert response.status_code == 200
    run = response.json()
    assert run["kind"] == "decision"
    assert run["bundle_id"] == "bundle_manual_acme"
    assert run["fixture_id"] == "custom/bundle_manual_acme"
    assert run["request"]["source"] == "manual_builder"
    assert run["request"]["scenario_title"] == "Manual Acme renewal context"
    assert run["result"]["bundle_id"] == "bundle_manual_acme"

    list_response = get("/runs")
    assert list_response.status_code == 200
    assert list_response.json()["runs"] == [
        {
            "run_id": run["run_id"],
            "kind": "decision",
            "bundle_id": "bundle_manual_acme",
            "fixture_id": "custom/bundle_manual_acme",
            "title": "Manual Acme renewal context",
            "created_at": run["created_at"],
            "decision": run["result"]["decision"],
            "final_decision": None,
        }
    ]


def test_runs_agent_endpoint_persists_agent_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "api_runs.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", store_path)

    response = post(
        "/runs/agent",
        {
            "fixture_id": "bundles/beta_needs_owner_validation",
            "owner_response_fixture_id": "owner_responses/beta_lina_validates_old_proposal",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "agent"
    assert payload["bundle_id"] == "bundle_beta_needs_owner_validation"
    assert payload["result"]["initial_decision"]["decision"] == "generate_context_request"
    assert payload["result"]["final_decision"]["decision"] == "auto_handoff"
    assert payload["result"]["metadata"]["execution_mode"] == "owner_response_rerun"

    list_response = get("/runs")
    assert list_response.status_code == 200
    assert list_response.json()["runs"] == [
        {
            "run_id": payload["run_id"],
            "kind": "agent",
            "bundle_id": "bundle_beta_needs_owner_validation",
            "fixture_id": "bundles/beta_needs_owner_validation",
            "title": None,
            "created_at": payload["created_at"],
            "decision": None,
            "final_decision": "auto_handoff",
        }
    ]


def test_product_api_workflow_supports_ui_run_review_and_feedback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_RUN_REVIEW_STORE_PATH",
        tmp_path / "api_run_reviews.jsonl",
    )
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "feedback_events.jsonl",
    )

    run_response = post(
        "/runs/decide",
        {
            "fixture_id": "bundles/northstar_similar_client_review",
            "as_of": "2026-06-21",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["result"]["decision"] == "needs_user_review"
    assert run_payload["result"]["approval_prompt"]["issue_type"] == (
        "similar_client_directional_context"
    )

    review_response = post(
        f"/runs/{run_id}/review",
        {
            "selected_choice_id": "use_directional_with_label",
            "responder_id": "local_user",
            "responder_name": "Local User",
            "notes": "Use as labelled directional context in the UI flow.",
        },
    )
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["review_response_result"]["accepted"] is True
    assert review_payload["review_event"]["run_id"] == run_id

    feedback_response = post(
        f"/runs/{run_id}/feedback",
        {
            "decision_outcome": "accepted",
            "source_outcomes": [
                {
                    "source_id": "src_northstar_similar_client_proposal",
                    "outcome": "accepted",
                    "reason": "Reviewer accepted it only as directional evidence.",
                }
            ],
            "metadata": {"submitted_from": "ui_workflow_test"},
        },
    )
    assert feedback_response.status_code == 200
    feedback_payload = feedback_response.json()
    assert feedback_payload["feedback_event"]["metadata"]["run_id"] == run_id
    assert feedback_payload["feedback_event"]["metadata"]["submitted_from"] == (
        "ui_workflow_test"
    )
    assert feedback_payload["feedback_event"]["source_outcomes"][0] == {
        "source_id": "src_northstar_similar_client_proposal",
        "source_type": "proposal",
        "source_system": "drive",
        "outcome": "accepted",
        "reason": "Reviewer accepted it only as directional evidence.",
        "metadata": {},
    }
    assert feedback_payload["feedback_snapshot"]["metadata"]["feedback_event_count"] == 1

    run_detail_response = get(f"/runs/{run_id}")
    assert run_detail_response.status_code == 200
    run_detail = run_detail_response.json()
    assert run_detail["run_id"] == run_id
    assert run_detail["review_events"] == [review_payload["review_event"]]

    snapshot_response = get("/feedback/snapshot")
    assert snapshot_response.status_code == 200
    assert snapshot_response.json() == feedback_payload["feedback_snapshot"]


def test_reviews_queue_endpoint_summarizes_pending_answered_and_learning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_RUN_REVIEW_STORE_PATH",
        tmp_path / "api_run_reviews.jsonl",
    )
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "feedback_events.jsonl",
    )
    pending_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/delta_contradictory_sources"},
    )
    learning_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/northstar_similar_client_review"},
    )
    answered_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/northstar_similar_client_review"},
    )
    learning_run_id = learning_response.json()["run_id"]
    answered_run_id = answered_response.json()["run_id"]

    learning_review_response = post(
        f"/runs/{learning_run_id}/review",
        {
            "selected_choice_id": "use_directional_with_label",
            "notes": "Use as directional context.",
        },
    )
    answered_review_response = post(
        f"/runs/{answered_run_id}/review",
        {
            "selected_choice_id": "use_directional_with_label",
            "notes": "Use as directional context.",
        },
    )
    answered_review_event_id = answered_review_response.json()["review_event"][
        "review_event_id"
    ]
    feedback_response = post(
        f"/runs/{answered_run_id}/feedback",
        {
            "decision_outcome": "blocked_confirmed",
            "metadata": {
                "review_event_id": answered_review_event_id,
                "submitted_from": "review_feedback",
            },
        },
    )

    response = get("/reviews/queue")

    assert pending_response.status_code == 200
    assert learning_review_response.status_code == 200
    assert feedback_response.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    items_by_run_id = {item["run_id"]: item for item in payload["items"]}
    assert items_by_run_id[pending_response.json()["run_id"]]["status"] == "pending_review"
    assert items_by_run_id[learning_run_id]["status"] == "needs_learning"
    assert items_by_run_id[learning_run_id]["latest_review_event_id"] == (
        learning_review_response.json()["review_event"]["review_event_id"]
    )
    assert items_by_run_id[answered_run_id]["status"] == "answered"
    assert items_by_run_id[answered_run_id]["learning_feedback_count"] == 1
    assert payload["counts"] == {
        "answered": 1,
        "needs_learning": 1,
        "pending_review": 1,
    }


def test_runs_review_endpoint_appends_inline_review_event(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_store_path = tmp_path / "api_runs.jsonl"
    review_store_path = tmp_path / "api_run_reviews.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", run_store_path)
    monkeypatch.setattr(api.main, "API_RUN_REVIEW_STORE_PATH", review_store_path)
    run_response = post(
        "/runs/decide",
        {
            "fixture_id": "bundles/northstar_similar_client_review",
            "as_of": "2026-06-21",
        },
    )
    run_payload = run_response.json()

    response = post(
        f"/runs/{run_payload['run_id']}/review",
        {
            "selected_choice_id": "use_directional_with_label",
            "responder_id": "local_user",
            "responder_name": "Local User",
            "notes": "Use as directional context only.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    review_event = payload["review_event"]
    result = payload["review_response_result"]
    assert payload["run"]["run_id"] == run_payload["run_id"]
    assert payload["run"]["review_events"] == [review_event]
    assert review_event["review_event_id"].startswith("review_")
    assert review_event["run_id"] == run_payload["run_id"]
    assert review_event["bundle_id"] == "bundle_northstar_similar_client_review"
    assert review_event["fixture_id"] == "bundles/northstar_similar_client_review"
    assert review_event["request"]["selected_choice_id"] == "use_directional_with_label"
    assert result["accepted"] is True
    assert result["status"] == "accepted"
    assert result["response"]["bundle_id"] == "bundle_northstar_similar_client_review"
    assert result["response"]["prompt_issue_type"] == "similar_client_directional_context"
    assert result["response"]["notes"] == "Use as directional context only."
    assert result["applied_effects"] == [
        "response_validated",
        "choice:use_directional_with_label",
        "caveat_accepted",
    ]
    assert review_store_path.exists()
    assert review_store_path.read_text(encoding="utf-8").count("\n") == 1

    detail_response = get(f"/runs/{run_payload['run_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["review_events"] == [review_event]


def test_runs_review_endpoint_can_review_agent_run_final_decision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_RUN_REVIEW_STORE_PATH",
        tmp_path / "api_run_reviews.jsonl",
    )
    run_response = post(
        "/runs/agent",
        {
            "fixture_id": "bundles/northstar_similar_client_review",
            "as_of": "2026-06-21",
            "max_iterations": 3,
        },
    )
    run_payload = run_response.json()

    response = post(
        f"/runs/{run_payload['run_id']}/review",
        {"selected_choice_id": "skip_source"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_response_result"]["accepted"] is True
    assert payload["review_response_result"]["response"]["selected_choice_id"] == "skip_source"
    assert payload["review_response_result"]["updated_decision"]["decision"] == "blocked"
    assert payload["run"]["review_events"][0]["run_id"] == run_payload["run_id"]


def test_runs_review_endpoint_persists_rejected_prompt_choice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    review_store_path = tmp_path / "api_run_reviews.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_RUN_REVIEW_STORE_PATH", review_store_path)
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/northstar_similar_client_review"},
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/review",
        {"selected_choice_id": "not_a_prompt_choice"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["review_response_result"]
    assert result["accepted"] is False
    assert result["status"] == "rejected"
    assert result["validation_errors"] == [
        "Response selected_choice_id is not valid for the approval prompt."
    ]
    assert payload["run"]["review_events"] == [payload["review_event"]]
    assert review_store_path.read_text(encoding="utf-8").count("\n") == 1


def test_runs_review_endpoint_rejects_run_without_approval_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    review_store_path = tmp_path / "api_run_reviews.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_RUN_REVIEW_STORE_PATH", review_store_path)
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/acme_auto_handoff"},
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/review",
        {"selected_choice_id": "skip_source"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Run does not have an approval prompt to answer.",
    }
    assert not review_store_path.exists()


def test_runs_review_endpoint_returns_404_for_unknown_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_RUN_REVIEW_STORE_PATH",
        tmp_path / "api_run_reviews.jsonl",
    )

    response = post(
        "/runs/run_missing/review",
        {"selected_choice_id": "skip_source"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found."}


def test_runs_detail_endpoint_returns_500_for_malformed_review_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    review_store_path = tmp_path / "api_run_reviews.jsonl"
    review_store_path.write_text("{not json}\n", encoding="utf-8")
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_RUN_REVIEW_STORE_PATH", review_store_path)
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/northstar_similar_client_review"},
    )
    run_id = run_response.json()["run_id"]

    response = get(f"/runs/{run_id}")

    assert response.status_code == 500
    assert "invalid run review event on line 1" in response.json()["detail"]


def test_runs_feedback_endpoint_appends_inline_feedback_event(
    tmp_path: Path,
    monkeypatch,
) -> None:
    feedback_store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", feedback_store_path)
    run_response = post(
        "/runs/decide",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "as_of": "2026-06-21",
        },
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/feedback",
        {
            "decision_outcome": "accepted",
            "generated_handoff_accepted": True,
            "source_outcomes": [
                {
                    "source_id": "src_acme_recent_crm_note",
                    "outcome": "accepted",
                    "reason": "Matched the actual handoff context.",
                }
            ],
            "metadata": {"submitted_from": "api_test"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    event = payload["feedback_event"]
    snapshot = payload["feedback_snapshot"]
    assert event["id"].startswith("feedback_")
    assert event["bundle_id"] == "bundle_acme_auto_handoff"
    assert event["decision"] == "auto_handoff"
    assert event["decision_outcome"] == "accepted"
    assert event["selected_source_ids"] == [
        "src_acme_recent_crm_note",
        "src_acme_recent_meeting_notes_clear_attendees",
    ]
    assert event["rejected_source_ids"] == []
    assert event["generated_handoff_accepted"] is True
    assert event["metadata"]["run_id"] == run_id
    assert event["metadata"]["run_kind"] == "decision"
    assert event["metadata"]["submitted_from"] == "api_test"
    outcomes = {outcome["source_id"]: outcome for outcome in event["source_outcomes"]}
    assert outcomes["src_acme_recent_crm_note"] == {
        "source_id": "src_acme_recent_crm_note",
        "source_type": "crm_note",
        "source_system": "salesforce",
        "outcome": "accepted",
        "reason": "Matched the actual handoff context.",
        "metadata": {},
    }
    assert outcomes["src_acme_recent_meeting_notes_clear_attendees"] == {
        "source_id": "src_acme_recent_meeting_notes_clear_attendees",
        "source_type": "meeting_notes",
        "source_system": "calendar",
        "outcome": "unknown",
        "reason": "No source-level feedback was provided for this selected source.",
        "metadata": {"feedback_source": "default_selected_source"},
    }
    assert snapshot["reliability_defaults"] == {
        "source_system:salesforce": 0.05,
        "source_type:crm_note": 0.81,
    }
    assert snapshot["metadata"]["feedback_event_count"] == 1
    assert snapshot["metadata"]["source_outcome_count"] == 2
    assert feedback_store_path.exists()
    assert feedback_store_path.read_text(encoding="utf-8").count("\n") == 1


def test_runs_feedback_endpoint_defaults_missing_selected_source_outcomes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "feedback_events.jsonl",
    )
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/acme_auto_handoff"},
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/feedback",
        {"decision_outcome": "accepted"},
    )

    assert response.status_code == 200
    event = response.json()["feedback_event"]
    assert event["selected_source_ids"] == [
        "src_acme_recent_crm_note",
        "src_acme_recent_meeting_notes_clear_attendees",
    ]
    assert {
        outcome["source_id"]: outcome["outcome"]
        for outcome in event["source_outcomes"]
    } == {
        "src_acme_recent_crm_note": "unknown",
        "src_acme_recent_meeting_notes_clear_attendees": "unknown",
    }
    assert response.json()["feedback_snapshot"]["reliability_defaults"] == {}


def test_runs_feedback_endpoint_records_rejected_source_outcomes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "feedback_events.jsonl",
    )
    run_response = post(
        "/runs/agent",
        {
            "fixture_id": "bundles/northstar_similar_client_review",
            "as_of": "2026-06-21",
        },
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/feedback",
        {
            "decision_outcome": "rejected",
            "correction_notes": "Similar-client evidence was too indirect.",
            "owner_response_outcome": "not_resolved",
            "source_outcomes": [
                {
                    "source_id": "src_northstar_similar_client_proposal",
                    "outcome": "rejected",
                }
            ],
        },
    )

    assert response.status_code == 200
    event = response.json()["feedback_event"]
    assert event["decision"] == "needs_user_review"
    assert event["decision_outcome"] == "rejected"
    assert event["rejected_source_ids"] == ["src_northstar_similar_client_proposal"]
    assert event["source_outcomes"][0]["source_type"] == "proposal"
    assert event["source_outcomes"][0]["source_system"] == "drive"
    assert event["source_outcomes"][0]["reason"] == (
        "rejected source feedback from run review."
    )
    assert event["owner_response_outcome"] == "not_resolved"
    assert event["correction_notes"] == "Similar-client evidence was too indirect."


def test_runs_feedback_endpoint_rejects_unknown_source_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    feedback_store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", feedback_store_path)
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/acme_auto_handoff"},
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/feedback",
        {
            "decision_outcome": "corrected",
            "source_outcomes": [
                {
                    "source_id": "src_missing",
                    "outcome": "corrected",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Feedback source_id is not available on the run: src_missing.",
    }
    assert not feedback_store_path.exists()


def test_runs_feedback_endpoint_rejects_duplicate_source_feedback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    feedback_store_path = tmp_path / "feedback_events.jsonl"
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(api.main, "API_FEEDBACK_STORE_PATH", feedback_store_path)
    run_response = post(
        "/runs/decide",
        {"fixture_id": "bundles/acme_auto_handoff"},
    )
    run_id = run_response.json()["run_id"]

    response = post(
        f"/runs/{run_id}/feedback",
        {
            "decision_outcome": "accepted",
            "source_outcomes": [
                {
                    "source_id": "src_acme_recent_crm_note",
                    "outcome": "accepted",
                },
                {
                    "source_id": "src_acme_recent_crm_note",
                    "outcome": "rejected",
                },
            ],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Duplicate source feedback for src_acme_recent_crm_note.",
    }
    assert not feedback_store_path.exists()


def test_runs_feedback_endpoint_returns_404_for_unknown_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")
    monkeypatch.setattr(
        api.main,
        "API_FEEDBACK_STORE_PATH",
        tmp_path / "feedback_events.jsonl",
    )

    response = post(
        "/runs/run_missing/feedback",
        {"decision_outcome": "accepted"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found."}


def test_runs_endpoint_allows_empty_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "missing_runs.jsonl")

    response = get("/runs")

    assert response.status_code == 200
    assert response.json() == {"runs": []}


def test_runs_endpoint_returns_404_for_unknown_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "missing_runs.jsonl")

    response = get("/runs/run_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found."}


def test_runs_endpoint_returns_500_for_malformed_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store_path = tmp_path / "api_runs.jsonl"
    store_path.write_text("{not json}\n", encoding="utf-8")
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", store_path)

    response = get("/runs")

    assert response.status_code == 500
    assert "invalid run record on line 1" in response.json()["detail"]


def test_runs_decide_endpoint_rejects_non_bundle_fixture(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")

    response = post(
        "/runs/decide",
        {"fixture_id": "strong/acme_recent_crm_note"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Fixture must be a bundle for this endpoint.",
    }


def test_runs_agent_endpoint_rejects_invalid_max_iterations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api.main, "API_RUN_STORE_PATH", tmp_path / "api_runs.jsonl")

    response = post(
        "/runs/agent",
        {
            "fixture_id": "bundles/acme_auto_handoff",
            "max_iterations": 0,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "max_iterations must be at least 1."}
