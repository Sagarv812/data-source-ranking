from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from data_source_ranking.loader import load_source_bundle, load_source_fixture
from data_source_ranking.models import RankedBundle, RankedSource, RankingDimension
from data_source_ranking.ranking import rank_bundle as rank_bundle_file
from data_source_ranking.ranking import rank_source as rank_source_file

app = typer.Typer(help="Evidence-quality ranking prototype CLI.")


@app.callback()
def main() -> None:
    pass


@app.command("rank-source")
def rank_source(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
) -> None:
    fixture = load_source_fixture(path)
    ranked = rank_source_file(fixture.context_need, fixture.source)
    if as_json:
        _print_json(ranked)
        return

    typer.echo(_format_ranked_source(ranked))


@app.command("rank-bundle")
def rank_bundle(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json", help="Print full result as JSON.")] = False,
) -> None:
    bundle = load_source_bundle(path)
    ranked = rank_bundle_file(bundle)
    if as_json:
        _print_json(ranked)
        return

    typer.echo(_format_ranked_bundle(ranked))


def _print_json(result: RankedSource | RankedBundle) -> None:
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))


def _format_ranked_source(ranked: RankedSource) -> str:
    lines = [
        f"Source: {ranked.source_id}",
        f"Tier: {ranked.tier.value}",
        f"Reason: {ranked.metadata['tier_reason']}",
        "",
        "Scores:",
    ]
    lines.extend(
        f"- {dimension.value}: {_score_text(ranked, dimension)}"
        for dimension in RankingDimension
    )
    lines.extend(["", "Weak points:"])
    lines.extend(_weak_point_lines(ranked.weak_points))
    return "\n".join(lines)


def _format_ranked_bundle(ranked: RankedBundle) -> str:
    lines = [
        f"Bundle: {ranked.id}",
        f"Decision: {ranked.decision.value}",
        f"Reason: {ranked.reasons[0] if ranked.reasons else 'No reason recorded.'}",
        "",
        "Sources:",
    ]
    lines.extend(
        f"- {source.source_id}: {source.tier.value}" for source in ranked.ranked_sources
    )
    lines.extend(["", "Weak points:"])
    lines.extend(_weak_point_lines(ranked.weak_points))
    return "\n".join(lines)


def _score_text(ranked: RankedSource, dimension: RankingDimension) -> str:
    score = ranked.scores[dimension.value]
    return f"{score.score:.2f} ({score.label})"


def _weak_point_lines(weak_points: list) -> list[str]:
    if not weak_points:
        return ["- none"]
    return [
        f"- {weak_point.type.value}: {weak_point.message}" for weak_point in weak_points
    ]


if __name__ == "__main__":
    app()
