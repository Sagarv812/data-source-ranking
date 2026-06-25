from __future__ import annotations

from data_source_ranking.loader import load_source_bundle
from data_source_ranking.models import DimensionScore, RankingDimension
from data_source_ranking.scoring import (
    AuthorityScorer,
    CompletenessScorer,
    CorroborationScorer,
    DirectnessScorer,
    FreshnessScorer,
    HistoricalReliabilityScorer,
    OwnershipSignalScorer,
    ScoringContext,
    SensitivityScorer,
    SpecificityScorer,
)


def test_all_dimension_scorers_run_for_one_source() -> None:
    bundle = load_source_bundle("fixtures/bundles/acme_auto_handoff.json")
    source = next(source for source in bundle.sources if source.id == "src_acme_recent_crm_note")
    context = ScoringContext(
        context_need=bundle.context_need,
        source=source,
        bundle_sources=bundle.sources,
    )
    scorers = [
        FreshnessScorer(),
        DirectnessScorer(),
        AuthorityScorer(),
        OwnershipSignalScorer(),
        CompletenessScorer(),
        CorroborationScorer(),
        SensitivityScorer(),
        SpecificityScorer(),
        HistoricalReliabilityScorer(),
    ]

    scores = [scorer.score(context) for scorer in scorers]

    assert all(isinstance(score, DimensionScore) for score in scores)
    assert {score.dimension for score in scores} == set(RankingDimension)
    assert all(score.reason for score in scores)
    assert all(0.0 <= score.score <= 1.0 for score in scores)

