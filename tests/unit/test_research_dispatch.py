"""Unit tests for ``llm_wiki_kit.research.dispatch`` (RFC-0001 Task 18).

Exercises ``dispatch_query`` against a tmp vault, with the provider's
``perplexity.dispatch`` monkeypatched so no real HTTP fires. Verifies
config-load, provider-pick, error-wrap, and markdown rendering against
the spec's acceptance criteria.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import ProviderConfig
from llm_wiki_kit.research.dispatch import (
    DispatchResult,
    ResearchDispatchError,
    dispatch_query,
)
from llm_wiki_kit.research.http import ResearchHTTPError
from llm_wiki_kit.research.providers import perplexity
from llm_wiki_kit.research.providers.perplexity import PerplexityResult

NOW = datetime(2026, 5, 17, 8, 51, 0, tzinfo=UTC)


def _write_config(vault_root: Path, body: str) -> Path:
    """Write a seed ``research-providers.yaml`` with the given managed-region body.

    The body is what lands between the ``# BEGIN MANAGED: providers``
    / ``# END MANAGED: providers`` markers; the kit's seed file
    (shipped by ``infrastructure:research``) is what's written
    verbatim to disk here. Tests parameterize ``body`` to exercise
    empty, single-provider, multi-provider, and typo cases.
    """

    config_path = vault_root / "research-providers.yaml"
    content = (
        "# llm-wiki-kit research providers config.\n"
        "# Edits outside the BEGIN/END markers below are preserved.\n"
        "\n"
        "# BEGIN MANAGED: providers\n"
        f"{body}"
        "# END MANAGED: providers\n"
    )
    config_path.write_text(content, encoding="utf-8")
    return config_path


def _install_fake_perplexity(
    monkeypatch: pytest.MonkeyPatch, answer: str = "answer", citations: list[str] | None = None
) -> None:
    """Replace ``perplexity.dispatch`` with a deterministic fake.

    Uses ``monkeypatch.setattr`` against the provider module — the
    dispatcher's registry holds a re-binding wrapper that re-reads
    ``perplexity.dispatch`` at call time, so this patch is seen.
    """

    citations = citations if citations is not None else ["https://example/a"]

    def _fake(config: ProviderConfig, query: str) -> PerplexityResult:
        return PerplexityResult(
            answer=answer, citations=list(citations), model=config.model or "sonar-pro"
        )

    monkeypatch.setattr(perplexity, "dispatch", _fake)


def test_dispatch_query_no_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)
    assert "infrastructure:research not installed" in str(exc_info.value)


def test_dispatch_query_empty_region_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "")
    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)
    assert "no research providers installed" in str(exc_info.value)


def test_dispatch_query_typo_surfaces_field_name(tmp_path: Path) -> None:
    """A typo inside a provider block produces a CLI-friendly message.

    Spec §"Config + models" acceptance criterion: the error message
    includes the literal bad-field name (so the user can grep their
    own snippet) and is prefixed with the config-file context.
    """

    _write_config(
        tmp_path,
        "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n  endpiont: https://x\n",
    )

    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)

    msg = str(exc_info.value)
    assert "invalid research-providers.yaml" in msg.lower() or "research-providers.yaml" in msg
    assert "endpiont" in msg


def test_dispatch_query_one_provider_no_flag_picks_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_perplexity(monkeypatch)
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    result = dispatch_query("q", None, tmp_path, now=NOW)

    assert isinstance(result, DispatchResult)
    assert result.event.provider == "perplexity"
    assert result.event.status == "ok"
    assert result.event.model == "sonar-pro"
    assert result.event.result_path is None


def test_dispatch_query_two_providers_no_flag_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_config(
        tmp_path,
        "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\ngemini:\n  api_key_env: GEMINI_API_KEY\n",
    )

    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)

    msg = str(exc_info.value)
    assert "pass --provider" in msg
    assert "perplexity" in msg
    assert "gemini" in msg


def test_dispatch_query_unknown_provider_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", "gemini", tmp_path, now=NOW)

    msg = str(exc_info.value)
    assert "'gemini' not installed" in msg
    assert "perplexity" in msg


def test_dispatch_query_slug_without_implementation_raises(tmp_path: Path) -> None:
    """A hand-edited config with an unsupported provider slug surfaces clearly.

    Defends against Task 19's Gemini being hand-added before this kit
    version ships it. The user sees a config-shaped error, not an
    uncaught ``KeyError`` traceback.
    """

    _write_config(tmp_path, "gemini:\n  api_key_env: GEMINI_API_KEY\n")

    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)
    assert "no implementation in this kit version" in str(exc_info.value)


def test_dispatch_query_renders_yaml_safe_query_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A query with quotes, leading dashes, and newlines round-trips.

    Spec acceptance: ``yaml.safe_load`` of the frontmatter slice
    yields the original query string byte-for-byte.
    """

    _install_fake_perplexity(monkeypatch, answer="ok")
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    tricky = 'a "quote"\n---\nleading-dash --x'
    result = dispatch_query(tricky, None, tmp_path, now=NOW)

    parsed = _parse_frontmatter(result.markdown)
    assert parsed["query"] == tricky


def test_dispatch_query_body_with_dashes_preserves_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Body containing ``---`` doesn't corrupt the frontmatter boundary.

    Spec acceptance: there is exactly one ``^---$`` line before the
    first blank line (the frontmatter closer); the body slice equals
    the provider's verbatim content.
    """

    _install_fake_perplexity(monkeypatch, answer="intro\n---\nmore")
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    result = dispatch_query("q", None, tmp_path, now=NOW)
    lines = result.markdown.split("\n")
    # First non-blank line is the opening ---
    assert lines[0] == "---"
    # Walk until first blank line; count ^---$ in [0, blank_idx).
    blank_idx = lines.index("")
    dash_only = [i for i in range(blank_idx) if lines[i] == "---"]
    # Opening and closing dash, no body-side dash inside the header.
    assert dash_only == [0, blank_idx - 1]

    # Body slice (lines after the blank) equals the provider's content.
    body = "\n".join(lines[blank_idx + 1 :]).rstrip("\n")
    assert body == "intro\n---\nmore"


def test_dispatch_query_fetched_at_has_T_separator_and_offset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``fetched_at`` is ISO-8601 with the literal ``T`` separator and ``+00:00``.

    Spec acceptance: passing a ``datetime`` to ``yaml.safe_dump``
    would emit the space-separated form; the renderer must
    ``.isoformat()`` first.
    """

    _install_fake_perplexity(monkeypatch)
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    result = dispatch_query("q", None, tmp_path, now=NOW)

    fm = _parse_frontmatter(result.markdown)
    assert "T" in fm["fetched_at"]
    assert fm["fetched_at"].endswith("+00:00")


def test_dispatch_query_citations_empty_renders_as_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_perplexity(monkeypatch, citations=[])
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    result = dispatch_query("q", None, tmp_path, now=NOW)
    fm = _parse_frontmatter(result.markdown)
    assert fm["citations"] == []


def test_dispatch_query_raises_research_dispatch_error_on_http_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Provider failure wraps as ``ResearchDispatchError`` with prepared event.

    Spec §"Dispatcher return-and-raise contract": ``exc.event`` is
    a ``status="error"`` ``ResearchQueryEvent`` the CLI will append
    before re-raising. ``str(exc)`` matches the provider's message.
    """

    def _fail(config: ProviderConfig, query: str) -> Any:
        raise ResearchHTTPError("perplexity: HTTP 401", status=401)

    monkeypatch.setattr(perplexity, "dispatch", _fail)
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    with pytest.raises(ResearchDispatchError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)

    exc = exc_info.value
    assert str(exc) == "perplexity: HTTP 401"
    assert exc.event.status == "error"
    assert exc.event.provider == "perplexity"
    assert exc.event.query == "q"
    assert exc.event.result_path is None


def test_dispatch_query_wikierror_from_provider_propagates_unwrapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Provider pre-flight ``WikiError`` (e.g. missing env var) is NOT wrapped.

    Spec §"Error paths" row 7: missing env var is config-shaped and
    ``Journaled? no`` — the user's intent ("research this") never
    materialized into a request the kit should record. The dispatcher
    must let the plain ``WikiError`` propagate so the CLI surfaces it
    as exit 2 with no audit event. Only ``ResearchHTTPError`` (a
    runtime-shaped failure) gets wrapped as ``ResearchDispatchError``.
    """

    def _fail(config: ProviderConfig, query: str) -> Any:
        raise WikiError("set PERPLEXITY_API_KEY in the environment")

    monkeypatch.setattr(perplexity, "dispatch", _fail)
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")

    with pytest.raises(WikiError) as exc_info:
        dispatch_query("q", None, tmp_path, now=NOW)
    assert "set PERPLEXITY_API_KEY" in str(exc_info.value)
    # Must NOT be a ResearchDispatchError (which would carry an event).
    assert not isinstance(exc_info.value, ResearchDispatchError)


def _parse_frontmatter(markdown: str) -> dict[str, Any]:
    """Extract YAML frontmatter as a dict.

    Splits on the first ``---``-only line and the next ``---``-only
    line. Used by the rendering tests to round-trip the frontmatter
    through ``yaml.safe_load`` and assert on field values.
    """

    lines = markdown.split("\n")
    assert lines[0] == "---", f"expected leading ---, got {lines[0]!r}"
    end_idx = lines.index("---", 1)
    yaml_text = "\n".join(lines[1:end_idx])
    loaded = yaml.safe_load(yaml_text)
    assert isinstance(loaded, dict)
    return loaded


def test_dispatch_query_naive_fetched_at_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``fetched_at`` must be timezone-aware (caller's responsibility).

    A naive datetime would render with the host's local offset, which
    fails the spec's ``+00:00`` invariant. The dispatcher catches this
    at the rendering boundary rather than silently localizing.
    """

    _install_fake_perplexity(monkeypatch)
    _write_config(tmp_path, "perplexity:\n  api_key_env: PERPLEXITY_API_KEY\n")
    naive = datetime(2026, 5, 17, 8, 51, 0)

    with pytest.raises(TypeError):
        dispatch_query("q", None, tmp_path, now=naive)
