from __future__ import annotations

from datetime import date

from data_source_ranking.decision_engine import decide
from data_source_ranking.loader import (
    load_simulated_retrieval_fixture,
    load_simulated_retrieval_sources,
    load_source_bundle,
)
from data_source_ranking.models import DecisionType, WeakPointType


def test_simulated_retrieval_fixture_resolves_retrieved_sources() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    sources = load_simulated_retrieval_sources(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )

    assert fixture.bundle_id == "bundle_gamma_blocked"
    assert fixture.query.needed_claim_ids == ["need_claim_current_concern"]
    assert set(fixture.query.weak_point_types) == {
        WeakPointType.VAGUE_CLAIM,
        WeakPointType.STALE_SOURCE,
        WeakPointType.LOW_DIRECTNESS,
    }
    assert [source.id for source in sources] == ["src_gammahealth_human_validated_context"]


def test_simulated_retrieval_source_improves_gammahealth_blocked_bundle() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    bundle = load_source_bundle("fixtures/bundles/gamma_blocked.json")
    retrieved_sources = load_simulated_retrieval_sources(
        "fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json"
    )
    updated_bundle = bundle.model_copy(
        update={"sources": [*bundle.sources, *retrieved_sources]}
    )

    original_decision = decide(bundle, as_of=date.fromisoformat(fixture.as_of))
    updated_decision = decide(updated_bundle, as_of=date.fromisoformat(fixture.as_of))

    assert original_decision.decision is DecisionType.BLOCKED
    assert fixture.expected is not None
    assert updated_decision.decision is fixture.expected.decision_after_retrieval
    assert updated_decision.selected_sources == fixture.expected.retrieved_source_ids


def test_simulated_retrieval_no_hit_fixture_resolves_no_sources() -> None:
    fixture = load_simulated_retrieval_fixture(
        "fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json"
    )
    sources = load_simulated_retrieval_sources(
        "fixtures/simulated_retrieval/gammahealth_no_retrieval_hit.json"
    )

    assert fixture.bundle_id == "bundle_gamma_blocked"
    assert fixture.retrieved_source_refs == []
    assert sources == []
    assert fixture.expected is not None
    assert fixture.expected.decision_after_retrieval is DecisionType.BLOCKED
