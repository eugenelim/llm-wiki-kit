#!/usr/bin/env python3
"""
wiki-search.py — Two-tier vault search.

Tier 1 (default): ripgrep — zero install, zero index, always fresh content.
Tier 2 (auto-upgrade): SQLite FTS5 — BM25 ranking, stemming, frontmatter-aware
filters; activated automatically once the vault crosses a size threshold.

The skill calls one entry point. Backend selection is internal and persistent
(one-way flip with hysteresis). Users can force a backend via
.wiki-search/config.yaml or by passing --backend.

Dependencies:
  - ripgrep (`rg`) on PATH — present on most dev machines.
  - Python 3.10+ stdlib only. sqlite3 with FTS5 ships with standard Python.
  - PyYAML is OPTIONAL; if missing, frontmatter parsing falls back to a small
    built-in YAML subset (sufficient for the common `key: value` and
    `tags: [a, b]` patterns wiki pages use).

Layout (per vault, inside the wiki/ directory):
  .wiki-search/
    state.json        # backend decision + last vault measurement (kit-managed)
    config.yaml       # optional user override (commit to vault for team-shared)
    index.sqlite      # FTS5 index (only when fts5 backend is active)

Usage:
  # Search (the common case — backend is auto-resolved)
  python wiki-search.py search wiki/ "event driven architecture"
  python wiki-search.py search wiki/ "compliance" --tag urgent --type meeting
  python wiki-search.py search wiki/ "kafka" --top 20

  # Inspect / control the backend
  python wiki-search.py backend wiki/                  # show current backend + state
  python wiki-search.py backend wiki/ --set fts5       # force FTS5 (builds index)
  python wiki-search.py backend wiki/ --set ripgrep    # force ripgrep
  python wiki-search.py backend wiki/ --set auto       # restore default
  python wiki-search.py backend wiki/ --reset          # forget the auto-flip

  # Manage the FTS5 index (only meaningful when FTS5 is active)
  python wiki-search.py index wiki/                    # incremental refresh
  python wiki-search.py index wiki/ --rebuild          # full rebuild from scratch
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

WORK_DIR_NAME = ".wiki-search"
STATE_FILE = "state.json"
CONFIG_FILE = "config.yaml"
INDEX_FILE = "index.sqlite"
SCHEMA_VERSION = 1

DEFAULTS = {
    "backend": "auto",                    # ripgrep | fts5 | auto
    "auto_enable_threshold_pages": 1000,
    "auto_enable_threshold_bytes": 50_000_000,
    "cache_window_seconds": 3600,
}


class IndexBuildError(Exception):
    """Raised when the FTS5 index cannot be built or refreshed."""


# ---------------------------------------------------------------------------
# YAML loader (PyYAML if available, else a small subset for frontmatter)
# ---------------------------------------------------------------------------

try:
    import yaml as _yaml  # type: ignore

    def load_yaml(text: str) -> dict:
        try:
            data = _yaml.safe_load(text) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
except ImportError:
    _yaml = None

    def load_yaml(text: str) -> dict:
        # Fallback YAML loader: handles the frontmatter shapes Obsidian writes —
        # `key: value`, quoted strings, inline lists `[a, b]`, and the
        # multi-line list shape Obsidian uses by default:
        #   tags:
        #     - foo
        #     - bar
        # Anything more elaborate needs PyYAML; we degrade gracefully (the
        # field is treated as missing).
        out: dict = {}
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.rstrip()
            i += 1
            if not line or line.lstrip().startswith("#") or ":" not in line:
                continue
            if line[0] in (" ", "\t"):
                continue   # skip nested-under-something keys
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if value == "":
                # Look ahead for a multi-line list `  - item`.
                items = []
                while i < len(lines):
                    peek = lines[i]
                    if peek.startswith((" ", "\t")) and peek.lstrip().startswith("-"):
                        items.append(peek.lstrip()[1:].strip().strip('"').strip("'"))
                        i += 1
                    elif peek.strip() == "":
                        i += 1
                    else:
                        break
                out[key] = items if items else ""
            elif value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                out[key] = [v for v in items if v]
            elif value.startswith('"') and value.endswith('"'):
                out[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                out[key] = value[1:-1]
            else:
                out[key] = value
        return out


# ---------------------------------------------------------------------------
# Config + state
# ---------------------------------------------------------------------------

@dataclass
class Config:
    backend: str = DEFAULTS["backend"]
    auto_enable_threshold_pages: int = DEFAULTS["auto_enable_threshold_pages"]
    auto_enable_threshold_bytes: int = DEFAULTS["auto_enable_threshold_bytes"]
    cache_window_seconds: int = DEFAULTS["cache_window_seconds"]


@dataclass
class State:
    backend_resolved: str | None = None       # last decision (ripgrep | fts5)
    fts5_enabled: bool = False                # one-way hysteresis flag
    last_check_ts: float = 0.0
    last_pages: int = 0
    last_bytes: int = 0
    schema_version: int = SCHEMA_VERSION
    notes: list[str] = field(default_factory=list)


def work_dir(wiki_path: Path) -> Path:
    return wiki_path / WORK_DIR_NAME


def load_config(wiki_path: Path) -> Config:
    cfg_path = work_dir(wiki_path) / CONFIG_FILE
    cfg = Config()
    if not cfg_path.exists():
        return cfg
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return cfg
    data = load_yaml(raw) or {}
    # Tolerate either top-level keys or nested under `kit.search.*` (matching
    # the spec) or `search.*`.
    sub = data
    for key in ("kit", "search"):
        if isinstance(sub, dict) and key in sub and isinstance(sub[key], dict):
            sub = sub[key]
    if not isinstance(sub, dict):
        sub = data
    for field_name in ("backend", "auto_enable_threshold_pages",
                       "auto_enable_threshold_bytes", "cache_window_seconds"):
        if field_name in sub:
            value = sub[field_name]
            if field_name == "backend":
                if value in ("ripgrep", "fts5", "auto"):
                    cfg.backend = value
            else:
                try:
                    setattr(cfg, field_name, int(value))
                except (TypeError, ValueError):
                    pass
    return cfg


def load_state(wiki_path: Path) -> State:
    state_path = work_dir(wiki_path) / STATE_FILE
    if not state_path.exists():
        return State()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return State()
    return State(
        backend_resolved=data.get("backend_resolved"),
        fts5_enabled=bool(data.get("fts5_enabled", False)),
        last_check_ts=float(data.get("last_check_ts", 0.0)),
        last_pages=int(data.get("last_pages", 0)),
        last_bytes=int(data.get("last_bytes", 0)),
        # Default to 0 (not SCHEMA_VERSION) so the resolve loop's drift check
        # treats files predating schema_version as stale and discards them.
        schema_version=int(data.get("schema_version", 0)),
        notes=list(data.get("notes", [])),
    )


def save_state(wiki_path: Path, state: State) -> None:
    work_dir(wiki_path).mkdir(parents=True, exist_ok=True)
    state_path = work_dir(wiki_path) / STATE_FILE
    payload = {
        "backend_resolved": state.backend_resolved,
        "fts5_enabled": state.fts5_enabled,
        "last_check_ts": state.last_check_ts,
        "last_pages": state.last_pages,
        "last_bytes": state.last_bytes,
        "schema_version": state.schema_version,
        "notes": state.notes[-20:],   # bound the log
    }
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(state_path)


# ---------------------------------------------------------------------------
# Vault walking + frontmatter
# ---------------------------------------------------------------------------

def iter_md_files(wiki_path: Path):
    for root, dirs, files in os.walk(wiki_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.endswith(".md"):
                yield Path(root) / fname


def measure_vault(wiki_path: Path) -> tuple[int, int]:
    pages = 0
    total = 0
    for fp in iter_md_files(wiki_path):
        try:
            total += fp.stat().st_size
        except OSError:
            continue
        pages += 1
    return pages, total


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].lstrip("\n")
    body = text[end + 4:].lstrip("\n")
    return load_yaml(fm_block), body


def extract_synopsis(body: str) -> str:
    m = re.search(r"##\s+Synopsis\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    for para in body.split("\n\n"):
        s = para.strip()
        if s and not s.startswith("#") and not s.startswith("---"):
            return s[:300]
    return ""


def normalize_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lstrip("#") for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,\s]+", value)
        return [p.lstrip("#") for p in parts if p]
    return []


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------

def resolve_backend(wiki_path: Path, *, force_recheck: bool = False) -> tuple[str, Config, State]:
    cfg = load_config(wiki_path)
    state = load_state(wiki_path)

    # Schema bump: discard any state from older versions.
    if state.schema_version != SCHEMA_VERSION:
        state = State()

    # When the caller forces a re-evaluation (e.g., `backend wiki/` for status),
    # always refresh the vault measurement. Override paths skip the auto-flip
    # check below, so without this they'd report stale pages/bytes counts.
    if force_recheck:
        pages, total = measure_vault(wiki_path)
        state.last_check_ts = time.time()
        state.last_pages = pages
        state.last_bytes = total

    # Explicit override wins.
    if cfg.backend == "ripgrep":
        state.backend_resolved = "ripgrep"
        save_state(wiki_path, state)
        return "ripgrep", cfg, state
    if cfg.backend == "fts5":
        try:
            ensure_fts5_index(wiki_path, full_rebuild=False, log=False)
        except IndexBuildError as exc:
            # Try once to recover by wiping and rebuilding (handles schema
            # drift and plain corruption). If that also fails, fall back.
            print(f"wiki-search: {exc}; attempting full rebuild", file=sys.stderr)
            try:
                force_rebuild_index(wiki_path, log=True)
            except (IndexBuildError, sqlite3.Error, OSError) as exc2:
                state.notes.append(f"[{_now_iso()}] forced fts5 but rebuild failed: {exc2}; "
                                   "this call uses ripgrep — fix the issue and the next "
                                   "call will retry the FTS5 path automatically")
                save_state(wiki_path, state)
                print(f"wiki-search: rebuild failed ({exc2}); using ripgrep for this call",
                      file=sys.stderr)
                return "ripgrep", cfg, state
            state.notes.append(f"[{_now_iso()}] FTS5 auto-recovered via full rebuild")
        state.fts5_enabled = True
        state.backend_resolved = "fts5"
        save_state(wiki_path, state)
        return "fts5", cfg, state

    # Auto path: stay flipped if previously flipped.
    if state.fts5_enabled:
        # Health check: if index disappeared, fall back silently and rebuild.
        idx = work_dir(wiki_path) / INDEX_FILE
        if not idx.exists():
            note = f"[{_now_iso()}] FTS5 index missing — rebuilding"
            state.notes.append(note)
            print(f"wiki-search: {note}", file=sys.stderr)
            try:
                ensure_fts5_index(wiki_path, full_rebuild=True, log=True)
            except (IndexBuildError, sqlite3.Error, OSError) as exc:
                state.notes.append(f"[{_now_iso()}] rebuild failed: {exc}; falling back to ripgrep")
                save_state(wiki_path, state)
                return "ripgrep", cfg, state
        state.backend_resolved = "fts5"
        save_state(wiki_path, state)
        return "fts5", cfg, state

    # Cache window — skip walking if the recorded backend is still trustworthy.
    age = time.time() - state.last_check_ts
    if not force_recheck and state.backend_resolved == "ripgrep" and age < cfg.cache_window_seconds:
        # Also bust the cache if the vault root mtime is newer than our last check.
        try:
            root_mtime = wiki_path.stat().st_mtime
        except OSError:
            root_mtime = 0
        if root_mtime <= state.last_check_ts:
            return "ripgrep", cfg, state

    # First-time (or refreshed) threshold check. Skip if force_recheck already
    # measured at the top of the function.
    if not force_recheck:
        pages, total = measure_vault(wiki_path)
        state.last_check_ts = time.time()
        state.last_pages = pages
        state.last_bytes = total
    else:
        pages, total = state.last_pages, state.last_bytes

    if pages > cfg.auto_enable_threshold_pages or total > cfg.auto_enable_threshold_bytes:
        msg = (f"Vault crossed size threshold ({pages} pages, "
               f"{total // (1024 * 1024)} MB) — enabling FTS5 backend, "
               "building index now (one-time setup).")
        print(f"wiki-search: {msg}", file=sys.stderr)
        state.notes.append(f"[{_now_iso()}] auto-enabled FTS5: {pages} pages, {total} bytes")
        try:
            ensure_fts5_index(wiki_path, full_rebuild=True, log=True)
        except (IndexBuildError, sqlite3.Error, OSError) as exc:
            state.notes.append(f"[{_now_iso()}] auto-enable bootstrap failed ({exc}); staying on ripgrep")
            print(f"wiki-search: bootstrap failed ({exc}); staying on ripgrep", file=sys.stderr)
            state.backend_resolved = "ripgrep"
            save_state(wiki_path, state)
            return "ripgrep", cfg, state
        state.fts5_enabled = True
        state.backend_resolved = "fts5"
        save_state(wiki_path, state)
        return "fts5", cfg, state

    state.backend_resolved = "ripgrep"
    save_state(wiki_path, state)
    return "ripgrep", cfg, state


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _record_note(wiki_path: Path, note: str) -> None:
    try:
        state = load_state(wiki_path)
        state.notes.append(note)
        save_state(wiki_path, state)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Ripgrep backend
# ---------------------------------------------------------------------------

def ripgrep_search(wiki_path: Path, query: str, top: int,
                   tag_filters: list[str], type_filter: str | None,
                   status_filter: str | None) -> str:
    if not query.strip():
        return _format_error("Empty query. Pass at least one search term.")
    if not shutil.which("rg"):
        return _format_error(
            "ripgrep (`rg`) is not on PATH. Install it (e.g., `brew install ripgrep` "
            "on macOS, `apt install ripgrep` on Debian/Ubuntu, `winget install BurntSushi.ripgrep.MSVC` "
            "on Windows) or set `backend: fts5` in .wiki-search/config.yaml to force the SQLite backend."
        )

    # `-F` (fixed-strings) matches literal substring — what users expect for
    # vault content searches like "kafka.lag" or "v2.0.0". For regex queries
    # the FTS5 backend exposes phrase/prefix/NEAR syntax instead.
    cmd = [
        "rg", "--json", "--type", "md", "--smart-case", "--fixed-strings",
        "--max-count", "5",     # avoid one giant page dominating results
        "--max-columns", "300",
        "--", query, str(wiki_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return _format_error("ripgrep timed out after 30s. Narrow the query or force FTS5.")

    if proc.returncode not in (0, 1):   # 1 = no matches; not an error
        return _format_error(f"ripgrep failed (exit {proc.returncode}): {proc.stderr.strip()}")

    hits: dict[str, dict] = {}   # path -> aggregated info
    for line in proc.stdout.splitlines():
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") != "match":
            continue
        data = evt.get("data", {})
        path = data.get("path", {}).get("text", "")
        if not path:
            continue
        snippet = data.get("lines", {}).get("text", "").strip()
        line_no = data.get("line_number", 0)
        entry = hits.setdefault(path, {"matches": 0, "snippets": []})
        entry["matches"] += 1
        if len(entry["snippets"]) < 2:
            entry["snippets"].append((line_no, snippet[:240]))

    if not hits:
        return _format_no_results(query, "ripgrep")

    tag_filters_lc = {t.lower() for t in tag_filters}
    enriched = []
    for path, info in hits.items():
        fp = Path(path)
        fm, body = _safe_read_frontmatter(fp)
        tags = normalize_tags(fm.get("tags"))
        page_type = str(fm.get("type", "")).strip()
        status = str(fm.get("status", "")).strip()

        tags_lc = {t.lower() for t in tags}
        if tag_filters_lc and not tag_filters_lc.issubset(tags_lc):
            continue
        if type_filter and page_type.lower() != type_filter.lower():
            continue
        if status_filter and status.lower() != status_filter.lower():
            continue

        title = fm.get("title") or fp.stem.replace("-", " ")
        synopsis = extract_synopsis(body)
        enriched.append({
            "path": fp.relative_to(wiki_path).as_posix(),
            "title": str(title),
            "type": page_type or "unknown",
            "status": status or "unknown",
            "tags": tags,
            "synopsis": synopsis,
            "matches": info["matches"],
            "snippets": info["snippets"],
        })

    if not enriched:
        return _format_no_results(query, "ripgrep (filtered out)")

    # Rank: more matches first, shorter title as tiebreaker (more specific page).
    enriched.sort(key=lambda r: (-r["matches"], len(r["title"])))
    enriched = enriched[:top]
    return _format_results(query, enriched, "ripgrep")


def _safe_read_frontmatter(fp: Path) -> tuple[dict, str]:
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, ""
    return split_frontmatter(text)


# ---------------------------------------------------------------------------
# FTS5 backend
# ---------------------------------------------------------------------------

FTS5_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('version', '{SCHEMA_VERSION}');

CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
    path UNINDEXED,
    title,
    synopsis,
    body,
    tags,
    page_type UNINDEXED,
    status UNINDEXED,
    modified UNINDEXED,
    tokenize = 'porter unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS vault_meta (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    title TEXT,
    page_type TEXT,
    status TEXT,
    tags TEXT,
    synopsis TEXT
);
"""


def fts5_connect(wiki_path: Path) -> sqlite3.Connection:
    work_dir(wiki_path).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(work_dir(wiki_path) / INDEX_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(FTS5_SCHEMA)
    # In-DB schema version: lets a kit upgrade detect drift and rebuild.
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    if row and str(row[0]) != str(SCHEMA_VERSION):
        raise IndexBuildError(f"FTS5 schema version mismatch (db={row[0]}, expected={SCHEMA_VERSION})")
    conn.commit()
    return conn


def force_rebuild_index(wiki_path: Path, *, log: bool) -> dict:
    """Unlink the existing index file (if any) and rebuild from scratch.

    Use this when a normal `ensure_fts5_index` call raises IndexBuildError —
    most commonly because of schema drift after a kit upgrade, but also for
    plain corruption. Deleting the file is the only way to escape a bad FTS5
    table definition or a wrong schema_meta.version row.
    """
    idx = work_dir(wiki_path) / INDEX_FILE
    for suffix in ("", "-shm", "-wal", "-journal"):
        try:
            (idx.parent / (idx.name + suffix)).unlink(missing_ok=True)
        except OSError:
            pass
    return ensure_fts5_index(wiki_path, full_rebuild=True, log=log)


def ensure_fts5_index(wiki_path: Path, *, full_rebuild: bool, log: bool) -> dict:
    """Build or refresh the FTS5 index. Returns a small stats dict."""
    try:
        conn = fts5_connect(wiki_path)
    except (sqlite3.Error, OSError) as exc:
        # Convert connect-time failures into IndexBuildError so callers' recovery
        # paths can react uniformly. fts5_connect already raises IndexBuildError
        # for schema drift; this catches everything else (corrupt file, perms).
        raise IndexBuildError(f"FTS5 connect failed: {exc}") from exc
    try:
        if full_rebuild:
            conn.execute("DELETE FROM vault_fts")
            conn.execute("DELETE FROM vault_meta")
            conn.commit()

        existing = {row[0]: row[1] for row in conn.execute("SELECT path, mtime FROM vault_meta")}
        seen: set[str] = set()
        upserted = 0

        for fp in iter_md_files(wiki_path):
            rel = fp.relative_to(wiki_path).as_posix()
            seen.add(rel)
            try:
                mtime = fp.stat().st_mtime
            except OSError:
                continue
            if rel in existing and abs(existing[rel] - mtime) < 1e-6:
                continue   # unchanged
            fm, body = _safe_read_frontmatter(fp)
            title = str(fm.get("title") or fp.stem.replace("-", " "))
            tags = " ".join(normalize_tags(fm.get("tags")))
            page_type = str(fm.get("type", "")).strip() or "unknown"
            status = str(fm.get("status", "")).strip() or "unknown"
            modified = str(fm.get("modified", ""))
            synopsis = extract_synopsis(body)

            conn.execute("DELETE FROM vault_fts WHERE path = ?", (rel,))
            conn.execute("DELETE FROM vault_meta WHERE path = ?", (rel,))
            conn.execute(
                "INSERT INTO vault_fts (path, title, synopsis, body, tags, page_type, status, modified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rel, title, synopsis, body, tags, page_type, status, modified),
            )
            conn.execute(
                "INSERT INTO vault_meta (path, mtime, title, page_type, status, tags, synopsis) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rel, mtime, title, page_type, status, tags, synopsis),
            )
            upserted += 1

        # Delete entries for pages that no longer exist on disk.
        deleted = 0
        for path in list(existing.keys()):
            if path not in seen:
                conn.execute("DELETE FROM vault_fts WHERE path = ?", (path,))
                conn.execute("DELETE FROM vault_meta WHERE path = ?", (path,))
                deleted += 1

        conn.commit()
        stats = {"upserted": upserted, "deleted": deleted, "total": len(seen)}
        if log:
            print(f"wiki-search: index refresh — {stats}", file=sys.stderr)
        return stats
    except (sqlite3.DatabaseError, OSError) as exc:
        raise IndexBuildError(f"index refresh failed: {exc}") from exc
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass


def fts5_search(wiki_path: Path, query: str, top: int,
                tag_filters: list[str], type_filter: str | None,
                status_filter: str | None) -> str:
    if not query.strip():
        return _format_error("Empty query. Pass at least one search term.")

    # Refresh the index incrementally before searching. Cheap when nothing changed.
    # Any failure (corruption, schema drift, OS error) triggers a one-shot wipe +
    # rebuild; if that also fails, fall back to ripgrep silently with a logged note.
    try:
        ensure_fts5_index(wiki_path, full_rebuild=False, log=False)
    except (IndexBuildError, sqlite3.Error) as exc:
        msg = f"[{_now_iso()}] FTS5 refresh failed ({exc}); rebuilding"
        print(f"wiki-search: {msg}", file=sys.stderr)
        _record_note(wiki_path, msg)
        try:
            force_rebuild_index(wiki_path, log=True)
        except Exception as exc2:
            note = f"[{_now_iso()}] FTS5 rebuild failed ({exc2}); falling back to ripgrep"
            print(f"wiki-search: {note}", file=sys.stderr)
            _record_note(wiki_path, note)
            return ripgrep_search(wiki_path, query, top, tag_filters, type_filter, status_filter)

    try:
        conn = fts5_connect(wiki_path)
    except (IndexBuildError, sqlite3.Error) as exc:
        note = f"[{_now_iso()}] FTS5 connect failed ({exc}); falling back to ripgrep"
        print(f"wiki-search: {note}", file=sys.stderr)
        _record_note(wiki_path, note)
        return ripgrep_search(wiki_path, query, top, tag_filters, type_filter, status_filter)

    try:
        # MATCH carries only the user's free-text query — tag/type/status filters
        # are applied in Python after retrieval. This avoids two pitfalls:
        #   1. FTS5's column-prefix syntax (`tags:event-driven`) tokenizes hyphens
        #      as separators, breaking kebab-case tag matching.
        #   2. A SQL LIMIT applied before post-filter could drop real matches.
        # We fetch up to `top * 20` ranked candidates, post-filter, then trim.
        sql_clauses = ["vault_fts MATCH ?"]
        params: list = [query.strip()]
        if type_filter:
            # Case-insensitive comparison so frontmatter casing variations don't
            # silently drop matches.
            sql_clauses.append("LOWER(page_type) = LOWER(?)")
            params.append(type_filter)
        if status_filter:
            sql_clauses.append("LOWER(status) = LOWER(?)")
            params.append(status_filter)

        candidate_limit = max(top * 20, 100) if tag_filters else top * 4
        params.append(candidate_limit)

        sql = f"""
            SELECT path, title, page_type, status, tags, synopsis,
                   bm25(vault_fts) AS score,
                   snippet(vault_fts, 3, '«', '»', ' … ', 12) AS snip
            FROM vault_fts
            WHERE {' AND '.join(sql_clauses)}
            ORDER BY score
            LIMIT ?
        """
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # Likely a malformed FTS5 query (unmatched quote, etc.); quote the
            # whole thing as a phrase and retry.
            params[0] = '"' + query.replace('"', '""') + '"'
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.Error as exc:
                note = f"[{_now_iso()}] FTS5 query failed ({exc}); falling back to ripgrep"
                print(f"wiki-search: {note}", file=sys.stderr)
                _record_note(wiki_path, note)
                return ripgrep_search(wiki_path, query, top, tag_filters, type_filter, status_filter)

        if not rows:
            return _format_no_results(query, "fts5")

        tag_filters_lc = {t.lower() for t in tag_filters}
        enriched = []
        for row in rows:
            path, title, page_type, status, tags_str, synopsis, score, snip = row
            tags = tags_str.split() if tags_str else []
            tags_lc = {t.lower() for t in tags}
            if tag_filters_lc and not tag_filters_lc.issubset(tags_lc):
                continue
            enriched.append({
                "path": path,
                "title": title,
                "type": page_type or "unknown",
                "status": status or "unknown",
                "tags": tags,
                "synopsis": synopsis or "",
                # FTS5's bm25() returns negative numbers (lower = better) so
                # ORDER BY ASC sorts most-relevant first. Negate for display so
                # users see a positive "more is better" relevance score.
                "score": -score if score is not None else 0.0,
                "snippet": snip,
            })
            if len(enriched) >= top:
                break

        if not enriched:
            return _format_no_results(query, "fts5 (filtered out)")
        return _format_results(query, enriched, "fts5")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Output formatting (markdown — designed for the agent to read)
# ---------------------------------------------------------------------------

def _format_results(query: str, results: list[dict], backend: str) -> str:
    lines = [f'## Search Results: "{query}"', "",
             f"Backend: **{backend}** · Showing {len(results)} result(s).", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. [[{r['path']}|{r['title']}]]")
        meta_bits = [f"**Type:** {r['type']}", f"**Status:** {r['status']}"]
        if r.get("tags"):
            meta_bits.append("**Tags:** " + ", ".join(f"#{t}" for t in r["tags"]))
        if "score" in r:
            meta_bits.append(f"**Score:** {r['score']:.2f}")
        if "matches" in r:
            meta_bits.append(f"**Matches:** {r['matches']}")
        lines.append(" · ".join(meta_bits))
        if r.get("synopsis"):
            lines.append("")
            lines.append(r["synopsis"])
        if r.get("snippet"):
            lines.append("")
            lines.append(f"> {r['snippet']}")
        for line_no, snip in r.get("snippets", []):
            lines.append("")
            lines.append(f"> L{line_no}: {snip}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_no_results(query: str, backend: str) -> str:
    return (f'## Search Results: "{query}"\n\n'
            f"Backend: **{backend}** · No matches.\n\n"
            "Try: different keywords, broader terms, or fall back to progressive "
            "loading (read `wiki/index.md`, scan synopses).\n")


def _format_error(msg: str) -> str:
    return f"## Search Error\n\n{msg}\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> int:
    wiki_path = Path(args.wiki_path).resolve()
    if not wiki_path.is_dir():
        print(f"Error: {wiki_path} is not a directory", file=sys.stderr)
        return 2

    if args.backend:
        backend = args.backend
        if backend == "fts5":
            try:
                ensure_fts5_index(wiki_path, full_rebuild=False, log=False)
            except IndexBuildError as exc:
                print(f"wiki-search: --backend fts5 hit {exc}; rebuilding", file=sys.stderr)
                try:
                    force_rebuild_index(wiki_path, log=True)
                except Exception as exc2:
                    print(f"wiki-search: rebuild failed ({exc2}); using ripgrep for this call",
                          file=sys.stderr)
                    backend = "ripgrep"
    else:
        backend, _, _ = resolve_backend(wiki_path)

    if not args.query.strip():
        sys.stdout.write(_format_error("Empty query. Pass at least one search term.\n"))
        return 2

    tag_filters = list(args.tag or [])
    if backend == "fts5":
        out = fts5_search(wiki_path, args.query, args.top, tag_filters, args.type, args.status)
    else:
        out = ripgrep_search(wiki_path, args.query, args.top, tag_filters, args.type, args.status)
    sys.stdout.write(out)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    wiki_path = Path(args.wiki_path).resolve()
    if not wiki_path.is_dir():
        print(f"Error: {wiki_path} is not a directory", file=sys.stderr)
        return 2
    try:
        stats = ensure_fts5_index(wiki_path, full_rebuild=args.rebuild, log=True)
    except IndexBuildError as exc:
        # Schema drift or corruption — wipe the file and rebuild from scratch.
        # `--rebuild` alone DELETEs rows but leaves the FTS5 table definition;
        # only unlinking the file recovers from a wrong table definition.
        print(f"wiki-search: {exc}; wiping and rebuilding from scratch", file=sys.stderr)
        try:
            stats = force_rebuild_index(wiki_path, log=True)
        except (IndexBuildError, sqlite3.Error, OSError) as exc2:
            print(f"Error: {exc2}", file=sys.stderr)
            return 1
    state = load_state(wiki_path)
    state.fts5_enabled = True
    save_state(wiki_path, state)
    print(json.dumps(stats, indent=2))
    return 0


def cmd_backend(args: argparse.Namespace) -> int:
    wiki_path = Path(args.wiki_path).resolve()
    if not wiki_path.is_dir():
        print(f"Error: {wiki_path} is not a directory", file=sys.stderr)
        return 2

    if args.reset:
        state_file = work_dir(wiki_path) / STATE_FILE
        if state_file.exists():
            state_file.unlink()
            print(f"wiki-search: reset {state_file}", file=sys.stderr)
        else:
            print(f"wiki-search: no state file at {state_file} — nothing to reset", file=sys.stderr)
        # Fall through to print the freshly-resolved backend status.

    if args.set:
        cfg_path = work_dir(wiki_path) / CONFIG_FILE
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        existing = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
        # Replace or insert the backend line. Keep it simple: rewrite the whole file
        # if the user is starting from defaults.
        if not existing or "backend" not in existing:
            cfg_path.write_text(
                "kit:\n  search:\n    backend: " + args.set + "\n",
                encoding="utf-8",
            )
        else:
            new = re.sub(r"(?m)^(\s*backend\s*:\s*).*$", rf"\1{args.set}", existing)
            cfg_path.write_text(new, encoding="utf-8")
        if args.set == "fts5":
            try:
                ensure_fts5_index(wiki_path, full_rebuild=False, log=True)
            except IndexBuildError as exc:
                print(f"wiki-search: --set fts5 hit {exc}; rebuilding", file=sys.stderr)
                try:
                    force_rebuild_index(wiki_path, log=True)
                except Exception as exc2:
                    print(f"wiki-search: --set fts5 wrote config but rebuild failed ({exc2}); "
                          "next search call will retry", file=sys.stderr)
        if args.set == "ripgrep" and args.delete_index:
            idx = work_dir(wiki_path) / INDEX_FILE
            removed = []
            for suffix in ("", "-shm", "-wal", "-journal"):
                victim = idx.parent / (idx.name + suffix)
                if victim.exists():
                    try:
                        victim.unlink()
                        removed.append(victim.name)
                    except OSError:
                        pass
            if removed:
                print(f"Deleted {', '.join(removed)} from {idx.parent}", file=sys.stderr)
        # Force re-resolution next call.
        state = load_state(wiki_path)
        if args.set == "ripgrep":
            state.fts5_enabled = False
        elif args.set == "fts5":
            state.fts5_enabled = True
        save_state(wiki_path, state)

    backend, cfg, state = resolve_backend(wiki_path, force_recheck=True)
    pages, total = state.last_pages, state.last_bytes
    info = {
        "backend": backend,
        "config_backend": cfg.backend,
        "fts5_enabled": state.fts5_enabled,
        "pages": pages,
        "bytes": total,
        "thresholds": {
            "pages": cfg.auto_enable_threshold_pages,
            "bytes": cfg.auto_enable_threshold_bytes,
        },
        "work_dir": str(work_dir(wiki_path)),
        "index_present": (work_dir(wiki_path) / INDEX_FILE).exists(),
        "recent_notes": state.notes[-5:],
    }
    print(json.dumps(info, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Two-tier vault search (ripgrep default, SQLite FTS5 auto-upgrade).",
    )
    sub = parser.add_subparsers(dest="command")

    search = sub.add_parser("search", help="Search the vault.")
    search.add_argument("wiki_path")
    search.add_argument("query")
    search.add_argument("--top", type=int, default=10)
    search.add_argument("--tag", action="append",
                        help="Restrict to pages with this tag (repeatable).")
    search.add_argument("--type", help="Restrict to pages with this frontmatter `type`.")
    search.add_argument("--status", help="Restrict to pages with this frontmatter `status`.")
    search.add_argument("--backend", choices=["ripgrep", "fts5"],
                        help="One-shot backend override (does not persist).")

    idx = sub.add_parser("index", help="Build or refresh the FTS5 index.")
    idx.add_argument("wiki_path")
    idx.add_argument("--rebuild", action="store_true",
                     help="Full rebuild instead of incremental refresh.")

    bk = sub.add_parser("backend", help="Inspect or change the active backend.")
    bk.add_argument("wiki_path")
    bk.add_argument("--set", choices=["ripgrep", "fts5", "auto"],
                    help="Persist this backend choice in .wiki-search/config.yaml.")
    bk.add_argument("--reset", action="store_true",
                    help="Delete .wiki-search/state.json so the next call re-evaluates from scratch.")
    bk.add_argument("--delete-index", action="store_true",
                    help="With --set ripgrep: also remove the FTS5 index file.")

    args = parser.parse_args(argv)

    if args.command == "search":
        return cmd_search(args)
    if args.command == "index":
        return cmd_index(args)
    if args.command == "backend":
        return cmd_backend(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
