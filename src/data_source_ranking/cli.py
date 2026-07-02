from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from data_source_ranking.decision_engine import decide as decide_file
from data_source_ranking.decisions import AutomationDecision
from data_source_ranking.loader import (
    FixtureLoadError,
    is_bundle_fixture,
    is_review_response_fixture,
    load_review_response_fixture,
    load_source_bundle,
    load_source_fixture,
)
from data_source_ranking.models import RankedBundle, RankedSource, RankingDimension, WeakPoint
from data_source_ranking.ranking import rank_bundle as rank_bundle_file
from data_source_ranking.ranking import rank_source as rank_source_file
from data_source_ranking.review_responses import (
    ReviewResponseResult,
    apply_review_response,
)
from data_source_ranking.scoring.common import DEFAULT_AS_OF

app = typer.Typer(help="Evidence-quality ranking prototype CLI.")


@app.callback()
def main() -> None:
    pass


@app.command("rank-source", help="Score one source fixture and assign an evidence tier.")
def rank_source(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
    show_metadata: Annotated[
        bool,
        typer.Option("--show-metadata", help="Include scoring metadata in readable output."),
    ] = False,
    as_of: Annotated[
        str,
        typer.Option("--as-of", help="Evaluation date used for freshness scoring."),
    ] = DEFAULT_AS_OF.isoformat(),
) -> None:
    fixture = load_source_fixture(path)
    ranked = rank_source_file(fixture.context_need, fixture.source, as_of=_parse_as_of(as_of))
    if as_json:
        _print_json(ranked)
        return

    typer.echo(_format_ranked_source(ranked, show_metadata=show_metadata))


@app.command("rank-bundle", help="Rank a bundle of sources and return the evidence-layer decision.")
def rank_bundle(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
    show_metadata: Annotated[
        bool,
        typer.Option("--show-metadata", help="Include ranking metadata in readable output."),
    ] = False,
    as_of: Annotated[
        str,
        typer.Option("--as-of", help="Evaluation date used for freshness scoring."),
    ] = DEFAULT_AS_OF.isoformat(),
) -> None:
    bundle = load_source_bundle(path)
    ranked = rank_bundle_file(bundle, as_of=_parse_as_of(as_of))
    if as_json:
        _print_json(ranked)
        return

    typer.echo(_format_ranked_bundle(ranked, show_metadata=show_metadata))


@app.command("decide", help="Produce the product-facing automation decision for a bundle.")
def decide(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
    show_metadata: Annotated[
        bool,
        typer.Option("--show-metadata", help="Include decision metadata in readable output."),
    ] = False,
    as_of: Annotated[
        str,
        typer.Option("--as-of", help="Evaluation date used for freshness scoring."),
    ] = DEFAULT_AS_OF.isoformat(),
) -> None:
    bundle = load_source_bundle(path)
    decision = decide_file(bundle, as_of=_parse_as_of(as_of))
    if as_json:
        _print_json(decision)
        return

    typer.echo(_format_automation_decision(decision, show_metadata=show_metadata))


@app.command("apply-review", help="Apply a fixture-backed approval-prompt response.")
def apply_review(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
    show_metadata: Annotated[
        bool,
        typer.Option("--show-metadata", help="Include review metadata in readable output."),
    ] = False,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Override the review fixture evaluation date."),
    ] = None,
) -> None:
    review_fixture = load_review_response_fixture(path)
    bundle_path = _resolve_review_bundle_path(path, review_fixture.bundle_path)
    bundle = load_source_bundle(bundle_path)
    effective_as_of = as_of or review_fixture.as_of or DEFAULT_AS_OF.isoformat()
    decision = decide_file(bundle, as_of=_parse_as_of(effective_as_of))
    result = apply_review_response(decision, review_fixture.response)
    if as_json:
        _print_json(result)
        return

    typer.echo(
        _format_review_response_result(
            result,
            review_path=path,
            bundle_path=bundle_path,
            show_metadata=show_metadata,
        )
    )


@app.command("validate-fixtures", help="Validate source, bundle, and review fixture JSON files.")
def validate_fixtures(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=True)],
) -> None:
    fixture_paths = _fixture_paths(path)
    if not fixture_paths:
        typer.echo(f"No JSON fixture files found under {path}.", err=True)
        raise typer.Exit(1)

    source_count = 0
    bundle_count = 0
    review_count = 0
    errors: list[str] = []

    for fixture_path in fixture_paths:
        try:
            if is_review_response_fixture(fixture_path):
                load_review_response_fixture(fixture_path)
                review_count += 1
            elif is_bundle_fixture(fixture_path):
                load_source_bundle(fixture_path)
                bundle_count += 1
            else:
                load_source_fixture(fixture_path)
                source_count += 1
        except FixtureLoadError as exc:
            errors.append(str(exc))

    if errors:
        typer.echo(f"Fixture validation failed for {len(errors)} file(s):", err=True)
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(1)

    typer.echo(
        f"Validated {len(fixture_paths)} fixture file(s): "
        f"{source_count} source, {bundle_count} bundle, {review_count} review."
    )


def _print_json(
    result: RankedSource | RankedBundle | AutomationDecision | ReviewResponseResult,
) -> None:
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))


def _format_ranked_source(ranked: RankedSource, show_metadata: bool = False) -> str:
    lines = [
        f"Source: {ranked.source_id}",
        f"Tier: {ranked.tier.value}",
        f"Reason: {ranked.metadata['tier_reason']}",
        "",
        "Scores:",
    ]
    for dimension in RankingDimension:
        lines.append(f"- {dimension.value}: {_score_text(ranked, dimension)}")
        if show_metadata:
            score = ranked.scores[dimension.value]
            lines.append(f"  metadata: {_metadata_text(score.metadata)}")
    lines.extend(["", "Weak points:"])
    lines.extend(_weak_point_lines(ranked.weak_points))
    if show_metadata:
        lines.extend(["", "Metadata:", _metadata_text(ranked.metadata)])
    return "\n".join(lines)


def _format_ranked_bundle(ranked: RankedBundle, show_metadata: bool = False) -> str:
    lines = [
        f"Bundle: {ranked.id}",
        f"Decision: {ranked.decision.value}",
        f"Reason: {ranked.reasons[0] if ranked.reasons else 'No reason recorded.'}",
        "",
        "Sources:",
    ]
    for source in ranked.ranked_sources:
        lines.append(f"- {source.source_id}: {source.tier.value}")
        if show_metadata:
            lines.append(f"  metadata: {_metadata_text(source.metadata)}")
    lines.extend(["", "Weak points:"])
    lines.extend(_weak_point_lines(ranked.weak_points))
    if show_metadata:
        lines.extend(["", "Metadata:", _metadata_text(ranked.metadata)])
    return "\n".join(lines)


def _format_automation_decision(
    decision: AutomationDecision,
    show_metadata: bool = False,
) -> str:
    lines = [
        f"Bundle: {decision.bundle_id}",
        f"Decision: {decision.decision.value}",
        f"Confidence: {decision.confidence.score:.2f} ({decision.confidence.label.value})",
        f"Summary: {decision.summary}",
        "",
        "Selected sources:",
        *_source_lines(decision.selected_sources),
        "",
        "Next action:",
        f"- {decision.next_action.type.value}: {decision.next_action.label}",
        f"  {decision.next_action.description}",
    ]
    if decision.next_action.question:
        lines.append(f"  question: {decision.next_action.question}")
    if decision.context_request:
        lines.extend(
            [
                "",
                "Context request:",
                f"- to: {decision.context_request.recipient_name}",
                f"- why: {decision.context_request.recipient_reason}",
                f"- question: {decision.context_request.question}",
            ]
        )
    if decision.approval_prompt:
        lines.extend(
            [
                "",
                "Approval prompt:",
                f"- {decision.approval_prompt.issue_type}: {decision.approval_prompt.question}",
                f"  recommended: {decision.approval_prompt.recommended_action}",
                "  choices:",
                *[
                    f"  - {choice.id}: {choice.label} ({choice.effect})"
                    for choice in decision.approval_prompt.choices
                ],
            ]
        )
    if decision.draft_handoff:
        lines.extend(["", "Draft handoff:", decision.draft_handoff.text])
    if decision.blocked_output:
        lines.extend(
            [
                "",
                "Blocked output:",
                f"- reason: {decision.blocked_output.blocking_reason}",
                "- missing evidence:",
                *_indented_lines(decision.blocked_output.missing_evidence),
                "- sources considered:",
                *_indented_lines(decision.blocked_output.sources_considered),
                "- blocking gates:",
                *_indented_lines(decision.blocked_output.blocking_policy_gates),
                f"- manual next step: {decision.blocked_output.manual_next_step}",
            ]
        )
    lines.extend(["", "Policy gates:"])
    lines.extend(
        f"- {gate.gate}: {gate.status.value} ({gate.effect.value})"
        for gate in decision.policy_gates
    )
    lines.extend(["", "Weak points:"])
    lines.extend(_weak_point_lines(decision.weak_points))
    if show_metadata:
        lines.extend(["", "Metadata:", _metadata_text(decision.metadata)])
    return "\n".join(lines)


def _format_review_response_result(
    result: ReviewResponseResult,
    review_path: Path,
    bundle_path: Path,
    show_metadata: bool = False,
) -> str:
    lines = [
        f"Review fixture: {review_path}",
        f"Bundle fixture: {bundle_path}",
        f"Bundle: {result.original_decision.bundle_id}",
        f"Status: {result.status.value}",
        f"Accepted: {str(result.accepted).lower()}",
        "",
        "Selected choice:",
        f"- {result.response.selected_choice_id}",
        "",
        "Applied effects:",
        *_indented_lines(result.applied_effects),
    ]
    if result.validation_errors:
        lines.extend(["", "Validation errors:", *_indented_lines(result.validation_errors)])
    if result.updated_decision:
        lines.extend(
            [
                "",
                "Updated decision:",
                f"- decision: {result.updated_decision.decision.value}",
                f"- summary: {result.updated_decision.summary}",
                f"- next action: {result.updated_decision.next_action.type.value}",
            ]
        )
        if result.updated_decision.next_action.question:
            lines.append(f"- question: {result.updated_decision.next_action.question}")
    else:
        lines.extend(["", "Updated decision:", "- none"])
    if show_metadata:
        lines.extend(["", "Metadata:", _metadata_text(result.metadata)])
    return "\n".join(lines)


def _source_lines(source_ids: list[str]) -> list[str]:
    if not source_ids:
        return ["- none"]
    return [f"- {source_id}" for source_id in source_ids]


def _indented_lines(values: list[str]) -> list[str]:
    if not values:
        return ["  - none"]
    return [f"  - {value}" for value in values]


def _score_text(ranked: RankedSource, dimension: RankingDimension) -> str:
    score = ranked.scores[dimension.value]
    return f"{score.score:.2f} ({score.label})"


def _weak_point_lines(weak_points: list[WeakPoint]) -> list[str]:
    if not weak_points:
        return ["- none"]
    return [
        f"- {weak_point.type.value}: {weak_point.message}" for weak_point in weak_points
    ]


def _metadata_text(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata, sort_keys=True)


def _fixture_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix == ".json" else []
    return sorted(file_path for file_path in path.rglob("*.json") if file_path.is_file())


def _resolve_review_bundle_path(review_path: Path, bundle_path_value: str) -> Path:
    bundle_path = Path(bundle_path_value)
    if bundle_path.is_absolute() or bundle_path.exists():
        return bundle_path

    relative_to_review = review_path.parent / bundle_path
    if relative_to_review.exists():
        return relative_to_review

    relative_to_fixture_root = _relative_to_fixture_root(review_path, bundle_path)
    if relative_to_fixture_root and relative_to_fixture_root.exists():
        return relative_to_fixture_root

    raise FixtureLoadError(
        f"bundle path {bundle_path_value!r} from review fixture {review_path} does not exist"
    )


def _relative_to_fixture_root(review_path: Path, bundle_path: Path) -> Path | None:
    review_path = review_path.resolve()
    fixture_root = next(
        (parent for parent in review_path.parents if parent.name == "fixtures"),
        None,
    )
    if fixture_root is None or not bundle_path.parts or bundle_path.parts[0] != "fixtures":
        return None
    return fixture_root.parent / bundle_path


def _parse_as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        typer.echo(f"Invalid --as-of date {value!r}. Use YYYY-MM-DD.", err=True)
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
