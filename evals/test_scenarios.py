from __future__ import annotations

from pathlib import Path

import pytest

from data_source_ranking.loader import (
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

SCENARIO_DIR = Path("fixtures")


def scenario_paths() -> list[Path]:
    return sorted(
        path
        for path in SCENARIO_DIR.rglob("*.json")
        if ".venv" not in path.parts and path.name != "README.md"
    )


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_all_json_scenarios_validate(path: Path) -> None:
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
    if "bundles" in path.parts:
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


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_non_strong_scenarios_include_expected_weak_points(path: Path) -> None:
    if "bundles" in path.parts:
        return

    scenario = load_source_fixture(path)

    assert scenario.expected is not None
    if scenario.expected.tier is not Tier.STRONG:
        assert scenario.expected.weak_points


@pytest.mark.parametrize("path", scenario_paths(), ids=str)
def test_similar_client_sources_include_similarity_reason(path: Path) -> None:
    if "bundles" in path.parts:
        return

    scenario = load_source_fixture(path)

    if scenario.source.directness_relation is DirectnessRelation.SIMILAR_CLIENT:
        assert scenario.source.similarity_reason
