from __future__ import annotations

import json

from typer.testing import CliRunner

from data_source_ranking.cli import app

runner = CliRunner()


def test_rank_source_command_prints_readable_summary() -> None:
    result = runner.invoke(app, ["rank-source", "fixtures/strong/acme_recent_crm_note.json"])

    assert result.exit_code == 0
    assert "Source: src_acme_recent_crm_note" in result.stdout
    assert "Tier: strong" in result.stdout
    assert "- freshness:" in result.stdout


def test_rank_bundle_command_prints_readable_summary() -> None:
    result = runner.invoke(app, ["rank-bundle", "fixtures/bundles/acme_auto_handoff.json"])

    assert result.exit_code == 0
    assert "Bundle: bundle_acme_auto_handoff" in result.stdout
    assert "Decision: auto_handoff" in result.stdout
    assert "- src_acme_recent_crm_note: strong" in result.stdout


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
