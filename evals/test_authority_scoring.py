from __future__ import annotations

from data_source_ranking.loader import load_source_fixture
from data_source_ranking.models import (
    ContextNeed,
    NeededClaim,
    OwnerCandidate,
    Person,
    PersonRole,
    Source,
    SourceType,
    WeakPointType,
)
from data_source_ranking.scoring import AuthorityScorer, ScoringContext


def score_fixture(path: str):
    fixture = load_source_fixture(path)
    return AuthorityScorer().score(
        ScoringContext(
            context_need=fixture.context_need,
            source=fixture.source,
        )
    )


def minimal_context_need() -> ContextNeed:
    return ContextNeed(
        id="need_test",
        client_id="client_test",
        email_goal="Prepare context.",
        needed_claims=[
            NeededClaim(
                id="need_claim_test",
                description="Test claim.",
            )
        ],
    )


def test_human_validated_context_scores_highest() -> None:
    score = score_fixture("fixtures/strong/gammahealth_human_validated_context.json")

    assert score.score == 1.0
    assert score.label == "validated"
    assert score.weak_points == []


def test_account_owner_crm_note_is_authoritative() -> None:
    score = score_fixture("fixtures/strong/acme_recent_crm_note.json")

    assert score.score == 0.9
    assert score.label == "authoritative"
    assert score.weak_points == []


def test_final_proposal_with_validation_scores_validated() -> None:
    score = score_fixture("fixtures/strong/northstar_final_proposal_with_feedback.json")

    assert score.score == 0.95
    assert score.label == "validated"
    assert score.weak_points == []


def test_meeting_notes_have_strong_provenance() -> None:
    score = score_fixture("fixtures/strong/deltabank_recent_meeting_notes_clear_attendees.json")

    assert score.score == 0.75
    assert score.label == "strong_provenance"
    assert score.weak_points == []


def test_partner_material_has_low_authority() -> None:
    score = score_fixture("fixtures/weak/deltabank_unverified_partner_material.json")

    assert score.score == 0.3
    assert score.label == "low_provenance"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_AUTHORITY]


def test_unknown_provenance_scores_low() -> None:
    source = Source(
        id="src_unknown_authority",
        type=SourceType.OTHER,
        title="Unknown source",
        summary="Unknown provenance.",
    )

    score = AuthorityScorer().score(
        ScoringContext(
            context_need=minimal_context_need(),
            source=source,
        )
    )

    assert score.score == 0.2
    assert score.label == "low_provenance"
    assert [point.type for point in score.weak_points] == [WeakPointType.LOW_AUTHORITY]


def test_owner_candidate_boosts_authority_less_than_author() -> None:
    source = Source(
        id="src_owner_candidate_only",
        type=SourceType.DECK,
        title="Owner candidate only",
        summary="Deck with no author but a likely account owner.",
        owner_candidates=[
            OwnerCandidate(
                id="user_owner",
                name="Owner User",
                role=PersonRole.ACCOUNT_OWNER,
                role_title="Account Owner",
                reason="Likely owner from account metadata.",
                confidence=0.9,
            )
        ],
    )
    authored_source = source.model_copy(
        update={
            "author": Person(
                id="user_owner",
                name="Owner User",
                role=PersonRole.ACCOUNT_OWNER,
                role_title="Account Owner",
            )
        }
    )

    owner_candidate_score = AuthorityScorer().score(
        ScoringContext(context_need=minimal_context_need(), source=source)
    )
    author_score = AuthorityScorer().score(
        ScoringContext(context_need=minimal_context_need(), source=authored_source)
    )

    assert owner_candidate_score.score == 0.74
    assert author_score.score == 0.9
