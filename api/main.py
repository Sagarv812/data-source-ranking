from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field

from api import settings
from api.run_store import (
    ApiRunKind,
    ApiRunListResponse,
    ApiRunRecord,
    ApiRunReviewEvent,
    RunStoreError,
    append_run_record,
    append_run_review_event,
    create_run_record,
    create_run_review_event,
    load_run_records,
    load_run_review_events,
    run_summary,
)
from data_source_ranking.agents.loop import run_agent
from data_source_ranking.agents.retrieval import SimulatedRetrievalFixture
from data_source_ranking.agents.state import AgentRunResult, OwnerResponseFixture
from data_source_ranking.decision_engine import decide
from data_source_ranking.decisions import AutomationDecision
from data_source_ranking.feedback import (
    DecisionOutcome,
    FeedbackEvent,
    FeedbackStoreError,
    ReliabilitySnapshot,
    SourceOutcome,
    SourceOutcomeStatus,
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
    load_source_bundle_fixture,
    load_source_fixture,
    resolve_review_bundle_path,
)
from data_source_ranking.models import (
    RankedBundle,
    Source,
    SourceBundle,
    SourceSystem,
    SourceType,
    StrictModel,
)
from data_source_ranking.ranking import rank_bundle
from data_source_ranking.review_responses import (
    ReviewResponse,
    ReviewResponseFixture,
    ReviewResponseResult,
    apply_review_response,
)
from data_source_ranking.scoring.common import DEFAULT_AS_OF

API_FIXTURE_ROOT = settings.API_FIXTURE_ROOT
API_FEEDBACK_STORE_PATH = settings.API_FEEDBACK_STORE_PATH
API_RUN_STORE_PATH = settings.API_RUN_STORE_PATH
API_RUN_REVIEW_STORE_PATH = settings.API_RUN_REVIEW_STORE_PATH


class FixtureKind(StrEnum):
    SOURCE = "source"
    BUNDLE = "bundle"
    REVIEW = "review"
    OWNER_RESPONSE = "owner_response"
    SIMULATED_RETRIEVAL = "simulated_retrieval"
    FEEDBACK = "feedback"


class HealthResponse(StrictModel):
    status: str = "ok"
    service: str = "data-source-ranking-api"


class FixtureSummary(StrictModel):
    id: str = Field(min_length=1)
    kind: FixtureKind
    path: str = Field(min_length=1)
    title: str = Field(min_length=1)
    object_id: str | None = None
    bundle_id: str | None = None
    source_id: str | None = None
    expected_decision: str | None = None
    expected_tier: str | None = None


class FixtureListResponse(StrictModel):
    fixtures: list[FixtureSummary]
    groups: dict[str, list[FixtureSummary]] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)


class FixtureDetailResponse(StrictModel):
    fixture: FixtureSummary
    payload: dict[str, Any]


class FixtureRunRequest(StrictModel):
    fixture_id: str = Field(min_length=1)
    as_of: date = DEFAULT_AS_OF


class AgentRunRequest(FixtureRunRequest):
    max_iterations: int = 3
    owner_response_fixture_id: str | None = None
    simulated_retrieval_fixture_id: str | None = None


class ApplyReviewRequest(StrictModel):
    review_fixture_id: str = Field(min_length=1)
    as_of: date | None = None


class RunReviewRequest(StrictModel):
    selected_choice_id: str = Field(min_length=1)
    responder_id: str = "local_user"
    responder_name: str = "Local User"
    selected_owner_id: str | None = None
    selected_owner_name: str | None = None
    user_accepts_risk: bool = False
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunReviewResponse(StrictModel):
    run: ApiRunRecord
    review_event: ApiRunReviewEvent
    review_response_result: ReviewResponseResult


class RunSourceFeedbackRequest(StrictModel):
    source_id: str = Field(min_length=1)
    outcome: SourceOutcomeStatus
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunFeedbackRequest(StrictModel):
    decision_outcome: DecisionOutcome
    source_outcomes: list[RunSourceFeedbackRequest] = Field(default_factory=list)
    generated_handoff_accepted: bool | None = None
    correction_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunFeedbackResponse(StrictModel):
    feedback_event: FeedbackEvent
    feedback_snapshot: ReliabilitySnapshot


class FeedbackRequest(StrictModel):
    feedback_fixture_id: str = Field(min_length=1)


app = FastAPI(
    title="Data Source Ranking API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/fixtures", response_model=FixtureListResponse)
async def list_fixtures(
    kind: FixtureKind | None = None,
    grouped: bool = False,
) -> FixtureListResponse:
    fixtures = [
        summary
        for summary in [_fixture_summary(path) for path in _fixture_paths()]
        if kind is None or summary.kind is kind
    ]
    return FixtureListResponse(
        fixtures=fixtures,
        groups=_fixture_groups(fixtures) if grouped else {},
        counts=_fixture_counts(fixtures),
    )


@app.get("/fixtures/{fixture_id:path}", response_model=FixtureDetailResponse)
async def get_fixture(fixture_id: str) -> FixtureDetailResponse:
    path = _fixture_path(fixture_id)
    summary = _fixture_summary(path)
    return FixtureDetailResponse(
        fixture=summary,
        payload=_fixture_payload(path, summary.kind),
    )


@app.post("/rank", response_model=RankedBundle)
async def rank(request: FixtureRunRequest) -> RankedBundle:
    return rank_bundle(_bundle_from_request(request), as_of=request.as_of)


@app.post("/decide", response_model=AutomationDecision)
async def decide_automation(request: FixtureRunRequest) -> AutomationDecision:
    return _decide_from_request(request)


@app.post("/run-agent", response_model=AgentRunResult)
async def run_agent_endpoint(request: AgentRunRequest) -> AgentRunResult:
    return _agent_run_from_request(request)


@app.post("/runs/decide", response_model=ApiRunRecord)
async def create_decision_run(request: FixtureRunRequest) -> ApiRunRecord:
    decision = _decide_from_request(request)
    return _append_api_run(
        ApiRunKind.DECISION,
        bundle_id=decision.bundle_id,
        fixture_id=request.fixture_id,
        request=request.model_dump(mode="json"),
        result=decision.model_dump(mode="json"),
    )


@app.post("/runs/agent", response_model=ApiRunRecord)
async def create_agent_run(request: AgentRunRequest) -> ApiRunRecord:
    result = _agent_run_from_request(request)
    return _append_api_run(
        ApiRunKind.AGENT,
        bundle_id=result.bundle_id,
        fixture_id=request.fixture_id,
        request=request.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )


@app.get("/runs", response_model=ApiRunListResponse)
async def list_runs() -> ApiRunListResponse:
    try:
        records = load_run_records(API_RUN_STORE_PATH)
    except RunStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiRunListResponse(runs=[run_summary(record) for record in records])


@app.get("/runs/{run_id}", response_model=ApiRunRecord)
async def get_run(run_id: str) -> ApiRunRecord:
    return _run_record_with_review_events(_api_run_by_id(run_id))


@app.post("/runs/{run_id}/review", response_model=RunReviewResponse)
async def review_run(run_id: str, request: RunReviewRequest) -> RunReviewResponse:
    record = _api_run_by_id(run_id)
    existing_events = _run_review_events_for_run(run_id)
    decision = _reviewable_decision_from_run(record)
    review_response = _review_response_from_request(decision, request)
    result = apply_review_response(decision, review_response)
    event = create_run_review_event(
        run_id=record.run_id,
        bundle_id=record.bundle_id,
        fixture_id=record.fixture_id,
        request=request.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    try:
        append_run_review_event(event, API_RUN_REVIEW_STORE_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RunReviewResponse(
        run=record.model_copy(update={"review_events": [*existing_events, event]}),
        review_event=event,
        review_response_result=result,
    )


@app.post("/runs/{run_id}/feedback", response_model=RunFeedbackResponse)
async def record_run_feedback(
    run_id: str,
    request: RunFeedbackRequest,
) -> RunFeedbackResponse:
    record = _api_run_by_id(run_id)
    decision = _decision_from_run(record)
    event = _feedback_event_from_request(record, decision, request)
    try:
        stored_event = append_feedback_event(event, API_FEEDBACK_STORE_PATH)
        snapshot = build_reliability_snapshot(load_feedback_events(API_FEEDBACK_STORE_PATH))
    except FeedbackStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RunFeedbackResponse(
        feedback_event=stored_event,
        feedback_snapshot=snapshot,
    )


def _agent_run_from_request(request: AgentRunRequest) -> AgentRunResult:
    if request.max_iterations < 1:
        raise HTTPException(
            status_code=400,
            detail="max_iterations must be at least 1.",
        )
    if request.owner_response_fixture_id and request.simulated_retrieval_fixture_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Use either owner_response_fixture_id or "
                "simulated_retrieval_fixture_id, not both."
            ),
        )
    bundle = _bundle_from_request(request)
    owner_response_fixture = _optional_owner_response_fixture(
        request.owner_response_fixture_id,
        bundle.id,
    )
    simulated_retrieval_fixture = _optional_simulated_retrieval_fixture(
        request.simulated_retrieval_fixture_id,
        bundle.id,
    )
    retrieved_sources = (
        load_simulated_retrieval_sources(
            _fixture_path(request.simulated_retrieval_fixture_id)
        )
        if request.simulated_retrieval_fixture_id
        else None
    )
    return run_agent(
        bundle,
        as_of=request.as_of,
        max_iterations=request.max_iterations,
        owner_response=(
            owner_response_fixture.response if owner_response_fixture else None
        ),
        simulated_retrieval=simulated_retrieval_fixture,
        retrieved_sources=retrieved_sources,
    )


@app.post("/apply-review", response_model=ReviewResponseResult)
async def apply_review_endpoint(request: ApplyReviewRequest) -> ReviewResponseResult:
    path = _fixture_path(request.review_fixture_id)
    review_fixture = _review_fixture(path)
    bundle_path = _review_bundle_path(path, review_fixture)
    try:
        bundle = load_source_bundle(bundle_path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    effective_as_of = (
        request.as_of
        or (date.fromisoformat(review_fixture.as_of) if review_fixture.as_of else None)
        or DEFAULT_AS_OF
    )
    decision = decide(bundle, as_of=effective_as_of)
    return apply_review_response(decision, review_fixture.response)


@app.post("/feedback", response_model=FeedbackEvent)
async def record_feedback(request: FeedbackRequest) -> FeedbackEvent:
    path = _fixture_path(request.feedback_fixture_id)
    if _fixture_kind(path) is not FixtureKind.FEEDBACK:
        raise HTTPException(
            status_code=400,
            detail="Fixture must be a feedback fixture.",
        )
    try:
        fixture = load_feedback_fixture(path)
        return append_feedback_event(fixture.event, API_FEEDBACK_STORE_PATH)
    except (FixtureLoadError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/feedback/snapshot", response_model=ReliabilitySnapshot)
async def feedback_snapshot() -> ReliabilitySnapshot:
    try:
        return build_reliability_snapshot(load_feedback_events(API_FEEDBACK_STORE_PATH))
    except FeedbackStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _fixture_paths() -> list[Path]:
    return sorted(path for path in API_FIXTURE_ROOT.rglob("*.json") if path.is_file())


def _fixture_groups(fixtures: list[FixtureSummary]) -> dict[str, list[FixtureSummary]]:
    groups = {kind.value: [] for kind in FixtureKind}
    for fixture in fixtures:
        groups[fixture.kind.value].append(fixture)
    return {kind: values for kind, values in groups.items() if values}


def _fixture_counts(fixtures: list[FixtureSummary]) -> dict[str, int]:
    counts = {kind.value: 0 for kind in FixtureKind}
    for fixture in fixtures:
        counts[fixture.kind.value] += 1
    return {kind: count for kind, count in counts.items() if count}


def _fixture_path(fixture_id: str) -> Path:
    if not fixture_id or Path(fixture_id).is_absolute() or ".." in Path(fixture_id).parts:
        raise HTTPException(status_code=404, detail="Fixture not found.")

    path = (API_FIXTURE_ROOT / f"{fixture_id}.json").resolve()
    fixture_root = API_FIXTURE_ROOT.resolve()
    if not path.is_relative_to(fixture_root) or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Fixture not found.")
    return path


def _bundle_from_request(request: FixtureRunRequest) -> SourceBundle:
    path = _fixture_path(request.fixture_id)
    kind = _fixture_kind(path)
    if kind is not FixtureKind.BUNDLE:
        raise HTTPException(
            status_code=400,
            detail="Fixture must be a bundle for this endpoint.",
        )
    try:
        return load_source_bundle(path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _decide_from_request(request: FixtureRunRequest) -> AutomationDecision:
    return decide(_bundle_from_request(request), as_of=request.as_of)


def _append_api_run(
    kind: ApiRunKind,
    bundle_id: str,
    fixture_id: str,
    request: dict[str, Any],
    result: dict[str, Any],
) -> ApiRunRecord:
    try:
        return append_run_record(
            create_run_record(
                kind=kind,
                bundle_id=bundle_id,
                fixture_id=fixture_id,
                request=request,
                result=result,
            ),
            API_RUN_STORE_PATH,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _api_run_by_id(run_id: str) -> ApiRunRecord:
    try:
        records = load_run_records(API_RUN_STORE_PATH)
    except RunStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    record = next((record for record in records if record.run_id == run_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record


def _run_review_events_for_run(run_id: str) -> list[ApiRunReviewEvent]:
    try:
        events = load_run_review_events(API_RUN_REVIEW_STORE_PATH)
    except RunStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [event for event in events if event.run_id == run_id]


def _run_record_with_review_events(record: ApiRunRecord) -> ApiRunRecord:
    return record.model_copy(
        update={"review_events": _run_review_events_for_run(record.run_id)}
    )


def _decision_from_run(record: ApiRunRecord) -> AutomationDecision:
    candidate_payloads: list[dict[str, Any]] = []
    if record.kind is ApiRunKind.DECISION:
        candidate_payloads.append(record.result)
    if record.kind is ApiRunKind.AGENT:
        final_decision = record.result.get("final_decision")
        initial_decision = record.result.get("initial_decision")
        if isinstance(final_decision, dict):
            candidate_payloads.append(final_decision)
        if isinstance(initial_decision, dict):
            candidate_payloads.append(initial_decision)

    invalid_payload_errors: list[str] = []
    for payload in candidate_payloads:
        try:
            decision = AutomationDecision.model_validate(payload)
        except ValueError as exc:
            invalid_payload_errors.append(str(exc))
            continue
        return decision

    if invalid_payload_errors:
        raise HTTPException(
            status_code=500,
            detail="Run record contains invalid decision payload.",
        )
    raise HTTPException(
        status_code=400,
        detail="Run does not contain a reviewable decision.",
    )


def _reviewable_decision_from_run(record: ApiRunRecord) -> AutomationDecision:
    decision = _decision_from_run(record)
    if decision.approval_prompt is None:
        raise HTTPException(
            status_code=400,
            detail="Run does not have an approval prompt to answer.",
        )
    return decision


def _review_response_from_request(
    decision: AutomationDecision,
    request: RunReviewRequest,
) -> ReviewResponse:
    if decision.approval_prompt is None:
        raise HTTPException(
            status_code=400,
            detail="Run does not have an approval prompt to answer.",
        )
    return ReviewResponse(
        bundle_id=decision.bundle_id,
        prompt_issue_type=decision.approval_prompt.issue_type,
        selected_choice_id=request.selected_choice_id,
        responder_id=request.responder_id,
        responder_name=request.responder_name,
        selected_owner_id=request.selected_owner_id,
        selected_owner_name=request.selected_owner_name,
        user_accepts_risk=request.user_accepts_risk,
        notes=request.notes,
        metadata=request.metadata,
    )


def _feedback_event_from_request(
    record: ApiRunRecord,
    decision: AutomationDecision,
    request: RunFeedbackRequest,
) -> FeedbackEvent:
    submitted_outcomes = _submitted_source_feedback_by_id(request)
    selected_source_ids = list(decision.selected_sources)
    all_source_ids = [*selected_source_ids]
    for source_id in submitted_outcomes:
        if source_id not in all_source_ids:
            all_source_ids.append(source_id)
    source_outcomes = [
        _source_outcome_from_request(
            record,
            decision,
            source_id,
            submitted_outcomes.get(source_id),
        )
        for source_id in all_source_ids
    ]
    rejected_source_ids = [
        outcome.source_id
        for outcome in source_outcomes
        if outcome.outcome in {SourceOutcomeStatus.REJECTED, SourceOutcomeStatus.CORRECTED}
    ]
    try:
        return FeedbackEvent(
            id=f"feedback_{uuid4().hex}",
            created_at=datetime.now(UTC),
            bundle_id=record.bundle_id,
            decision=decision.decision,
            decision_outcome=request.decision_outcome,
            selected_source_ids=selected_source_ids,
            rejected_source_ids=rejected_source_ids,
            source_outcomes=source_outcomes,
            user_approval_outcome=request.decision_outcome,
            generated_handoff_accepted=request.generated_handoff_accepted,
            correction_notes=request.correction_notes,
            metadata={
                "run_id": record.run_id,
                "run_kind": record.kind.value,
                "fixture_id": record.fixture_id,
                "feedback_source": "inline_run_feedback",
                **request.metadata,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _submitted_source_feedback_by_id(
    request: RunFeedbackRequest,
) -> dict[str, RunSourceFeedbackRequest]:
    outcomes: dict[str, RunSourceFeedbackRequest] = {}
    for outcome in request.source_outcomes:
        if outcome.source_id in outcomes:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate source feedback for {outcome.source_id}.",
            )
        outcomes[outcome.source_id] = outcome
    return outcomes


def _source_outcome_from_request(
    record: ApiRunRecord,
    decision: AutomationDecision,
    source_id: str,
    requested_outcome: RunSourceFeedbackRequest | None,
) -> SourceOutcome:
    source_type, source_system = _source_profile_for_feedback(record, decision, source_id)
    if requested_outcome is None:
        return SourceOutcome(
            source_id=source_id,
            source_type=source_type,
            source_system=source_system,
            outcome=SourceOutcomeStatus.UNKNOWN,
            reason="No source-level feedback was provided for this selected source.",
            metadata={"feedback_source": "default_selected_source"},
        )
    return SourceOutcome(
        source_id=source_id,
        source_type=source_type,
        source_system=source_system,
        outcome=requested_outcome.outcome,
        reason=(
            requested_outcome.reason
            or f"{requested_outcome.outcome.value} source feedback from run review."
        ),
        metadata=requested_outcome.metadata,
    )


def _source_profile_for_feedback(
    record: ApiRunRecord,
    decision: AutomationDecision,
    source_id: str,
) -> tuple[SourceType, SourceSystem]:
    source = _bundle_source_by_id(record).get(source_id)
    if source is not None:
        return source.type, source.source_system

    citation = next(
        (citation for citation in decision.source_citations if citation.source_id == source_id),
        None,
    )
    if citation is not None:
        return citation.source_type, SourceSystem.LOCAL_FIXTURE

    ranked_source = next(
        (
            ranked_source
            for ranked_source in decision.ranked_bundle.ranked_sources
            if ranked_source.source_id == source_id
        ),
        None,
    )
    if ranked_source is not None:
        source_type = ranked_source.metadata.get("source_type", SourceType.OTHER.value)
        try:
            return SourceType(source_type), SourceSystem.LOCAL_FIXTURE
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Run source {source_id} has invalid source_type metadata.",
            ) from exc

    raise HTTPException(
        status_code=400,
        detail=f"Feedback source_id is not available on the run: {source_id}.",
    )


def _bundle_source_by_id(record: ApiRunRecord) -> dict[str, Source]:
    try:
        bundle = _bundle_from_request(
            FixtureRunRequest(fixture_id=record.fixture_id)
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return {}
        if exc.status_code == 400:
            return {}
        raise
    return {source.id: source for source in bundle.sources}


def _optional_owner_response_fixture(
    fixture_id: str | None,
    bundle_id: str,
) -> OwnerResponseFixture | None:
    if fixture_id is None:
        return None
    path = _fixture_path(fixture_id)
    if _fixture_kind(path) is not FixtureKind.OWNER_RESPONSE:
        raise HTTPException(
            status_code=400,
            detail="Fixture must be an owner-response fixture.",
        )
    try:
        fixture = load_owner_response_fixture(path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if fixture.response.bundle_id != bundle_id:
        raise HTTPException(
            status_code=400,
            detail="Owner response fixture bundle_id does not match bundle.",
        )
    return fixture


def _optional_simulated_retrieval_fixture(
    fixture_id: str | None,
    bundle_id: str,
) -> SimulatedRetrievalFixture | None:
    if fixture_id is None:
        return None
    path = _fixture_path(fixture_id)
    if _fixture_kind(path) is not FixtureKind.SIMULATED_RETRIEVAL:
        raise HTTPException(
            status_code=400,
            detail="Fixture must be a simulated-retrieval fixture.",
        )
    try:
        fixture = load_simulated_retrieval_fixture(path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if fixture.bundle_id != bundle_id:
        raise HTTPException(
            status_code=400,
            detail="Simulated retrieval fixture bundle_id does not match bundle.",
        )
    return fixture


def _review_fixture(path: Path) -> ReviewResponseFixture:
    if _fixture_kind(path) is not FixtureKind.REVIEW:
        raise HTTPException(
            status_code=400,
            detail="Fixture must be a review fixture.",
        )
    try:
        return load_review_response_fixture(path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _review_bundle_path(path: Path, fixture: ReviewResponseFixture) -> Path:
    try:
        return resolve_review_bundle_path(path, fixture.bundle_path)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _fixture_summary(path: Path) -> FixtureSummary:
    try:
        kind = _fixture_kind(path)
        return _summary_for_kind(path, kind)
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _fixture_kind(path: Path) -> FixtureKind:
    if is_feedback_fixture(path):
        return FixtureKind.FEEDBACK
    if is_simulated_retrieval_fixture(path):
        return FixtureKind.SIMULATED_RETRIEVAL
    if is_owner_response_fixture(path):
        return FixtureKind.OWNER_RESPONSE
    if is_review_response_fixture(path):
        return FixtureKind.REVIEW
    if is_bundle_fixture(path):
        return FixtureKind.BUNDLE
    return FixtureKind.SOURCE


def _summary_for_kind(path: Path, kind: FixtureKind) -> FixtureSummary:
    fixture_id = _fixture_id(path)
    fixture_path = _relative_fixture_path(path)
    if kind is FixtureKind.BUNDLE:
        fixture = load_source_bundle_fixture(path)
        return FixtureSummary(
            id=fixture_id,
            kind=kind,
            path=fixture_path,
            title=fixture.title,
            object_id=fixture.id,
            bundle_id=fixture.id,
            expected_decision=(
                fixture.expected.decision.value
                if fixture.expected and fixture.expected.decision
                else None
            ),
        )
    if kind is FixtureKind.SOURCE:
        fixture = load_source_fixture(path)
        return FixtureSummary(
            id=fixture_id,
            kind=kind,
            path=fixture_path,
            title=fixture.source.title,
            object_id=fixture.source.id,
            source_id=fixture.source.id,
            expected_tier=(
                fixture.expected.tier.value
                if fixture.expected and fixture.expected.tier
                else None
            ),
        )
    if kind is FixtureKind.REVIEW:
        fixture = load_review_response_fixture(path)
        return FixtureSummary(
            id=fixture_id,
            kind=kind,
            path=fixture_path,
            title=f"{fixture.response.prompt_issue_type}: {fixture.response.selected_choice_id}",
            object_id=fixture.response.bundle_id,
            bundle_id=fixture.response.bundle_id,
        )
    if kind is FixtureKind.OWNER_RESPONSE:
        fixture = load_owner_response_fixture(path)
        return FixtureSummary(
            id=fixture_id,
            kind=kind,
            path=fixture_path,
            title=f"{fixture.response.owner_name}: {fixture.response.outcome.value}",
            object_id=fixture.response.bundle_id,
            bundle_id=fixture.response.bundle_id,
            source_id=fixture.response.source_id,
        )
    if kind is FixtureKind.SIMULATED_RETRIEVAL:
        fixture = load_simulated_retrieval_fixture(path)
        return FixtureSummary(
            id=fixture_id,
            kind=kind,
            path=fixture_path,
            title=f"Simulated retrieval for {fixture.bundle_id}",
            object_id=fixture.bundle_id,
            bundle_id=fixture.bundle_id,
            expected_decision=(
                fixture.expected.decision_after_retrieval.value
                if fixture.expected and fixture.expected.decision_after_retrieval
                else None
            ),
        )

    fixture = load_feedback_fixture(path)
    return FixtureSummary(
        id=fixture_id,
        kind=kind,
        path=fixture_path,
        title=f"Feedback: {fixture.event.decision_outcome.value}",
        object_id=fixture.event.id,
        bundle_id=fixture.event.bundle_id,
        expected_decision=fixture.event.decision.value,
    )


def _fixture_payload(path: Path, kind: FixtureKind) -> dict[str, Any]:
    try:
        if kind is FixtureKind.BUNDLE:
            return load_source_bundle(path).model_dump(mode="json")
        if kind is FixtureKind.SOURCE:
            return load_source_fixture(path).model_dump(mode="json")
        if kind is FixtureKind.REVIEW:
            return load_review_response_fixture(path).model_dump(mode="json")
        if kind is FixtureKind.OWNER_RESPONSE:
            return load_owner_response_fixture(path).model_dump(mode="json")
        if kind is FixtureKind.SIMULATED_RETRIEVAL:
            return load_simulated_retrieval_fixture(path).model_dump(mode="json")
        return load_feedback_fixture(path).model_dump(mode="json")
    except FixtureLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _fixture_id(path: Path) -> str:
    return path.resolve().relative_to(API_FIXTURE_ROOT.resolve()).with_suffix("").as_posix()


def _relative_fixture_path(path: Path) -> str:
    return path.resolve().relative_to(API_FIXTURE_ROOT.resolve()).as_posix()
