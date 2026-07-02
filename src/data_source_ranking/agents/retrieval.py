from __future__ import annotations

from typing import Any

from pydantic import Field

from data_source_ranking.models import (
    DecisionType,
    Source,
    SourceBundle,
    StrictModel,
    WeakPointType,
)


class SimulatedRetrievalQuery(StrictModel):
    needed_claim_ids: list[str] = Field(default_factory=list)
    weak_point_types: list[WeakPointType] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulatedRetrievalExpected(StrictModel):
    decision_after_retrieval: DecisionType | None = None
    retrieved_source_ids: list[str] = Field(default_factory=list)


class SimulatedRetrievalFixture(StrictModel):
    bundle_id: str = Field(min_length=1)
    as_of: str | None = None
    query: SimulatedRetrievalQuery
    retrieved_source_refs: list[str] = Field(default_factory=list)
    expected: SimulatedRetrievalExpected | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulatedRetrievalResult(StrictModel):
    accepted: bool
    fixture: SimulatedRetrievalFixture
    original_bundle: SourceBundle
    updated_bundle: SourceBundle | None = None
    retrieved_sources: list[Source] = Field(default_factory=list)
    added_source_ids: list[str] = Field(default_factory=list)
    skipped_duplicate_source_ids: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    applied_effects: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def apply_simulated_retrieval(
    bundle: SourceBundle,
    fixture: SimulatedRetrievalFixture,
    retrieved_sources: list[Source],
) -> SimulatedRetrievalResult:
    errors = _validation_errors(bundle, fixture)
    if errors:
        return SimulatedRetrievalResult(
            accepted=False,
            fixture=fixture,
            original_bundle=bundle,
            retrieved_sources=retrieved_sources,
            validation_errors=errors,
            metadata=_metadata(fixture, retrieved_sources),
        )

    existing_source_ids = {source.id for source in bundle.sources}
    added_sources = [
        source for source in retrieved_sources if source.id not in existing_source_ids
    ]
    skipped_duplicate_source_ids = [
        source.id for source in retrieved_sources if source.id in existing_source_ids
    ]
    updated_bundle = bundle.model_copy(
        update={"sources": [*bundle.sources, *added_sources]}
    )
    return SimulatedRetrievalResult(
        accepted=True,
        fixture=fixture,
        original_bundle=bundle,
        updated_bundle=updated_bundle,
        retrieved_sources=retrieved_sources,
        added_source_ids=[source.id for source in added_sources],
        skipped_duplicate_source_ids=skipped_duplicate_source_ids,
        applied_effects=[
            "retrieval_fixture_validated",
            "sources_added" if added_sources else "no_new_sources",
        ],
        metadata={
            **_metadata(fixture, retrieved_sources),
            "added_source_count": len(added_sources),
            "skipped_duplicate_source_count": len(skipped_duplicate_source_ids),
        },
    )


def _validation_errors(
    bundle: SourceBundle,
    fixture: SimulatedRetrievalFixture,
) -> list[str]:
    errors: list[str] = []
    if fixture.bundle_id != bundle.id:
        errors.append("Simulated retrieval bundle_id does not match the source bundle.")
    return errors


def _metadata(
    fixture: SimulatedRetrievalFixture,
    retrieved_sources: list[Source],
) -> dict[str, Any]:
    return {
        "bundle_id": fixture.bundle_id,
        "needed_claim_ids": fixture.query.needed_claim_ids,
        "weak_point_types": [
            weak_point_type.value for weak_point_type in fixture.query.weak_point_types
        ],
        "search_terms": fixture.query.search_terms,
        "retrieved_source_ids": [source.id for source in retrieved_sources],
    }
