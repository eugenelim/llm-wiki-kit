#!/usr/bin/env python3
"""
wiki-search.py — BM25 full-text search over an Obsidian vault.

Optional scaling layer for vaults that outgrow progressive loading
(~500+ wiki pages). Builds a BM25 index from all markdown files
and returns ranked results with synopses.

Dependencies:
  pip install bm25s[core] PyStemmer pyyaml

Usage:
  # Build/rebuild the index
  python wiki-search.py index /path/to/vault/wiki

  # Search the index
  python wiki-search.py search /path/to/vault/wiki "event driven architecture"

  # Search with more results
  python wiki-search.py search /path/to/vault/wiki "kafka consumer groups" --top 20

Output:
  Prints ranked results as markdown with filepath, score, and synopsis.
  Designed to be called by Claude Code as part of the wiki-search skill.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path

try:
    import bm25s
    import Stemmer
except ImportError:
    print(
        "Error: Required packages not installed.\n"
        "Run: pip install bm25s[core] PyStemmer pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

INDEX_DIR = ".wiki-search-index"


def extract_frontmatter_and_content(filepath):
    """Extract YAML frontmatter and body content from a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        return {}, ""

    fm = {}
    body = content

    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1 and yaml:
            try:
                fm = yaml.safe_load(content[3:end]) or {}
            except yaml.YAMLError:
                fm = {}
            body = content[end + 3 :]

    return fm, body


def extract_synopsis(body):
    """Extract the Synopsis section from page body."""
    match = re.search(
        r"##\s+Synopsis\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    # Fallback: first non-empty paragraph
    for para in body.split("\n\n"):
        stripped = para.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return stripped[:300]
    return ""


def collect_documents(wiki_path):
    """Collect all markdown files with their metadata."""
    documents = []

    for root, dirs, files in os.walk(wiki_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for fname in files:
            if not fname.endswith(".md"):
                continue

            filepath = os.path.join(root, fname)
            relpath = os.path.relpath(filepath, wiki_path)
            fm, body = extract_frontmatter_and_content(filepath)
            synopsis = extract_synopsis(body)

            # Build searchable text: title + tags + synopsis + body
            title = fm.get("title", fname.replace(".md", "").replace("-", " "))
            tags = " ".join(str(t) for t in fm.get("tags", []))
            searchable = f"{title} {tags} {body}"

            documents.append(
                {
                    "path": relpath,
                    "title": title,
                    "type": fm.get("type", "unknown"),
                    "status": fm.get("status", "unknown"),
                    "synopsis": synopsis,
                    "searchable": searchable,
                }
            )

    return documents


def build_index(wiki_path):
    """Build BM25 index from vault markdown files."""
    wiki_path = os.path.abspath(wiki_path)
    index_path = os.path.join(wiki_path, INDEX_DIR)
    os.makedirs(index_path, exist_ok=True)

    print(f"Scanning {wiki_path}...", file=sys.stderr)
    documents = collect_documents(wiki_path)
    print(f"Found {len(documents)} markdown files.", file=sys.stderr)

    if not documents:
        print("No documents found. Nothing to index.", file=sys.stderr)
        return

    # Tokenize with stemming
    stemmer = Stemmer.Stemmer("english")
    corpus = [doc["searchable"] for doc in documents]
    corpus_tokens = bm25s.tokenize(corpus, stopwords="en", stemmer=stemmer)

    # Build index
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)

    # Save index
    retriever.save(index_path, corpus=corpus)

    # Save metadata separately
    metadata = [
        {
            "path": doc["path"],
            "title": doc["title"],
            "type": doc["type"],
            "status": doc["status"],
            "synopsis": doc["synopsis"],
        }
        for doc in documents
    ]
    with open(os.path.join(index_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(
        f"Index built: {len(documents)} documents in {index_path}", file=sys.stderr
    )


def search_index(wiki_path, query, top_k=10):
    """Search the BM25 index and return ranked results."""
    wiki_path = os.path.abspath(wiki_path)
    index_path = os.path.join(wiki_path, INDEX_DIR)

    if not os.path.exists(index_path):
        print(
            "Error: No index found. Run 'wiki-search.py index' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load index and metadata
    retriever = bm25s.BM25.load(index_path, load_corpus=True)
    with open(os.path.join(index_path, "metadata.json")) as f:
        metadata = json.load(f)

    # Tokenize query
    stemmer = Stemmer.Stemmer("english")
    query_tokens = bm25s.tokenize(query, stemmer=stemmer)

    # Search
    results, scores = retriever.retrieve(query_tokens, k=min(top_k, len(metadata)))

    # Format output as markdown
    lines = [
        f"## Search Results: \"{query}\"",
        "",
        f"Showing top {min(top_k, len(metadata))} of {len(metadata)} indexed pages.",
        "",
    ]

    for i in range(results.shape[1]):
        doc_idx = results[0, i]
        score = scores[0, i]

        if score <= 0:
            break

        meta = metadata[doc_idx]
        lines.append(f"### {i + 1}. [[{meta['path']}|{meta['title']}]]")
        lines.append(f"**Score:** {score:.2f} · **Type:** {meta['type']} · **Status:** {meta['status']}")
        if meta["synopsis"]:
            lines.append(f"\n{meta['synopsis']}")
        lines.append("")

    if all(scores[0, i] <= 0 for i in range(results.shape[1])):
        lines.append("No relevant results found for this query.")
        lines.append("")
        lines.append("Try:")
        lines.append("- Different keywords (check `wiki/synonyms.md` for alternatives)")
        lines.append("- Broader terms")
        lines.append("- Falling back to progressive loading (index.md → synopsis scan)")

    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="BM25 full-text search for Obsidian wiki vaults"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Index command
    idx_parser = subparsers.add_parser("index", help="Build/rebuild the search index")
    idx_parser.add_argument("wiki_path", help="Path to the wiki/ directory")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search the index")
    search_parser.add_argument("wiki_path", help="Path to the wiki/ directory")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--top", type=int, default=10, help="Number of results (default: 10)"
    )

    args = parser.parse_args()

    if args.command == "index":
        build_index(args.wiki_path)
    elif args.command == "search":
        search_index(args.wiki_path, args.query, args.top)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
