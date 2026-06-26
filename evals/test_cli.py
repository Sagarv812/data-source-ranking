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
    assert " bundle." in result.stdout


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
