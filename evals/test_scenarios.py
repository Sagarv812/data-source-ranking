from __future__ import annotations

from pathlib import Path

import pytest

from data_source_ranking.agents.retrieval import SimulatedRetrievalFixture
from data_source_ranking.agents.state import OwnerResponseFixture
from data_source_ranking.loader import (
    FixtureLoadError,
    is_bundle_fixture,
    is_owner_response_fixture,
    is_review_response_fixture,
    is_simulated_retrieval_fixture,
    load_owner_response_fixture,
    load_review_response_fixture,
    load_simulated_retrieval_fixture,
    load_simulated_retrieval_sources,
    load_source_bundle,
    load_source_bundle_fixture,
    load_source_fixture,
)
from data_source_ranking.models import (
    DecisionType,
    DirectnessRelation,
    SourceBundle,
    SourceBundleFixture,
    SourceFixture,
    Tier,
)
from data_source_ranking.review_responses import ReviewResponseFixture

SCENARIO_DIR = Path("fixtures")


def scenario_paths() -> list[Path]:
    return sorted(
        path
        for path in SCENARIO_DIR.rglob("*.json")
        if ".venv" not in path.parts and path.name != "README.md"
    )


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_all_json_scenarios_validate(path: Path) -> None:
    if "simulated_retrieval" in path.parts:
        retrieval_fixture = load_simulated_retrieval_fixture(path)
        assert isinstance(retrieval_fixture, SimulatedRetrievalFixture)
        assert len(load_simulated_retrieval_sources(path)) == len(
            retrieval_fixture.retrieved_source_refs
        )
        return

    if "owner_responses" in path.parts:
        owner_response_fixture = load_owner_response_fixture(path)
        assert isinstance(owner_response_fixture, OwnerResponseFixture)
        return

    if "reviews" in path.parts:
        review_fixture = load_review_response_fixture(path)
        assert isinstance(review_fixture, ReviewResponseFixture)
        return

    if "bundles" in path.parts:
        bundle_fixture = load_source_bundle_fixture(path)
        assert isinstance(bundle_fixture, SourceBundleFixture)

        scenario = load_source_bundle(path)
        assert isinstance(scenario, SourceBundle)
        return

    scenario = load_source_fixture(path)
    assert isinstance(scenario, SourceFixture)


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_all_source_scenarios_include_expected_tier(path: Path) -> None:
    if (
        "bundles" in path.parts
        or "reviews" in path.parts
        or "owner_responses" in path.parts
        or "simulated_retrieval" in path.parts
    ):
        return

    scenario = load_source_fixture(path)

    assert scenario.expected is not None
    assert scenario.expected.tier in {Tier.STRONG, Tier.MEDIUM, Tier.WEAK}


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_all_bundle_scenarios_include_expected_decision(path: Path) -> None:
    if "bundles" not in path.parts:
        return

    scenario = load_source_bundle_fixture(path)

    assert scenario.expected is not None
    assert scenario.expected.decision in {
        DecisionType.AUTO_HANDOFF,
        DecisionType.GENERATE_CONTEXT_REQUEST,
        DecisionType.NEEDS_USER_REVIEW,
        DecisionType.BLOCKED,
    }


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_bundle_refs_resolve_to_sources(path: Path) -> None:
    if "bundles" not in path.parts:
        return

    bundle_fixture = load_source_bundle_fixture(path)
    bundle = load_source_bundle(path)

    assert len(bundle.sources) == len(bundle_fixture.source_refs)
    assert {source.id for source in bundle.sources}


def test_bundle_fixture_detection_uses_json_shape() -> None:
    assert is_bundle_fixture("fixtures/bundles/acme_auto_handoff.json")
    assert not is_bundle_fixture("fixtures/strong/acme_recent_crm_note.json")
    assert not is_bundle_fixture("fixtures/reviews/similar_client_use_directional.json")


def test_review_fixture_detection_uses_json_shape() -> None:
    assert is_review_response_fixture("fixtures/reviews/similar_client_use_directional.json")
    assert not is_review_response_fixture("fixtures/bundles/acme_auto_handoff.json")
    assert not is_review_response_fixture("fixtures/strong/acme_recent_crm_note.json")
    assert not is_review_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    assert not is_review_response_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )


def test_owner_response_fixture_detection_uses_json_shape() -> None:
    assert is_owner_response_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    assert not is_owner_response_fixture("fixtures/reviews/similar_client_use_directional.json")
    assert not is_owner_response_fixture("fixtures/bundles/acme_auto_handoff.json")
    assert not is_owner_response_fixture("fixtures/strong/acme_recent_crm_note.json")
    assert not is_owner_response_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )


def test_simulated_retrieval_fixture_detection_uses_json_shape() -> None:
    assert is_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    assert not is_simulated_retrieval_fixture(
        "fixtures/reviews/similar_client_use_directional.json"
    )
    assert not is_simulated_retrieval_fixture(
        "fixtures/owner_responses/beta_lina_validates_old_proposal.json"
    )
    assert not is_simulated_retrieval_fixture("fixtures/bundles/acme_auto_handoff.json")
    assert not is_simulated_retrieval_fixture("fixtures/strong/acme_recent_crm_note.json")


def test_malformed_json_raises_fixture_load_error(tmp_path: Path) -> None:
    fixture_path = tmp_path / "broken.json"
    fixture_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(FixtureLoadError, match="invalid JSON"):
        load_source_fixture(fixture_path)


def test_missing_required_source_fields_raise_fixture_load_error(tmp_path: Path) -> None:
    fixture_path = tmp_path / "missing_source_fields.json"
    fixture_path.write_text(
        """
        {
          "context_need": {
            "id": "need_test",
            "client_id": "client_test",
            "email_goal": "Prepare context.",
            "needed_claims": [
              {
                "id": "need_claim_current_concern",
                "type": "current_client_concern",
                "description": "Current client concern."
              }
            ]
          },
          "source": {
            "id": "src_missing_title",
            "type": "crm_note",
            "summary": "Client raised timeline risk."
          }
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(FixtureLoadError, match="invalid fixture"):
        load_source_fixture(fixture_path)


def test_broken_bundle_source_ref_raises_fixture_load_error(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle_with_broken_ref.json"
    bundle_path.write_text(
        """
        {
          "id": "bundle_broken",
          "title": "Broken bundle",
          "context_need": {
            "id": "need_test",
            "client_id": "client_test",
            "email_goal": "Prepare context.",
            "needed_claims": [
              {
                "id": "need_claim_current_concern",
                "type": "current_client_concern",
                "description": "Current client concern."
              }
            ]
          },
          "source_refs": [
            "fixtures/strong/does_not_exist.json"
          ]
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(FixtureLoadError, match="does not exist"):
        load_source_bundle(bundle_path)


def test_source_fixture_loaded_as_bundle_raises_fixture_load_error() -> None:
    with pytest.raises(FixtureLoadError, match="invalid fixture"):
        load_source_bundle("fixtures/strong/acme_recent_crm_note.json")


def test_bundle_fixture_loaded_as_source_raises_fixture_load_error() -> None:
    with pytest.raises(FixtureLoadError, match="invalid fixture"):
        load_source_fixture("fixtures/bundles/acme_auto_handoff.json")


def test_bundle_refs_resolve_from_absolute_path_outside_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path = Path("fixtures/bundles/acme_auto_handoff.json").resolve()
    monkeypatch.chdir(tmp_path)

    bundle = load_source_bundle(bundle_path)

    assert {source.id for source in bundle.sources} >= {"src_acme_recent_crm_note"}


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_non_strong_scenarios_include_expected_weak_points(path: Path) -> None:
    if (
        "bundles" in path.parts
        or "reviews" in path.parts
        or "owner_responses" in path.parts
        or "simulated_retrieval" in path.parts
    ):
        return

    scenario = load_source_fixture(path)

    assert scenario.expected is not None
    if scenario.expected.tier is not Tier.STRONG:
        assert scenario.expected.weak_points


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_similar_client_sources_include_similarity_reason(path: Path) -> None:
    if (
        "bundles" in path.parts
        or "reviews" in path.parts
        or "owner_responses" in path.parts
        or "simulated_retrieval" in path.parts
    ):
        return

    scenario = load_source_fixture(path)

    if scenario.source.directness_relation is DirectnessRelation.SIMILAR_CLIENT:
        assert scenario.source.similarity_reason
