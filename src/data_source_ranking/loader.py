from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from data_source_ranking.agents.retrieval import SimulatedRetrievalFixture
from data_source_ranking.agents.state import OwnerResponseFixture
from data_source_ranking.models import Source, SourceBundle, SourceBundleFixture, SourceFixture
from data_source_ranking.review_responses import ReviewResponseFixture


class FixtureLoadError(ValueError):
    """Raised when a fixture cannot be read or validated."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FixtureLoadError(f"could not read fixture {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(f"invalid JSON in fixture {path}: {exc}") from exc


def _validate_fixture[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    data = _load_json(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise FixtureLoadError(f"invalid fixture {path}:\n{exc}") from exc


def load_source_fixture(path: str | Path) -> SourceFixture:
    return _validate_fixture(Path(path), SourceFixture)


def load_source_bundle(path: str | Path) -> SourceBundle:
    bundle_path = Path(path)
    bundle_fixture = _validate_fixture(bundle_path, SourceBundleFixture)
    sources = [
        load_source_fixture(_resolve_source_ref(bundle_path, source_ref)).source
        for source_ref in bundle_fixture.source_refs
    ]
    return SourceBundle(
        id=bundle_fixture.id,
        title=bundle_fixture.title,
        context_need=bundle_fixture.context_need,
        sources=sources,
        expected=bundle_fixture.expected,
        metadata=bundle_fixture.metadata,
    )


def load_source_bundle_fixture(path: str | Path) -> SourceBundleFixture:
    return _validate_fixture(Path(path), SourceBundleFixture)


def load_review_response_fixture(path: str | Path) -> ReviewResponseFixture:
    return _validate_fixture(Path(path), ReviewResponseFixture)


def load_owner_response_fixture(path: str | Path) -> OwnerResponseFixture:
    return _validate_fixture(Path(path), OwnerResponseFixture)


def load_simulated_retrieval_fixture(path: str | Path) -> SimulatedRetrievalFixture:
    return _validate_fixture(Path(path), SimulatedRetrievalFixture)


def load_simulated_retrieval_sources(path: str | Path) -> list[Source]:
    retrieval_path = Path(path)
    fixture = load_simulated_retrieval_fixture(retrieval_path)
    return [
        load_source_fixture(_resolve_source_ref(retrieval_path, source_ref)).source
        for source_ref in fixture.retrieved_source_refs
    ]


def is_bundle_fixture(path: str | Path) -> bool:
    data = _load_json(Path(path))
    return "source_refs" in data


def is_owner_response_fixture(path: str | Path) -> bool:
    data = _load_json(Path(path))
    response = data.get("response")
    return (
        "bundle_path" in data
        and isinstance(response, dict)
        and "source_id" in response
        and "owner_id" in response
    )


def is_simulated_retrieval_fixture(path: str | Path) -> bool:
    data = _load_json(Path(path))
    return (
        "bundle_id" in data
        and isinstance(data.get("query"), dict)
        and isinstance(data.get("retrieved_source_refs"), list)
    )


def is_review_response_fixture(path: str | Path) -> bool:
    data = _load_json(Path(path))
    response = data.get("response")
    return (
        "bundle_path" in data
        and isinstance(response, dict)
        and "prompt_issue_type" in response
        and "selected_choice_id" in response
    )


def _resolve_source_ref(bundle_path: Path, source_ref: str) -> Path:
    source_path = Path(source_ref)
    if source_path.is_absolute() or source_path.exists():
        return source_path

    relative_to_bundle = bundle_path.parent / source_path
    if relative_to_bundle.exists():
        return relative_to_bundle

    relative_to_fixture_root = _relative_to_fixture_root(bundle_path, source_path)
    if relative_to_fixture_root and relative_to_fixture_root.exists():
        return relative_to_fixture_root

    raise FixtureLoadError(f"source ref {source_ref!r} from bundle {bundle_path} does not exist")


def _relative_to_fixture_root(bundle_path: Path, source_path: Path) -> Path | None:
    bundle_path = bundle_path.resolve()
    fixture_root = next(
        (parent for parent in bundle_path.parents if parent.name == "fixtures"),
        None,
    )
    if fixture_root is None or source_path.parts[0] != "fixtures":
        return None
    return fixture_root.parent / source_path
