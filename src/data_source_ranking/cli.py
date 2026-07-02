from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from data_source_ranking.agents.loop import run_agent as run_agent_file
from data_source_ranking.agents.state import AgentRunResult
from data_source_ranking.decision_engine import decide as decide_file
from data_source_ranking.decisions import AutomationDecision
from data_source_ranking.feedback import (
    DEFAULT_FEEDBACK_STORE_PATH,
    FeedbackEvent,
    ReliabilitySnapshot,
    append_feedback_event,
    build_reliability_snapshot,
    load_feedback_events,
)
from data_source_ranking.loader import (
    FixtureLoadError,
    is_bundle_fixture,
    is_feedback_fixture,
    is_owner_response_fixture,
    is_review_response_fixture,
    is_simulated_retrieval_fixture,
    load_feedback_fixture,
    load_owner_response_fixture,
    load_review_response_fixture,
    load_simulated_retrieval_fixture,
    load_simulated_retrieval_sources,
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
feedback_app = typer.Typer(help="Record feedback and inspect reliability snapshots.")
app.add_typer(feedback_app, name="feedback")


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
    feedback_store: Annotated[
        Path | None,
        typer.Option("--feedback-store", help="Feedback JSONL store for learned reliability."),
    ] = None,
) -> None:
    fixture = load_source_fixture(path)
    ranked = rank_source_file(
        fixture.context_need,
        fixture.source,
        as_of=_parse_as_of(as_of),
        reliability_defaults=_feedback_reliability_defaults(feedback_store),
    )
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
    feedback_store: Annotated[
        Path | None,
        typer.Option("--feedback-store", help="Feedback JSONL store for learned reliability."),
    ] = None,
) -> None:
    bundle = load_source_bundle(path)
    ranked = rank_bundle_file(
        bundle,
        as_of=_parse_as_of(as_of),
        reliability_defaults=_feedback_reliability_defaults(feedback_store),
    )
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
    feedback_store: Annotated[
        Path | None,
        typer.Option("--feedback-store", help="Feedback JSONL store for learned reliability."),
    ] = None,
) -> None:
    bundle = load_source_bundle(path)
    decision = decide_file(
        bundle,
        as_of=_parse_as_of(as_of),
        reliability_defaults=_feedback_reliability_defaults(feedback_store),
    )
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


@app.command("run-agent", help="Run the bounded deterministic agent loop for a bundle.")
def run_agent(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Override the agent evaluation date."),
    ] = None,
    max_iterations: Annotated[
        int,
        typer.Option("--max-iterations", help="Maximum bounded loop iterations."),
    ] = 3,
    owner_response_path: Annotated[
        Path | None,
        typer.Option(
            "--owner-response",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Owner-response fixture to apply before re-running the loop.",
        ),
    ] = None,
    simulated_retrieval_path: Annotated[
        Path | None,
        typer.Option(
            "--simulated-retrieval",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Simulated-retrieval fixture to apply before re-running the loop.",
        ),
    ] = None,
    feedback_store: Annotated[
        Path | None,
        typer.Option("--feedback-store", help="Feedback JSONL store for learned reliability."),
    ] = None,
) -> None:
    if max_iterations < 1:
        typer.echo("Invalid --max-iterations. Use a value of 1 or greater.", err=True)
        raise typer.Exit(1)
    if owner_response_path and simulated_retrieval_path:
        typer.echo(
            "Use either --owner-response or --simulated-retrieval, not both.",
            err=True,
        )
        raise typer.Exit(1)

    bundle = load_source_bundle(path)
    owner_response_fixture = (
        load_owner_response_fixture(owner_response_path) if owner_response_path else None
    )
    simulated_retrieval_fixture = (
        load_simulated_retrieval_fixture(simulated_retrieval_path)
        if simulated_retrieval_path
        else None
    )
    retrieved_sources = (
        load_simulated_retrieval_sources(simulated_retrieval_path)
        if simulated_retrieval_path
        else None
    )
    if (
        owner_response_fixture
        and owner_response_fixture.response.bundle_id != bundle.id
    ):
        typer.echo(
            "Owner response fixture bundle_id "
            f"{owner_response_fixture.response.bundle_id!r} does not match bundle "
            f"{bundle.id!r}.",
            err=True,
        )
        raise typer.Exit(1)
    if (
        simulated_retrieval_fixture
        and simulated_retrieval_fixture.bundle_id != bundle.id
    ):
        typer.echo(
            "Simulated retrieval fixture bundle_id "
            f"{simulated_retrieval_fixture.bundle_id!r} does not match bundle "
            f"{bundle.id!r}.",
            err=True,
        )
        raise typer.Exit(1)

    effective_as_of = (
        as_of
        or (owner_response_fixture.as_of if owner_response_fixture else None)
        or (simulated_retrieval_fixture.as_of if simulated_retrieval_fixture else None)
        or DEFAULT_AS_OF.isoformat()
    )
    feedback_snapshot = _feedback_snapshot(feedback_store)
    result = run_agent_file(
        bundle,
        as_of=_parse_as_of(effective_as_of),
        max_iterations=max_iterations,
        owner_response=(
            owner_response_fixture.response if owner_response_fixture else None
        ),
        simulated_retrieval=simulated_retrieval_fixture,
        retrieved_sources=retrieved_sources,
        reliability_defaults=(
            feedback_snapshot.reliability_defaults if feedback_snapshot else None
        ),
        feedback_metadata=feedback_snapshot.metadata if feedback_snapshot else None,
    )
    if as_json:
        _print_json(result)
        return

    typer.echo(_format_agent_run_result(result))


@feedback_app.command("add", help="Append a fixture-backed feedback event to the local store.")
def feedback_add(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    store_path: Annotated[
        Path,
        typer.Option("--store-path", help="Feedback JSONL store path."),
    ] = DEFAULT_FEEDBACK_STORE_PATH,
    as_json: Annotated[bool, typer.Option("--json", help="Print appended event as JSON.")] = False,
) -> None:
    fixture = load_feedback_fixture(path)
    event = append_feedback_event(fixture.event, store_path)
    if as_json:
        _print_json(event)
        return

    typer.echo(_format_feedback_add_result(event, store_path))


@feedback_app.command("snapshot", help="Build a reliability snapshot from stored feedback.")
def feedback_snapshot(
    store_path: Annotated[
        Path,
        typer.Option("--store-path", help="Feedback JSONL store path."),
    ] = DEFAULT_FEEDBACK_STORE_PATH,
    as_json: Annotated[bool, typer.Option("--json", help="Print snapshot as JSON.")] = False,
) -> None:
    events = load_feedback_events(store_path)
    snapshot = build_reliability_snapshot(events)
    if as_json:
        _print_json(snapshot)
        return

    typer.echo(_format_reliability_snapshot(snapshot, store_path))


@app.command(
    "validate-fixtures",
    help=(
        "Validate source, bundle, review, owner-response, simulated-retrieval, "
        "and feedback fixture JSON files."
    ),
)
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
    owner_response_count = 0
    simulated_retrieval_count = 0
    feedback_count = 0
    errors: list[str] = []

    for fixture_path in fixture_paths:
        try:
            if is_feedback_fixture(fixture_path):
                load_feedback_fixture(fixture_path)
                feedback_count += 1
            elif is_simulated_retrieval_fixture(fixture_path):
                load_simulated_retrieval_fixture(fixture_path)
                simulated_retrieval_count += 1
            elif is_owner_response_fixture(fixture_path):
                load_owner_response_fixture(fixture_path)
                owner_response_count += 1
            elif is_review_response_fixture(fixture_path):
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
        f"{source_count} source, {bundle_count} bundle, {review_count} review, "
        f"{owner_response_count} owner response, "
        f"{simulated_retrieval_count} simulated retrieval, "
        f"{feedback_count} feedback."
    )


def _print_json(
    result: RankedSource
    | RankedBundle
    | AutomationDecision
    | ReviewResponseResult
    | AgentRunResult
    | FeedbackEvent
    | ReliabilitySnapshot,
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


def _format_feedback_add_result(event: FeedbackEvent, store_path: Path) -> str:
    return "\n".join(
        [
            f"Feedback stored: {event.id}",
            f"Store: {store_path}",
            f"Bundle: {event.bundle_id}",
            f"Decision: {event.decision.value}",
            f"Outcome: {event.decision_outcome.value}",
            "",
            "Source outcomes:",
            *[
                (
                    f"- {outcome.source_id}: {outcome.outcome.value} "
                    f"({outcome.source_type.value}, {outcome.source_system.value})"
                )
                for outcome in event.source_outcomes
            ],
        ]
    )


def _format_reliability_snapshot(snapshot: ReliabilitySnapshot, store_path: Path) -> str:
    lines = [
        f"Feedback store: {store_path}",
        f"Feedback events: {snapshot.metadata['feedback_event_count']}",
        f"Source outcomes: {snapshot.metadata['source_outcome_count']}",
        "",
        "Learned defaults:",
    ]
    if snapshot.reliability_defaults:
        lines.extend(
            f"- {key}: {value:.2f}"
            for key, value in sorted(snapshot.reliability_defaults.items())
        )
    else:
        lines.append("- none")

    lines.extend(["", "Updates:"])
    if snapshot.updates:
        for update in snapshot.updates:
            lines.extend(
                [
                    f"- {update.key}: {update.static_value:.2f} -> "
                    f"{update.learned_value:.2f} ({update.delta:+.2f})",
                    "  reasons:",
                    *_indented_lines(update.reasons),
                ]
            )
    else:
        lines.append("- none")
    return "\n".join(lines)


def _format_agent_run_result(result: AgentRunResult) -> str:
    action = result.steps[-1].action if result.steps else None
    lines = [
        f"Agent run: {result.bundle_id}",
        f"Initial decision: {result.initial_decision.decision.value}",
        f"Final decision: {result.final_decision.decision.value}",
        f"Stop reason: {result.stop_reason.value}",
        f"Execution mode: {result.metadata['execution_mode']}",
        f"Learned feedback: {_learned_feedback_text(result)}",
        "",
        "Selected action:",
    ]
    if action:
        lines.extend(
            [
                f"- {action.type.value}: {action.label}",
                f"  {action.reason}",
            ]
        )
        if question := action.metadata.get("question"):
            lines.append(f"  question: {question}")
    else:
        lines.append("- none")
    lines.extend(_owner_response_lines(result))
    lines.extend(_simulated_retrieval_lines(result))
    lines.extend(["", "Steps:"])
    if result.steps:
        lines.extend(
            f"- #{step.sequence} {step.action.type.value} -> "
            f"{step.stop_reason.value if step.stop_reason else 'none'}"
            for step in result.steps
        )
    else:
        lines.append("- none")
    lines.extend(["", "Audit:"])
    lines.extend(
        f"- #{event.sequence} {event.event_type.value}: {event.title}"
        for event in result.audit_trace.events
    )
    return "\n".join(lines)


def _owner_response_lines(result: AgentRunResult) -> list[str]:
    owner_result = result.state.owner_response_result
    if owner_result:
        lines = [
            "",
            "Owner response:",
            f"- accepted: {str(owner_result.accepted).lower()}",
            f"- source: {owner_result.response.source_id}",
            f"- owner: {owner_result.response.owner_name}",
            "- effects:",
            *_indented_lines(owner_result.applied_effects),
        ]
        if owner_result.validation_errors:
            lines.extend(
                [
                    "- validation errors:",
                    *_indented_lines(owner_result.validation_errors),
                ]
            )
        return lines

    if result.state.owner_responses:
        response = result.state.owner_responses[-1]
        validation_errors = [
            error
            for step in result.steps
            for error in step.metadata.get("validation_errors", [])
            if isinstance(error, str)
        ]
        return [
            "",
            "Owner response:",
            "- accepted: false",
            f"- source: {response.source_id}",
            f"- owner: {response.owner_name}",
            "- effects:",
            *_indented_lines([]),
            "- validation errors:",
            *_indented_lines(validation_errors),
        ]

    return []


def _simulated_retrieval_lines(result: AgentRunResult) -> list[str]:
    retrieval_result = result.state.simulated_retrieval_result
    if not retrieval_result:
        return []

    lines = [
        "",
        "Simulated retrieval:",
        f"- accepted: {str(retrieval_result.accepted).lower()}",
        "- retrieved sources:",
        *_indented_lines([source.id for source in retrieval_result.retrieved_sources]),
        "- added sources:",
        *_indented_lines(retrieval_result.added_source_ids),
        "- skipped duplicate sources:",
        *_indented_lines(retrieval_result.skipped_duplicate_source_ids),
        "- effects:",
        *_indented_lines(retrieval_result.applied_effects),
    ]
    if retrieval_result.validation_errors:
        lines.extend(
            [
                "- validation errors:",
                *_indented_lines(retrieval_result.validation_errors),
            ]
        )
    return lines


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


def _feedback_reliability_defaults(feedback_store: Path | None) -> dict[str, float] | None:
    snapshot = _feedback_snapshot(feedback_store)
    return snapshot.reliability_defaults if snapshot else None


def _feedback_snapshot(feedback_store: Path | None) -> ReliabilitySnapshot | None:
    if feedback_store is None:
        return None
    return build_reliability_snapshot(load_feedback_events(feedback_store))


def _learned_feedback_text(result: AgentRunResult) -> str:
    if result.metadata.get("uses_learned_feedback"):
        return (
            f"applied ({result.metadata['reliability_default_count']} defaults, "
            f"{result.metadata['feedback_event_count']} events)"
        )
    return "not applied"


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
