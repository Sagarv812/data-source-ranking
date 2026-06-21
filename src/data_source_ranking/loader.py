from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from data_source_ranking.models import SourceBundle, SourceFixture


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
    return _validate_fixture(Path(path), SourceBundle)
