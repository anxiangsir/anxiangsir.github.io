"""
Site-wide tests for anxiangsir.github.io
Covers: HTML structure, Python syntax, JSON validity, API utilities, RAG engine.
Excludes: Mario game tests (separate test files).

Run:  pytest tests/test_site.py -v
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

import pytest

# ── paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "pages"
API_DIR = ROOT / "api"

# Make api/ importable
sys.path.insert(0, str(API_DIR))


# ═══════════════════════════════════════════════════════════════════════
# GROUP 1: HTML pages — basic structure validation
# ═══════════════════════════════════════════════════════════════════════

# All HTML files (excluding mario.html)
HTML_FILES = sorted(
    p
    for p in [ROOT / "index.html"] + list(PAGES_DIR.glob("*.html"))
    if "mario" not in p.name.lower()
)


@pytest.mark.parametrize("html_path", HTML_FILES, ids=lambda p: p.name)
def test_html_has_doctype(html_path):
    """Every HTML page must start with <!DOCTYPE html>."""
    content = html_path.read_text(encoding="utf-8")
    assert content.strip().lower().startswith("<!doctype html"), (
        f"{html_path.name} missing <!DOCTYPE html>"
    )


@pytest.mark.parametrize("html_path", HTML_FILES, ids=lambda p: p.name)
def test_html_has_head_and_title(html_path):
    """Every HTML page must have <head> with a <title>."""
    content = html_path.read_text(encoding="utf-8").lower()
    assert "<head>" in content, f"{html_path.name} missing <head>"
    assert "<title>" in content and "</title>" in content, (
        f"{html_path.name} missing <title>"
    )


@pytest.mark.parametrize("html_path", HTML_FILES, ids=lambda p: p.name)
def test_html_has_charset(html_path):
    """Every HTML page should declare charset=utf-8."""
    content = html_path.read_text(encoding="utf-8").lower()
    assert 'charset="utf-8"' in content or "charset=utf-8" in content, (
        f"{html_path.name} missing charset declaration"
    )


# ═══════════════════════════════════════════════════════════════════════
# GROUP 2: Python files — syntax validation (no imports that need DB)
# ═══════════════════════════════════════════════════════════════════════

PY_FILES = sorted(API_DIR.glob("*.py"))


@pytest.mark.parametrize("py_path", PY_FILES, ids=lambda p: p.name)
def test_python_syntax(py_path):
    """Every Python file must parse without syntax errors."""
    source = py_path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(py_path))
    except SyntaxError as e:
        pytest.fail(f"Syntax error in {py_path.name}: {e}")


# ═══════════════════════════════════════════════════════════════════════
# GROUP 3: JSON files — validity
# ═══════════════════════════════════════════════════════════════════════


def test_vercel_json_valid():
    """vercel.json must be valid JSON."""
    path = ROOT / "vercel.json"
    assert path.exists(), "vercel.json not found"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_vercel_json_has_rewrites():
    """vercel.json should have rewrites and headers."""
    data = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert "rewrites" in data, "vercel.json missing 'rewrites'"
    assert "headers" in data, "vercel.json missing 'headers'"
    assert len(data["rewrites"]) > 0, "vercel.json has empty rewrites"


def test_knowledge_base_valid():
    """knowledge_base.json must be valid and have documents."""
    path = API_DIR / "knowledge_base.json"
    assert path.exists(), "knowledge_base.json not found"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "documents" in data
    assert len(data["documents"]) > 0, "knowledge_base.json has no documents"


def test_knowledge_base_documents_have_required_fields():
    """Each document in knowledge_base.json must have id and type."""
    data = json.loads((API_DIR / "knowledge_base.json").read_text(encoding="utf-8"))
    for i, doc in enumerate(data["documents"]):
        assert "id" in doc, f"Document #{i} missing 'id'"
        assert "type" in doc, f"Document #{i} missing 'type'"
        assert doc["type"] in ("publication", "github_project"), (
            f"Document #{i} has unknown type: {doc['type']}"
        )


# ═══════════════════════════════════════════════════════════════════════
# GROUP 4: vercel.json rewrite targets — files must exist
# ═══════════════════════════════════════════════════════════════════════


def test_vercel_rewrite_destinations_exist():
    """Every rewrite destination file in vercel.json must exist on disk."""
    data = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    for rule in data.get("rewrites", []):
        dest = rule.get("destination", "")
        # Skip API rewrites (serverless functions)
        if dest.startswith("/api/"):
            continue
        # File paths like /pages/blog.html
        file_path = ROOT / dest.lstrip("/")
        assert file_path.exists(), (
            f"Rewrite destination missing: {dest} (expected at {file_path})"
        )


# ═══════════════════════════════════════════════════════════════════════
# GROUP 5: RAG utils — pure function tests (no DB/network needed)
# ═══════════════════════════════════════════════════════════════════════


class TestRagTokenizer:
    """Test rag_utils._tokenize and related functions."""

    def test_basic_english_tokenization(self):
        from rag_utils import _tokenize

        tokens = _tokenize("face recognition training")
        assert "face" in tokens
        assert "recognition" in tokens
        assert "training" in tokens

    def test_stop_words_removed(self):
        from rag_utils import _tokenize

        tokens = _tokenize("the is a for of with")
        assert len(tokens) == 0, f"Stop words not removed: {tokens}"

    def test_chinese_tokens_expanded(self):
        from rag_utils import _tokenize

        tokens = _tokenize("人脸识别")
        # Should include both Chinese and English equivalents
        assert "face" in tokens or "recognition" in tokens, (
            f"Chinese not expanded: {tokens}"
        )

    def test_mixed_language(self):
        from rag_utils import _tokenize

        tokens = _tokenize("InsightFace 人脸识别")
        assert "insightface" in tokens
        # Chinese expansion should also be present
        assert "face" in tokens or "recognition" in tokens


class TestRagSearch:
    """Test rag_utils.search on the real knowledge base."""

    def test_search_returns_results(self):
        from rag_utils import search

        results = search("InsightFace face recognition")
        assert len(results) > 0, "Search returned no results for 'InsightFace'"

    def test_search_returns_dicts(self):
        from rag_utils import search

        results = search("multimodal vision encoder")
        for r in results:
            assert isinstance(r, dict)
            assert "_score" in r
            assert r["_score"] > 0

    def test_search_respects_top_k(self):
        from rag_utils import search

        results = search("training", top_k=2)
        assert len(results) <= 2

    def test_search_empty_query(self):
        from rag_utils import search

        results = search("")
        assert results == []

    def test_search_nonsense_query(self):
        from rag_utils import search

        results = search("xyzzyplugh99999")
        assert results == [], f"Unexpected results for nonsense query: {results}"


class TestRagFormatContext:
    """Test rag_utils.format_context."""

    def test_format_empty(self):
        from rag_utils import format_context

        assert format_context([]) == ""

    def test_format_publication(self):
        from rag_utils import format_context

        doc = {
            "type": "publication",
            "title": "Test Paper",
            "venue": "CVPR 2024",
            "paper_url": "https://example.com",
            "summary": "A great paper.",
        }
        result = format_context([doc])
        assert "Test Paper" in result
        assert "CVPR 2024" in result

    def test_format_github_project(self):
        from rag_utils import format_context

        doc = {
            "type": "github_project",
            "name": "MyRepo",
            "url": "https://github.com/test/repo",
            "stars": "1000+",
            "description": "A cool project.",
        }
        result = format_context([doc])
        assert "MyRepo" in result
        assert "github.com" in result


# ═══════════════════════════════════════════════════════════════════════
# GROUP 6: Visitor API — pure utility functions
# ═══════════════════════════════════════════════════════════════════════


class TestAnonymizeIp:
    """Test visitor._anonymize_ip without needing Flask context."""

    def _get_fn(self):
        from visitor import _anonymize_ip

        return _anonymize_ip

    def test_ipv4_last_octet_zeroed(self):
        fn = self._get_fn()
        assert fn("192.168.1.123") == "192.168.1.0"

    def test_ipv4_already_zero(self):
        fn = self._get_fn()
        assert fn("10.0.0.0") == "10.0.0.0"

    def test_empty_string(self):
        fn = self._get_fn()
        assert fn("") == "0.0.0.0"

    def test_none(self):
        fn = self._get_fn()
        assert fn(None) == "0.0.0.0"

    def test_invalid_ip(self):
        fn = self._get_fn()
        assert fn("not-an-ip") == "0.0.0.0"

    def test_ipv6_lower_bits_zeroed(self):
        fn = self._get_fn()
        result = fn("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        # Lower 80 bits should be zeroed
        assert result != "0.0.0.0"  # Should be valid IPv6
        # Verify the result is a valid IPv6 address
        import ipaddress

        addr = ipaddress.ip_address(result)
        assert isinstance(addr, ipaddress.IPv6Address)


# ═══════════════════════════════════════════════════════════════════════
# GROUP 7: Schema / data integrity checks
# ═══════════════════════════════════════════════════════════════════════


def test_schema_sql_exists():
    """schema.sql should exist in the project root."""
    assert (ROOT / "schema.sql").exists(), "schema.sql not found"


def test_requirements_txt_has_key_deps():
    """requirements.txt should list essential dependencies."""
    content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dep in ["flask", "openai", "requests"]:
        assert dep in content.lower(), f"requirements.txt missing {dep}"


def test_no_broken_internal_links_in_index():
    """index.html should not reference non-existent local files in href/src."""
    content = (ROOT / "index.html").read_text(encoding="utf-8")
    # Find relative href/src references (not http, not #, not javascript:, not mailto:)
    refs = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
    broken = []
    for ref in refs:
        # Skip external URLs, anchors, JS, mailto, data URIs, template vars
        if any(
            ref.startswith(p)
            for p in ("http", "//", "#", "javascript:", "mailto:", "data:", "{", "/_")
        ):
            continue
        # Resolve relative path
        target = ROOT / ref.lstrip("/")
        if not target.exists():
            broken.append(ref)
    # Allow some flexibility — CSS/JS from CDNs might not be local
    # Only flag clearly local paths that don't exist
    local_broken = [
        b for b in broken if not b.startswith("assets/") or (ROOT / b).parent.exists()
    ]
    # Filter to only asset files that should definitely exist
    truly_broken = []
    for b in local_broken:
        # If parent dir exists but file doesn't, it's truly broken
        target = ROOT / b.lstrip("/")
        if target.parent.exists() and not target.exists():
            truly_broken.append(b)
    assert not truly_broken, f"Broken local references in index.html: {truly_broken}"


# ═══════════════════════════════════════════════════════════════════════
# GROUP 8: Citation data
# ═══════════════════════════════════════════════════════════════════════


def test_citation_data_json_valid():
    """data/citation_data.json should be valid JSON if it exists."""
    path = ROOT / "data" / "citation_data.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list)), "citation_data.json has unexpected type"
