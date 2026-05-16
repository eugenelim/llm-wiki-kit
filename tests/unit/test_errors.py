"""Tests for ``llm_wiki_kit.errors``.

These pin the contract that ADR-0005 names: every kit error inherits from
``WikiError`` so the CLI boundary can catch one base, and ``ValidationError``
reformats Pydantic's structured errors into the
``Invalid <thing> at <path>: <human message>`` shape that the CLI prints.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import (
    JournalCorruptError,
    ValidationError,
    WikiError,
)


class _Sample(BaseModel):
    name: str
    count: int


def _pydantic_error(data: object) -> PydanticValidationError:
    try:
        _Sample.model_validate(data)
    except PydanticValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


def test_wiki_error_is_exception_subclass() -> None:
    assert issubclass(WikiError, Exception)


def test_validation_error_inherits_from_wiki_error() -> None:
    assert issubclass(ValidationError, WikiError)


def test_journal_corrupt_error_inherits_from_wiki_error() -> None:
    assert issubclass(JournalCorruptError, WikiError)


def test_validation_error_formats_one_field() -> None:
    pyd = _pydantic_error({"name": "ok"})
    err = ValidationError("primitive", pyd)
    text = str(err)
    assert "Invalid primitive" in text
    assert "count" in text


def test_validation_error_formats_multiple_fields() -> None:
    pyd = _pydantic_error({"name": 5, "count": "two"})
    err = ValidationError("recipe", pyd)
    text = str(err)
    assert text.count("Invalid recipe") == 2
    assert "name" in text
    assert "count" in text


def test_validation_error_renders_nested_loc_with_dotted_path() -> None:
    class Outer(BaseModel):
        inner: _Sample

    try:
        Outer.model_validate({"inner": {"name": "ok"}})
    except PydanticValidationError as exc:
        pyd = exc
    else:
        raise AssertionError("expected a ValidationError")

    err = ValidationError("contract", pyd)
    text = str(err)
    assert "inner.count" in text


def test_validation_error_preserves_original_pydantic_error() -> None:
    pyd = _pydantic_error({"name": "ok"})
    err = ValidationError("primitive", pyd)
    assert err.pydantic_error is pyd
    assert err.thing == "primitive"


def test_journal_corrupt_error_carries_line_number() -> None:
    err = JournalCorruptError(line=7, reason="missing discriminator")
    assert err.line == 7
    assert "7" in str(err)
    assert "missing discriminator" in str(err)


def test_wiki_error_is_catchable_as_a_single_base() -> None:
    pyd = _pydantic_error({"name": "ok"})
    errors_raised: list[Exception] = [
        ValidationError("primitive", pyd),
        JournalCorruptError(line=1, reason="bad json"),
    ]
    for e in errors_raised:
        with pytest.raises(WikiError):
            raise e
