"""Shared pytest fixtures across the kit's test suite.

The autouse fixture below resets the lazy-cache module attribute that
``cli._kit_root()`` writes to. Without per-test reset, a unit test that
monkeypatches ``cli._bundled_assets_path`` to a tmp directory would leave
``cli._KIT_ROOT`` pointing at a deleted tmp path for subsequent tests.

See ``docs/specs/wheel-bundled-assets/spec.md`` §Invariants for the lazy
resolution contract and ``tests/unit/test_cli_kit_root.py`` for the
grep guard that keeps direct ``_KIT_ROOT`` reads contained.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from llm_wiki_kit import cli


@pytest.fixture(autouse=True)
def _reset_lazy_kit_root() -> Iterator[None]:
    """Reset ``cli._KIT_ROOT`` to ``None`` before and after each test."""

    cli._KIT_ROOT = None
    yield
    cli._KIT_ROOT = None
